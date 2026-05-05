import logging
import os
import tempfile
from typing import Optional

from fastapi import APIRouter, HTTPException
from minio import Minio
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(tags=["transcription"])

_whisper_model = None
_pyannote_pipeline = None
_pyannote_attempted = False

VOICEMAIL_PHRASES = [
    # Standard ISP voicemail prompts
    "forwarded to voicemail", "forward to voicemail", "voicemail",
    "leave your message", "leave a message",
    "after the tone", "at the tone", "after the beep", "at the beep",
    "not available", "is not available", "cannot take your call",
    "you have reached", "please leave", "record your message", "please record",
    "when you have finished", "hang up", "finished recording",
    "tone to begin", "record after", "press any key",
    "mailbox", "in count of",
    # Common Indian ISP voicemail phrases (Airtel, Jio, BSNL, Vi)
    "the number you are trying", "the person you are trying",
    "the person you're trying", "currently not available",
    "switched off", "out of coverage", "not reachable",
    "please try again", "please try after",
    "apna sandesh", "sandesh chod", "awaaz ke baad",
]


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class TranscribeRequest(BaseModel):
    minio_path: str
    language: Optional[str] = None
    min_speakers: int = 2
    max_speakers: int = 2


class TranscriptSegment(BaseModel):
    speaker: str
    start_ms: int
    end_ms: int
    text: str
    confidence: float


class TranscribeResponse(BaseModel):
    segments: list[TranscriptSegment]
    language: str
    duration_seconds: float
    call_type: str = "LIVE"   # LIVE | VOICEMAIL | NO_ANSWER


# ---------------------------------------------------------------------------
# Whisper model loader
# ---------------------------------------------------------------------------

def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        model_size = os.getenv("WHISPER_MODEL_SIZE", "small")
        device = os.getenv("WHISPER_DEVICE", "cpu")
        compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
        cache_dir = os.getenv("MODEL_CACHE_DIR", "/app/model_cache")
        logger.info("Loading Whisper '%s' on %s (%s)", model_size, device, compute_type)
        try:
            _whisper_model = WhisperModel(
                model_size, device=device, compute_type=compute_type, download_root=cache_dir,
            )
        except (RuntimeError, Exception) as exc:
            if device != "cpu":
                logger.warning(
                    "Whisper failed on %s (%s): %s — falling back to CPU/int8",
                    device, compute_type, exc,
                )
                _whisper_model = WhisperModel(
                    model_size, device="cpu", compute_type="int8", download_root=cache_dir,
                )
            else:
                raise
        logger.info("Whisper model loaded")
    return _whisper_model


def _base_transcribe_kwargs(language: Optional[str]) -> dict:
    kwargs: dict = {
        "beam_size": 5,
        "word_timestamps": True,
        "vad_filter": True,
        "vad_parameters": {"min_silence_duration_ms": 300, "speech_pad_ms": 200},
        "condition_on_previous_text": False,
        "no_speech_threshold": 0.6,
        "log_prob_threshold": -1.0,
        "compression_ratio_threshold": 2.4,
    }
    if language:
        kwargs["language"] = language
    return kwargs


# ---------------------------------------------------------------------------
# Stereo channel split  (Fix 1)
# 3CX standard: left channel = outgoing (AGENT), right = incoming (CUSTOMER)
# ---------------------------------------------------------------------------

def _is_stereo(audio_path: str) -> bool:
    try:
        from pydub import AudioSegment
        return AudioSegment.from_file(audio_path).channels == 2
    except Exception as exc:
        logger.warning("Stereo check failed: %s", exc)
        return False


def _transcribe_stereo(
    audio_path: str, model, kwargs: dict, tmpdir: str
) -> tuple[list[TranscriptSegment], str, float]:
    """
    Split stereo audio, transcribe each channel independently.
    Left channel → AGENT, Right channel → CUSTOMER.
    Eliminates speaker diarization guesswork entirely.
    """
    from pydub import AudioSegment

    audio = AudioSegment.from_file(audio_path)
    channels = audio.split_to_mono()
    duration_seconds = len(audio) / 1000.0
    segments: list[TranscriptSegment] = []
    language = "en"

    for channel_audio, speaker in zip(channels, ["AGENT", "CUSTOMER"]):
        channel_path = f"{tmpdir}/{speaker.lower()}.wav"
        channel_audio.export(channel_path, format="wav")
        segs_iter, info = model.transcribe(channel_path, **kwargs)
        if speaker == "AGENT":
            language = info.language
        for seg in segs_iter:
            if not seg.text.strip():
                continue
            avg_conf = (
                sum(w.probability for w in seg.words) / len(seg.words)
                if seg.words else 0.9
            )
            segments.append(TranscriptSegment(
                speaker=speaker,
                start_ms=int(seg.start * 1000),
                end_ms=int(seg.end * 1000),
                text=seg.text.strip(),
                confidence=round(avg_conf, 4),
            ))

    segments.sort(key=lambda s: s.start_ms)
    logger.info("Stereo split complete — AGENT segs: %d, CUSTOMER segs: %d",
                sum(1 for s in segments if s.speaker == "AGENT"),
                sum(1 for s in segments if s.speaker == "CUSTOMER"))
    return segments, language, duration_seconds


# ---------------------------------------------------------------------------
# Mono heuristic (fallback when audio is mono)
# ---------------------------------------------------------------------------

def _transcribe_mono(
    audio_path: str, model, kwargs: dict
) -> tuple[list[TranscriptSegment], str, float]:
    segs_iter, info = model.transcribe(audio_path, **kwargs)
    whisper_segments = [s for s in segs_iter if s.text.strip()]

    pipeline = _get_pyannote_pipeline()
    if pipeline is not None:
        try:
            diarization = pipeline(audio_path)
            segments = _assign_speakers_pyannote(whisper_segments, diarization)
            logger.info("Pyannote diarization applied")
            return segments, info.language, round(info.duration, 2)
        except Exception as exc:
            logger.warning("Pyannote failed: %s — using heuristic", exc)

    segments = _assign_speakers_heuristic(whisper_segments)
    return segments, info.language, round(info.duration, 2)


def _get_pyannote_pipeline():
    global _pyannote_pipeline, _pyannote_attempted
    if _pyannote_attempted:
        return _pyannote_pipeline
    _pyannote_attempted = True
    hf_token = os.getenv("HUGGINGFACE_TOKEN", "").strip()
    if not hf_token:
        logger.info("HUGGINGFACE_TOKEN not set — mono calls use heuristic speaker assignment")
        return None
    try:
        from pyannote.audio import Pipeline
        _pyannote_pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1", use_auth_token=hf_token,
        )
        logger.info("Pyannote pipeline loaded")
    except Exception as exc:
        logger.warning("Pyannote load failed: %s", exc)
    return _pyannote_pipeline


def _assign_speakers_pyannote(whisper_segments: list, diarization) -> list[TranscriptSegment]:
    turn_list = list(diarization.itertracks(yield_label=True))
    unique_speakers: list[str] = []
    for _, _, spk in turn_list:
        if spk not in unique_speakers:
            unique_speakers.append(spk)
    label_map = {spk: ("AGENT" if i == 0 else "CUSTOMER") for i, spk in enumerate(unique_speakers[:2])}
    result: list[TranscriptSegment] = []
    for seg in whisper_segments:
        best_label = "AGENT"
        best_overlap = -1.0
        for turn, _, spk in turn_list:
            overlap = min(turn.end, seg.end) - max(turn.start, seg.start)
            if overlap > best_overlap:
                best_overlap = overlap
                best_label = label_map.get(spk, "AGENT")
        avg_conf = sum(w.probability for w in seg.words) / len(seg.words) if seg.words else 0.9
        result.append(TranscriptSegment(
            speaker=best_label, start_ms=int(seg.start * 1000), end_ms=int(seg.end * 1000),
            text=seg.text.strip(), confidence=round(avg_conf, 4),
        ))
    return result


def _assign_speakers_heuristic(whisper_segments: list) -> list[TranscriptSegment]:
    """
    Turn-taking heuristic. Speaker with the most total talk time → AGENT
    (outbound sales agents talk more than customers).
    """
    PAUSE_THRESHOLD = 0.8
    provisional: list[dict] = []
    spk_idx = 0
    prev_end = 0.0

    for seg in whisper_segments:
        if seg.start - prev_end >= PAUSE_THRESHOLD and prev_end > 0:
            spk_idx = 1 - spk_idx
        avg_conf = sum(w.probability for w in seg.words) / len(seg.words) if seg.words else 0.9
        provisional.append({
            "spk": spk_idx, "start_ms": int(seg.start * 1000), "end_ms": int(seg.end * 1000),
            "text": seg.text.strip(), "confidence": round(avg_conf, 4),
        })
        prev_end = seg.end

    time_0 = sum(s["end_ms"] - s["start_ms"] for s in provisional if s["spk"] == 0)
    time_1 = sum(s["end_ms"] - s["start_ms"] for s in provisional if s["spk"] == 1)
    agent_spk = 0 if time_0 >= time_1 else 1

    return [
        TranscriptSegment(
            speaker="AGENT" if s["spk"] == agent_spk else "CUSTOMER",
            start_ms=s["start_ms"], end_ms=s["end_ms"],
            text=s["text"], confidence=s["confidence"],
        )
        for s in provisional
    ]


# ---------------------------------------------------------------------------
# Voicemail / no-answer detection  (Fix 2)
# ---------------------------------------------------------------------------

def _detect_call_type(segments: list[TranscriptSegment], duration_seconds: float) -> str:
    if not segments:
        return "NO_ANSWER"

    # Check full transcript (not just first 60s) — voicemail prompt can appear anywhere in short calls
    full_text = " ".join(s.text.lower() for s in segments)
    early_text = " ".join(s.text.lower() for s in segments if s.start_ms < 60000)

    for phrase in VOICEMAIL_PHRASES:
        if phrase in early_text:
            logger.info("Voicemail phrase detected: '%s'", phrase)
            return "VOICEMAIL"

    # Also check full text for short calls (< 60s) where voicemail prompt fills entire call
    if duration_seconds < 60:
        for phrase in VOICEMAIL_PHRASES:
            if phrase in full_text:
                logger.info("Voicemail phrase detected in short call: '%s'", phrase)
                return "VOICEMAIL"

    if duration_seconds < 30:
        return "NO_ANSWER"

    # If only one speaker (no agent speech detected) in a short call, likely voicemail
    agent_segs = [s for s in segments if s.speaker == "AGENT"]
    if not agent_segs and duration_seconds < 120:
        logger.info("No agent speech in short call — classifying as VOICEMAIL")
        return "VOICEMAIL"

    return "LIVE"


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(request: TranscribeRequest) -> TranscribeResponse:
    minio_client = Minio(
        os.getenv("MINIO_ENDPOINT", "minio:9000"),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin123"),
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
    )
    bucket = os.getenv("MINIO_BUCKET_RECORDINGS", "call-recordings")

    with tempfile.TemporaryDirectory() as tmpdir:
        ext = request.minio_path.rsplit(".", 1)[-1] if "." in request.minio_path else "wav"
        audio_path = f"{tmpdir}/audio.{ext}"

        try:
            minio_client.fget_object(bucket, request.minio_path, audio_path)
        except Exception as exc:
            logger.error("MinIO download failed for %s: %s", request.minio_path, exc)
            raise HTTPException(status_code=404, detail=f"Audio file not found: {exc}")

        model = _get_whisper_model()
        kwargs = _base_transcribe_kwargs(request.language)

        if _is_stereo(audio_path):
            logger.info("Stereo audio — using channel-based speaker attribution (Fix 1)")
            segments, language, duration_seconds = _transcribe_stereo(
                audio_path, model, kwargs, tmpdir
            )
        else:
            logger.info("Mono audio — using heuristic/pyannote speaker assignment")
            segments, language, duration_seconds = _transcribe_mono(audio_path, model, kwargs)

        call_type = _detect_call_type(segments, duration_seconds)
        logger.info("Transcription done: %.1fs, lang=%s, %d segs, call_type=%s",
                    duration_seconds, language, len(segments), call_type)

        return TranscribeResponse(
            segments=segments,
            language=language,
            duration_seconds=round(duration_seconds, 2),
            call_type=call_type,
        )

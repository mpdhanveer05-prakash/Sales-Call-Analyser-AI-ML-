import logging
import os
import tempfile
from typing import Optional

from fastapi import APIRouter, HTTPException
from minio import Minio
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(tags=["transcription"])

# Lazy-loaded globals — initialised once on first request
_whisper_model = None
_pyannote_pipeline = None
_pyannote_attempted = False


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


# ---------------------------------------------------------------------------
# Model helpers
# ---------------------------------------------------------------------------

def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        model_size = os.getenv("WHISPER_MODEL_SIZE", "base")
        device = os.getenv("WHISPER_DEVICE", "cpu")
        compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
        cache_dir = os.getenv("MODEL_CACHE_DIR", "/app/model_cache")

        logger.info("Loading Whisper model '%s' on %s (%s)", model_size, device, compute_type)
        _whisper_model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            download_root=cache_dir,
        )
        logger.info("Whisper model loaded")
    return _whisper_model


def _get_pyannote_pipeline(min_speakers: int, max_speakers: int):
    global _pyannote_pipeline, _pyannote_attempted
    if _pyannote_attempted:
        return _pyannote_pipeline

    _pyannote_attempted = True
    hf_token = os.getenv("HUGGINGFACE_TOKEN", "").strip()
    if not hf_token:
        logger.info("HUGGINGFACE_TOKEN not set — using heuristic speaker assignment")
        return None

    try:
        from pyannote.audio import Pipeline

        logger.info("Loading Pyannote speaker diarization pipeline")
        _pyannote_pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token,
        )
        logger.info("Pyannote pipeline loaded")
    except Exception as exc:
        logger.warning("Failed to load Pyannote pipeline: %s — using heuristic", exc)
        _pyannote_pipeline = None

    return _pyannote_pipeline


# ---------------------------------------------------------------------------
# Speaker assignment helpers
# ---------------------------------------------------------------------------

def _assign_speakers_pyannote(
    whisper_segments: list,
    diarization,
    min_speakers: int,
    max_speakers: int,
) -> list[TranscriptSegment]:
    """Map Pyannote diarization turns onto Whisper segments."""
    turn_list = list(diarization.itertracks(yield_label=True))

    unique_speakers: list[str] = []
    for _, _, spk in turn_list:
        if spk not in unique_speakers:
            unique_speakers.append(spk)

    speaker_label = {spk: ("AGENT" if i == 0 else "CUSTOMER") for i, spk in enumerate(unique_speakers[:2])}

    result: list[TranscriptSegment] = []
    for seg in whisper_segments:
        seg_start, seg_end = seg.start, seg.end
        best_label = "AGENT"
        best_overlap = -1.0

        for turn, _, spk in turn_list:
            overlap = min(turn.end, seg_end) - max(turn.start, seg_start)
            if overlap > best_overlap:
                best_overlap = overlap
                best_label = speaker_label.get(spk, "AGENT")

        avg_conf = (
            sum(w.probability for w in seg.words) / len(seg.words)
            if seg.words else 0.9
        )
        result.append(TranscriptSegment(
            speaker=best_label,
            start_ms=int(seg_start * 1000),
            end_ms=int(seg_end * 1000),
            text=seg.text.strip(),
            confidence=round(avg_conf, 4),
        ))
    return result


def _assign_speakers_heuristic(whisper_segments: list) -> list[TranscriptSegment]:
    """
    Turn-taking heuristic for 2-speaker outbound phone calls.
    Alternates speakers on pauses >= PAUSE_THRESHOLD seconds.
    The speaker with the most total talk time is labelled AGENT — more
    robust than assuming the first speaker is the agent, because in 3CX
    recordings the customer often answers first ("Hello?").
    """
    PAUSE_THRESHOLD = 0.8

    provisional: list[dict] = []
    spk_idx = 0
    prev_end = 0.0

    for seg in whisper_segments:
        gap = seg.start - prev_end
        if gap >= PAUSE_THRESHOLD and prev_end > 0:
            spk_idx = 1 - spk_idx

        avg_conf = (
            sum(w.probability for w in seg.words) / len(seg.words)
            if seg.words else 0.9
        )
        provisional.append({
            "spk": spk_idx,
            "start_ms": int(seg.start * 1000),
            "end_ms": int(seg.end * 1000),
            "text": seg.text.strip(),
            "confidence": round(avg_conf, 4),
        })
        prev_end = seg.end

    # Determine which provisional index is the AGENT: the one with more
    # total speaking time (outbound sales agents talk more than customers).
    time_0 = sum((s["end_ms"] - s["start_ms"]) for s in provisional if s["spk"] == 0)
    time_1 = sum((s["end_ms"] - s["start_ms"]) for s in provisional if s["spk"] == 1)
    agent_spk = 0 if time_0 >= time_1 else 1

    return [
        TranscriptSegment(
            speaker="AGENT" if s["spk"] == agent_spk else "CUSTOMER",
            start_ms=s["start_ms"],
            end_ms=s["end_ms"],
            text=s["text"],
            confidence=s["confidence"],
        )
        for s in provisional
    ]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(request: TranscribeRequest) -> TranscribeResponse:
    # Download audio from MinIO
    minio_client = Minio(
        os.getenv("MINIO_ENDPOINT", "minio:9000"),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin123"),
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
    )
    bucket = os.getenv("MINIO_BUCKET_RECORDINGS", "call-recordings")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Preserve extension so ffmpeg can detect format
        ext = request.minio_path.rsplit(".", 1)[-1] if "." in request.minio_path else "wav"
        audio_path = f"{tmpdir}/audio.{ext}"

        try:
            minio_client.fget_object(bucket, request.minio_path, audio_path)
        except Exception as exc:
            logger.error("MinIO download failed for %s: %s", request.minio_path, exc)
            raise HTTPException(status_code=404, detail=f"Audio file not found in storage: {exc}")

        # Run transcription
        model = _get_whisper_model()
        transcribe_kwargs: dict = {
            "beam_size": 5,
            "word_timestamps": True,
            "vad_filter": True,
            "vad_parameters": {"min_silence_duration_ms": 300, "speech_pad_ms": 200},
            "condition_on_previous_text": False,  # prevents hallucination loops
            "no_speech_threshold": 0.6,
            "log_prob_threshold": -1.0,
            "compression_ratio_threshold": 2.4,
        }
        if request.language:
            transcribe_kwargs["language"] = request.language

        logger.info("Transcribing %s", request.minio_path)
        segments_iter, info = model.transcribe(audio_path, **transcribe_kwargs)
        whisper_segments = [s for s in segments_iter if s.text.strip()]
        logger.info("Transcription done: %.1fs, lang=%s, %d segments", info.duration, info.language, len(whisper_segments))

        # Speaker diarization
        pipeline = _get_pyannote_pipeline(request.min_speakers, request.max_speakers)

        if pipeline is not None:
            try:
                diarization = pipeline(
                    audio_path,
                    min_speakers=request.min_speakers,
                    max_speakers=request.max_speakers,
                )
                segments = _assign_speakers_pyannote(
                    whisper_segments, diarization, request.min_speakers, request.max_speakers
                )
                logger.info("Pyannote diarization applied")
            except Exception as exc:
                logger.warning("Pyannote diarization error: %s — falling back to heuristic", exc)
                segments = _assign_speakers_heuristic(whisper_segments)
        else:
            segments = _assign_speakers_heuristic(whisper_segments)

        return TranscribeResponse(
            segments=segments,
            language=info.language,
            duration_seconds=round(info.duration, 2),
        )

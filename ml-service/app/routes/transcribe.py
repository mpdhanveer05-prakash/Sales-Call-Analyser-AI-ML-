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
_whisperx_align_model = None
_whisperx_metadata = None
_whisperx_attempted = False

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
    speaker: str                          # Back-compat: AGENT/CUSTOMER/SYSTEM
    role: str = "UNKNOWN"                 # Semantic role: HUMAN_AGENT, AUTO_ATTENDANT, etc.
    role_confidence: float = 0.0
    start_ms: int
    end_ms: int
    text: str
    confidence: float


class TranscribeResponse(BaseModel):
    segments: list[TranscriptSegment]
    language: str
    duration_seconds: float
    call_type: str = "LIVE"                # LIVE | VOICEMAIL | NO_ANSWER (back-compat)
    call_topology: str = "UNKNOWN"         # Semantic topology of the call
    topology_confidence: float = 0.0


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
    """Returns True only if the file is true stereo with distinct channels.

    If both channels are essentially identical (summed audio, common with mis-
    configured PBXs), returns False so the caller falls back to diarization.
    """
    try:
        from pydub import AudioSegment
        import numpy as np

        audio = AudioSegment.from_file(audio_path)
        if audio.channels != 2:
            return False

        # Compare channels — if they're nearly identical the recording is summed
        samples = np.array(audio.get_array_of_samples()).reshape(-1, 2)
        left = samples[:, 0].astype(np.float32)
        right = samples[:, 1].astype(np.float32)

        # Cosine similarity — 1.0 = identical channels (summed audio)
        denom = (np.linalg.norm(left) * np.linalg.norm(right)) or 1.0
        similarity = float(np.dot(left, right) / denom)
        logger.info("Stereo similarity L vs R: %.3f", similarity)

        if similarity > 0.98:
            logger.warning("Stereo channels nearly identical — treating as mono for diarization")
            return False
        return True
    except Exception as exc:
        logger.warning("Stereo check failed: %s", exc)
        return False


# Strong agent-introduction signals — phrases an agent says but customers virtually never do
_AGENT_INTRO_PATTERNS = [
    "this is",          # "This is Zahra with O'Connor"
    "calling from",     # "Calling from O'Connor"
    "calling regarding",
    "calling about",
    "this call regarding",
    "regarding your",   # "regarding your property tax"
    "with o'connor", "with oconnor",  # company-specific — adjust per deployment
    "with the company",
    "how are you today",
    "do you have a moment",
    "is this a good time",
]


def _score_agent_likelihood(channel_segments: list[dict]) -> float:
    """Higher score = more likely to be the agent channel.

    Combines: agent-intro phrase matches + total talk time (sales agents talk
    more than customers on outbound, and lead the conversation on inbound too).
    """
    if not channel_segments:
        return 0.0
    text_lower = " ".join(s["text"].lower() for s in channel_segments)
    intro_matches = sum(1 for pat in _AGENT_INTRO_PATTERNS if pat in text_lower)
    total_ms = sum(s["end_ms"] - s["start_ms"] for s in channel_segments)
    # Intro phrase match is the strongest signal — weight 10x talk time
    return intro_matches * 10.0 + (total_ms / 1000.0)


def _transcribe_stereo(
    audio_path: str, model, kwargs: dict, tmpdir: str
) -> tuple[list[TranscriptSegment], str, float]:
    """
    Split stereo audio, transcribe each channel independently, then auto-detect
    which channel is the AGENT based on:
      1. Manual override via STEREO_CHANNEL_AGENT=left|right (highest priority)
      2. Agent-intro phrase matching in transcript ("this is X with Y company")
      3. Talk-time fallback (agent typically dominates the call)
    """
    from pydub import AudioSegment

    audio = AudioSegment.from_file(audio_path)
    channels = audio.split_to_mono()
    duration_seconds = len(audio) / 1000.0
    language = "en"

    # Transcribe each channel separately and collect segments per channel
    per_channel: list[list[dict]] = [[], []]
    for idx, channel_audio in enumerate(channels):
        channel_path = f"{tmpdir}/ch{idx}.wav"
        channel_audio.export(channel_path, format="wav")
        segs_iter, info = model.transcribe(channel_path, **kwargs)
        if idx == 0:
            language = info.language
        for seg in segs_iter:
            if not seg.text.strip():
                continue
            avg_conf = (
                sum(w.probability for w in seg.words) / len(seg.words)
                if seg.words else 0.9
            )
            per_channel[idx].append({
                "start_ms": int(seg.start * 1000),
                "end_ms": int(seg.end * 1000),
                "text": seg.text.strip(),
                "confidence": round(avg_conf, 4),
            })

    # Decide which channel is the AGENT
    manual = os.getenv("STEREO_CHANNEL_AGENT", "").lower().strip()
    if manual == "left":
        agent_idx = 0
        decision = "manual override (STEREO_CHANNEL_AGENT=left)"
    elif manual == "right":
        agent_idx = 1
        decision = "manual override (STEREO_CHANNEL_AGENT=right)"
    elif os.getenv("STEREO_CHANNEL_SWAP", "false").lower() == "true":
        agent_idx = 1
        decision = "STEREO_CHANNEL_SWAP=true"
    else:
        score_left = _score_agent_likelihood(per_channel[0])
        score_right = _score_agent_likelihood(per_channel[1])
        agent_idx = 0 if score_left >= score_right else 1
        decision = f"auto-detected (left_score={score_left:.1f}, right_score={score_right:.1f})"

    customer_idx = 1 - agent_idx
    logger.info("Stereo agent channel: %s (%s)",
                "LEFT" if agent_idx == 0 else "RIGHT", decision)

    # Build final segment list with correct AGENT/CUSTOMER labels
    segments: list[TranscriptSegment] = []
    for seg in per_channel[agent_idx]:
        segments.append(TranscriptSegment(speaker="AGENT", **seg))
    for seg in per_channel[customer_idx]:
        segments.append(TranscriptSegment(speaker="CUSTOMER", **seg))

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
    """Map Pyannote speaker labels to AGENT/CUSTOMER.

    The speaker with the most total talk time is labeled AGENT — in outbound
    sales calls the agent reliably dominates the conversation.
    """
    turn_list = list(diarization.itertracks(yield_label=True))

    # Calculate total talk time per speaker — most talkative = AGENT
    talk_time: dict[str, float] = {}
    for turn, _, spk in turn_list:
        talk_time[spk] = talk_time.get(spk, 0) + (turn.end - turn.start)

    if not talk_time:
        # No speakers detected — fall through with default AGENT
        label_map: dict[str, str] = {}
    else:
        sorted_speakers = sorted(talk_time.items(), key=lambda x: x[1], reverse=True)
        label_map = {sorted_speakers[0][0]: "AGENT"}
        if len(sorted_speakers) > 1:
            label_map[sorted_speakers[1][0]] = "CUSTOMER"
        logger.info("Pyannote speaker mapping by talk time: %s", label_map)

    result: list[TranscriptSegment] = []
    for seg in whisper_segments:
        best_label = "AGENT"
        best_overlap = -1.0
        for turn, _, spk in turn_list:
            overlap = min(turn.end, seg.end) - max(turn.start, seg.start)
            if overlap > best_overlap:
                best_overlap = overlap
                best_label = label_map.get(spk, "CUSTOMER")
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
# Optional WhisperX wav2vec2 alignment — improves word-level timestamp accuracy
# Enable by:  USE_WHISPERX_ALIGNMENT=true  and uncomment whisperx in requirements.txt
# ---------------------------------------------------------------------------

def _get_whisperx_align():
    global _whisperx_align_model, _whisperx_metadata, _whisperx_attempted
    if _whisperx_attempted:
        return _whisperx_align_model, _whisperx_metadata
    _whisperx_attempted = True
    if os.getenv("USE_WHISPERX_ALIGNMENT", "false").lower() != "true":
        return None, None
    try:
        import whisperx
        device = os.getenv("WHISPER_DEVICE", "cuda")
        _whisperx_align_model, _whisperx_metadata = whisperx.load_align_model(
            language_code="en", device=device,
        )
        logger.info("WhisperX alignment model loaded on %s", device)
    except Exception as exc:
        logger.warning("WhisperX unavailable (%s) — using faster-whisper word timestamps", exc)
    return _whisperx_align_model, _whisperx_metadata


def _align_segments_whisperx(
    segments: list[TranscriptSegment], audio_path: str
) -> list[TranscriptSegment]:
    """Refine word-level timestamps via wav2vec2 forced alignment.  No-op if disabled."""
    align_model, metadata = _get_whisperx_align()
    if align_model is None:
        return segments
    try:
        import whisperx
        device = os.getenv("WHISPER_DEVICE", "cuda")
        wx_segments = [
            {"start": s.start_ms / 1000.0, "end": s.end_ms / 1000.0, "text": s.text}
            for s in segments
        ]
        result = whisperx.align(
            wx_segments, align_model, metadata, audio_path, device=device,
            return_char_alignments=False,
        )
        aligned = result.get("segments", [])
        if len(aligned) != len(segments):
            return segments
        return [
            TranscriptSegment(
                speaker=orig.speaker,
                start_ms=int(a.get("start", orig.start_ms / 1000) * 1000),
                end_ms=int(a.get("end", orig.end_ms / 1000) * 1000),
                text=orig.text,
                confidence=orig.confidence,
            )
            for orig, a in zip(segments, aligned)
        ]
    except Exception as exc:
        logger.warning("WhisperX align failed (%s) — using original timestamps", exc)
        return segments


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

        # Optional WhisperX wav2vec2 alignment for more precise word timestamps
        segments = _align_segments_whisperx(segments, audio_path)

        # ---------- Semantic role classification (Phase 1) ----------
        # Replaces channel-based AGENT/CUSTOMER labelling with per-segment role:
        #   HUMAN_AGENT, HUMAN_CUSTOMER, AUTO_ATTENDANT, IVR_SYSTEM,
        #   VOICEMAIL_GREETING, VOICEMAIL_MENU, UNKNOWN
        from app.services import speaker_role_classifier as src

        classifier_input = [
            {
                "text": s.text,
                "start_ms": s.start_ms,
                "end_ms": s.end_ms,
                "channel": 0 if s.speaker == "AGENT" else 1,
            }
            for s in segments
        ]
        cls_result = src.classify_segments(classifier_input)

        # Attach role + role_confidence to segments. Also keep a derived `speaker`
        # column for back-compat with code that still reads AGENT/CUSTOMER.
        segments = [
            TranscriptSegment(
                speaker=_role_to_speaker(c.role, orig.speaker),
                role=c.role,
                role_confidence=c.confidence,
                start_ms=orig.start_ms,
                end_ms=orig.end_ms,
                text=orig.text,
                confidence=orig.confidence,
            )
            for orig, c in zip(segments, cls_result.segments)
        ]

        # Derive call_type from topology for back-compat with downstream code that
        # still reads call_type. Topology is the source of truth going forward.
        call_topology = cls_result.call_topology
        topology_conf = cls_result.topology_confidence
        topology_dispo = src.topology_to_disposition(call_topology)
        if topology_dispo == "VOICEMAIL":
            call_type = "VOICEMAIL"
        elif topology_dispo == "NO_ANSWER":
            call_type = "NO_ANSWER"
        else:
            call_type = _detect_call_type(segments, duration_seconds)

        logger.info(
            "Transcription done: %.1fs, lang=%s, %d segs, call_type=%s, topology=%s (%.2f)",
            duration_seconds, language, len(segments), call_type, call_topology, topology_conf,
        )

        return TranscribeResponse(
            segments=segments,
            language=language,
            duration_seconds=round(duration_seconds, 2),
            call_type=call_type,
            call_topology=call_topology,
            topology_confidence=topology_conf,
        )


def _role_to_speaker(role: str, fallback_speaker: str) -> str:
    """Map semantic role back to legacy speaker label for back-compat.

    Frontend should read `role` directly; this is only for downstream code that
    has not been updated yet.
    """
    if role == "HUMAN_AGENT":
        return "AGENT"
    if role == "HUMAN_CUSTOMER":
        return "CUSTOMER"
    if role in ("AUTO_ATTENDANT", "IVR_SYSTEM", "VOICEMAIL_GREETING", "VOICEMAIL_MENU"):
        return "SYSTEM"
    return fallback_speaker

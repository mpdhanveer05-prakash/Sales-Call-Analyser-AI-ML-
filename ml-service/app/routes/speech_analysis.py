import logging
import os
import re
import tempfile
from typing import Optional

import httpx
import numpy as np
from fastapi import APIRouter, HTTPException
from minio import Minio
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(tags=["speech-analysis"])

# Pre-compiled filler word pattern
_FILLER_RE = re.compile(
    r"\b(um+|uh+|hmm+|ah+|er+|like|basically|you\s+know|i\s+mean|sort\s+of|kind\s+of|right\??|okay\??|so\b|anyway)\b",
    re.IGNORECASE,
)

_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        import spacy
        _nlp = spacy.load("en_core_web_sm", disable=["ner", "parser"])
    return _nlp


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TranscriptSegmentIn(BaseModel):
    speaker: str
    start_ms: int
    end_ms: int
    text: str
    confidence: Optional[float] = None


class SpeechAnalysisRequest(BaseModel):
    minio_path: str
    transcript: list[TranscriptSegmentIn]
    language: str = "en"


class RawSpeechMetrics(BaseModel):
    avg_word_confidence: float
    f0_mean_hz: Optional[float]
    f0_std_hz: Optional[float]
    pause_count: int
    pause_rate_per_min: float
    grammar_errors_per_100: float
    grammar_error_count: int
    word_count: int
    type_token_ratio: float
    unique_word_count: int
    pace_wpm: float
    low_confidence_pct: float
    filler_count: int
    fillers_per_min: float
    agent_talk_ratio: float
    duration_seconds: float


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/analyze-speech", response_model=RawSpeechMetrics)
def analyze_speech(request: SpeechAnalysisRequest) -> RawSpeechMetrics:
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
            raise HTTPException(status_code=404, detail=f"Audio not found in storage: {exc}")

        agent_segs = [s for s in request.transcript if s.speaker == "AGENT"]
        all_segs = request.transcript

        if not agent_segs:
            raise HTTPException(status_code=422, detail="No AGENT segments found in transcript")

        # --- Transcript-based metrics (AGENT only) ---
        agent_text = " ".join(s.text.strip() for s in agent_segs)
        agent_duration_ms = sum(s.end_ms - s.start_ms for s in agent_segs)
        total_duration_ms = max((s.end_ms for s in all_segs), default=1)

        agent_duration_min = agent_duration_ms / 60_000
        total_duration_sec = total_duration_ms / 1000.0

        words = agent_text.split()
        word_count = len(words)
        pace_wpm = (word_count / agent_duration_min) if agent_duration_min > 0 else 0.0

        fillers = _FILLER_RE.findall(agent_text)
        filler_count = len(fillers)
        fillers_per_min = filler_count / agent_duration_min if agent_duration_min > 0 else 0.0

        # Vocabulary — type-token ratio on lemmatised, stop-removed content words
        nlp = _get_nlp()
        doc = nlp(agent_text.lower()[:1_000_000])  # guard against very long text
        content_tokens = [t.lemma_ for t in doc if t.is_alpha and not t.is_stop and len(t) > 1]
        unique_word_count = len(set(content_tokens))
        type_token_ratio = unique_word_count / max(len(content_tokens), 1)

        # Whisper confidence
        confidences = [s.confidence for s in agent_segs if s.confidence is not None]
        avg_word_confidence = float(np.mean(confidences)) if confidences else 0.85
        low_confidence_pct = float(
            sum(1 for c in confidences if c < 0.6) / max(len(confidences), 1)
        )

        agent_talk_ratio = agent_duration_ms / max(total_duration_ms, 1)

        # --- LanguageTool grammar check ---
        grammar_error_count = 0
        lt_url = os.getenv("LANGUAGETOOL_URL", "http://languagetool:8010")
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(
                    f"{lt_url}/v2/check",
                    data={"text": agent_text[:10_000], "language": "en-US"},
                )
            if resp.status_code == 200:
                matches = resp.json().get("matches", [])
                grammar_error_count = sum(
                    1 for m in matches
                    if m.get("rule", {}).get("issueType") not in ("style", "typographical", "whitespace")
                )
        except Exception as exc:
            logger.warning("LanguageTool unavailable: %s — grammar score defaulting to 0 errors", exc)

        grammar_errors_per_100 = (grammar_error_count / max(word_count, 1)) * 100

        # --- Acoustic: F0 pitch analysis (parselmouth) ---
        f0_mean_hz: Optional[float] = None
        f0_std_hz: Optional[float] = None
        try:
            import parselmouth
            from parselmouth.praat import call as praat_call

            snd = parselmouth.Sound(audio_path)
            pitch_obj = praat_call(snd, "To Pitch", 0.0, 75.0, 600.0)
            f0_values = pitch_obj.selected_array["frequency"]
            voiced = f0_values[f0_values > 0]
            if len(voiced) >= 20:
                f0_mean_hz = float(np.mean(voiced))
                f0_std_hz = float(np.std(voiced))
        except Exception as exc:
            logger.warning("Parselmouth F0 analysis failed: %s", exc)

        # --- Acoustic: pause detection (librosa) ---
        pause_count = 0
        pause_rate_per_min = 0.0
        try:
            import librosa

            y, sr = librosa.load(audio_path, sr=16_000, mono=True)
            duration_audio_min = len(y) / sr / 60.0

            frame_length = 1024
            hop_length = 256
            rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]

            # Silence = below 20th percentile RMS
            silence_thresh = float(np.percentile(rms, 20))
            min_pause_frames = int(0.3 * sr / hop_length)  # 0.3 s min pause

            in_pause = False
            consecutive = 0
            for val in rms:
                if val <= silence_thresh:
                    consecutive += 1
                    if consecutive >= min_pause_frames and not in_pause:
                        pause_count += 1
                        in_pause = True
                else:
                    consecutive = 0
                    in_pause = False

            pause_rate_per_min = pause_count / max(duration_audio_min, 0.01)
        except Exception as exc:
            logger.warning("Librosa pause analysis failed: %s", exc)

        return RawSpeechMetrics(
            avg_word_confidence=round(avg_word_confidence, 4),
            f0_mean_hz=round(f0_mean_hz, 2) if f0_mean_hz is not None else None,
            f0_std_hz=round(f0_std_hz, 2) if f0_std_hz is not None else None,
            pause_count=pause_count,
            pause_rate_per_min=round(pause_rate_per_min, 2),
            grammar_errors_per_100=round(grammar_errors_per_100, 2),
            grammar_error_count=grammar_error_count,
            word_count=word_count,
            type_token_ratio=round(type_token_ratio, 4),
            unique_word_count=unique_word_count,
            pace_wpm=round(pace_wpm, 1),
            low_confidence_pct=round(low_confidence_pct, 4),
            filler_count=filler_count,
            fillers_per_min=round(fillers_per_min, 2),
            agent_talk_ratio=round(agent_talk_ratio, 4),
            duration_seconds=round(total_duration_sec, 2),
        )

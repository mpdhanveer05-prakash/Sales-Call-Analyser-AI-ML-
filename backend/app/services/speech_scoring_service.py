"""
Convert raw acoustic/NLP metrics from the ML service into 0-100 per-dimension scores.

Weights must sum to 1.0:
  pronunciation 15%, intonation 15%, fluency 15%, grammar 15%
  vocabulary 10%, pace 10%, clarity 10%, filler_words 10%
"""
from typing import Optional


WEIGHTS: dict[str, float] = {
    "pronunciation": 0.15,
    "intonation":    0.15,
    "fluency":       0.15,
    "grammar":       0.15,
    "vocabulary":    0.10,
    "pace":          0.10,
    "clarity":       0.10,
    "filler_score":  0.10,
}


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# Per-dimension scoring functions
# ---------------------------------------------------------------------------

def score_pronunciation(avg_confidence: float) -> float:
    """Whisper word-level confidence (0-1) → 0-100."""
    return round(_clamp(avg_confidence * 100), 1)


def score_intonation(f0_std_hz: Optional[float]) -> float:
    """
    F0 standard deviation:
    - < 5 Hz  → monotone → low score
    - 20-80 Hz → natural variance → 100
    - > 80 Hz  → too varied → decreasing
    """
    if f0_std_hz is None:
        return 65.0  # default when parselmouth fails

    if f0_std_hz < 5:
        return 20.0
    if f0_std_hz < 20:
        return round(20 + (f0_std_hz - 5) / 15 * 60, 1)
    if f0_std_hz <= 80:
        return 100.0
    return round(_clamp(100 - (f0_std_hz - 80) * 1.5), 1)


def score_fluency(pause_rate_per_min: float) -> float:
    """
    Pauses per minute:
    - 3-8 per minute → natural pacing → 100
    - < 3  → possibly too rushed or no pauses detected
    - > 8  → choppy, too many hesitations
    """
    if pause_rate_per_min < 1:
        return 60.0
    if pause_rate_per_min < 3:
        return round(60 + (pause_rate_per_min - 1) / 2 * 40, 1)
    if pause_rate_per_min <= 8:
        return 100.0
    return round(_clamp(100 - (pause_rate_per_min - 8) * 7), 1)


def score_grammar(errors_per_100_words: float) -> float:
    """
    Grammar errors per 100 words:
    - 0   → 100
    - 12+ → 0
    """
    return round(_clamp(100 - errors_per_100_words * 8.33), 1)


def score_vocabulary(type_token_ratio: float) -> float:
    """
    Type-token ratio on content words:
    - 0.0 → 0, 0.5+ → 100
    """
    return round(_clamp(type_token_ratio * 200), 1)


def score_pace(pace_wpm: float) -> float:
    """
    Words per minute:
    - 120-160 WPM → ideal for sales calls → 100
    - < 80 or > 200 → 0
    """
    if pace_wpm <= 0:
        return 50.0
    if 120 <= pace_wpm <= 160:
        return 100.0
    if pace_wpm < 120:
        return round(_clamp(60 + (pace_wpm - 80) / 40 * 40), 1)
    return round(_clamp(100 - (pace_wpm - 160) / 40 * 40), 1)


def score_clarity(low_confidence_pct: float) -> float:
    """
    Percentage of low-confidence Whisper words (0-1):
    - 0% unclear → 100, 50%+ unclear → 0
    """
    return round(_clamp((1 - low_confidence_pct) * 100), 1)


def score_filler_words(fillers_per_min: float) -> float:
    """
    Filler words per minute:
    - 0 → 100, 5+ per min → 25, 8+ → 0
    """
    return round(_clamp(100 - fillers_per_min * 15), 1)


# ---------------------------------------------------------------------------
# Composite calculator
# ---------------------------------------------------------------------------

def compute_speech_scores(metrics: dict) -> dict:
    """
    metrics: RawSpeechMetrics dict from ML service.
    Returns a dict with individual dimension scores + composite.
    """
    pronunciation = score_pronunciation(metrics.get("avg_word_confidence", 0.85))
    intonation    = score_intonation(metrics.get("f0_std_hz"))
    fluency       = score_fluency(metrics.get("pause_rate_per_min", 5.0))
    grammar       = score_grammar(metrics.get("grammar_errors_per_100", 0.0))
    vocabulary    = score_vocabulary(metrics.get("type_token_ratio", 0.4))
    pace          = score_pace(metrics.get("pace_wpm", 140.0))
    clarity       = score_clarity(metrics.get("low_confidence_pct", 0.0))
    filler_score  = score_filler_words(metrics.get("fillers_per_min", 0.0))

    dim_scores = {
        "pronunciation": pronunciation,
        "intonation":    intonation,
        "fluency":       fluency,
        "grammar":       grammar,
        "vocabulary":    vocabulary,
        "pace":          pace,
        "clarity":       clarity,
        "filler_score":  filler_score,
    }

    composite = sum(dim_scores[k] * WEIGHTS[k] for k in WEIGHTS)

    return {
        **dim_scores,
        "composite": round(composite, 1),
        "fillers_per_min": metrics.get("fillers_per_min", 0.0),
        "pace_wpm": metrics.get("pace_wpm", 0.0),
        "talk_ratio": metrics.get("agent_talk_ratio", 0.5),
    }

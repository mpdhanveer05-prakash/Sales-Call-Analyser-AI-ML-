"""
Unit tests for speech_scoring_service.py.

Uses the actual metric key names that compute_speech_scores() reads:
  - avg_word_confidence  (maps to pronunciation)
  - f0_std_hz            (maps to intonation)
  - pause_rate_per_min   (maps to fluency)
  - grammar_errors_per_100 (maps to grammar)
  - type_token_ratio     (maps to vocabulary)
  - pace_wpm             (maps to pace)
  - low_confidence_pct   (maps to clarity)
  - fillers_per_min      (maps to filler_score)
  - agent_talk_ratio     (preserved as talk_ratio)
"""
import pytest

from app.services.speech_scoring_service import compute_speech_scores


def test_compute_speech_scores_returns_all_dimensions():
    metrics = {
        "avg_word_confidence": 0.85,   # pronunciation_score equivalent
        "f0_std_hz": 45.0,
        "pause_rate_per_min": 5.0,
        "grammar_errors_per_100": 2.0,
        "type_token_ratio": 0.55,      # ttr equivalent
        "pace_wpm": 140.0,
        "low_confidence_pct": 0.08,    # 8% as a fraction (0-1)
        "fillers_per_min": 3.0,
        "agent_talk_ratio": 0.6,       # talk_ratio equivalent
    }
    result = compute_speech_scores(metrics)
    for dim in [
        "pronunciation", "intonation", "fluency", "grammar",
        "vocabulary", "pace", "clarity", "filler_score", "composite",
    ]:
        assert dim in result, f"Missing dimension: {dim}"
        assert 0 <= result[dim] <= 100, f"Score out of range: {dim}={result[dim]}"


def test_composite_is_weighted_average():
    metrics = {
        "avg_word_confidence": 1.0,    # pronunciation_score = 1.0
        "f0_std_hz": 60.0,
        "pause_rate_per_min": 2.0,
        "grammar_errors_per_100": 0.0,
        "type_token_ratio": 0.7,       # ttr = 0.7
        "pace_wpm": 150.0,
        "low_confidence_pct": 0.0,
        "fillers_per_min": 0.0,
        "agent_talk_ratio": 0.6,
    }
    result = compute_speech_scores(metrics)
    assert result["composite"] > 80, (
        f"Perfect metrics should yield high composite score, got {result['composite']}"
    )


def test_extreme_low_scores():
    """All-bad inputs should produce low but valid scores."""
    metrics = {
        "avg_word_confidence": 0.0,
        "f0_std_hz": 0.0,
        "pause_rate_per_min": 30.0,
        "grammar_errors_per_100": 20.0,
        "type_token_ratio": 0.0,
        "pace_wpm": 20.0,
        "low_confidence_pct": 1.0,
        "fillers_per_min": 15.0,
        "agent_talk_ratio": 0.1,
    }
    result = compute_speech_scores(metrics)
    assert result["composite"] >= 0
    assert result["composite"] <= 100
    assert result["composite"] < 50, (
        f"All-bad metrics should yield low composite score, got {result['composite']}"
    )


def test_extra_passthrough_metrics():
    """fillers_per_min, pace_wpm, and talk_ratio are preserved in result."""
    metrics = {
        "avg_word_confidence": 0.9,
        "f0_std_hz": 40.0,
        "pause_rate_per_min": 4.0,
        "grammar_errors_per_100": 1.0,
        "type_token_ratio": 0.5,
        "pace_wpm": 135.0,
        "low_confidence_pct": 0.05,
        "fillers_per_min": 2.0,
        "agent_talk_ratio": 0.55,
    }
    result = compute_speech_scores(metrics)
    assert "fillers_per_min" in result
    assert "pace_wpm" in result
    assert "talk_ratio" in result
    assert result["fillers_per_min"] == 2.0
    assert result["pace_wpm"] == 135.0
    assert result["talk_ratio"] == 0.55

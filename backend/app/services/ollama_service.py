"""
Ollama LLM service for sales quality scoring, call summarisation, and disposition classification.

All functions are synchronous — intended for use inside Celery tasks.
Uses Ollama's /api/generate with format=json for structured outputs.
"""
import json
import logging
import re
import time
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

DISPOSITION_CODES = [
    "CONVERTED", "INTERESTED_FOLLOWUP", "INTERESTED_NO_NEXTSTEP",
    "OBJECTION_PRICE", "OBJECTION_TIMING", "OBJECTION_AUTHORITY",
    "OBJECTION_NEED", "OBJECTION_COMPETITOR", "NOT_INTERESTED",
    "CALLBACK_REQUESTED", "VOICEMAIL", "NO_ANSWER", "WRONG_NUMBER",
    "GATEKEEPER", "DNC", "PARTIAL_CALL", "LANGUAGE_BARRIER", "OTHER",
]

SALES_DIMENSIONS = [
    "greeting", "rapport", "discovery", "value_explanation",
    "objection_handling", "script_adherence", "closing", "compliance",
]

SALES_WEIGHTS: dict[str, float] = {
    "greeting":          0.10,
    "rapport":           0.10,
    "discovery":         0.15,
    "value_explanation": 0.20,
    "objection_handling":0.20,
    "script_adherence":  0.10,
    "closing":           0.10,
    "compliance":        0.05,
}


# ---------------------------------------------------------------------------
# Transcript formatter
# ---------------------------------------------------------------------------

def format_transcript(segments: list[dict], max_words: int = 6000) -> str:
    lines: list[str] = []
    word_count = 0
    for seg in segments:
        start_sec = seg["start_ms"] // 1000
        m, s = divmod(start_sec, 60)
        text = seg["text"].strip()
        words = text.split()
        if word_count + len(words) > max_words:
            lines.append(f"[{m:02d}:{s:02d} {seg['speaker']}] [...transcript truncated for length...]")
            break
        lines.append(f"[{m:02d}:{s:02d} {seg['speaker']}] {text}")
        word_count += len(words)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON extraction helpers
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Cannot parse JSON from: {text[:300]}")


def _call_ollama(prompt: str, system: str, max_retries: int = 3) -> dict:
    payload = {
        "model": settings.ollama_default_model,
        "prompt": prompt,
        "system": system,
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 2048, "seed": 42},
    }
    last_exc: Exception = RuntimeError("No attempts made")
    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=float(settings.ollama_timeout_seconds)) as client:
                resp = client.post(f"{settings.ollama_url}/api/generate", json=payload)
                resp.raise_for_status()
            data = resp.json()
            result = _extract_json(data.get("response", ""))
            return result
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            last_exc = exc
            wait = 15 * (attempt + 1)
            logger.warning("Ollama connection error (attempt %d/%d): %s — retrying in %ds", attempt + 1, max_retries, exc, wait)
            time.sleep(wait)
        except ValueError as exc:
            last_exc = exc
            logger.warning("JSON parse failed (attempt %d/%d): %s", attempt + 1, max_retries, exc)
            if attempt < max_retries - 1:
                time.sleep(5)
    raise RuntimeError(f"Ollama failed after {max_retries} attempts: {last_exc}")


# ---------------------------------------------------------------------------
# Sales quality scoring
# ---------------------------------------------------------------------------

_SALES_SYSTEM = (
    "You are an expert sales quality analyst. "
    "Evaluate sales call transcripts objectively and output structured JSON only. "
    "Score strictly from 0 to 10 with 10 being perfect and 0 being completely absent."
)

_SALES_PROMPT_TEMPLATE = """Analyze this outbound sales call transcript and score the AGENT on 8 dimensions.

SALES SCRIPT RUBRIC (required talking points):
{rubric_text}

TRANSCRIPT:
{transcript}

Score each dimension from 0 to 10. Return ONLY valid JSON with this exact structure (no extra text):
{{
  "greeting":          {{"score": 0, "justification": "...", "quote": "..."}},
  "rapport":           {{"score": 0, "justification": "...", "quote": "..."}},
  "discovery":         {{"score": 0, "justification": "...", "quote": "..."}},
  "value_explanation": {{"score": 0, "justification": "...", "quote": "..."}},
  "objection_handling":{{"score": 0, "justification": "...", "quote": "..."}},
  "script_adherence":  {{"score": 0, "justification": "...", "quote": "..."}},
  "closing":           {{"score": 0, "justification": "...", "quote": "..."}},
  "compliance":        {{"score": 0, "justification": "...", "quote": "..."}}
}}"""


def score_sales_quality(segments: list[dict], rubric: dict) -> dict:
    """
    Returns dict with keys:
      - scores: {dim: {score, justification, quote}}
      - composite: float (0-100)
      - dimension_scores: {dim: float 0-100}
    """
    rubric_text = "\n".join(f"- {p}" for p in rubric.get("required_points", ["Cover key product benefits", "Ask for commitment"]))
    transcript = format_transcript(segments)

    prompt = _SALES_PROMPT_TEMPLATE.format(rubric_text=rubric_text, transcript=transcript)
    raw = _call_ollama(prompt, _SALES_SYSTEM)

    # Validate and extract per-dimension scores
    scores: dict[str, Any] = {}
    dimension_scores: dict[str, float] = {}
    for dim in SALES_DIMENSIONS:
        dim_data = raw.get(dim, {})
        if not isinstance(dim_data, dict):
            dim_data = {}
        raw_score = dim_data.get("score", 5)
        try:
            raw_score = max(0, min(10, float(raw_score)))
        except (TypeError, ValueError):
            raw_score = 5.0
        scores[dim] = {
            "score": raw_score,
            "justification": str(dim_data.get("justification", "")),
            "quote": str(dim_data.get("quote", "")),
        }
        dimension_scores[dim] = round(raw_score * 10, 1)  # 0-100

    composite = sum(dimension_scores[d] * SALES_WEIGHTS[d] for d in SALES_DIMENSIONS)
    return {
        "scores": scores,
        "dimension_scores": dimension_scores,
        "composite": round(composite, 1),
    }


# ---------------------------------------------------------------------------
# Call summary
# ---------------------------------------------------------------------------

_SUMMARY_SYSTEM = (
    "You are a senior sales manager reviewing a call recording. "
    "Provide concise, actionable insights for coaching. Output JSON only."
)

_SUMMARY_PROMPT_TEMPLATE = """Analyze this sales call transcript and generate a structured summary.

TRANSCRIPT:
{transcript}

Return ONLY valid JSON (no extra text):
{{
  "executive_summary": "3-4 sentence summary of the call outcome and key highlights",
  "key_moments": ["moment 1", "moment 2", "moment 3"],
  "coaching_suggestions": ["actionable suggestion 1", "actionable suggestion 2", "actionable suggestion 3"]
}}"""


def generate_summary(segments: list[dict]) -> dict:
    """Returns {executive_summary, key_moments, coaching_suggestions}."""
    transcript = format_transcript(segments)
    prompt = _SUMMARY_PROMPT_TEMPLATE.format(transcript=transcript)
    raw = _call_ollama(prompt, _SUMMARY_SYSTEM)

    return {
        "executive_summary": str(raw.get("executive_summary", "Summary not available.")),
        "key_moments": [str(m) for m in raw.get("key_moments", [])[:10]],
        "coaching_suggestions": [str(s) for s in raw.get("coaching_suggestions", [])[:10]],
    }


# ---------------------------------------------------------------------------
# Disposition classification
# ---------------------------------------------------------------------------

_DISPOSITION_SYSTEM = (
    "You are a sales operations analyst. "
    "Classify sales call outcomes using the provided taxonomy. Output JSON only."
)

_DISPOSITION_PROMPT_TEMPLATE = """Classify this sales call into exactly ONE of these 18 disposition codes:

{codes}

TRANSCRIPT:
{transcript}

Return ONLY valid JSON (no extra text):
{{"disposition": "ONE_CODE", "confidence": 0.95, "reasoning": "one sentence reason"}}"""


def classify_disposition(segments: list[dict]) -> dict:
    """Returns {disposition, confidence, reasoning}."""
    codes = "\n".join(DISPOSITION_CODES)
    transcript = format_transcript(segments)
    prompt = _DISPOSITION_PROMPT_TEMPLATE.format(codes=codes, transcript=transcript)
    raw = _call_ollama(prompt, _DISPOSITION_SYSTEM)

    disposition = str(raw.get("disposition", "OTHER")).upper().strip()
    if disposition not in DISPOSITION_CODES:
        logger.warning("LLM returned unknown disposition '%s' — defaulting to OTHER", disposition)
        disposition = "OTHER"

    try:
        confidence = max(0.0, min(1.0, float(raw.get("confidence", 0.5))))
    except (TypeError, ValueError):
        confidence = 0.5

    return {
        "disposition": disposition,
        "confidence": round(confidence, 3),
        "reasoning": str(raw.get("reasoning", "")),
    }


# ---------------------------------------------------------------------------
# Coaching moments extraction
# ---------------------------------------------------------------------------

COACHING_CATEGORIES = [
    "greeting", "rapport", "discovery", "value_proposition",
    "objection_handling", "closing", "compliance", "missed_opportunity",
]

_COACHING_SYSTEM = (
    "You are an expert sales coach reviewing a recorded sales call. "
    "Identify specific moments where the agent could improve. Output structured JSON only."
)

_COACHING_PROMPT_TEMPLATE = """Review this sales call transcript and identify 3 to 5 specific coaching moments where the agent could improve.

TRANSCRIPT:
{transcript}

For each coaching moment, provide the approximate start and end timestamps in milliseconds, a category, and a reason explaining the coaching opportunity.

Valid categories: {categories}

Return ONLY valid JSON with this exact structure (no extra text):
{{
  "moments": [
    {{
      "start_ms": 5000,
      "end_ms": 35000,
      "category": "objection_handling",
      "reason": "Agent failed to acknowledge the customer price concern before jumping to justification."
    }}
  ]
}}"""


def _format_transcript_with_timestamps(segments: list[dict], max_words: int = 3000) -> str:
    """Format transcript as 'SPEAKER [M:SS]: text' with timestamps."""
    lines: list[str] = []
    word_count = 0
    for seg in segments:
        start_sec = seg["start_ms"] // 1000
        m, s = divmod(start_sec, 60)
        text = seg["text"].strip()
        words = text.split()
        if word_count + len(words) > max_words:
            lines.append(f"{seg['speaker']} [{m}:{s:02d}]: [...transcript truncated for length...]")
            break
        lines.append(f"{seg['speaker']} [{m}:{s:02d}]: {text}")
        word_count += len(words)
    return "\n".join(lines)


def extract_coaching_moments(segments: list[dict]) -> list[dict]:
    """
    Identify 3-5 coaching moments from transcript segments using the LLM.

    Returns a list of dicts with keys: start_ms, end_ms, category, reason.
    Always returns [] on any error — never raises.
    """
    if not segments:
        return []

    try:
        transcript = _format_transcript_with_timestamps(segments, max_words=3000)
        categories_str = ", ".join(COACHING_CATEGORIES)
        prompt = _COACHING_PROMPT_TEMPLATE.format(
            transcript=transcript,
            categories=categories_str,
        )
        raw = _call_ollama(prompt, _COACHING_SYSTEM)

        moments_raw = raw.get("moments", [])
        if not isinstance(moments_raw, list):
            logger.warning("extract_coaching_moments: LLM returned non-list moments field")
            return []

        result: list[dict] = []
        for item in moments_raw[:10]:  # cap at 10 for safety
            if not isinstance(item, dict):
                continue
            try:
                start_ms = int(item.get("start_ms", 0))
                end_ms = int(item.get("end_ms", 0))
            except (TypeError, ValueError):
                continue

            category = str(item.get("category", "missed_opportunity")).lower().strip()
            if category not in COACHING_CATEGORIES:
                category = "missed_opportunity"

            reason = str(item.get("reason", "")).strip()
            if not reason:
                continue

            result.append({
                "start_ms": start_ms,
                "end_ms": end_ms,
                "category": category,
                "reason": reason,
            })

        return result

    except Exception as exc:
        logger.warning("extract_coaching_moments failed for call — returning []: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Objection extraction
# ---------------------------------------------------------------------------

OBJECTION_TYPES = ["PRICE", "TIMING", "AUTHORITY", "NEED", "COMPETITOR", "OTHER"]

_OBJECTION_SYSTEM = (
    "You are a sales analyst identifying customer objections in call transcripts. "
    "Output structured JSON only."
)

_OBJECTION_PROMPT_TEMPLATE = """Review this sales call transcript and identify all customer objections raised.

TRANSCRIPT:
{transcript}

For each objection, provide the timestamp in milliseconds, the objection type, an exact or near-exact quote from the customer, and whether the agent successfully resolved it.

Valid objection_types: {types}

Return ONLY valid JSON with this exact structure (no extra text):
{{
  "objections": [
    {{
      "timestamp_ms": 45000,
      "objection_type": "PRICE",
      "quote": "That seems quite expensive for what we are getting.",
      "resolved": true
    }}
  ]
}}"""


def extract_objections(segments: list[dict]) -> list[dict]:
    """
    Extract customer objections from transcript segments using the LLM.

    Returns a list of dicts with keys: timestamp_ms, objection_type, quote, resolved.
    Always returns [] on any error — never raises.
    """
    if not segments:
        return []

    try:
        transcript = _format_transcript_with_timestamps(segments, max_words=3000)
        types_str = ", ".join(OBJECTION_TYPES)
        prompt = _OBJECTION_PROMPT_TEMPLATE.format(
            transcript=transcript,
            types=types_str,
        )
        raw = _call_ollama(prompt, _OBJECTION_SYSTEM)

        objections_raw = raw.get("objections", [])
        if not isinstance(objections_raw, list):
            logger.warning("extract_objections: LLM returned non-list objections field")
            return []

        result: list[dict] = []
        for item in objections_raw[:20]:  # cap at 20 for safety
            if not isinstance(item, dict):
                continue
            try:
                timestamp_ms = int(item.get("timestamp_ms", 0))
            except (TypeError, ValueError):
                timestamp_ms = 0

            objection_type = str(item.get("objection_type", "OTHER")).upper().strip()
            if objection_type not in OBJECTION_TYPES:
                objection_type = "OTHER"

            quote = str(item.get("quote", "")).strip()
            if not quote:
                continue

            resolved_raw = item.get("resolved", False)
            resolved = bool(resolved_raw) if isinstance(resolved_raw, bool) else str(resolved_raw).lower() == "true"

            result.append({
                "timestamp_ms": timestamp_ms,
                "objection_type": objection_type,
                "quote": quote,
                "resolved": resolved,
            })

        return result

    except Exception as exc:
        logger.warning("extract_objections failed for call — returning []: %s", exc)
        return []

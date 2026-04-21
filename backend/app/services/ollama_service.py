"""
LLM service for sales quality scoring, summarisation, sentiment, and disposition.

Uses Claude API when CLAUDE_API_KEY is set (higher accuracy, faster).
Falls back to Ollama (local) otherwise.

All functions are synchronous — intended for Celery tasks.
"""
import json
import logging
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
# Transcript formatters
# ---------------------------------------------------------------------------

def format_transcript(segments: list[dict], max_words: int = 2000) -> str:
    lines: list[str] = []
    word_count = 0
    for seg in segments:
        start_sec = seg["start_ms"] // 1000
        m, s = divmod(start_sec, 60)
        text = seg["text"].strip()
        words = text.split()
        if word_count + len(words) > max_words:
            lines.append(f"[{m:02d}:{s:02d} {seg['speaker']}] [...transcript truncated...]")
            break
        lines.append(f"[{m:02d}:{s:02d} {seg['speaker']}] {text}")
        word_count += len(words)
    return "\n".join(lines)


def _format_transcript_with_timestamps(segments: list[dict], max_words: int = 2000) -> str:
    lines: list[str] = []
    word_count = 0
    for seg in segments:
        start_sec = seg["start_ms"] // 1000
        m, s = divmod(start_sec, 60)
        text = seg["text"].strip()
        words = text.split()
        if word_count + len(words) > max_words:
            lines.append(f"{seg['speaker']} [{m}:{s:02d}]: [...truncated...]")
            break
        lines.append(f"{seg['speaker']} [{m}:{s:02d}]: {text}")
        word_count += len(words)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON extraction
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


# ---------------------------------------------------------------------------
# LLM backends
# ---------------------------------------------------------------------------

def _call_claude(prompt: str, system: str, max_tokens: int = 1024) -> dict:
    headers = {
        "x-api-key": settings.claude_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": settings.claude_model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
        resp.raise_for_status()
    content = resp.json()["content"][0]["text"]
    return _extract_json(content)


def _call_ollama(prompt: str, system: str, max_retries: int = 3, num_predict: int = 1000) -> dict:
    payload = {
        "model": settings.ollama_default_model,
        "prompt": prompt,
        "system": system,
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": num_predict, "seed": 42},
    }
    last_exc: Exception = RuntimeError("No attempts made")
    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=float(settings.ollama_timeout_seconds)) as client:
                resp = client.post(f"{settings.ollama_url}/api/generate", json=payload)
                resp.raise_for_status()
            return _extract_json(resp.json().get("response", ""))
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            last_exc = exc
            wait = 15 * (attempt + 1)
            logger.warning("Ollama error (attempt %d/%d): %s — retrying in %ds", attempt + 1, max_retries, exc, wait)
            time.sleep(wait)
        except ValueError as exc:
            last_exc = exc
            logger.warning("JSON parse failed (attempt %d/%d): %s", attempt + 1, max_retries, exc)
            if attempt < max_retries - 1:
                time.sleep(5)
    raise RuntimeError(f"Ollama failed after {max_retries} attempts: {last_exc}")


def _call_llm(prompt: str, system: str, max_tokens: int = 1000) -> dict:
    """Use Claude if API key is configured, otherwise Ollama."""
    if settings.claude_api_key:
        try:
            return _call_claude(prompt, system, max_tokens)
        except Exception as exc:
            logger.warning("Claude API failed, falling back to Ollama: %s", exc)
    return _call_ollama(prompt, system, num_predict=max_tokens)


# ---------------------------------------------------------------------------
# Sales quality scoring
# ---------------------------------------------------------------------------

_SALES_SYSTEM = (
    "You are an expert sales quality analyst. "
    "Evaluate sales call transcripts objectively and output structured JSON only. "
    "Score strictly from 0 to 10 with 10 being perfect and 0 being completely absent. "
    "Be precise — quote exact phrases from the transcript as evidence."
)

_SALES_PROMPT_TEMPLATE = """Analyze this outbound sales call and score the AGENT on 8 dimensions.

SALES SCRIPT RUBRIC (required talking points):
{rubric_text}

TRANSCRIPT:
{transcript}

Score each dimension 0-10 based ONLY on evidence in the transcript. Return ONLY valid JSON:
{{
  "greeting":          {{"score": 0, "justification": "...", "quote": "exact quote or empty string"}},
  "rapport":           {{"score": 0, "justification": "...", "quote": "..."}},
  "discovery":         {{"score": 0, "justification": "...", "quote": "..."}},
  "value_explanation": {{"score": 0, "justification": "...", "quote": "..."}},
  "objection_handling":{{"score": 0, "justification": "...", "quote": "..."}},
  "script_adherence":  {{"score": 0, "justification": "...", "quote": "..."}},
  "closing":           {{"score": 0, "justification": "...", "quote": "..."}},
  "compliance":        {{"score": 0, "justification": "...", "quote": "..."}}
}}"""


def score_sales_quality(segments: list[dict], rubric: dict) -> dict:
    rubric_text = "\n".join(f"- {p}" for p in rubric.get("required_points", ["Cover key product benefits", "Ask for commitment"]))
    transcript = format_transcript(segments)
    prompt = _SALES_PROMPT_TEMPLATE.format(rubric_text=rubric_text, transcript=transcript)
    raw = _call_llm(prompt, _SALES_SYSTEM)

    scores: dict[str, Any] = {}
    dimension_scores: dict[str, float] = {}
    for dim in SALES_DIMENSIONS:
        dim_data = raw.get(dim, {})
        if not isinstance(dim_data, dict):
            dim_data = {}
        try:
            raw_score = max(0, min(10, float(dim_data.get("score", 5))))
        except (TypeError, ValueError):
            raw_score = 5.0
        scores[dim] = {
            "score": raw_score,
            "justification": str(dim_data.get("justification", "")),
            "quote": str(dim_data.get("quote", "")),
        }
        dimension_scores[dim] = round(raw_score * 10, 1)

    composite = sum(dimension_scores[d] * SALES_WEIGHTS[d] for d in SALES_DIMENSIONS)
    return {"scores": scores, "dimension_scores": dimension_scores, "composite": round(composite, 1)}


# ---------------------------------------------------------------------------
# Call summary
# ---------------------------------------------------------------------------

_SUMMARY_SYSTEM = (
    "You are a senior sales manager reviewing a call recording. "
    "Provide concise, actionable insights. Output JSON only."
)

_SUMMARY_PROMPT_TEMPLATE = """Analyze this sales call and generate a structured summary.

TRANSCRIPT:
{transcript}

Return ONLY valid JSON:
{{
  "executive_summary": "3-4 sentence summary of the call outcome and key highlights",
  "key_moments": ["moment 1", "moment 2", "moment 3"],
  "coaching_suggestions": ["actionable suggestion 1", "suggestion 2", "suggestion 3"]
}}"""


def generate_summary(segments: list[dict]) -> dict:
    transcript = format_transcript(segments)
    raw = _call_llm(_SUMMARY_PROMPT_TEMPLATE.format(transcript=transcript), _SUMMARY_SYSTEM)
    return {
        "executive_summary": str(raw.get("executive_summary", "Summary not available.")),
        "key_moments": [str(m) for m in raw.get("key_moments", [])[:10]],
        "coaching_suggestions": [str(s) for s in raw.get("coaching_suggestions", [])[:10]],
    }


# ---------------------------------------------------------------------------
# Disposition classification
# ---------------------------------------------------------------------------

_DISPOSITION_SYSTEM = (
    "You are a sales operations analyst. Classify call outcomes. Output JSON only."
)

_DISPOSITION_PROMPT_TEMPLATE = """Classify this sales call into exactly ONE of these 18 disposition codes:

{codes}

TRANSCRIPT:
{transcript}

Return ONLY valid JSON:
{{"disposition": "ONE_CODE", "confidence": 0.95, "reasoning": "one sentence"}}"""


def classify_disposition(segments: list[dict]) -> dict:
    codes = "\n".join(DISPOSITION_CODES)
    transcript = format_transcript(segments)
    raw = _call_llm(_DISPOSITION_PROMPT_TEMPLATE.format(codes=codes, transcript=transcript), _DISPOSITION_SYSTEM)

    disposition = str(raw.get("disposition", "OTHER")).upper().strip()
    if disposition not in DISPOSITION_CODES:
        logger.warning("LLM returned unknown disposition '%s' — defaulting to OTHER", disposition)
        disposition = "OTHER"
    try:
        confidence = max(0.0, min(1.0, float(raw.get("confidence", 0.5))))
    except (TypeError, ValueError):
        confidence = 0.5
    return {"disposition": disposition, "confidence": round(confidence, 3), "reasoning": str(raw.get("reasoning", ""))}


# ---------------------------------------------------------------------------
# Sentiment timeline
# ---------------------------------------------------------------------------

_SENTIMENT_SYSTEM = (
    "You are a customer sentiment analyst. Analyze the CUSTOMER's emotional state during a sales call. "
    "Output JSON only."
)

_SENTIMENT_PROMPT_TEMPLATE = """Analyze the CUSTOMER's sentiment at 5 key phases of this sales call.
Use the timestamps in the transcript to estimate phase boundaries.

TRANSCRIPT:
{transcript}

Return ONLY valid JSON with exactly 5 phases:
{{
  "phases": [
    {{"phase": "Opening", "start_ms": 0, "end_ms": 60000, "sentiment": "neutral", "score": 0.5, "evidence": "brief reason"}},
    {{"phase": "Discovery", "start_ms": 60000, "end_ms": 180000, "sentiment": "positive", "score": 0.7, "evidence": "..."}},
    {{"phase": "Pitch", "start_ms": 180000, "end_ms": 300000, "sentiment": "neutral", "score": 0.5, "evidence": "..."}},
    {{"phase": "Objection", "start_ms": 300000, "end_ms": 420000, "sentiment": "negative", "score": 0.3, "evidence": "..."}},
    {{"phase": "Closing", "start_ms": 420000, "end_ms": 600000, "sentiment": "neutral", "score": 0.5, "evidence": "..."}}
  ]
}}
Rules: sentiment must be "positive", "neutral", or "negative". score: 0.0=very negative, 1.0=very positive."""


def analyze_sentiment_timeline(segments: list[dict]) -> list[dict]:
    """Returns list of sentiment phases. Returns [] on any error."""
    if not segments:
        return []
    try:
        transcript = _format_transcript_with_timestamps(segments, max_words=2000)
        raw = _call_llm(_SENTIMENT_PROMPT_TEMPLATE.format(transcript=transcript), _SENTIMENT_SYSTEM)

        phases = raw.get("phases", [])
        if not isinstance(phases, list):
            return []

        result: list[dict] = []
        for p in phases[:10]:
            if not isinstance(p, dict):
                continue
            sentiment = str(p.get("sentiment", "neutral")).lower()
            if sentiment not in ("positive", "neutral", "negative"):
                sentiment = "neutral"
            try:
                score = max(0.0, min(1.0, float(p.get("score", 0.5))))
                start_ms = int(p.get("start_ms", 0))
                end_ms = int(p.get("end_ms", 0))
            except (TypeError, ValueError):
                continue
            result.append({
                "phase": str(p.get("phase", "Unknown")),
                "start_ms": start_ms,
                "end_ms": end_ms,
                "sentiment": sentiment,
                "score": round(score, 3),
                "evidence": str(p.get("evidence", "")),
            })
        return result
    except Exception as exc:
        logger.warning("analyze_sentiment_timeline failed — returning []: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Coaching moments extraction
# ---------------------------------------------------------------------------

COACHING_CATEGORIES = [
    "greeting", "rapport", "discovery", "value_proposition",
    "objection_handling", "closing", "compliance", "missed_opportunity",
]

_COACHING_SYSTEM = (
    "You are an expert sales coach. Identify where the agent could improve. Output JSON only."
)

_COACHING_PROMPT_TEMPLATE = """Identify 3 to 5 specific coaching moments in this sales call.

TRANSCRIPT:
{transcript}

Valid categories: {categories}

Return ONLY valid JSON:
{{
  "moments": [
    {{"start_ms": 5000, "end_ms": 35000, "category": "objection_handling", "reason": "Agent jumped to price before acknowledging the concern."}}
  ]
}}"""


def extract_coaching_moments(segments: list[dict]) -> list[dict]:
    if not segments:
        return []
    try:
        transcript = _format_transcript_with_timestamps(segments, max_words=2000)
        raw = _call_llm(
            _COACHING_PROMPT_TEMPLATE.format(transcript=transcript, categories=", ".join(COACHING_CATEGORIES)),
            _COACHING_SYSTEM,
        )
        result: list[dict] = []
        for item in (raw.get("moments", []) or [])[:10]:
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
            result.append({"start_ms": start_ms, "end_ms": end_ms, "category": category, "reason": reason})
        return result
    except Exception as exc:
        logger.warning("extract_coaching_moments failed — returning []: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Objection extraction
# ---------------------------------------------------------------------------

OBJECTION_TYPES = ["PRICE", "TIMING", "AUTHORITY", "NEED", "COMPETITOR", "OTHER"]

_OBJECTION_SYSTEM = "You are a sales analyst identifying customer objections. Output JSON only."

_OBJECTION_PROMPT_TEMPLATE = """Identify all customer objections in this sales call.

TRANSCRIPT:
{transcript}

Valid objection_types: {types}

Return ONLY valid JSON:
{{
  "objections": [
    {{"timestamp_ms": 45000, "objection_type": "PRICE", "quote": "That seems quite expensive.", "resolved": true}}
  ]
}}"""


def extract_objections(segments: list[dict]) -> list[dict]:
    if not segments:
        return []
    try:
        transcript = _format_transcript_with_timestamps(segments, max_words=2000)
        raw = _call_llm(
            _OBJECTION_PROMPT_TEMPLATE.format(transcript=transcript, types=", ".join(OBJECTION_TYPES)),
            _OBJECTION_SYSTEM,
        )
        result: list[dict] = []
        for item in (raw.get("objections", []) or [])[:20]:
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
            result.append({"timestamp_ms": timestamp_ms, "objection_type": objection_type, "quote": quote, "resolved": resolved})
        return result
    except Exception as exc:
        logger.warning("extract_objections failed — returning []: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Combined analysis — single LLM call for all outputs (6x faster on CPU)
# ---------------------------------------------------------------------------

_COMBINED_SYSTEM = (
    "You are an expert sales call analyst. Analyze sales call transcripts and return "
    "all analysis as a single structured JSON object. Output valid JSON only — no prose, "
    "no markdown, no explanation outside the JSON."
)

_COMBINED_PROMPT_TEMPLATE = """Analyze this outbound sales call and return ONE JSON object covering all analysis.

SALES RUBRIC (required talking points):
{rubric_text}

DISPOSITION CODES (pick exactly one):
{disposition_codes}

TRANSCRIPT:
{transcript}

Return ONLY this JSON (fill in all values based on the transcript):
{{
  "sales_scores": {{
    "greeting":           {{"score": 5, "justification": "reason", "quote": ""}},
    "rapport":            {{"score": 5, "justification": "reason", "quote": ""}},
    "discovery":          {{"score": 5, "justification": "reason", "quote": ""}},
    "value_explanation":  {{"score": 5, "justification": "reason", "quote": ""}},
    "objection_handling": {{"score": 5, "justification": "reason", "quote": ""}},
    "script_adherence":   {{"score": 5, "justification": "reason", "quote": ""}},
    "closing":            {{"score": 5, "justification": "reason", "quote": ""}},
    "compliance":         {{"score": 5, "justification": "reason", "quote": ""}}
  }},
  "summary": {{
    "executive_summary": "3-4 sentence summary of call outcome",
    "key_moments": ["moment 1", "moment 2", "moment 3"],
    "coaching_suggestions": ["suggestion 1", "suggestion 2", "suggestion 3"]
  }},
  "disposition": {{"disposition": "ONE_CODE", "confidence": 0.85, "reasoning": "one sentence"}},
  "coaching_moments": [
    {{"start_ms": 0, "end_ms": 30000, "category": "greeting", "reason": "reason for coaching"}}
  ],
  "objections": [
    {{"timestamp_ms": 0, "objection_type": "PRICE", "quote": "exact quote", "resolved": false}}
  ],
  "sentiment_timeline": [
    {{"phase": "Opening",   "start_ms": 0,      "end_ms": 60000,  "sentiment": "neutral",  "score": 0.5, "evidence": "reason"}},
    {{"phase": "Discovery", "start_ms": 60000,  "end_ms": 180000, "sentiment": "neutral",  "score": 0.5, "evidence": "reason"}},
    {{"phase": "Pitch",     "start_ms": 180000, "end_ms": 300000, "sentiment": "neutral",  "score": 0.5, "evidence": "reason"}},
    {{"phase": "Objection", "start_ms": 300000, "end_ms": 420000, "sentiment": "neutral",  "score": 0.5, "evidence": "reason"}},
    {{"phase": "Closing",   "start_ms": 420000, "end_ms": 999999, "sentiment": "neutral",  "score": 0.5, "evidence": "reason"}}
  ]
}}"""


def analyze_call_complete(segments: list[dict], rubric: dict) -> dict:
    """
    Single LLM call returning all analysis.
    Replaces 6 separate calls — ~6x faster on CPU inference.
    """
    rubric_text = "\n".join(
        f"- {p}" for p in rubric.get("required_points", [
            "Introduce yourself and company",
            "Ask discovery questions",
            "Explain product benefits",
            "Handle objections",
            "Ask for a next step or commitment",
        ])
    )
    transcript = format_transcript(segments, max_words=1200)
    prompt = _COMBINED_PROMPT_TEMPLATE.format(
        rubric_text=rubric_text,
        disposition_codes="\n".join(DISPOSITION_CODES),
        transcript=transcript,
    )

    raw = _call_llm(prompt, _COMBINED_SYSTEM, max_tokens=1500)

    # --- Sales scores ---
    raw_scores = raw.get("sales_scores", {})
    scores: dict[str, Any] = {}
    dimension_scores: dict[str, float] = {}
    for dim in SALES_DIMENSIONS:
        dim_data = raw_scores.get(dim, {})
        if not isinstance(dim_data, dict):
            dim_data = {}
        try:
            raw_score = max(0, min(10, float(dim_data.get("score", 5))))
        except (TypeError, ValueError):
            raw_score = 5.0
        scores[dim] = {
            "score": raw_score,
            "justification": str(dim_data.get("justification", "")),
            "quote": str(dim_data.get("quote", "")),
        }
        dimension_scores[dim] = round(raw_score * 10, 1)
    composite = sum(dimension_scores[d] * SALES_WEIGHTS[d] for d in SALES_DIMENSIONS)

    # --- Summary ---
    raw_sum = raw.get("summary", {})
    summary = {
        "executive_summary": str(raw_sum.get("executive_summary", "Summary not available.")),
        "key_moments": [str(m) for m in raw_sum.get("key_moments", [])[:10]],
        "coaching_suggestions": [str(s) for s in raw_sum.get("coaching_suggestions", [])[:10]],
    }

    # --- Disposition ---
    raw_disp = raw.get("disposition", {})
    disp_code = str(raw_disp.get("disposition", "OTHER")).upper().strip()
    if disp_code not in DISPOSITION_CODES:
        disp_code = "OTHER"
    try:
        confidence = max(0.0, min(1.0, float(raw_disp.get("confidence", 0.5))))
    except (TypeError, ValueError):
        confidence = 0.5
    disposition = {
        "disposition": disp_code,
        "confidence": round(confidence, 3),
        "reasoning": str(raw_disp.get("reasoning", "")),
    }

    # --- Coaching moments ---
    coaching_moments: list[dict] = []
    for item in (raw.get("coaching_moments", []) or [])[:10]:
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
        if reason:
            coaching_moments.append({"start_ms": start_ms, "end_ms": end_ms, "category": category, "reason": reason})

    # --- Objections ---
    objections: list[dict] = []
    for item in (raw.get("objections", []) or [])[:20]:
        if not isinstance(item, dict):
            continue
        try:
            timestamp_ms = int(item.get("timestamp_ms", 0))
        except (TypeError, ValueError):
            timestamp_ms = 0
        obj_type = str(item.get("objection_type", "OTHER")).upper().strip()
        if obj_type not in OBJECTION_TYPES:
            obj_type = "OTHER"
        quote = str(item.get("quote", "")).strip()
        if not quote:
            continue
        resolved_raw = item.get("resolved", False)
        resolved = bool(resolved_raw) if isinstance(resolved_raw, bool) else str(resolved_raw).lower() == "true"
        objections.append({"timestamp_ms": timestamp_ms, "objection_type": obj_type, "quote": quote, "resolved": resolved})

    # --- Sentiment timeline ---
    sentiment_timeline: list[dict] = []
    for p in (raw.get("sentiment_timeline", []) or [])[:10]:
        if not isinstance(p, dict):
            continue
        sentiment = str(p.get("sentiment", "neutral")).lower()
        if sentiment not in ("positive", "neutral", "negative"):
            sentiment = "neutral"
        try:
            score = max(0.0, min(1.0, float(p.get("score", 0.5))))
            start_ms = int(p.get("start_ms", 0))
            end_ms = int(p.get("end_ms", 0))
        except (TypeError, ValueError):
            continue
        sentiment_timeline.append({
            "phase": str(p.get("phase", "Unknown")),
            "start_ms": start_ms,
            "end_ms": end_ms,
            "sentiment": sentiment,
            "score": round(score, 3),
            "evidence": str(p.get("evidence", "")),
        })

    return {
        "sales": {"scores": scores, "dimension_scores": dimension_scores, "composite": round(composite, 1)},
        "summary": summary,
        "disposition": disposition,
        "coaching_moments": coaching_moments,
        "objections": objections,
        "sentiment_timeline": sentiment_timeline,
    }

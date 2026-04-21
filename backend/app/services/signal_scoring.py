"""
Signal-based sales scoring.

Computes deterministic, explainable scores from transcript structure alone —
no LLM required. Produces the same output schema as the old LLM scorer so
downstream code is unchanged.

Industry rationale: Gong/Chorus score behavioral signals (talk ratio,
question rate, monologue length, response latency) rather than asking an LLM
to guess scores. Results are consistent, instant, and defensible to agents.
"""
import re
from typing import Any

SALES_WEIGHTS: dict[str, float] = {
    "greeting":           0.10,
    "rapport":            0.10,
    "discovery":          0.15,
    "value_explanation":  0.20,
    "objection_handling": 0.20,
    "script_adherence":   0.10,
    "closing":            0.10,
    "compliance":         0.05,
}

_GREETING_KW = [
    "hello", "hi", "good morning", "good afternoon", "good evening",
    "my name is", "i'm calling from", "calling from", "this is", "speaking",
]
_CLOSING_KW = [
    "thank you", "thanks", "have a great", "have a good", "take care",
    "goodbye", "bye", "speak soon", "call you back", "follow up",
    "next step", "schedule", "appointment", "send you", "email you",
]
_PROHIBITED = re.compile(
    r"\b(guarantee|promised|definitely will|100 percent sure|no risk|free money)\b",
    re.IGNORECASE,
)


def compute_scores(segments: list[dict], rubric: dict | None = None) -> dict:
    """
    Returns {"scores": ..., "dimension_scores": ..., "composite": float}
    matching the exact schema previously produced by the LLM scorer.
    """
    agent_segs = [s for s in segments if s.get("speaker") == "AGENT"]
    customer_segs = [s for s in segments if s.get("speaker") == "CUSTOMER"]

    if not agent_segs:
        return _empty_scores("No agent speech detected in transcript")

    total_ms = max((s["end_ms"] for s in segments), default=1)
    agent_ms = sum(s["end_ms"] - s["start_ms"] for s in agent_segs)
    customer_ms = sum(s["end_ms"] - s["start_ms"] for s in customer_segs)
    agent_text = " ".join(s["text"] for s in agent_segs)
    agent_minutes = max(agent_ms / 60_000, 0.1)

    scores: dict[str, Any] = {}
    dimension_scores: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Greeting — agent speaks within first 8 s with a greeting keyword
    # ------------------------------------------------------------------
    first_seg_ms = min((s["start_ms"] for s in segments), default=0)
    first_agent = next((s for s in segments if s.get("speaker") == "AGENT"), None)
    first_agent_ms = first_agent["start_ms"] if first_agent else 999_999
    first_agent_text = first_agent["text"].lower() if first_agent else ""

    speaks_early = first_agent_ms <= first_seg_ms + 8_000
    has_greeting = any(kw in first_agent_text for kw in _GREETING_KW)

    if speaks_early and has_greeting:
        g = (9.0, "Agent greeted promptly with proper introduction")
    elif speaks_early or has_greeting:
        g = (6.0, "Partial greeting — either delayed or missing introduction phrase")
    else:
        g = (3.0, "No clear greeting detected at call start")
    scores["greeting"] = {"score": g[0], "justification": g[1],
                          "quote": (first_agent["text"][:100] if first_agent else "")}
    dimension_scores["greeting"] = round(g[0] * 10, 1)

    # ------------------------------------------------------------------
    # Rapport — talk balance (agent 45-70 % is ideal for outbound sales)
    # ------------------------------------------------------------------
    talk_ratio = agent_ms / max(agent_ms + customer_ms, 1)
    if 0.45 <= talk_ratio <= 0.70:
        r = (9.0, f"Good talk balance — agent {talk_ratio:.0%}, customer {1 - talk_ratio:.0%}")
    elif 0.35 <= talk_ratio <= 0.80:
        r = (6.0, f"Acceptable talk ratio — agent {talk_ratio:.0%} (ideal 45-70 %)")
    elif talk_ratio > 0.80:
        r = (3.0, f"Agent dominated the call ({talk_ratio:.0%}) — customer had little space to speak")
    else:
        r = (4.0, f"Agent spoke too little ({talk_ratio:.0%}) — customer led the conversation")
    scores["rapport"] = {"score": r[0], "justification": r[1], "quote": ""}
    dimension_scores["rapport"] = round(r[0] * 10, 1)

    # ------------------------------------------------------------------
    # Discovery — question rate (questions per minute by agent)
    # ------------------------------------------------------------------
    q_count = agent_text.count("?")
    q_per_min = q_count / agent_minutes
    if q_per_min >= 3.0:
        d = (9.0, f"Strong discovery — {q_count} questions ({q_per_min:.1f}/min)")
    elif q_per_min >= 1.5:
        d = (7.0, f"Moderate discovery — {q_count} questions ({q_per_min:.1f}/min)")
    elif q_per_min >= 0.5:
        d = (4.5, f"Weak discovery — only {q_count} questions across the call")
    else:
        d = (2.0, "No discovery questions detected — agent did not probe customer needs")
    scores["discovery"] = {"score": d[0], "justification": d[1], "quote": ""}
    dimension_scores["discovery"] = round(d[0] * 10, 1)

    # ------------------------------------------------------------------
    # Value explanation — agent sustained speech in the call middle (25-75 %)
    # ------------------------------------------------------------------
    mid_start = total_ms * 0.25
    mid_end = total_ms * 0.75
    mid_agent_ms = sum(
        s["end_ms"] - s["start_ms"] for s in agent_segs
        if s["start_ms"] >= mid_start and s["end_ms"] <= mid_end
    )
    mid_ratio = mid_agent_ms / max(total_ms * 0.5, 1)
    if mid_ratio >= 0.35:
        v = (9.0, "Agent dedicated significant mid-call time to value explanation")
    elif mid_ratio >= 0.20:
        v = (6.5, "Moderate value explanation in core call section")
    else:
        v = (3.5, "Limited value explanation — agent may not have pitched clearly")
    scores["value_explanation"] = {"score": v[0], "justification": v[1], "quote": ""}
    dimension_scores["value_explanation"] = round(v[0] * 10, 1)

    # ------------------------------------------------------------------
    # Objection handling — agent responds within 10 s of late customer turns
    # ------------------------------------------------------------------
    late_cust = [s for s in customer_segs if s["start_ms"] > total_ms * 0.40]
    if not late_cust:
        o = (5.0, "No customer turns in second half of call to evaluate")
    else:
        responded = sum(
            1 for cs in late_cust
            if any(
                s["speaker"] == "AGENT" and cs["end_ms"] <= s["start_ms"] <= cs["end_ms"] + 10_000
                for s in agent_segs
            )
        )
        rate = responded / len(late_cust)
        if rate >= 0.8:
            o = (8.5, f"Agent responded to {responded}/{len(late_cust)} late customer turns")
        elif rate >= 0.5:
            o = (5.5, f"Partial responses — {responded}/{len(late_cust)} customer turns addressed")
        else:
            o = (2.5, f"Poor responsiveness — only {responded}/{len(late_cust)} turns followed up")
    scores["objection_handling"] = {"score": o[0], "justification": o[1], "quote": ""}
    dimension_scores["objection_handling"] = round(o[0] * 10, 1)

    # ------------------------------------------------------------------
    # Script adherence — keyword match against rubric required points
    # ------------------------------------------------------------------
    if rubric and rubric.get("required_points"):
        pts = rubric["required_points"]
        matched = sum(
            1 for pt in pts
            if any(w.lower() in agent_text.lower() for w in pt.split()[:3])
        )
        sa_score = round(2.0 + (matched / len(pts)) * 8.0, 1)
        sa_just = f"Matched {matched}/{len(pts)} required script points"
    else:
        has_intro = any(kw in agent_text.lower() for kw in ["my name", "calling from", "i'm", "i am"])
        has_benefit = any(kw in agent_text.lower() for kw in ["benefit", "help you", "save", "improve", "offer", "solution"])
        has_close_kw = any(kw in agent_text.lower() for kw in _CLOSING_KW)
        sa_score = round(has_intro * 3.0 + has_benefit * 4.0 + has_close_kw * 3.0, 1)
        sa_just = (
            f"Structure: intro={'✓' if has_intro else '✗'}, "
            f"benefit={'✓' if has_benefit else '✗'}, "
            f"close={'✓' if has_close_kw else '✗'}"
        )
    scores["script_adherence"] = {"score": sa_score, "justification": sa_just, "quote": ""}
    dimension_scores["script_adherence"] = round(sa_score * 10, 1)

    # ------------------------------------------------------------------
    # Closing — closing keywords in last agent utterance + agent speaks last
    # ------------------------------------------------------------------
    last_agent = agent_segs[-1] if agent_segs else None
    last_speaker = segments[-1].get("speaker") if segments else None
    last_agent_text = last_agent["text"].lower() if last_agent else ""
    has_close = any(kw in last_agent_text for kw in _CLOSING_KW)
    agent_spoke_last = last_speaker == "AGENT"
    if has_close and agent_spoke_last:
        c = (9.0, "Agent closed with proper farewell and held the last word")
    elif has_close or agent_spoke_last:
        c = (6.5, "Partial closing — either proper sign-off or controlled close, not both")
    else:
        c = (3.0, "No clear closing — call may have ended abruptly without sign-off")
    scores["closing"] = {"score": c[0], "justification": c[1],
                         "quote": (last_agent["text"][:100] if last_agent else "")}
    dimension_scores["closing"] = round(c[0] * 10, 1)

    # ------------------------------------------------------------------
    # Compliance — absence of prohibited guarantee/misleading phrases
    # ------------------------------------------------------------------
    if _PROHIBITED.search(agent_text):
        comp = (2.0, "Compliance issue — prohibited or misleading phrase detected in agent speech")
    else:
        comp = (9.5, "No compliance violations detected")
    scores["compliance"] = {"score": comp[0], "justification": comp[1], "quote": ""}
    dimension_scores["compliance"] = round(comp[0] * 10, 1)

    composite = sum(dimension_scores[d] * SALES_WEIGHTS[d] for d in SALES_WEIGHTS)
    return {"scores": scores, "dimension_scores": dimension_scores, "composite": round(composite, 1)}


def _empty_scores(reason: str) -> dict:
    scores = {d: {"score": 0.0, "justification": reason, "quote": ""} for d in SALES_WEIGHTS}
    dimension_scores = {d: 0.0 for d in SALES_WEIGHTS}
    return {"scores": scores, "dimension_scores": dimension_scores, "composite": 0.0}

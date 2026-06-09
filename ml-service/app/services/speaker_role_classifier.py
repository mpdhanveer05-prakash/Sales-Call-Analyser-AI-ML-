"""
Per-segment semantic speaker-role classification.

Replaces channel-based AGENT/CUSTOMER labeling with semantic roles:
  HUMAN_AGENT, HUMAN_CUSTOMER, AUTO_ATTENDANT, IVR_SYSTEM,
  VOICEMAIL_GREETING, VOICEMAIL_MENU, UNKNOWN

Hybrid pipeline:
  Stage A: regex rules           (deterministic, ~ms, catches automation/intros)
  Stage B: LLM batch refinement  (qwen2.5:14b, semantic context, catches edges)
  Stage C: temporal smoothing    (machine doesn't get interrupted mid-prompt)
  Stage D: call topology         (HUMAN_TO_VOICEMAIL, HUMAN_VIA_AA_TO_HUMAN, …)
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Role taxonomy + downstream category mapping
# ---------------------------------------------------------------------------

ROLE_HUMAN_AGENT = "HUMAN_AGENT"
ROLE_HUMAN_CUSTOMER = "HUMAN_CUSTOMER"
ROLE_AUTO_ATTENDANT = "AUTO_ATTENDANT"
ROLE_IVR = "IVR_SYSTEM"
ROLE_VM_GREETING = "VOICEMAIL_GREETING"
ROLE_VM_MENU = "VOICEMAIL_MENU"
ROLE_UNKNOWN = "UNKNOWN"

VALID_ROLES = {
    ROLE_HUMAN_AGENT, ROLE_HUMAN_CUSTOMER,
    ROLE_AUTO_ATTENDANT, ROLE_IVR,
    ROLE_VM_GREETING, ROLE_VM_MENU,
    ROLE_UNKNOWN,
}
AUTOMATED_ROLES = {ROLE_AUTO_ATTENDANT, ROLE_IVR, ROLE_VM_GREETING, ROLE_VM_MENU}
HUMAN_ROLES = {ROLE_HUMAN_AGENT, ROLE_HUMAN_CUSTOMER}

# Call-topology values
TOPOLOGY_HUMAN_TO_HUMAN = "HUMAN_TO_HUMAN"
TOPOLOGY_HUMAN_TO_VOICEMAIL = "HUMAN_TO_VOICEMAIL"
TOPOLOGY_HUMAN_VIA_AA_TO_HUMAN = "HUMAN_VIA_AUTO_ATTENDANT_TO_HUMAN"
TOPOLOGY_HUMAN_VIA_AA_TO_VOICEMAIL = "HUMAN_VIA_AUTO_ATTENDANT_TO_VOICEMAIL"
TOPOLOGY_HUMAN_VIA_IVR_TO_HUMAN = "HUMAN_VIA_IVR_TO_HUMAN"
TOPOLOGY_ABANDONED = "ABANDONED"
TOPOLOGY_UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Stage A: rule patterns
# ---------------------------------------------------------------------------

_RULES: dict[str, list[re.Pattern]] = {
    ROLE_AUTO_ATTENDANT: [
        re.compile(r"\bpress\s+(?:one|two|three|four|five|six|seven|eight|nine|zero|pound|star|\d)\b", re.I),
        re.compile(r"\bthank\s+you\s+for\s+calling\b", re.I),
        re.compile(r"\bdirectory\s+search\b", re.I),
        re.compile(r"\byour\s+call\s+may\s+be\s+recorded\b", re.I),
        re.compile(r"\btransferring\s+your\s+call\b", re.I),
        re.compile(r"\bplease\s+listen\s+carefully\b", re.I),
        re.compile(r"\bmain\s+menu\b", re.I),
        re.compile(r"\bif\s+you\s+know\s+your\s+party'?s?\s+extension\b", re.I),
        re.compile(r"\bfor\s+(?:sales|support|billing|customer\s+service)\b.*\bpress\b", re.I),
    ],
    ROLE_VM_GREETING: [
        re.compile(r"\bperson\s+you(?:\s+are|'re)\s+trying\s+to\s+reach\b", re.I),
        re.compile(r"\bcurrently\s+(?:unavailable|not\s+available)\b", re.I),
        re.compile(r"\bleave\s+a\s+(?:detailed\s+)?message\b", re.I),
        re.compile(r"\bafter\s+(?:the\s+)?(?:tone|beep)\b", re.I),
        re.compile(r"\bat\s+the\s+(?:tone|beep)\b", re.I),
        re.compile(r"\bvoice\s*mail\b", re.I),
        re.compile(r"\brecord\s+your\s+message\b", re.I),
        re.compile(r"\bwhen\s+you\s+have\s+finished\s+recording\b", re.I),
        re.compile(r"\b(?:has\s+been\s+)?forwarded\s+to\s+voicemail\b", re.I),
    ],
    ROLE_VM_MENU: [
        re.compile(r"\bto\s+replay\b.*\bpress\b", re.I),
        re.compile(r"\bto\s+send\b.*\bpress\b", re.I),
        re.compile(r"\bto\s+(?:re-?\s*record|erase|delete)\b.*\bpress\b", re.I),
        re.compile(r"\bmessage\s+(?:sent|saved|deleted|erased)\b", re.I),
        re.compile(r"\bsent\s+with\s+high\s+importance\b", re.I),
        re.compile(r"\bto\s+continue\s+holding\b", re.I),
    ],
    ROLE_IVR: [
        re.compile(r"\bplease\s+say\b", re.I),
        re.compile(r"\bdid\s+you\s+say\b", re.I),
        re.compile(r"\bi\s+didn'?t\s+understand\b", re.I),
        re.compile(r"\bsay\s+(?:yes|no|main\s+menu)\b", re.I),
        re.compile(r"\bgo\s+ahead\b.*\bspeak\b", re.I),
        re.compile(r"\benter\s+your\s+account\s+number\b", re.I),
    ],
    # Strong human-agent self-introduction phrases (sales agents commonly say these)
    ROLE_HUMAN_AGENT: [
        re.compile(r"\bthis\s+is\s+\w+\b.*\b(?:calling|from|with)\b", re.I),
        re.compile(r"\bcalling\s+from\s+\w+", re.I),
        re.compile(r"\bcalling\s+regarding\b", re.I),
        re.compile(r"\bcalling\s+about\b", re.I),
        re.compile(r"\bi'?m\s+calling\s+(?:from|regarding|about)\b", re.I),
        re.compile(r"\bmy\s+name\s+is\s+\w+", re.I),
    ],
}

# Phrases that look automated-ish but are spoken by humans leaving messages
# These should NOT escalate to VM_GREETING/MENU when the surrounding context is human.
_HUMAN_VM_LEAVE_HINTS = [
    re.compile(r"\bplease\s+(?:call|give)\s+me\s+back\b", re.I),
    re.compile(r"\byou\s+can\s+reach\s+me\s+at\b", re.I),
    re.compile(r"\bI(?:'ll)?\s+(?:call|try)\s+(?:back|again)\b", re.I),
    re.compile(r"\bhave\s+a\s+(?:great|good|beautiful)\s+(?:day|evening)\b", re.I),
]


@dataclass
class SegmentClassification:
    """One classified transcript segment."""
    index: int
    role: str
    confidence: float
    reason: str = ""

    @property
    def is_automated(self) -> bool:
        return self.role in AUTOMATED_ROLES

    @property
    def is_human(self) -> bool:
        return self.role in HUMAN_ROLES


@dataclass
class ClassificationResult:
    """Output of the full classifier pipeline."""
    segments: list[SegmentClassification] = field(default_factory=list)
    call_topology: str = TOPOLOGY_UNKNOWN
    topology_confidence: float = 0.0


# ---------------------------------------------------------------------------
# Stage A: rule scoring
# ---------------------------------------------------------------------------

def _rule_score_one(text: str) -> tuple[str | None, float, str]:
    """Score a single segment against rule patterns. Returns (role, confidence, reason)."""
    if not text or not text.strip():
        return None, 0.0, ""

    role_hits: dict[str, int] = {}
    for role, patterns in _RULES.items():
        for p in patterns:
            if p.search(text):
                role_hits[role] = role_hits.get(role, 0) + 1

    if not role_hits:
        return None, 0.0, ""

    best_role = max(role_hits, key=role_hits.get)
    hit_count = role_hits[best_role]

    # Down-weight VM_GREETING/MENU if human-leaving-voicemail hints are present
    if best_role in (ROLE_VM_GREETING, ROLE_VM_MENU):
        if any(p.search(text) for p in _HUMAN_VM_LEAVE_HINTS):
            return ROLE_HUMAN_AGENT, 0.72, "human leaving voicemail phrase"

    if hit_count >= 2:
        return best_role, 0.96, f"{hit_count} rule matches"
    return best_role, 0.82, "1 rule match"


# ---------------------------------------------------------------------------
# Stage B: LLM refinement (batched)
# ---------------------------------------------------------------------------

_LLM_SYSTEM_PROMPT = """You are an expert at classifying segments of recorded sales phone calls.

For each numbered segment, output the SEMANTIC ROLE of the speaker — what kind of entity is talking, not which phone line. Valid roles:

- HUMAN_AGENT       : Live sales agent making/receiving the call (representing the calling company)
- HUMAN_CUSTOMER    : Live prospect/customer/contact on the other end (the called party speaking)
- AUTO_ATTENDANT    : Company's automated answering system ("Thank you for calling X, press 1 for sales")
- VOICEMAIL_GREETING: Voicemail intro recording ("The person is unavailable, leave a message after the tone")
- VOICEMAIL_MENU    : Voicemail navigation prompts ("To replay press 1", "Message sent")
- IVR_SYSTEM        : Interactive voice response menus, voice recognition prompts
- UNKNOWN           : Cannot determine

CRITICAL RULES:
1. Automated systems use telltale phrases: "press 1", "after the tone", "your call may be recorded", "directory search"
2. A human leaving a voicemail says things like "Hi, this is X, please call back, you can reach me at..." — these are HUMAN_AGENT or HUMAN_CUSTOMER, NOT voicemail greetings
3. Once a speaker is established as automated within a channel, adjacent segments on the same channel are usually automated too
4. The channel index (ch=0 or ch=1) is provided as a hint but is NOT the answer — your job is semantic, not channel-based
5. Sales agents typically self-identify with name + company ("This is John from Acme")
6. Customers/prospects respond with short conversational replies, ask about products, raise objections
7. If a human is leaving a voicemail (i.e. talking on what would normally be the "customer side" but the customer didn't pick up), still label them HUMAN_AGENT — they are the calling sales agent

CALL TOPOLOGY (assign one):
- HUMAN_TO_HUMAN                    : Both sides are humans, real conversation
- HUMAN_TO_VOICEMAIL                : Agent reached voicemail directly and left a message
- HUMAN_VIA_AUTO_ATTENDANT_TO_HUMAN : Agent went through auto-attendant and reached a human
- HUMAN_VIA_AUTO_ATTENDANT_TO_VOICEMAIL : Agent went through auto-attendant and ended up in voicemail
- HUMAN_VIA_IVR_TO_HUMAN            : Agent navigated IVR menus to reach a human
- ABANDONED                         : Call ended before reaching anyone meaningful
- UNKNOWN

Return ONLY valid JSON, no other text."""


_LLM_USER_TEMPLATE = """TRANSCRIPT SEGMENTS:
{segments_block}

PRELIMINARY HINTS (from rule matching — may be wrong):
{hints_block}

Return ONLY this JSON:
{{
  "call_topology": "ONE_OF_TOPOLOGY_VALUES",
  "topology_confidence": 0.95,
  "segments": [
    {{"index": 0, "role": "AUTO_ATTENDANT", "confidence": 0.97, "reason": "press X menu prompt"}},
    {{"index": 1, "role": "HUMAN_AGENT", "confidence": 0.94, "reason": "self-identifies with name and company"}}
  ]
}}"""


def _format_for_llm(
    segments: list[dict], rule_hints: list[SegmentClassification]
) -> tuple[str, str]:
    """Build the LLM user prompt with full segment context."""
    seg_lines = []
    hint_lines = []
    for i, seg in enumerate(segments):
        t = seg["start_ms"] // 1000
        m, sec = divmod(t, 60)
        ch = seg.get("channel", 0)
        text = seg["text"].strip()
        seg_lines.append(f"[idx={i}  t={m}:{sec:02d}  ch={ch}]  {text}")

        h = rule_hints[i]
        if h.role != ROLE_UNKNOWN:
            hint_lines.append(f"idx={i}: rule suggests {h.role} (conf={h.confidence:.2f})")

    if not hint_lines:
        hint_lines.append("(no rule matches)")
    return "\n".join(seg_lines), "\n".join(hint_lines)


def _llm_classify(
    segments: list[dict], rule_hints: list[SegmentClassification]
) -> dict[str, Any]:
    """Call qwen2.5:14b once for the whole transcript. Returns parsed JSON or {} on failure."""
    if not segments:
        return {}

    segments_block, hints_block = _format_for_llm(segments, rule_hints)
    user_prompt = _LLM_USER_TEMPLATE.format(
        segments_block=segments_block,
        hints_block=hints_block,
    )

    ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434")
    model = os.getenv("SPEAKER_ROLE_MODEL", os.getenv("OLLAMA_DEFAULT_MODEL", "qwen2.5:14b-instruct"))
    # Default 90s — if Ollama is busy/blocked beyond that, fall back to rules
    # rather than holding up the whole transcription pipeline.
    timeout = float(os.getenv("SPEAKER_ROLE_TIMEOUT", "90"))

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": model,
                    "system": _LLM_SYSTEM_PROMPT,
                    "prompt": user_prompt,
                    "format": "json",
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": min(4000, 60 * len(segments) + 400),
                        "seed": 42,
                    },
                },
            )
            resp.raise_for_status()
        raw = resp.json().get("response", "{}")
        return json.loads(raw)
    except Exception as exc:
        logger.warning("LLM speaker-role classification failed (%s) — using rule output only", exc)
        return {}


# ---------------------------------------------------------------------------
# Stage C: temporal coherence smoothing
# ---------------------------------------------------------------------------

def _smooth(classifications: list[SegmentClassification]) -> list[SegmentClassification]:
    """Apply coherence rules: isolated misclassifications surrounded by same neighbours
    get flipped to the neighbour role."""
    if len(classifications) < 3:
        return classifications

    smoothed = list(classifications)
    for i in range(1, len(smoothed) - 1):
        prev_role = smoothed[i - 1].role
        next_role = smoothed[i + 1].role
        curr = smoothed[i]

        # Same-role neighbours sandwiching a low-confidence different segment → flip
        if (
            prev_role == next_role
            and prev_role != curr.role
            and curr.confidence < 0.80
        ):
            curr.role = prev_role
            curr.confidence = max(curr.confidence, 0.75)
            curr.reason = f"smoothed (neighbours both {prev_role})"

    return smoothed


# ---------------------------------------------------------------------------
# Stage D: call-topology derivation (LLM is primary; this is a fallback)
# ---------------------------------------------------------------------------

def _derive_topology(classifications: list[SegmentClassification]) -> tuple[str, float]:
    """Derive topology from the sequence of roles when the LLM didn't give one."""
    if not classifications:
        return TOPOLOGY_ABANDONED, 0.6

    roles = [c.role for c in classifications]
    has_aa = ROLE_AUTO_ATTENDANT in roles
    has_ivr = ROLE_IVR in roles
    has_vm = ROLE_VM_GREETING in roles or ROLE_VM_MENU in roles
    has_human_customer = ROLE_HUMAN_CUSTOMER in roles
    has_human_agent = ROLE_HUMAN_AGENT in roles

    if has_vm and has_human_agent and not has_human_customer:
        if has_aa:
            return TOPOLOGY_HUMAN_VIA_AA_TO_VOICEMAIL, 0.85
        return TOPOLOGY_HUMAN_TO_VOICEMAIL, 0.88
    if has_aa and has_human_agent and has_human_customer:
        return TOPOLOGY_HUMAN_VIA_AA_TO_HUMAN, 0.82
    if has_ivr and has_human_agent and has_human_customer:
        return TOPOLOGY_HUMAN_VIA_IVR_TO_HUMAN, 0.82
    if has_human_agent and has_human_customer and not (has_aa or has_ivr or has_vm):
        return TOPOLOGY_HUMAN_TO_HUMAN, 0.90
    if not has_human_customer and not has_human_agent:
        return TOPOLOGY_ABANDONED, 0.7
    return TOPOLOGY_UNKNOWN, 0.5


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def _channel_fallback(
    segments: list[dict], rule_results: list[SegmentClassification]
) -> None:
    """When the LLM is unavailable and a segment has no rule match, assign role
    from channel hints: agent channel → HUMAN_AGENT, customer channel → HUMAN_CUSTOMER.
    This is a last-resort fallback; mutates rule_results in place."""
    # Determine which channel is most likely AGENT — channel with majority of
    # HUMAN_AGENT or AUTO_ATTENDANT rule matches (agent intros tend to occur on
    # one channel; auto-attendants on the other in outbound calls).
    ch_agent_score = {0: 0, 1: 0}
    for i, seg in enumerate(segments):
        ch = seg.get("channel", 0)
        if rule_results[i].role == ROLE_HUMAN_AGENT:
            ch_agent_score[ch] += 1
    agent_ch = max(ch_agent_score, key=ch_agent_score.get)

    for i, seg in enumerate(segments):
        if rule_results[i].role != ROLE_UNKNOWN:
            continue
        ch = seg.get("channel", 0)
        if ch == agent_ch:
            rule_results[i].role = ROLE_HUMAN_AGENT
            rule_results[i].confidence = 0.55
            rule_results[i].reason = "channel fallback (no LLM, no rule match)"
        else:
            rule_results[i].role = ROLE_HUMAN_CUSTOMER
            rule_results[i].confidence = 0.55
            rule_results[i].reason = "channel fallback (no LLM, no rule match)"


def classify_segments(segments: list[dict]) -> ClassificationResult:
    """
    Classify each transcript segment with a semantic role.

    Input segments must be dicts with at least: 'text', 'start_ms', 'end_ms'.
    Optional: 'channel' (0 or 1) — passed as a hint to the LLM.

    Returns a ClassificationResult containing per-segment roles plus a global
    call_topology label. Falls back gracefully to rule-only labelling if the
    LLM is unreachable.
    """
    if not segments:
        return ClassificationResult(
            segments=[], call_topology=TOPOLOGY_ABANDONED, topology_confidence=0.6,
        )

    # Stage A: rules
    rule_results: list[SegmentClassification] = []
    for i, seg in enumerate(segments):
        role, conf, reason = _rule_score_one(seg.get("text", ""))
        rule_results.append(SegmentClassification(
            index=i,
            role=role or ROLE_UNKNOWN,
            confidence=conf,
            reason=reason or "no rule match",
        ))

    # Decide whether to call the LLM:
    #   - USE_LLM_SPEAKER_ROLES=false (default): rules + channel fallback only.
    #     Fast, deterministic, no Ollama contention with sales scoring.
    #   - USE_LLM_SPEAKER_ROLES=true: also call LLM to refine ambiguous segments.
    #     Only fires when there's actually something ambiguous to refine.
    llm_enabled = os.getenv("USE_LLM_SPEAKER_ROLES", "false").lower() == "true"
    ambiguous_count = sum(
        1 for r in rule_results
        if r.confidence < 0.85 or r.role == ROLE_UNKNOWN
    )
    use_llm = llm_enabled and ambiguous_count > 0

    final: list[SegmentClassification]
    topology = TOPOLOGY_UNKNOWN
    topology_conf = 0.5

    if use_llm:
        # Stage B: LLM refinement (opt-in via USE_LLM_SPEAKER_ROLES=true)
        llm_raw = _llm_classify(segments, rule_results)
        llm_by_idx: dict[int, dict] = {}
        for s in llm_raw.get("segments", []) or []:
            try:
                llm_by_idx[int(s.get("index", -1))] = s
            except (TypeError, ValueError):
                continue

        topology_str = str(llm_raw.get("call_topology", TOPOLOGY_UNKNOWN)).upper().strip()
        if topology_str in {
            TOPOLOGY_HUMAN_TO_HUMAN, TOPOLOGY_HUMAN_TO_VOICEMAIL,
            TOPOLOGY_HUMAN_VIA_AA_TO_HUMAN, TOPOLOGY_HUMAN_VIA_AA_TO_VOICEMAIL,
            TOPOLOGY_HUMAN_VIA_IVR_TO_HUMAN, TOPOLOGY_ABANDONED, TOPOLOGY_UNKNOWN,
        }:
            topology = topology_str
            try:
                topology_conf = max(0.0, min(1.0, float(llm_raw.get("topology_confidence", 0.5))))
            except (TypeError, ValueError):
                topology_conf = 0.5

        # Ensemble: combine rule + LLM per segment.
        # Rule weight = 0.4 if high-conf else 0.2; LLM weight = 0.6 always when present.
        merged: list[SegmentClassification] = []
        for i, rule_res in enumerate(rule_results):
            llm_seg = llm_by_idx.get(i)
            if llm_seg and str(llm_seg.get("role", "")).upper() in VALID_ROLES:
                llm_role = str(llm_seg["role"]).upper()
                try:
                    llm_conf = max(0.0, min(1.0, float(llm_seg.get("confidence", 0.5))))
                except (TypeError, ValueError):
                    llm_conf = 0.5

                votes: dict[str, float] = {}
                if rule_res.role != ROLE_UNKNOWN:
                    rule_weight = 0.4 if rule_res.confidence >= 0.85 else 0.2
                    votes[rule_res.role] = votes.get(rule_res.role, 0) + rule_weight * rule_res.confidence
                votes[llm_role] = votes.get(llm_role, 0) + 0.6 * llm_conf

                role = max(votes, key=votes.get)
                conf = min(votes[role], 1.0)
                reason = (
                    f"ensemble (rule={rule_res.role}/{rule_res.confidence:.2f}, "
                    f"llm={llm_role}/{llm_conf:.2f})"
                )
                if role == llm_role:
                    reason = str(llm_seg.get("reason") or reason)
            else:
                # No LLM output for this segment — use rule result or UNKNOWN
                role = rule_res.role
                conf = rule_res.confidence
                reason = rule_res.reason

            if conf < 0.60:
                role = ROLE_UNKNOWN

            merged.append(SegmentClassification(
                index=i, role=role, confidence=round(conf, 3), reason=reason,
            ))
        final = merged
    else:
        # No LLM — rules + channel fallback for UNKNOWN segments
        _channel_fallback(segments, rule_results)
        final = rule_results

    # Stage C: temporal smoothing
    final = _smooth(final)

    # Stage D: topology fallback if LLM didn't give one
    if topology == TOPOLOGY_UNKNOWN:
        topology, topology_conf = _derive_topology(final)

    logger.info(
        "Speaker role classification: %d segments, topology=%s (%.2f), "
        "AGENT=%d, CUSTOMER=%d, AUTOMATED=%d, UNKNOWN=%d",
        len(final), topology, topology_conf,
        sum(1 for c in final if c.role == ROLE_HUMAN_AGENT),
        sum(1 for c in final if c.role == ROLE_HUMAN_CUSTOMER),
        sum(1 for c in final if c.role in AUTOMATED_ROLES),
        sum(1 for c in final if c.role == ROLE_UNKNOWN),
    )

    return ClassificationResult(
        segments=final,
        call_topology=topology,
        topology_confidence=round(topology_conf, 3),
    )


# ---------------------------------------------------------------------------
# Helpers exported for downstream services
# ---------------------------------------------------------------------------

def topology_to_disposition(topology: str) -> str | None:
    """Map call topology directly to a disposition code for non-LIVE calls."""
    if topology in (TOPOLOGY_HUMAN_TO_VOICEMAIL, TOPOLOGY_HUMAN_VIA_AA_TO_VOICEMAIL):
        return "VOICEMAIL"
    if topology == TOPOLOGY_ABANDONED:
        return "NO_ANSWER"
    return None  # LIVE call — let the LLM classify

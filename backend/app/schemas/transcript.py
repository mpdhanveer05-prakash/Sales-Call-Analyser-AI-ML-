import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TranscriptSegmentOut(BaseModel):
    id: uuid.UUID
    speaker: str                       # Back-compat: AGENT / CUSTOMER / SYSTEM
    role: str = "UNKNOWN"              # Semantic: HUMAN_AGENT, AUTO_ATTENDANT, etc.
    role_confidence: Optional[float] = None
    start_ms: int
    end_ms: int
    text: str
    confidence: Optional[float]

    model_config = {"from_attributes": True}


class TranscriptOut(BaseModel):
    id: uuid.UUID
    call_id: uuid.UUID
    language: Optional[str]
    duration_seconds: Optional[float]
    segment_count: int
    segments: list[TranscriptSegmentOut]
    created_at: datetime

    model_config = {"from_attributes": True}


class TranscriptStatsOut(BaseModel):
    """Lightweight stats included on the call detail response."""
    segment_count: int
    language: Optional[str]
    duration_seconds: Optional[float]
    agent_segment_count: int
    customer_segment_count: int

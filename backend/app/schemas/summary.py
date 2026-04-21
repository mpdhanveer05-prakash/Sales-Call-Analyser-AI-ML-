import uuid
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel


class SentimentPhase(BaseModel):
    phase: str
    start_ms: int
    end_ms: int
    sentiment: str
    score: float
    evidence: Optional[str] = None


class SummaryOut(BaseModel):
    id: uuid.UUID
    call_id: uuid.UUID
    executive_summary: str
    key_moments: list[str]
    coaching_suggestions: list[str]
    disposition_confidence: Optional[float]
    disposition_reasoning: Optional[str]
    sentiment_timeline: Optional[list[dict]] = None
    created_at: datetime

    model_config = {"from_attributes": True}

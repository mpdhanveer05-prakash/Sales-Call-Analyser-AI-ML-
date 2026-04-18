import uuid
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel


class SpeechScoreOut(BaseModel):
    id: uuid.UUID
    call_id: uuid.UUID
    pronunciation: float
    intonation: float
    fluency: float
    grammar: float
    vocabulary: float
    pace: float
    clarity: float
    filler_score: float
    composite: float
    fillers_per_min: Optional[float]
    pace_wpm: Optional[float]
    talk_ratio: Optional[float]
    created_at: datetime

    model_config = {"from_attributes": True}


class SalesScoreOut(BaseModel):
    id: uuid.UUID
    call_id: uuid.UUID
    greeting: float
    rapport: float
    discovery: float
    value_explanation: float
    objection_handling: float
    script_adherence: float
    closing: float
    compliance: float
    composite: float
    details: Optional[dict[str, Any]]
    created_at: datetime

    model_config = {"from_attributes": True}


class CallScoresOut(BaseModel):
    call_id: uuid.UUID
    speech: Optional[SpeechScoreOut]
    sales: Optional[SalesScoreOut]

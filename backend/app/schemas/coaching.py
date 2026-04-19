from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CoachingClipOut(BaseModel):
    id: UUID
    call_id: UUID
    start_ms: int
    end_ms: int
    category: str
    reason: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ObjectionOut(BaseModel):
    id: UUID
    call_id: UUID
    timestamp_ms: int
    objection_type: str
    quote: str
    resolved: bool
    created_at: datetime

    model_config = {"from_attributes": True}

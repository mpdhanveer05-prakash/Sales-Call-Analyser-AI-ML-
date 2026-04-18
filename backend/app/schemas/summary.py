import uuid
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel


class SummaryOut(BaseModel):
    id: uuid.UUID
    call_id: uuid.UUID
    executive_summary: str
    key_moments: list[str]
    coaching_suggestions: list[str]
    disposition_confidence: Optional[float]
    disposition_reasoning: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}

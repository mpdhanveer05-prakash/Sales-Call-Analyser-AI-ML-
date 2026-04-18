from datetime import date, datetime
from uuid import UUID
from typing import Optional

from pydantic import BaseModel

from app.models.call import CallStatus


class CallUploadResponse(BaseModel):
    id: UUID
    status: CallStatus
    agent_id: UUID
    call_date: date
    original_filename: str
    message: str = "Processing started"


class CallOut(BaseModel):
    id: UUID
    agent_id: UUID
    agent_name: str
    call_date: date
    duration_seconds: Optional[int]
    status: CallStatus
    disposition: Optional[str]
    speech_score: Optional[float]
    sales_score: Optional[float]
    original_filename: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class CallListResponse(BaseModel):
    data: list[CallOut]
    total: int
    page: int
    pages: int

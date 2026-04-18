import uuid
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel


class ScriptRubric(BaseModel):
    required_points: list[str] = []
    prohibited_phrases: list[str] = []
    required_disclosures: list[str] = []


class ScriptCreate(BaseModel):
    name: str
    content: str
    rubric: ScriptRubric = ScriptRubric()
    is_active: bool = True


class ScriptUpdate(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    rubric: Optional[ScriptRubric] = None
    is_active: Optional[bool] = None


class ScriptOut(BaseModel):
    id: uuid.UUID
    name: str
    content: str
    rubric: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

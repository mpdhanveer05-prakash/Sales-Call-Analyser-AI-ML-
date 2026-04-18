from uuid import UUID
from pydantic import BaseModel


class AgentOut(BaseModel):
    id: UUID
    user_id: UUID
    employee_id: str | None
    full_name: str
    email: str
    team_id: UUID | None
    team_name: str | None

    model_config = {"from_attributes": True}


class AgentListResponse(BaseModel):
    data: list[AgentOut]
    total: int
    page: int
    pages: int

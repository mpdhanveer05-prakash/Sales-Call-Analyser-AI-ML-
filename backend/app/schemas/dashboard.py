from pydantic import BaseModel
from typing import Optional
import uuid


class ScoreTrendPoint(BaseModel):
    week: str
    avg_speech: Optional[float]
    avg_sales: Optional[float]
    call_count: int


class AgentScorecardOut(BaseModel):
    agent_id: str
    agent_name: str
    employee_id: Optional[str]
    team_name: Optional[str]
    call_count: int
    avg_speech_score: Optional[float]
    avg_sales_score: Optional[float]
    disposition_breakdown: dict  # disposition -> count
    score_trend: list[ScoreTrendPoint]
    strengths: list[str]  # top 3 dimensions
    weaknesses: list[str]  # bottom 3 dimensions


class LeaderboardEntry(BaseModel):
    rank: int
    agent_id: str
    agent_name: str
    call_count: int
    avg_speech_score: Optional[float]
    avg_sales_score: Optional[float]
    composite_score: Optional[float]


class TeamDashboardOut(BaseModel):
    total_calls: int
    avg_speech_score: Optional[float]
    avg_sales_score: Optional[float]
    conversion_rate: Optional[float]
    disposition_breakdown: dict
    weekly_trend: list[ScoreTrendPoint]
    leaderboard: list[LeaderboardEntry]


class CallAnalyticsOut(BaseModel):
    call_id: uuid.UUID
    agent_seconds: float
    customer_seconds: float
    total_seconds: float
    talk_ratio: float
    silence_count: int
    silence_total_seconds: float
    interruption_count: int


class AgentComparisonOut(BaseModel):
    period_days: int
    agent_a: AgentScorecardOut
    agent_b: AgentScorecardOut


class KeywordAlertOut(BaseModel):
    id: uuid.UUID
    keyword: str
    category: str
    is_active: bool
    created_at: str

    model_config = {"from_attributes": True}

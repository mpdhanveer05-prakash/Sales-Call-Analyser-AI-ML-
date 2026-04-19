from pydantic import BaseModel
from typing import Optional


class SearchRequest(BaseModel):
    query: str
    search_type: str = "keyword"  # "keyword" or "semantic"
    agent_id: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    disposition: Optional[str] = None
    limit: int = 20


class MatchedSegment(BaseModel):
    start_ms: int
    text: str


class SearchResult(BaseModel):
    call_id: str
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    call_date: Optional[str] = None
    disposition: Optional[str] = None
    speech_score: Optional[float] = None
    sales_score: Optional[float] = None
    duration_seconds: Optional[int] = None
    highlights: list[str] = []
    matched_segment: Optional[MatchedSegment] = None
    score: float = 0.0

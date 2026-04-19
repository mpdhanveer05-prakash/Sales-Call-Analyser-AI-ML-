from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.agent import Agent
from app.models.user import User, UserRole
from app.schemas.search import SearchRequest, SearchResult
from app.services import search_service

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=list[SearchResult])
async def search(
    body: SearchRequest,
    current_user: User = Depends(CurrentUser),
    db: AsyncSession = Depends(get_db),
) -> list[SearchResult]:
    """Full-text search across call transcripts.

    Agents are automatically scoped to their own calls.
    Managers and admins may pass an optional agent_id filter.
    """
    effective_agent_id = body.agent_id

    if current_user.role == UserRole.AGENT:
        result = await db.execute(
            select(Agent).where(Agent.user_id == current_user.id)
        )
        own_agent = result.scalar_one_or_none()
        effective_agent_id = str(own_agent.id) if own_agent else "none"

    results = search_service.search_calls(
        query=body.query,
        agent_id=effective_agent_id,
        date_from=body.date_from,
        date_to=body.date_to,
        disposition=body.disposition,
        limit=body.limit,
    )

    return [SearchResult(**r) for r in results]

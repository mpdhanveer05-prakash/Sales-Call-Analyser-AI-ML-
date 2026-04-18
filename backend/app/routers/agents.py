import math
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.agent import Agent
from app.models.user import User
from app.schemas.agent import AgentListResponse, AgentOut

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=AgentListResponse)
async def list_agents(
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=200),
    current_user: User = Depends(CurrentUser),  # type: ignore[misc]
    db: AsyncSession = Depends(get_db),
) -> AgentListResponse:
    total_result = await db.execute(select(func.count()).select_from(Agent))
    total = total_result.scalar_one()

    result = await db.execute(
        select(Agent)
        .options(selectinload(Agent.user), selectinload(Agent.team))
        .order_by(Agent.created_at.asc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    agents = result.scalars().all()

    data = [
        AgentOut(
            id=a.id,
            user_id=a.user_id,
            employee_id=a.employee_id,
            full_name=a.user.full_name if a.user else "Unknown",
            email=a.user.email if a.user else "",
            team_id=a.team_id,
            team_name=a.team.name if a.team else None,
        )
        for a in agents
    ]

    return AgentListResponse(
        data=data,
        total=total,
        page=page,
        pages=math.ceil(total / limit) if total else 0,
    )

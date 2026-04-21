import asyncio
import math
from datetime import date, timedelta
from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.agent import Agent
from app.models.call import Call, CallStatus
from app.models.scores import SalesScore, SpeechScore
from app.models.user import User, UserRole
from app.schemas.agent import AgentListResponse, AgentOut
from app.schemas.dashboard import AgentScorecardOut, AgentComparisonOut, ScoreTrendPoint

router = APIRouter(prefix="/agents", tags=["agents"])


def _round_opt(value: Optional[float], ndigits: int = 1) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), ndigits)


@router.get("", response_model=AgentListResponse)
async def list_agents(
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=200),
    current_user: User = Depends(get_current_user),
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


@router.get("/{agent_id}/scorecard", response_model=AgentScorecardOut)
async def get_agent_scorecard(
    agent_id: UUID,
    period: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentScorecardOut:
    """Return a detailed scorecard for an individual agent.

    Agents may only access their own scorecard.
    Managers and admins may access any agent's scorecard.
    """
    # RBAC: agents may only see their own scorecard
    if current_user.role == UserRole.AGENT:
        own_result = await db.execute(
            select(Agent).where(Agent.user_id == current_user.id)
        )
        own_agent = own_result.scalar_one_or_none()
        if own_agent is None or own_agent.id != agent_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You may only access your own scorecard.",
            )

    # Fetch agent with user + team
    agent_result = await db.execute(
        select(Agent)
        .options(selectinload(Agent.user), selectinload(Agent.team))
        .where(Agent.id == agent_id)
    )
    agent = agent_result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found."
        )

    agent_user = agent.user
    agent_name = agent_user.full_name if agent_user else "Unknown"
    team_name = agent.team.name if agent.team else None

    cutoff: date = date.today() - timedelta(days=period)

    base_filter = and_(
        Call.agent_id == agent_id,
        Call.status == CallStatus.COMPLETED,
        Call.call_date >= cutoff,
    )

    # --- Call count ---
    count_result = await db.execute(
        select(func.count(Call.id)).where(base_filter)
    )
    call_count: int = count_result.scalar_one() or 0

    # --- Avg speech score (composite) ---
    avg_speech_result = await db.execute(
        select(func.avg(SpeechScore.composite))
        .join(Call, SpeechScore.call_id == Call.id)
        .where(base_filter)
    )
    avg_speech_score = _round_opt(avg_speech_result.scalar_one_or_none())

    # --- Avg sales score (composite) ---
    avg_sales_result = await db.execute(
        select(func.avg(SalesScore.composite))
        .join(Call, SalesScore.call_id == Call.id)
        .where(base_filter)
    )
    avg_sales_score = _round_opt(avg_sales_result.scalar_one_or_none())

    # --- Disposition breakdown ---
    disp_result = await db.execute(
        select(Call.disposition, func.count(Call.id))
        .where(base_filter)
        .group_by(Call.disposition)
    )
    disposition_breakdown: dict = {
        (row[0] or "UNKNOWN"): row[1] for row in disp_result.all()
    }

    # --- Weekly trend ---
    week_label = func.to_char(
        func.date_trunc("week", cast(Call.call_date, sa.DateTime)),
        "IYYY-\"W\"IW",
    )
    trend_result = await db.execute(
        select(
            week_label.label("week"),
            func.avg(SpeechScore.composite).label("avg_speech"),
            func.avg(SalesScore.composite).label("avg_sales"),
            func.count(Call.id).label("call_count"),
        )
        .outerjoin(SpeechScore, SpeechScore.call_id == Call.id)
        .outerjoin(SalesScore, SalesScore.call_id == Call.id)
        .where(base_filter)
        .group_by("week")
        .order_by("week")
    )
    score_trend = [
        ScoreTrendPoint(
            week=row.week,
            avg_speech=_round_opt(row.avg_speech),
            avg_sales=_round_opt(row.avg_sales),
            call_count=row.call_count,
        )
        for row in trend_result.all()
    ]

    # --- Speech dimension averages for strengths / weaknesses ---
    speech_dims = [
        "pronunciation",
        "intonation",
        "fluency",
        "grammar",
        "vocabulary",
        "pace",
        "clarity",
        "filler_score",
    ]
    speech_dim_cols = [
        func.avg(getattr(SpeechScore, dim)).label(dim) for dim in speech_dims
    ]
    speech_dim_result = await db.execute(
        select(*speech_dim_cols)
        .join(Call, SpeechScore.call_id == Call.id)
        .where(base_filter)
    )
    speech_dim_row = speech_dim_result.one_or_none()

    # Sales dimension averages
    sales_dims = [
        "greeting",
        "rapport",
        "discovery",
        "value_explanation",
        "objection_handling",
        "script_adherence",
        "closing",
        "compliance",
    ]
    sales_dim_cols = [
        func.avg(getattr(SalesScore, dim)).label(dim) for dim in sales_dims
    ]
    sales_dim_result = await db.execute(
        select(*sales_dim_cols)
        .join(Call, SalesScore.call_id == Call.id)
        .where(base_filter)
    )
    sales_dim_row = sales_dim_result.one_or_none()

    # Build combined dimension map
    dim_scores: dict[str, float] = {}
    if speech_dim_row:
        for dim in speech_dims:
            val = getattr(speech_dim_row, dim, None)
            if val is not None:
                dim_scores[f"speech:{dim}"] = float(val)
    if sales_dim_row:
        for dim in sales_dims:
            val = getattr(sales_dim_row, dim, None)
            if val is not None:
                dim_scores[f"sales:{dim}"] = float(val)

    sorted_dims = sorted(dim_scores.items(), key=lambda x: x[1], reverse=True)
    strengths = [d for d, _ in sorted_dims[:3]]
    weaknesses = [d for d, _ in sorted_dims[-3:] if sorted_dims]
    # Reverse weaknesses so the worst is first
    weaknesses = list(reversed(weaknesses))

    return AgentScorecardOut(
        agent_id=str(agent.id),
        agent_name=agent_name,
        employee_id=agent.employee_id,
        team_name=team_name,
        call_count=call_count,
        avg_speech_score=avg_speech_score,
        avg_sales_score=avg_sales_score,
        disposition_breakdown=disposition_breakdown,
        score_trend=score_trend,
        strengths=strengths,
        weaknesses=weaknesses,
    )


async def _build_scorecard(agent_id: UUID, period: int, db: AsyncSession) -> AgentScorecardOut:
    agent_result = await db.execute(
        select(Agent)
        .options(selectinload(Agent.user), selectinload(Agent.team))
        .where(Agent.id == agent_id)
    )
    agent = agent_result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent {agent_id} not found.")

    cutoff: date = date.today() - timedelta(days=period)
    base_filter = and_(
        Call.agent_id == agent_id,
        Call.status == CallStatus.COMPLETED,
        Call.call_date >= cutoff,
    )

    count_result = await db.execute(select(func.count(Call.id)).where(base_filter))
    call_count: int = count_result.scalar_one() or 0

    avg_speech_result = await db.execute(
        select(func.avg(SpeechScore.composite)).join(Call, SpeechScore.call_id == Call.id).where(base_filter)
    )
    avg_speech_score = _round_opt(avg_speech_result.scalar_one_or_none())

    avg_sales_result = await db.execute(
        select(func.avg(SalesScore.composite)).join(Call, SalesScore.call_id == Call.id).where(base_filter)
    )
    avg_sales_score = _round_opt(avg_sales_result.scalar_one_or_none())

    disp_result = await db.execute(
        select(Call.disposition, func.count(Call.id)).where(base_filter).group_by(Call.disposition)
    )
    disposition_breakdown = {(row[0] or "UNKNOWN"): row[1] for row in disp_result.all()}

    week_label = func.to_char(
        func.date_trunc("week", cast(Call.call_date, sa.DateTime)), "IYYY-\"W\"IW"
    )
    trend_result = await db.execute(
        select(
            week_label.label("week"),
            func.avg(SpeechScore.composite).label("avg_speech"),
            func.avg(SalesScore.composite).label("avg_sales"),
            func.count(Call.id).label("call_count"),
        )
        .outerjoin(SpeechScore, SpeechScore.call_id == Call.id)
        .outerjoin(SalesScore, SalesScore.call_id == Call.id)
        .where(base_filter)
        .group_by("week")
        .order_by("week")
    )
    score_trend = [
        ScoreTrendPoint(week=row.week, avg_speech=_round_opt(row.avg_speech),
                        avg_sales=_round_opt(row.avg_sales), call_count=row.call_count)
        for row in trend_result.all()
    ]

    speech_dims = ["pronunciation", "intonation", "fluency", "grammar", "vocabulary", "pace", "clarity", "filler_score"]
    sales_dims = ["greeting", "rapport", "discovery", "value_explanation", "objection_handling", "script_adherence", "closing", "compliance"]

    speech_dim_result = await db.execute(
        select(*[func.avg(getattr(SpeechScore, d)).label(d) for d in speech_dims])
        .join(Call, SpeechScore.call_id == Call.id).where(base_filter)
    )
    speech_dim_row = speech_dim_result.one_or_none()

    sales_dim_result = await db.execute(
        select(*[func.avg(getattr(SalesScore, d)).label(d) for d in sales_dims])
        .join(Call, SalesScore.call_id == Call.id).where(base_filter)
    )
    sales_dim_row = sales_dim_result.one_or_none()

    dim_scores: dict[str, float] = {}
    if speech_dim_row:
        for d in speech_dims:
            v = getattr(speech_dim_row, d, None)
            if v is not None:
                dim_scores[f"speech:{d}"] = float(v)
    if sales_dim_row:
        for d in sales_dims:
            v = getattr(sales_dim_row, d, None)
            if v is not None:
                dim_scores[f"sales:{d}"] = float(v)

    sorted_dims = sorted(dim_scores.items(), key=lambda x: x[1], reverse=True)
    strengths = [d for d, _ in sorted_dims[:3]]
    weaknesses = list(reversed([d for d, _ in sorted_dims[-3:] if sorted_dims]))

    return AgentScorecardOut(
        agent_id=str(agent.id),
        agent_name=agent.user.full_name if agent.user else "Unknown",
        employee_id=agent.employee_id,
        team_name=agent.team.name if agent.team else None,
        call_count=call_count,
        avg_speech_score=avg_speech_score,
        avg_sales_score=avg_sales_score,
        disposition_breakdown=disposition_breakdown,
        score_trend=score_trend,
        strengths=strengths,
        weaknesses=weaknesses,
    )


@router.get("/compare", response_model=AgentComparisonOut)
async def compare_agents(
    agent_a: UUID = Query(...),
    agent_b: UUID = Query(...),
    period: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentComparisonOut:
    if current_user.role == UserRole.AGENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Managers and admins only")

    scorecard_a, scorecard_b = await asyncio.gather(
        _build_scorecard(agent_a, period, db),
        _build_scorecard(agent_b, period, db),
    )
    return AgentComparisonOut(period_days=period, agent_a=scorecard_a, agent_b=scorecard_b)

"""Team dashboard and leaderboard endpoints."""
import logging
from typing import Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentUser, require_roles
from app.models.agent import Agent
from app.models.call import Call, CallStatus
from app.models.scores import SalesScore, SpeechScore
from app.models.user import User, UserRole
from app.schemas.dashboard import LeaderboardEntry, ScoreTrendPoint, TeamDashboardOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_MANAGER_OR_ADMIN = require_roles(UserRole.ADMIN, UserRole.MANAGER)


def _round_optional(value: Optional[float], ndigits: int = 1) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), ndigits)


# ---------------------------------------------------------------------------
# GET /dashboard/team
# ---------------------------------------------------------------------------


@router.get("/team", response_model=TeamDashboardOut)
async def get_team_dashboard(
    period: int = Query(30, ge=1, le=365),
    current_user: User = Depends(_MANAGER_OR_ADMIN),
    db: AsyncSession = Depends(get_db),
) -> TeamDashboardOut:
    """Return aggregated team-wide metrics for the last ``period`` days."""

    cutoff = sa.func.current_date() - sa.cast(
        sa.literal(f"{period} days"), sa.Interval
    )

    completed_filter = and_(
        Call.status == CallStatus.COMPLETED,
        Call.call_date >= cutoff,
    )

    # --- Total calls ---
    total_result = await db.execute(
        select(func.count(Call.id)).where(completed_filter)
    )
    total_calls: int = total_result.scalar_one() or 0

    # --- Avg speech score (from speech_scores table) ---
    avg_speech_result = await db.execute(
        select(func.avg(SpeechScore.composite))
        .join(Call, SpeechScore.call_id == Call.id)
        .where(completed_filter)
    )
    avg_speech_score = _round_optional(avg_speech_result.scalar_one_or_none())

    # --- Avg sales score (from sales_scores table) ---
    avg_sales_result = await db.execute(
        select(func.avg(SalesScore.composite))
        .join(Call, SalesScore.call_id == Call.id)
        .where(completed_filter)
    )
    avg_sales_score = _round_optional(avg_sales_result.scalar_one_or_none())

    # --- Conversion rate ---
    converted_result = await db.execute(
        select(func.count(Call.id)).where(
            and_(completed_filter, Call.disposition == "CONVERTED")
        )
    )
    converted_count: int = converted_result.scalar_one() or 0
    conversion_rate: Optional[float] = (
        round(converted_count / total_calls, 4) if total_calls > 0 else None
    )

    # --- Disposition breakdown ---
    disp_result = await db.execute(
        select(Call.disposition, func.count(Call.id))
        .where(completed_filter)
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
        .where(completed_filter)
        .group_by("week")
        .order_by("week")
    )
    weekly_trend = [
        ScoreTrendPoint(
            week=row.week,
            avg_speech=_round_optional(row.avg_speech),
            avg_sales=_round_optional(row.avg_sales),
            call_count=row.call_count,
        )
        for row in trend_result.all()
    ]

    # --- Leaderboard ---
    leaderboard = await _build_leaderboard(db, completed_filter, limit=10)

    return TeamDashboardOut(
        total_calls=total_calls,
        avg_speech_score=avg_speech_score,
        avg_sales_score=avg_sales_score,
        conversion_rate=conversion_rate,
        disposition_breakdown=disposition_breakdown,
        weekly_trend=weekly_trend,
        leaderboard=leaderboard,
    )


# ---------------------------------------------------------------------------
# GET /dashboard/leaderboard
# ---------------------------------------------------------------------------


@router.get("/leaderboard", response_model=list[LeaderboardEntry])
async def get_leaderboard(
    period: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(_MANAGER_OR_ADMIN),
    db: AsyncSession = Depends(get_db),
) -> list[LeaderboardEntry]:
    """Return agent leaderboard sorted by composite score."""

    cutoff = sa.func.current_date() - sa.cast(
        sa.literal(f"{period} days"), sa.Interval
    )

    completed_filter = and_(
        Call.status == CallStatus.COMPLETED,
        Call.call_date >= cutoff,
    )

    return await _build_leaderboard(db, completed_filter, limit=limit)


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


async def _build_leaderboard(
    db: AsyncSession,
    completed_filter: sa.sql.elements.ClauseElement,
    limit: int = 10,
) -> list[LeaderboardEntry]:
    """Build a ranked leaderboard from the given call filter."""

    lb_result = await db.execute(
        select(
            Agent.id.label("agent_id"),
            User.full_name.label("agent_name"),
            func.count(Call.id).label("call_count"),
            func.avg(SpeechScore.composite).label("avg_speech"),
            func.avg(SalesScore.composite).label("avg_sales"),
        )
        .join(Call, Call.agent_id == Agent.id)
        .join(User, User.id == Agent.user_id)
        .outerjoin(SpeechScore, SpeechScore.call_id == Call.id)
        .outerjoin(SalesScore, SalesScore.call_id == Call.id)
        .where(completed_filter)
        .group_by(Agent.id, User.full_name)
        .order_by(
            sa.nullslast(
                (
                    (func.avg(SpeechScore.composite) + func.avg(SalesScore.composite))
                    / 2
                ).desc()
            )
        )
        .limit(limit)
    )

    entries: list[LeaderboardEntry] = []
    for rank, row in enumerate(lb_result.all(), start=1):
        avg_speech = _round_optional(row.avg_speech)
        avg_sales = _round_optional(row.avg_sales)

        if avg_speech is not None and avg_sales is not None:
            composite = round((avg_speech + avg_sales) / 2, 1)
        elif avg_speech is not None:
            composite = avg_speech
        elif avg_sales is not None:
            composite = avg_sales
        else:
            composite = None

        entries.append(
            LeaderboardEntry(
                rank=rank,
                agent_id=str(row.agent_id),
                agent_name=row.agent_name,
                call_count=row.call_count,
                avg_speech_score=avg_speech,
                avg_sales_score=avg_sales,
                composite_score=composite,
            )
        )

    return entries

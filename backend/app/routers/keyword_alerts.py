from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.keyword_alert import CallKeywordHit, KeywordAlert
from app.models.user import User, UserRole
from app.schemas.dashboard import KeywordAlertOut

router = APIRouter(prefix="/keyword-alerts", tags=["keyword-alerts"])


class KeywordAlertCreate(BaseModel):
    keyword: str
    category: str = "CUSTOM"

    @field_validator("keyword")
    @classmethod
    def keyword_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("keyword must not be empty")
        if len(v) > 200:
            raise ValueError("keyword must be 200 characters or fewer")
        return v


class KeywordAlertUpdate(BaseModel):
    is_active: Optional[bool] = None
    category: Optional[str] = None


class KeywordAlertListOut(BaseModel):
    data: List[KeywordAlertOut]
    total: int


class CallKeywordHitOut(BaseModel):
    id: UUID
    call_id: UUID
    keyword_alert_id: UUID
    keyword: str
    category: str
    hit_count: int
    sample_quotes: Optional[list] = None
    created_at: str

    model_config = {"from_attributes": True}


@router.get("", response_model=KeywordAlertListOut)
async def list_keyword_alerts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KeywordAlertListOut:
    result = await db.execute(
        select(KeywordAlert).order_by(KeywordAlert.created_at.desc())
    )
    keywords = result.scalars().all()
    return KeywordAlertListOut(
        data=[KeywordAlertOut(
            id=k.id,
            keyword=k.keyword,
            category=k.category,
            is_active=k.is_active,
            created_at=k.created_at.isoformat(),
        ) for k in keywords],
        total=len(keywords),
    )


@router.post("", response_model=KeywordAlertOut, status_code=status.HTTP_201_CREATED)
async def create_keyword_alert(
    body: KeywordAlertCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KeywordAlertOut:
    if current_user.role == UserRole.AGENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Managers and admins only")

    existing = await db.execute(
        select(KeywordAlert).where(KeywordAlert.keyword == body.keyword)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Keyword '{body.keyword}' already exists",
        )

    kw = KeywordAlert(keyword=body.keyword, category=body.category)
    db.add(kw)
    await db.commit()
    await db.refresh(kw)
    return KeywordAlertOut(
        id=kw.id,
        keyword=kw.keyword,
        category=kw.category,
        is_active=kw.is_active,
        created_at=kw.created_at.isoformat(),
    )


@router.patch("/{alert_id}", response_model=KeywordAlertOut)
async def update_keyword_alert(
    alert_id: UUID,
    body: KeywordAlertUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KeywordAlertOut:
    if current_user.role == UserRole.AGENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Managers and admins only")

    result = await db.execute(select(KeywordAlert).where(KeywordAlert.id == alert_id))
    kw = result.scalar_one_or_none()
    if kw is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyword alert not found")

    if body.is_active is not None:
        kw.is_active = body.is_active
    if body.category is not None:
        kw.category = body.category
    kw.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(kw)
    return KeywordAlertOut(
        id=kw.id,
        keyword=kw.keyword,
        category=kw.category,
        is_active=kw.is_active,
        created_at=kw.created_at.isoformat(),
    )


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_keyword_alert(
    alert_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    if current_user.role == UserRole.AGENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Managers and admins only")

    result = await db.execute(select(KeywordAlert).where(KeywordAlert.id == alert_id))
    kw = result.scalar_one_or_none()
    if kw is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyword alert not found")

    await db.delete(kw)
    await db.commit()


@router.get("/hits/{call_id}", response_model=List[CallKeywordHitOut])
async def get_keyword_hits_for_call(
    call_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[CallKeywordHitOut]:
    from sqlalchemy.orm import joinedload
    result = await db.execute(
        select(CallKeywordHit)
        .options(joinedload(CallKeywordHit.keyword_alert))
        .where(CallKeywordHit.call_id == call_id)
        .order_by(CallKeywordHit.hit_count.desc())
    )
    hits = result.unique().scalars().all()
    return [
        CallKeywordHitOut(
            id=h.id,
            call_id=h.call_id,
            keyword_alert_id=h.keyword_alert_id,
            keyword=h.keyword_alert.keyword,
            category=h.keyword_alert.category,
            hit_count=h.hit_count,
            sample_quotes=h.sample_quotes,
            created_at=h.created_at.isoformat(),
        )
        for h in hits
    ]

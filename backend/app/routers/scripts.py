from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.script import Script
from app.models.user import User, UserRole
from app.schemas.script import ScriptCreate, ScriptOut, ScriptUpdate

router = APIRouter(prefix="/scripts", tags=["scripts"])


def _require_manager(user: User) -> None:
    if user.role not in (UserRole.ADMIN, UserRole.MANAGER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Managers and admins only")


@router.get("", response_model=list[ScriptOut])
async def list_scripts(
    active_only: bool = True,
    current_user: User = Depends(CurrentUser),  # type: ignore[misc]
    db: AsyncSession = Depends(get_db),
) -> list[ScriptOut]:
    stmt = select(Script)
    if active_only:
        stmt = stmt.where(Script.is_active.is_(True))
    result = await db.execute(stmt.order_by(Script.updated_at.desc()))
    return [ScriptOut.model_validate(s) for s in result.scalars().all()]


@router.get("/{script_id}", response_model=ScriptOut)
async def get_script(
    script_id: UUID,
    current_user: User = Depends(CurrentUser),  # type: ignore[misc]
    db: AsyncSession = Depends(get_db),
) -> ScriptOut:
    result = await db.execute(select(Script).where(Script.id == script_id))
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
    return ScriptOut.model_validate(script)


@router.post("", response_model=ScriptOut, status_code=status.HTTP_201_CREATED)
async def create_script(
    body: ScriptCreate,
    current_user: User = Depends(CurrentUser),  # type: ignore[misc]
    db: AsyncSession = Depends(get_db),
) -> ScriptOut:
    _require_manager(current_user)
    script = Script(
        name=body.name,
        content=body.content,
        rubric=body.rubric.model_dump(),
        is_active=body.is_active,
    )
    db.add(script)
    await db.commit()
    await db.refresh(script)
    return ScriptOut.model_validate(script)


@router.patch("/{script_id}", response_model=ScriptOut)
async def update_script(
    script_id: UUID,
    body: ScriptUpdate,
    current_user: User = Depends(CurrentUser),  # type: ignore[misc]
    db: AsyncSession = Depends(get_db),
) -> ScriptOut:
    _require_manager(current_user)
    result = await db.execute(select(Script).where(Script.id == script_id))
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    if body.name is not None:
        script.name = body.name
    if body.content is not None:
        script.content = body.content
    if body.rubric is not None:
        script.rubric = body.rubric.model_dump()
    if body.is_active is not None:
        script.is_active = body.is_active

    await db.commit()
    await db.refresh(script)
    return ScriptOut.model_validate(script)

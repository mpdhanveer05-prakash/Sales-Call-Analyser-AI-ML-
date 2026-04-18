import math
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.call import Call, CallStatus
from app.models.agent import Agent
from app.models.user import User, UserRole
from app.schemas.call import CallListResponse, CallOut, CallUploadResponse
from app.schemas.transcript import TranscriptOut, TranscriptSegmentOut
from app.schemas.scores import CallScoresOut, SpeechScoreOut, SalesScoreOut
from app.schemas.summary import SummaryOut
from app.models.transcript import Transcript
from app.models.scores import SpeechScore, SalesScore
from app.models.summary import Summary
from app.services import storage_service
from app.config import settings

router = APIRouter(prefix="/calls", tags=["calls"])

ALLOWED_CONTENT_TYPES = {
    "audio/wav", "audio/wave", "audio/x-wav",
    "audio/mpeg", "audio/mp3",
    "audio/mp4", "audio/x-m4a",
    "audio/ogg", "audio/vorbis",
    "audio/flac", "audio/x-flac",
    "application/octet-stream",
}


def _validate_upload(file: UploadFile, file_bytes: bytes) -> None:
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in settings.allowed_extensions_set:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File type '{ext}' not allowed. Accepted: {settings.allowed_audio_extensions}",
        )
    if len(file_bytes) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.max_upload_size_mb} MB",
        )


@router.post("/upload", response_model=CallUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_call(
    file: UploadFile = File(...),
    agent_id: UUID = Form(...),
    call_date: date = Form(...),
    current_user: User = Depends(CurrentUser),  # type: ignore[misc]
    db: AsyncSession = Depends(get_db),
) -> CallUploadResponse:
    file_bytes = await file.read()
    _validate_upload(file, file_bytes)

    # Agents can only upload for themselves
    if current_user.role == UserRole.AGENT:
        result = await db.execute(select(Agent).where(Agent.user_id == current_user.id))
        own_agent = result.scalar_one_or_none()
        if own_agent is None or own_agent.id != agent_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agents can only upload their own calls")

    # Verify agent exists
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    content_type = file.content_type or "application/octet-stream"
    object_key = storage_service.upload_audio(file_bytes, file.filename, content_type)

    call = Call(
        agent_id=agent_id,
        uploaded_by=current_user.id,
        audio_url=object_key,
        original_filename=file.filename,
        file_size_bytes=len(file_bytes),
        status=CallStatus.QUEUED,
        call_date=call_date,
    )
    db.add(call)
    await db.flush()

    # Dispatch Celery task
    from app.workers.process_call_task import process_call_task
    process_call_task.delay(str(call.id))

    return CallUploadResponse(
        id=call.id,
        status=call.status,
        agent_id=call.agent_id,
        call_date=call.call_date,
        original_filename=call.original_filename,
    )


@router.get("", response_model=CallListResponse)
async def list_calls(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    agent_id: Optional[UUID] = Query(None),
    status_filter: Optional[CallStatus] = Query(None, alias="status"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    current_user: User = Depends(CurrentUser),  # type: ignore[misc]
    db: AsyncSession = Depends(get_db),
) -> CallListResponse:
    filters = []

    # RBAC scoping
    if current_user.role == UserRole.AGENT:
        result = await db.execute(select(Agent).where(Agent.user_id == current_user.id))
        own_agent = result.scalar_one_or_none()
        if own_agent:
            filters.append(Call.agent_id == own_agent.id)
        else:
            return CallListResponse(data=[], total=0, page=page, pages=0)
    elif current_user.role == UserRole.MANAGER and current_user.team_id:
        result = await db.execute(select(Agent.id).where(Agent.team_id == current_user.team_id))
        team_agent_ids = [row[0] for row in result.fetchall()]
        if team_agent_ids:
            filters.append(Call.agent_id.in_(team_agent_ids))
        else:
            return CallListResponse(data=[], total=0, page=page, pages=0)

    if agent_id:
        filters.append(Call.agent_id == agent_id)
    if status_filter:
        filters.append(Call.status == status_filter)
    if date_from:
        filters.append(Call.call_date >= date_from)
    if date_to:
        filters.append(Call.call_date <= date_to)

    where_clause = and_(*filters) if filters else True

    total_result = await db.execute(select(func.count()).select_from(Call).where(where_clause))
    total = total_result.scalar_one()

    calls_result = await db.execute(
        select(Call)
        .options(selectinload(Call.agent).selectinload(Agent.user))
        .where(where_clause)
        .order_by(Call.uploaded_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    calls = calls_result.scalars().all()

    data = [
        CallOut(
            id=c.id,
            agent_id=c.agent_id,
            agent_name=c.agent.user.full_name if c.agent and c.agent.user else "Unknown",
            call_date=c.call_date,
            duration_seconds=c.duration_seconds,
            status=c.status,
            disposition=c.disposition,
            speech_score=float(c.speech_score) if c.speech_score else None,
            sales_score=float(c.sales_score) if c.sales_score else None,
            original_filename=c.original_filename,
            uploaded_at=c.uploaded_at,
        )
        for c in calls
    ]

    return CallListResponse(
        data=data,
        total=total,
        page=page,
        pages=math.ceil(total / limit) if total else 0,
    )


@router.get("/{call_id}", response_model=CallOut)
async def get_call(
    call_id: UUID,
    current_user: User = Depends(CurrentUser),  # type: ignore[misc]
    db: AsyncSession = Depends(get_db),
) -> CallOut:
    result = await db.execute(
        select(Call)
        .options(selectinload(Call.agent).selectinload(Agent.user))
        .where(Call.id == call_id)
    )
    call = result.scalar_one_or_none()
    if call is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")

    # RBAC check
    if current_user.role == UserRole.AGENT:
        agent_result = await db.execute(select(Agent).where(Agent.user_id == current_user.id))
        own_agent = agent_result.scalar_one_or_none()
        if not own_agent or call.agent_id != own_agent.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    elif current_user.role == UserRole.MANAGER and current_user.team_id:
        if call.agent.team_id != current_user.team_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return CallOut(
        id=call.id,
        agent_id=call.agent_id,
        agent_name=call.agent.user.full_name if call.agent and call.agent.user else "Unknown",
        call_date=call.call_date,
        duration_seconds=call.duration_seconds,
        status=call.status,
        disposition=call.disposition,
        speech_score=float(call.speech_score) if call.speech_score else None,
        sales_score=float(call.sales_score) if call.sales_score else None,
        original_filename=call.original_filename,
        uploaded_at=call.uploaded_at,
    )


@router.get("/{call_id}/transcript", response_model=TranscriptOut)
async def get_call_transcript(
    call_id: UUID,
    current_user: User = Depends(CurrentUser),  # type: ignore[misc]
    db: AsyncSession = Depends(get_db),
) -> TranscriptOut:
    # Verify call access (reuse RBAC logic)
    call_result = await db.execute(
        select(Call).options(selectinload(Call.agent)).where(Call.id == call_id)
    )
    call = call_result.scalar_one_or_none()
    if call is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")

    if current_user.role == UserRole.AGENT:
        agent_result = await db.execute(select(Agent).where(Agent.user_id == current_user.id))
        own_agent = agent_result.scalar_one_or_none()
        if not own_agent or call.agent_id != own_agent.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    elif current_user.role == UserRole.MANAGER and current_user.team_id:
        if call.agent.team_id != current_user.team_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    transcript_result = await db.execute(
        select(Transcript)
        .options(joinedload(Transcript.segments))
        .where(Transcript.call_id == call_id)
    )
    transcript = transcript_result.unique().scalar_one_or_none()
    if transcript is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not yet available — call may still be processing",
        )

    return TranscriptOut(
        id=transcript.id,
        call_id=transcript.call_id,
        language=transcript.language,
        duration_seconds=float(transcript.duration_seconds) if transcript.duration_seconds else None,
        segment_count=transcript.segment_count,
        segments=[
            TranscriptSegmentOut(
                id=s.id,
                speaker=s.speaker,
                start_ms=s.start_ms,
                end_ms=s.end_ms,
                text=s.text,
                confidence=float(s.confidence) if s.confidence else None,
            )
            for s in transcript.segments
        ],
        created_at=transcript.created_at,
    )


@router.get("/{call_id}/audio-url")
async def get_call_audio_url(
    call_id: UUID,
    current_user: User = Depends(CurrentUser),  # type: ignore[misc]
    db: AsyncSession = Depends(get_db),
) -> dict:
    call_result = await db.execute(
        select(Call).options(selectinload(Call.agent)).where(Call.id == call_id)
    )
    call = call_result.scalar_one_or_none()
    if call is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")

    if current_user.role == UserRole.AGENT:
        agent_result = await db.execute(select(Agent).where(Agent.user_id == current_user.id))
        own_agent = agent_result.scalar_one_or_none()
        if not own_agent or call.agent_id != own_agent.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    elif current_user.role == UserRole.MANAGER and current_user.team_id:
        if call.agent.team_id != current_user.team_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    url = storage_service.get_presigned_url(call.audio_url, expires_hours=2)
    return {"url": url}


@router.get("/{call_id}/scores", response_model=CallScoresOut)
async def get_call_scores(
    call_id: UUID,
    current_user: User = Depends(CurrentUser),  # type: ignore[misc]
    db: AsyncSession = Depends(get_db),
) -> CallScoresOut:
    call_result = await db.execute(
        select(Call).options(selectinload(Call.agent)).where(Call.id == call_id)
    )
    call = call_result.scalar_one_or_none()
    if call is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")

    if current_user.role == UserRole.AGENT:
        agent_result = await db.execute(select(Agent).where(Agent.user_id == current_user.id))
        own_agent = agent_result.scalar_one_or_none()
        if not own_agent or call.agent_id != own_agent.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    elif current_user.role == UserRole.MANAGER and current_user.team_id:
        if call.agent.team_id != current_user.team_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    score_result = await db.execute(
        select(SpeechScore).where(SpeechScore.call_id == call_id)
    )
    speech = score_result.scalar_one_or_none()

    speech_out: SpeechScoreOut | None = None
    if speech:
        speech_out = SpeechScoreOut(
            id=speech.id,
            call_id=speech.call_id,
            pronunciation=float(speech.pronunciation),
            intonation=float(speech.intonation),
            fluency=float(speech.fluency),
            grammar=float(speech.grammar),
            vocabulary=float(speech.vocabulary),
            pace=float(speech.pace),
            clarity=float(speech.clarity),
            filler_score=float(speech.filler_score),
            composite=float(speech.composite),
            fillers_per_min=float(speech.fillers_per_min) if speech.fillers_per_min else None,
            pace_wpm=float(speech.pace_wpm) if speech.pace_wpm else None,
            talk_ratio=float(speech.talk_ratio) if speech.talk_ratio else None,
            created_at=speech.created_at,
        )

    # Sales score
    sales_result = await db.execute(select(SalesScore).where(SalesScore.call_id == call_id))
    sales = sales_result.scalar_one_or_none()

    sales_out: SalesScoreOut | None = None
    if sales:
        sales_out = SalesScoreOut(
            id=sales.id,
            call_id=sales.call_id,
            greeting=float(sales.greeting),
            rapport=float(sales.rapport),
            discovery=float(sales.discovery),
            value_explanation=float(sales.value_explanation),
            objection_handling=float(sales.objection_handling),
            script_adherence=float(sales.script_adherence),
            closing=float(sales.closing),
            compliance=float(sales.compliance),
            composite=float(sales.composite),
            details=sales.details,
            created_at=sales.created_at,
        )

    return CallScoresOut(call_id=call_id, speech=speech_out, sales=sales_out)


@router.get("/{call_id}/summary", response_model=SummaryOut)
async def get_call_summary(
    call_id: UUID,
    current_user: User = Depends(CurrentUser),  # type: ignore[misc]
    db: AsyncSession = Depends(get_db),
) -> SummaryOut:
    call_result = await db.execute(
        select(Call).options(selectinload(Call.agent)).where(Call.id == call_id)
    )
    call = call_result.scalar_one_or_none()
    if call is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")

    if current_user.role == UserRole.AGENT:
        agent_result = await db.execute(select(Agent).where(Agent.user_id == current_user.id))
        own_agent = agent_result.scalar_one_or_none()
        if not own_agent or call.agent_id != own_agent.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    elif current_user.role == UserRole.MANAGER and current_user.team_id:
        if call.agent.team_id != current_user.team_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    summary_result = await db.execute(select(Summary).where(Summary.call_id == call_id))
    summary = summary_result.scalar_one_or_none()
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Summary not yet available — call may still be processing",
        )

    return SummaryOut(
        id=summary.id,
        call_id=summary.call_id,
        executive_summary=summary.executive_summary,
        key_moments=summary.key_moments or [],
        coaching_suggestions=summary.coaching_suggestions or [],
        disposition_confidence=float(summary.disposition_confidence) if summary.disposition_confidence else None,
        disposition_reasoning=summary.disposition_reasoning,
        created_at=summary.created_at,
    )

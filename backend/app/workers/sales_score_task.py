import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.call import Call, CallStatus
from app.models.coaching import CoachingClip, Objection
from app.models.scores import SalesScore
from app.models.summary import Summary
from app.models.transcript import Transcript
from app.models.script import Script
from app.services import ollama_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

DEFAULT_RUBRIC = {
    "required_points": [
        "Introduce yourself and company",
        "Ask discovery questions",
        "Explain product benefits",
        "Handle objections",
        "Ask for a next step or commitment",
    ]
}


# ---------------------------------------------------------------------------
# Async DB helpers
# ---------------------------------------------------------------------------

async def _update_call_status(call_id: str, status: CallStatus, error: str | None = None) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Call).where(Call.id == UUID(call_id)))
        call = result.scalar_one_or_none()
        if call:
            call.status = status
            if error:
                call.error_message = error
            if status == CallStatus.COMPLETED:
                call.processed_at = datetime.now(timezone.utc)
            await db.commit()


async def _fetch_data(call_id: str) -> tuple[list[dict], dict]:
    """Returns (transcript_segments_as_dicts, rubric_dict)."""
    async with AsyncSessionLocal() as db:
        tr_result = await db.execute(
            select(Transcript)
            .options(joinedload(Transcript.segments))
            .where(Transcript.call_id == UUID(call_id))
        )
        transcript = tr_result.unique().scalar_one_or_none()
        segs = [
            {
                "speaker": s.speaker,
                "start_ms": s.start_ms,
                "end_ms": s.end_ms,
                "text": s.text,
                "confidence": float(s.confidence) if s.confidence else None,
            }
            for s in (transcript.segments if transcript else [])
        ]

        script_result = await db.execute(
            select(Script).where(Script.is_active.is_(True)).order_by(Script.updated_at.desc())
        )
        script = script_result.scalars().first()
        rubric = script.rubric if script else DEFAULT_RUBRIC

    return segs, rubric


async def _save_results(
    call_id: str,
    sales_result: dict,
    summary_result: dict,
    disposition_result: dict,
    coaching_moments: list[dict],
    objections: list[dict],
) -> None:
    async with AsyncSessionLocal() as db:
        # Remove previous records (idempotent)
        for Model in (SalesScore, Summary):
            existing = await db.execute(select(Model).where(Model.call_id == UUID(call_id)))
            row = existing.scalar_one_or_none()
            if row:
                await db.delete(row)

        # Remove previous coaching clips and objections (idempotent)
        old_clips = await db.execute(select(CoachingClip).where(CoachingClip.call_id == UUID(call_id)))
        for clip in old_clips.scalars().all():
            await db.delete(clip)

        old_objections = await db.execute(select(Objection).where(Objection.call_id == UUID(call_id)))
        for obj in old_objections.scalars().all():
            await db.delete(obj)

        await db.flush()

        dim = sales_result["dimension_scores"]
        db.add(SalesScore(
            call_id=UUID(call_id),
            greeting=dim["greeting"],
            rapport=dim["rapport"],
            discovery=dim["discovery"],
            value_explanation=dim["value_explanation"],
            objection_handling=dim["objection_handling"],
            script_adherence=dim["script_adherence"],
            closing=dim["closing"],
            compliance=dim["compliance"],
            composite=sales_result["composite"],
            details=sales_result["scores"],
        ))

        db.add(Summary(
            call_id=UUID(call_id),
            executive_summary=summary_result["executive_summary"],
            key_moments=summary_result["key_moments"],
            coaching_suggestions=summary_result["coaching_suggestions"],
            disposition_confidence=disposition_result.get("confidence"),
            disposition_reasoning=disposition_result.get("reasoning"),
        ))

        # Save coaching clips
        for moment in coaching_moments:
            db.add(CoachingClip(
                call_id=UUID(call_id),
                start_ms=moment["start_ms"],
                end_ms=moment["end_ms"],
                category=moment["category"],
                reason=moment["reason"],
            ))

        # Save objections
        for obj in objections:
            db.add(Objection(
                call_id=UUID(call_id),
                timestamp_ms=obj["timestamp_ms"],
                objection_type=obj["objection_type"],
                quote=obj["quote"],
                resolved=obj["resolved"],
            ))

        # Update denormalised columns on call
        call_result = await db.execute(select(Call).where(Call.id == UUID(call_id)))
        call = call_result.scalar_one_or_none()
        if call:
            call.sales_score = sales_result["composite"]
            call.disposition = disposition_result["disposition"]

        await db.commit()
        logger.info(
            "Saved sales scores for call %s — composite=%.1f, disposition=%s, "
            "coaching_clips=%d, objections=%d",
            call_id, sales_result["composite"], disposition_result["disposition"],
            len(coaching_moments), len(objections),
        )


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------

@celery_app.task(name="score_sales", bind=True, max_retries=3)
def sales_score_task(self, call_id: str) -> dict:
    logger.info("Starting sales scoring for call %s", call_id)

    try:
        segments, rubric = asyncio.run(_fetch_data(call_id))
        if not segments:
            raise ValueError(f"No transcript segments for call {call_id}")

        logger.info("Running Ollama sales scoring for call %s (%d segments)", call_id, len(segments))
        sales_result = ollama_service.score_sales_quality(segments, rubric)

        logger.info("Running Ollama summarisation for call %s", call_id)
        summary_result = ollama_service.generate_summary(segments)

        logger.info("Running Ollama disposition classification for call %s", call_id)
        disposition_result = ollama_service.classify_disposition(segments)

        logger.info("Extracting coaching moments and objections for call %s", call_id)
        coaching_moments = ollama_service.extract_coaching_moments(segments)
        objections = ollama_service.extract_objections(segments)

        asyncio.run(_save_results(
            call_id, sales_result, summary_result, disposition_result,
            coaching_moments, objections,
        ))
        asyncio.run(_update_call_status(call_id, CallStatus.COMPLETED))

        logger.info(
            "Sales scoring complete for call %s — composite=%.1f, disposition=%s",
            call_id, sales_result["composite"], disposition_result["disposition"],
        )

        # Chain index task (best-effort)
        try:
            from app.workers.index_task import index_task
            index_task.delay(call_id)
        except Exception as e:
            logger.warning("Could not dispatch index_task for call %s: %s", call_id, e)

        return {
            "call_id": call_id,
            "sales_composite": sales_result["composite"],
            "disposition": disposition_result["disposition"],
        }

    except Exception as exc:
        logger.error("Sales scoring failed for call %s: %s", call_id, exc)
        asyncio.run(_update_call_status(call_id, CallStatus.FAILED, str(exc)))
        raise self.retry(exc=exc, countdown=120)

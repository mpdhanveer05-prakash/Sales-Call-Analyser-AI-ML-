import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.config import settings
from app.database import SyncSessionLocal
from app.models.call import Call, CallStatus
from app.models.coaching import CoachingClip, Objection
from app.models.scores import SalesScore
from app.models.summary import Summary
from app.models.transcript import Transcript
from app.models.script import Script
from app.services import ollama_service, signal_scoring
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


def _is_cancelled(call_id: str) -> bool:
    with SyncSessionLocal() as db:
        result = db.execute(select(Call.status).where(Call.id == UUID(call_id)))
        s = result.scalar_one_or_none()
        return s == CallStatus.CANCELLED


def _update_call_status(call_id: str, status: CallStatus, error: str | None = None) -> None:
    with SyncSessionLocal() as db:
        result = db.execute(select(Call).where(Call.id == UUID(call_id)))
        call = result.scalar_one_or_none()
        if call:
            call.status = status
            if error:
                call.error_message = error
            if status == CallStatus.COMPLETED:
                call.processed_at = datetime.now(timezone.utc)
            db.commit()


def _fetch_data(call_id: str) -> tuple[list[dict], dict]:
    with SyncSessionLocal() as db:
        tr_result = db.execute(
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

        script_result = db.execute(
            select(Script).where(Script.is_active.is_(True)).order_by(Script.updated_at.desc())
        )
        script = script_result.scalars().first()
        rubric = script.rubric if script else DEFAULT_RUBRIC

    return segs, rubric


def _save_results(
    call_id: str,
    sales_result: dict,
    summary_result: dict,
    disposition_result: dict,
    coaching_moments: list[dict],
    objections: list[dict],
    sentiment_timeline: list[dict] | None = None,
    skip_sales_score: bool = False,
) -> None:
    with SyncSessionLocal() as db:
        for Model in (SalesScore, Summary):
            existing = db.execute(select(Model).where(Model.call_id == UUID(call_id)))
            row = existing.scalar_one_or_none()
            if row:
                db.delete(row)

        old_clips = db.execute(select(CoachingClip).where(CoachingClip.call_id == UUID(call_id)))
        for clip in old_clips.scalars().all():
            db.delete(clip)

        old_objections = db.execute(select(Objection).where(Objection.call_id == UUID(call_id)))
        for obj in old_objections.scalars().all():
            db.delete(obj)

        db.flush()

        # Skip SalesScore row entirely for non-live calls (VOICEMAIL, NO_ANSWER)
        if not skip_sales_score:
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
            sentiment_timeline=sentiment_timeline or [],
        ))

        for moment in coaching_moments:
            db.add(CoachingClip(
                call_id=UUID(call_id),
                start_ms=moment["start_ms"],
                end_ms=moment["end_ms"],
                category=moment["category"],
                reason=moment["reason"],
            ))

        for obj in objections:
            db.add(Objection(
                call_id=UUID(call_id),
                timestamp_ms=obj["timestamp_ms"],
                objection_type=obj["objection_type"],
                quote=obj["quote"],
                resolved=obj["resolved"],
            ))

        call_result = db.execute(select(Call).where(Call.id == UUID(call_id)))
        call = call_result.scalar_one_or_none()
        if call:
            # sales_score stays null for VOICEMAIL/NO_ANSWER — frontend shows "N/A"
            if not skip_sales_score:
                call.sales_score = sales_result["composite"]
            call.disposition = disposition_result["disposition"]

        db.commit()
        logger.info(
            "Saved results for call %s — sales=%s, disposition=%s, clips=%d, objections=%d",
            call_id,
            f"{sales_result['composite']:.1f}" if not skip_sales_score else "N/A",
            disposition_result["disposition"],
            len(coaching_moments), len(objections),
        )


@celery_app.task(name="score_sales", bind=True, max_retries=3)
def sales_score_task(self, call_id: str) -> dict:
    logger.info("Starting sales scoring for call %s", call_id)

    try:
        if _is_cancelled(call_id):
            logger.info("Call %s is cancelled — skipping sales scoring", call_id)
            return {"call_id": call_id, "skipped": "cancelled"}

        segments, rubric = _fetch_data(call_id)
        if not segments:
            raise ValueError(f"No transcript segments for call {call_id}")

        # Detect call type from early disposition (set by transcribe_task) or re-detect
        with SyncSessionLocal() as db:
            call_row = db.execute(select(Call).where(Call.id == UUID(call_id))).scalar_one_or_none()
            early_disposition = call_row.disposition if call_row else None
        call_type = early_disposition if early_disposition in ("VOICEMAIL", "NO_ANSWER") else "LIVE"

        # Fix 4: Signal-based scores (instant, deterministic, no LLM)
        if call_type in ("VOICEMAIL", "NO_ANSWER"):
            logger.info("Call %s is %s — using minimal scoring", call_id, call_type)
            sales_result = signal_scoring._empty_scores(f"Not applicable — {call_type} call")
        else:
            logger.info("Computing signal-based sales scores for call %s (%d segments)", call_id, len(segments))
            sales_result = signal_scoring.compute_scores(segments, rubric)

        # Fix 2 + 4: LLM handles narrative only (summary, disposition, coaching, sentiment)
        logger.info("Running LLM summary analysis for call %s (call_type=%s)", call_id, call_type)
        llm_result = ollama_service.analyze_call_summary(segments, call_type=call_type)

        summary_result = llm_result["summary"]
        disposition_result = llm_result["disposition"]
        coaching_moments = llm_result["coaching_moments"]
        objections = llm_result["objections"]
        sentiment_timeline = llm_result["sentiment_timeline"]

        _save_results(
            call_id, sales_result, summary_result, disposition_result,
            coaching_moments, objections, sentiment_timeline,
            skip_sales_score=(call_type in ("VOICEMAIL", "NO_ANSWER")),
        )
        _update_call_status(call_id, CallStatus.COMPLETED)

        logger.info(
            "Sales scoring complete for call %s — composite=%.1f, disposition=%s",
            call_id, sales_result["composite"], disposition_result["disposition"],
        )

        try:
            from app.workers.index_task import index_task
            index_task.delay(call_id)
        except Exception as e:
            logger.warning("Could not dispatch index_task for call %s: %s", call_id, e)

        try:
            from app.workers.keyword_check_task import keyword_check_task
            keyword_check_task.delay(call_id)
        except Exception as e:
            logger.warning("Could not dispatch keyword_check_task for call %s: %s", call_id, e)

        return {
            "call_id": call_id,
            "sales_composite": sales_result["composite"],
            "disposition": disposition_result["disposition"],
        }

    except Exception as exc:
        logger.error("Sales scoring failed for call %s: %s", call_id, exc)
        _update_call_status(call_id, CallStatus.FAILED, str(exc))
        raise self.retry(exc=exc, countdown=120)

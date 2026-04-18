import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.call import Call, CallStatus
from app.models.scores import SpeechScore
from app.models.transcript import Transcript, TranscriptSegment
from app.services.speech_scoring_service import compute_speech_scores
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


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


async def _fetch_transcript_for_scoring(call_id: str) -> tuple[str | None, list[dict]]:
    """Returns (minio_path, segments_as_dicts)."""
    async with AsyncSessionLocal() as db:
        call_result = await db.execute(select(Call).where(Call.id == UUID(call_id)))
        call = call_result.scalar_one_or_none()
        if not call:
            return None, []

        tr_result = await db.execute(
            select(Transcript)
            .options(joinedload(Transcript.segments))
            .where(Transcript.call_id == UUID(call_id))
        )
        transcript = tr_result.unique().scalar_one_or_none()
        if not transcript:
            return call.audio_url, []

        segs = [
            {
                "speaker": s.speaker,
                "start_ms": s.start_ms,
                "end_ms": s.end_ms,
                "text": s.text,
                "confidence": float(s.confidence) if s.confidence else None,
            }
            for s in transcript.segments
        ]
        return call.audio_url, segs


async def _save_speech_score(call_id: str, scores: dict) -> None:
    async with AsyncSessionLocal() as db:
        # Idempotent — remove existing before inserting
        existing = await db.execute(select(SpeechScore).where(SpeechScore.call_id == UUID(call_id)))
        row = existing.scalar_one_or_none()
        if row:
            await db.delete(row)
            await db.flush()

        db.add(SpeechScore(
            call_id=UUID(call_id),
            pronunciation=scores["pronunciation"],
            intonation=scores["intonation"],
            fluency=scores["fluency"],
            grammar=scores["grammar"],
            vocabulary=scores["vocabulary"],
            pace=scores["pace"],
            clarity=scores["clarity"],
            filler_score=scores["filler_score"],
            composite=scores["composite"],
            fillers_per_min=scores.get("fillers_per_min"),
            pace_wpm=scores.get("pace_wpm"),
            talk_ratio=scores.get("talk_ratio"),
        ))

        # Update the denormalised speech_score column on the call row
        call_result = await db.execute(select(Call).where(Call.id == UUID(call_id)))
        call = call_result.scalar_one_or_none()
        if call:
            call.speech_score = scores["composite"]

        await db.commit()
        logger.info("Saved speech scores for call %s — composite=%.1f", call_id, scores["composite"])


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------

@celery_app.task(name="score_speech", bind=True, max_retries=3)
def speech_score_task(self, call_id: str) -> dict:
    logger.info("Starting speech scoring for call %s", call_id)

    try:
        asyncio.run(_update_call_status(call_id, CallStatus.SCORING))

        minio_path, segments = asyncio.run(_fetch_transcript_for_scoring(call_id))
        if not minio_path:
            raise ValueError(f"Call {call_id} not found")
        if not segments:
            raise ValueError(f"No transcript segments found for call {call_id}")

        # Call ML service
        payload = {"minio_path": minio_path, "transcript": segments}
        with httpx.Client(timeout=600.0) as client:
            response = client.post(
                f"{settings.ml_service_url}/analyze-speech",
                json=payload,
            )
            response.raise_for_status()

        raw_metrics = response.json()
        scores = compute_speech_scores(raw_metrics)

        asyncio.run(_save_speech_score(call_id, scores))

        # Chain to sales scoring (LLM layer — runs Ollama)
        from app.workers.sales_score_task import sales_score_task
        sales_score_task.delay(call_id)

        logger.info("Speech scoring complete for call %s — composite=%.1f — dispatched sales scoring", call_id, scores["composite"])
        return {"call_id": call_id, "composite": scores["composite"]}

    except httpx.HTTPStatusError as exc:
        error_msg = f"ML service error: {exc.response.status_code} — {exc.response.text[:200]}"
        logger.error(error_msg)
        asyncio.run(_update_call_status(call_id, CallStatus.FAILED, error_msg))
        raise self.retry(exc=exc, countdown=60)

    except Exception as exc:
        logger.error("Speech scoring failed for call %s: %s", call_id, exc)
        asyncio.run(_update_call_status(call_id, CallStatus.FAILED, str(exc)))
        raise self.retry(exc=exc, countdown=60)

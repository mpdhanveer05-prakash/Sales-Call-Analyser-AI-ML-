import logging
from uuid import UUID

import httpx
from sqlalchemy import select

from app.config import settings
from app.database import SyncSessionLocal
from app.models.call import Call, CallStatus
from app.models.transcript import Transcript, TranscriptSegment
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_call(call_id: str) -> Call | None:
    with SyncSessionLocal() as db:
        result = db.execute(select(Call).where(Call.id == UUID(call_id)))
        return result.scalar_one_or_none()


def _is_cancelled(call_id: str) -> bool:
    with SyncSessionLocal() as db:
        result = db.execute(select(Call.status).where(Call.id == UUID(call_id)))
        status = result.scalar_one_or_none()
        return status == CallStatus.CANCELLED


def _update_call_status(call_id: str, status: CallStatus, error: str | None = None) -> None:
    with SyncSessionLocal() as db:
        result = db.execute(select(Call).where(Call.id == UUID(call_id)))
        call = result.scalar_one_or_none()
        if call:
            call.status = status
            if error:
                call.error_message = error
            db.commit()


def _save_transcript(
    call_id: str,
    language: str,
    duration_seconds: float,
    segments_data: list[dict],
) -> None:
    with SyncSessionLocal() as db:
        result = db.execute(select(Transcript).where(Transcript.call_id == UUID(call_id)))
        existing = result.scalar_one_or_none()
        if existing:
            db.delete(existing)
            db.flush()

        transcript = Transcript(
            call_id=UUID(call_id),
            language=language,
            duration_seconds=duration_seconds,
            segment_count=len(segments_data),
        )
        db.add(transcript)
        db.flush()

        for seg in segments_data:
            db.add(TranscriptSegment(
                transcript_id=transcript.id,
                speaker=seg["speaker"],
                start_ms=seg["start_ms"],
                end_ms=seg["end_ms"],
                text=seg["text"],
                confidence=seg.get("confidence"),
            ))

        call_result = db.execute(select(Call).where(Call.id == UUID(call_id)))
        call = call_result.scalar_one_or_none()
        if call and call.duration_seconds is None and duration_seconds:
            call.duration_seconds = int(duration_seconds)

        db.commit()
        logger.info("Saved %d transcript segments for call %s", len(segments_data), call_id)


@celery_app.task(name="transcribe_call", bind=True, max_retries=3)
def transcribe_call_task(self, call_id: str) -> dict:
    logger.info("Starting transcription for call %s", call_id)

    try:
        if _is_cancelled(call_id):
            logger.info("Call %s is cancelled — skipping transcription", call_id)
            return {"call_id": call_id, "skipped": "cancelled"}

        _update_call_status(call_id, CallStatus.TRANSCRIBING)

        call = _get_call(call_id)
        if not call:
            raise ValueError(f"Call {call_id} not found in database")

        payload = {"minio_path": call.audio_url}
        with httpx.Client(timeout=600.0) as client:
            response = client.post(
                f"{settings.ml_service_url}/transcribe",
                json=payload,
            )
            response.raise_for_status()

        result = response.json()
        segments = result["segments"]
        language = result["language"]
        duration_seconds = result["duration_seconds"]

        _save_transcript(call_id, language, duration_seconds, segments)
        _update_call_status(call_id, CallStatus.ANALYZING)

        from app.workers.speech_score_task import speech_score_task
        speech_score_task.delay(call_id)

        logger.info(
            "Transcription complete for call %s: %d segments, lang=%s — dispatched speech scoring",
            call_id, len(segments), language,
        )
        return {"call_id": call_id, "segment_count": len(segments), "language": language}

    except httpx.HTTPStatusError as exc:
        error_msg = f"ML service error: {exc.response.status_code} — {exc.response.text[:200]}"
        logger.error(error_msg)
        _update_call_status(call_id, CallStatus.FAILED, error_msg)
        raise self.retry(exc=exc, countdown=60)

    except Exception as exc:
        logger.error("Transcription failed for call %s: %s", call_id, exc)
        _update_call_status(call_id, CallStatus.FAILED, str(exc))
        raise self.retry(exc=exc, countdown=60)

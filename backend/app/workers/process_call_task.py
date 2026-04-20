import logging
from uuid import UUID

from sqlalchemy import select

from app.database import SyncSessionLocal
from app.models.call import Call, CallStatus
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _update_call_status(call_id: str, status: CallStatus, error: str | None = None) -> None:
    with SyncSessionLocal() as db:
        result = db.execute(select(Call).where(Call.id == UUID(call_id)))
        call = result.scalar_one_or_none()
        if call:
            call.status = status
            if error:
                call.error_message = error
            db.commit()


@celery_app.task(name="process_call", bind=True, max_retries=3)
def process_call_task(self, call_id: str) -> dict:
    logger.info("process_call received for call %s — dispatching transcription", call_id)

    try:
        _update_call_status(call_id, CallStatus.QUEUED)

        from app.workers.transcribe_task import transcribe_call_task
        transcribe_call_task.delay(call_id)

        return {"call_id": call_id, "dispatched": "transcribe_call"}

    except Exception as exc:
        logger.error("Error dispatching call %s: %s", call_id, exc)
        _update_call_status(call_id, CallStatus.FAILED, str(exc))
        raise self.retry(exc=exc, countdown=30)

import asyncio
import logging
from uuid import UUID

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.call import Call, CallStatus
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _update_call_status(call_id: str, status: CallStatus, error: str | None = None) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Call).where(Call.id == UUID(call_id)))
        call = result.scalar_one_or_none()
        if call:
            call.status = status
            if error:
                call.error_message = error
            await db.commit()


@celery_app.task(name="process_call", bind=True, max_retries=3)
def process_call_task(self, call_id: str) -> dict:
    logger.info(f"Processing call {call_id}")

    try:
        asyncio.run(_update_call_status(call_id, CallStatus.ANALYZING))
        # Stub: Phase 2 will add real transcription here
        logger.info(f"Call {call_id} picked up by worker (stub — Phase 2 adds transcription)")
        return {"call_id": call_id, "status": "stub_complete"}
    except Exception as exc:
        logger.error(f"Error processing call {call_id}: {exc}")
        asyncio.run(_update_call_status(call_id, CallStatus.FAILED, str(exc)))
        raise self.retry(exc=exc, countdown=30)

import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.database import SyncSessionLocal
from app.models.call import Call
from app.models.keyword_alert import CallKeywordHit, KeywordAlert
from app.models.transcript import Transcript
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="check_keywords", bind=True, max_retries=2)
def keyword_check_task(self, call_id: str) -> dict:
    logger.info("Starting keyword check for call %s", call_id)
    try:
        with SyncSessionLocal() as db:
            # Load active keywords
            kw_result = db.execute(
                select(KeywordAlert).where(KeywordAlert.is_active.is_(True))
            )
            keywords = kw_result.scalars().all()
            if not keywords:
                return {"call_id": call_id, "hits": 0}

            # Load transcript segments
            tr_result = db.execute(
                select(Transcript)
                .options(joinedload(Transcript.segments))
                .where(Transcript.call_id == uuid.UUID(call_id))
            )
            transcript = tr_result.unique().scalar_one_or_none()
            if not transcript:
                return {"call_id": call_id, "hits": 0}

            segments = transcript.segments

            # Delete old hits for this call
            old_hits = db.execute(
                select(CallKeywordHit).where(CallKeywordHit.call_id == uuid.UUID(call_id))
            )
            for hit in old_hits.scalars().all():
                db.delete(hit)
            db.flush()

            total_hits = 0
            for kw in keywords:
                pattern = re.compile(re.escape(kw.keyword), re.IGNORECASE)
                hit_count = 0
                sample_quotes: list[dict] = []

                for seg in segments:
                    matches = pattern.findall(seg.text)
                    if matches:
                        hit_count += len(matches)
                        if len(sample_quotes) < 5:
                            sample_quotes.append({
                                "timestamp_ms": seg.start_ms,
                                "speaker": seg.speaker,
                                "text": seg.text[:200],
                            })

                if hit_count > 0:
                    db.add(CallKeywordHit(
                        call_id=uuid.UUID(call_id),
                        keyword_alert_id=kw.id,
                        hit_count=hit_count,
                        sample_quotes=sample_quotes,
                    ))
                    total_hits += hit_count
                    logger.info("Keyword '%s' found %d times in call %s", kw.keyword, hit_count, call_id)

            # Update call flag
            call_result = db.execute(select(Call).where(Call.id == uuid.UUID(call_id)))
            call = call_result.scalar_one_or_none()
            if call:
                call.has_keyword_hit = total_hits > 0

            db.commit()

        logger.info("Keyword check complete for call %s — total hits: %d", call_id, total_hits)
        return {"call_id": call_id, "hits": total_hits}

    except Exception as exc:
        logger.error("Keyword check failed for call %s: %s", call_id, exc)
        raise self.retry(exc=exc, countdown=30)

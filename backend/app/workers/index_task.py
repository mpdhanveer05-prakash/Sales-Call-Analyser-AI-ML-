"""Celery task: index a completed call into OpenSearch and store its embedding."""
import asyncio
import logging
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy import select, text
from sqlalchemy.orm import joinedload

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.agent import Agent
from app.models.call import Call, CallStatus
from app.models.transcript import Transcript
from app.models.user import User
from app.services import search_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Async DB helpers
# ---------------------------------------------------------------------------


async def _fetch_call_data(call_id: str) -> Optional[dict]:
    """Fetch all data needed to index a call.  Returns None if call not found."""
    async with AsyncSessionLocal() as db:
        # Load call with agent -> user chain
        call_result = await db.execute(
            select(Call)
            .options(
                joinedload(Call.agent).joinedload(Agent.user),
                joinedload(Call.agent).joinedload(Agent.team),
            )
            .where(Call.id == UUID(call_id))
        )
        call = call_result.unique().scalar_one_or_none()
        if call is None:
            return None

        agent = call.agent
        agent_user: Optional[User] = agent.user if agent else None
        agent_name = agent_user.full_name if agent_user else None

        # Fetch speech_score composite from speech_scores table
        from app.models.scores import SpeechScore, SalesScore

        ss_result = await db.execute(
            select(SpeechScore.composite).where(SpeechScore.call_id == UUID(call_id))
        )
        speech_composite: Optional[float] = ss_result.scalar_one_or_none()
        if speech_composite is not None:
            speech_composite = float(speech_composite)

        sales_result = await db.execute(
            select(SalesScore.composite).where(SalesScore.call_id == UUID(call_id))
        )
        sales_composite: Optional[float] = sales_result.scalar_one_or_none()
        if sales_composite is not None:
            sales_composite = float(sales_composite)

        # Fetch transcript segments
        tr_result = await db.execute(
            select(Transcript)
            .options(joinedload(Transcript.segments))
            .where(Transcript.call_id == UUID(call_id))
        )
        transcript = tr_result.unique().scalar_one_or_none()
        segments = []
        if transcript:
            segments = [
                {
                    "speaker": seg.speaker,
                    "start_ms": seg.start_ms,
                    "end_ms": seg.end_ms,
                    "text": seg.text,
                }
                for seg in transcript.segments
            ]

        return {
            "call_id": str(call.id),
            "agent_id": str(agent.id) if agent else None,
            "agent_name": agent_name,
            "call_date": call.call_date,
            "disposition": call.disposition,
            "speech_score": speech_composite,
            "sales_score": sales_composite,
            "duration_seconds": call.duration_seconds,
            "segments": segments,
        }


async def _save_embedding(call_id: str, embedding: list[float]) -> None:
    """Persist the embedding vector to the calls table via raw SQL."""
    # Format the vector as a PostgreSQL vector literal: '[0.1,0.2,...]'
    vec_literal = "[" + ",".join(str(v) for v in embedding) + "]"
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("UPDATE calls SET embedding = :emb::vector WHERE id = :id"),
            {"emb": vec_literal, "id": call_id},
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------


@celery_app.task(name="index_call", bind=True, max_retries=3)
def index_task(self, call_id: str) -> dict:
    """Index call into OpenSearch and optionally embed agent transcript text."""
    logger.info("Starting index task for call %s", call_id)

    try:
        data = asyncio.run(_fetch_call_data(call_id))
        if data is None:
            logger.warning("index_task: call %s not found in DB — skipping", call_id)
            return {"call_id": call_id, "status": "skipped"}

        # Index into OpenSearch
        search_service.index_call(
            call_id=data["call_id"],
            agent_id=data["agent_id"],
            agent_name=data["agent_name"],
            call_date=data["call_date"],
            disposition=data["disposition"],
            speech_score=data["speech_score"],
            sales_score=data["sales_score"],
            duration_seconds=data["duration_seconds"],
            segments=data["segments"],
        )

        # Build agent-only text for embedding (best-effort)
        agent_segments = [
            seg["text"]
            for seg in data["segments"]
            if seg.get("speaker", "").upper() == "AGENT"
        ]
        agent_text = " ".join(agent_segments)

        if agent_text.strip():
            try:
                ml_url = settings.ml_service_url.rstrip("/")
                with httpx.Client(timeout=60.0) as http_client:
                    resp = http_client.post(
                        f"{ml_url}/embed",
                        json={"text": agent_text[:4000]},
                    )
                    resp.raise_for_status()
                    embedding: list[float] = resp.json()["embedding"]

                asyncio.run(_save_embedding(call_id, embedding))
                logger.info("Saved embedding for call %s (dim=%d)", call_id, len(embedding))
            except Exception as emb_exc:  # noqa: BLE001
                logger.warning(
                    "Could not generate/save embedding for call %s: %s",
                    call_id,
                    emb_exc,
                )

        logger.info("index_task complete for call %s", call_id)
        return {"call_id": call_id, "status": "indexed"}

    except Exception as exc:
        logger.error("index_task failed for call %s: %s", call_id, exc)
        raise self.retry(exc=exc, countdown=60)

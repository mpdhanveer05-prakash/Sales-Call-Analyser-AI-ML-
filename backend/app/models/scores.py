import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base

if TYPE_CHECKING:
    from app.models.call import Call


class SpeechScore(Base):
    __tablename__ = "speech_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Dimension scores 0-100
    pronunciation: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    intonation: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    fluency: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    grammar: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    vocabulary: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    pace: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    clarity: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    filler_score: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    composite: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)

    # Raw metrics preserved for re-scoring
    fillers_per_min: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    pace_wpm: Mapped[Optional[float]] = mapped_column(Numeric(6, 1), nullable=True)
    talk_ratio: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    call: Mapped["Call"] = relationship("Call", back_populates="speech_score_rel")


class SalesScore(Base):
    __tablename__ = "sales_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Dimension scores 0-100 (LLM raw 0-10 × 10)
    greeting: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    rapport: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    discovery: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    value_explanation: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    objection_handling: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    script_adherence: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    closing: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    compliance: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    composite: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)

    # Per-dimension justifications + quotes from the LLM
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    call: Mapped["Call"] = relationship("Call", back_populates="sales_score_rel")

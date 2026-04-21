import enum
import uuid
from datetime import date, datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, Integer, Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.user import User
    from app.models.transcript import Transcript
    from app.models.scores import SpeechScore, SalesScore
    from app.models.summary import Summary
    from app.models.coaching import CoachingClip, Objection


class CallStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    TRANSCRIBING = "TRANSCRIBING"
    ANALYZING = "ANALYZING"
    SCORING = "SCORING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False, index=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    audio_url: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[CallStatus] = mapped_column(SAEnum(CallStatus, name="callstatus"), nullable=False, default=CallStatus.QUEUED, index=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    call_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    disposition: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    speech_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    sales_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    has_keyword_hit: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    agent: Mapped["Agent"] = relationship("Agent", back_populates="calls")
    uploader: Mapped["User"] = relationship("User", foreign_keys=[uploaded_by])
    transcript: Mapped[Optional["Transcript"]] = relationship("Transcript", back_populates="call", uselist=False, cascade="all, delete-orphan")
    speech_score_rel: Mapped[Optional["SpeechScore"]] = relationship("SpeechScore", back_populates="call", uselist=False, cascade="all, delete-orphan")
    sales_score_rel: Mapped[Optional["SalesScore"]] = relationship("SalesScore", back_populates="call", uselist=False, cascade="all, delete-orphan")
    summary: Mapped[Optional["Summary"]] = relationship("Summary", back_populates="call", uselist=False, cascade="all, delete-orphan")
    coaching_clips: Mapped[list["CoachingClip"]] = relationship("CoachingClip", back_populates="call", cascade="all, delete-orphan")
    objections: Mapped[list["Objection"]] = relationship("Objection", back_populates="call", cascade="all, delete-orphan")

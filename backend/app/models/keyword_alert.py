import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Boolean, Integer, JSON, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base

if TYPE_CHECKING:
    from app.models.call import Call


class KeywordAlert(Base):
    __tablename__ = "keyword_alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    keyword: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="CUSTOM")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    hits: Mapped[list["CallKeywordHit"]] = relationship("CallKeywordHit", back_populates="keyword_alert", cascade="all, delete-orphan")


class CallKeywordHit(Base):
    __tablename__ = "call_keyword_hits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, index=True)
    keyword_alert_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("keyword_alerts.id", ondelete="CASCADE"), nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sample_quotes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    keyword_alert: Mapped["KeywordAlert"] = relationship("KeywordAlert", back_populates="hits")

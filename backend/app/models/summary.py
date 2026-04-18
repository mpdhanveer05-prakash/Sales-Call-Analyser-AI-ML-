import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Text, DateTime, ForeignKey, Numeric, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base

if TYPE_CHECKING:
    from app.models.call import Call


class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    key_moments: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    coaching_suggestions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    disposition_confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    disposition_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    call: Mapped["Call"] = relationship("Call", back_populates="summary")

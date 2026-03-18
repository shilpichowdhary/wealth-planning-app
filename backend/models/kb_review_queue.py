import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import String, Text, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base

class ReviewStatus(str, PyEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RESUBMITTED = "resubmitted"
    RE_REJECTED = "re_rejected"

class KBReviewQueue(Base):
    __tablename__ = "kb_review_queue"

    entry_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    jurisdiction: Mapped[str] = mapped_column(String, nullable=False)
    topic: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    web_url: Mapped[str] = mapped_column(String, nullable=False)
    date_retrieved: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    current_status: Mapped[ReviewStatus] = mapped_column(Enum(ReviewStatus), default=ReviewStatus.PENDING)
    reviewed_by: Mapped[str | None] = mapped_column(String, ForeignKey("users.user_id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejection_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resubmission_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_count: Mapped[int] = mapped_column(Integer, default=0)

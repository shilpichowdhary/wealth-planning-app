import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class AuditLog(Base):
    """Append-only record of security/compliance-relevant events.

    Written via backend.services.audit_service.log_event(). The closed
    EVENT_TYPES registry in that module is the source of truth for valid
    event_type strings; values outside it are dropped (and logged at ERROR
    so the typo surfaces) rather than written here.

    actor_user_id is nullable to allow logging pre-authentication events
    (failed logins, SSO failures) where the actor's identity isn't known.
    """

    __tablename__ = "audit_log"

    audit_id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True, nullable=False
    )
    actor_user_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.user_id"), nullable=True
    )
    actor_ip: Mapped[str | None] = mapped_column(String, nullable=True)
    event_type: Mapped[str] = mapped_column(String, index=True, nullable=False)
    target_type: Mapped[str | None] = mapped_column(String, nullable=True)
    target_id: Mapped[str | None] = mapped_column(String, nullable=True)
    outcome: Mapped[str] = mapped_column(String, nullable=False)  # 'success' | 'failure'
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)

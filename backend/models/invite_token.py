from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class InviteToken(Base):
    """One-time magic-link token for advisor onboarding and password setup.

    The token itself is the primary key (URL-safe random, ~256-bit entropy).
    Single-use: once `used_at` is set, the token cannot be redeemed again.
    Expiry is enforced at the endpoint layer against `expires_at`.
    Admins can revoke outstanding invites by setting `revoked=True`
    (e.g. if a fresh invite is issued for the same advisor).
    """

    __tablename__ = "invite_tokens"

    token: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.user_id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String, ForeignKey("users.user_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

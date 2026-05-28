"""Audit logging service.

Usage:
    from backend.services.audit_service import log_event
    await log_event(db, event_type="auth.login.success",
                    actor_user_id=user.user_id, request=request)

All event_type strings must be in EVENT_TYPES — that's the single source of
truth so a typo at a call site is logged at ERROR rather than silently
writing junk to the audit log. Writes never raise into the calling
endpoint: an audit-infrastructure issue must not be able to take down a
business-critical request path.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


EVENT_TYPES: set[str] = {
    # auth
    "auth.login.success",
    "auth.login.failure",
    "auth.sso.success",
    "auth.sso.failure",
    "auth.logout",
    "auth.invite.accept",
    # admin
    "admin.user.create",
    "admin.user.deactivate",
    "admin.user.reset_password",
    "admin.settings.change",
    # cases
    "case.open",
    "case.archive",
    "case.view",
    # kb review
    "kb.review.approve",
    "kb.review.reject",
    "kb.review.resubmit",
    "kb.review.re_reject",
    # system
    "system.startup",
}


def _client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        # X-Forwarded-For can be a chain; the left-most entry is the original client.
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


async def log_event(
    db: AsyncSession,
    *,
    event_type: str,
    actor_user_id: str | None = None,
    request: Request | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    outcome: str = "success",
    detail: dict[str, Any] | None = None,
) -> None:
    """Write one audit event. Never raises.

    Audit-log failures must not break the calling endpoint, so all
    exceptions are caught and logged at WARN. Unknown event_type values
    are logged at ERROR (programming error) and dropped.
    """
    if event_type not in EVENT_TYPES:
        logger.error("Unknown audit event_type: %s", event_type)
        return
    try:
        entry = AuditLog(
            actor_user_id=actor_user_id,
            actor_ip=_client_ip(request),
            event_type=event_type,
            target_type=target_type,
            target_id=target_id,
            outcome=outcome,
            detail=detail,
        )
        db.add(entry)
        await db.commit()
    except Exception:
        logger.warning("Audit log write failed for event %s", event_type, exc_info=True)

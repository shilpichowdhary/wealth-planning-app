from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from backend.database import get_db
from backend.models.audit_log import AuditLog
from backend.models.user import User, UserRole
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/admin/audit", tags=["admin", "audit"])


@router.get("")
async def list_audit_events(
    from_ts: datetime | None = Query(None, alias="from"),
    to_ts: datetime | None = Query(None, alias="to"),
    user_id: str | None = None,
    event_type: str | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin-only query of the audit log with newest-first ordering.

    Hard cap of 500 rows per page; callers paginate via `offset` + `limit`.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin only")

    stmt = select(AuditLog).order_by(desc(AuditLog.occurred_at))
    if from_ts:
        stmt = stmt.where(AuditLog.occurred_at >= from_ts)
    if to_ts:
        stmt = stmt.where(AuditLog.occurred_at <= to_ts)
    if user_id:
        stmt = stmt.where(AuditLog.actor_user_id == user_id)
    if event_type:
        stmt = stmt.where(AuditLog.event_type == event_type)
    stmt = stmt.offset(offset).limit(limit)

    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "audit_id": r.audit_id,
            "occurred_at": r.occurred_at.isoformat(),
            "actor_user_id": r.actor_user_id,
            "actor_ip": r.actor_ip,
            "event_type": r.event_type,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "outcome": r.outcome,
            "detail": r.detail,
        }
        for r in rows
    ]

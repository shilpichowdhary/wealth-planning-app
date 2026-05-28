import pytest
from sqlalchemy import select

from backend.main import app
from backend.models.audit_log import AuditLog
from backend.models.kb_review_queue import KBReviewQueue, ReviewStatus
from backend.kb.kb_manager import KBManager
from backend.routers.kb import get_kb_manager


@pytest.fixture
def kb_override(tmp_path):
    """Mirror test_kb_review's fixture so the approve path writes into a
    tmp ChromaDB instead of polluting the dev KB."""
    manager = KBManager(chroma_path=str(tmp_path / "chroma"))
    app.dependency_overrides[get_kb_manager] = lambda: manager
    yield manager
    app.dependency_overrides.pop(get_kb_manager, None)


@pytest.mark.asyncio
async def test_login_success_writes_audit_event(async_client, db_session):
    from backend.models.user import User, UserRole
    from backend.services.auth_service import hash_password

    user = User(
        name="Audit Test",
        email="audit@test.com",
        hashed_password=hash_password("AuditPass-2026!"),
        role=UserRole.ADVISOR,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    r = await async_client.post(
        "/auth/token",
        data={"username": "audit@test.com", "password": "AuditPass-2026!"},
    )
    assert r.status_code == 200, r.text

    rows = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.event_type == "auth.login.success")
        )
    ).scalars().all()
    assert any(row.actor_user_id == user.user_id for row in rows)


@pytest.mark.asyncio
async def test_login_failure_writes_audit_event(async_client, db_session):
    r = await async_client.post(
        "/auth/token",
        data={"username": "nobody@test.com", "password": "wrong"},
    )
    assert r.status_code == 401

    rows = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.event_type == "auth.login.failure")
        )
    ).scalars().all()
    assert len(rows) >= 1
    assert rows[-1].outcome == "failure"
    assert rows[-1].detail.get("email") == "nobody@test.com"


@pytest.mark.asyncio
async def test_kb_review_approve_writes_audit_event(
    async_client, auth_headers, db_session, kb_override
):
    entry = KBReviewQueue(
        jurisdiction="IN",
        topic="x",
        content="c",
        web_url="https://x",
        current_status=ReviewStatus.PENDING,
    )
    db_session.add(entry)
    await db_session.commit()
    await db_session.refresh(entry)

    r = await async_client.post(
        f"/kb/review-queue/{entry.entry_id}/action",
        json={"action": "approve"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text

    rows = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.event_type == "kb.review.approve")
        )
    ).scalars().all()
    assert len(rows) >= 1
    assert rows[-1].target_type == "kb_entry"
    assert rows[-1].target_id == entry.entry_id


@pytest.mark.asyncio
async def test_unknown_event_type_does_not_raise(db_session):
    """Mistyped event_type should be logged at ERROR and otherwise dropped."""
    from backend.services.audit_service import log_event

    await log_event(db_session, event_type="not.a.real.event")
    rows = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.event_type == "not.a.real.event")
        )
    ).scalars().all()
    assert rows == []

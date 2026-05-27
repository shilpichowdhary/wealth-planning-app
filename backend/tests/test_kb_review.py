import pytest
from backend.main import app
from backend.models.kb_review_queue import KBReviewQueue, ReviewStatus
from backend.routers.kb import get_kb_manager
from backend.kb.kb_manager import KBManager


@pytest.fixture
def kb_override(tmp_path):
    """Override the kb manager dependency to write into a tmp ChromaDB so
    the approve path doesn't pollute the dev KB."""
    manager = KBManager(chroma_path=str(tmp_path / "chroma"))
    app.dependency_overrides[get_kb_manager] = lambda: manager
    yield manager
    app.dependency_overrides.pop(get_kb_manager, None)


async def _seed_entry(db_session, status=ReviewStatus.PENDING, **kwargs):
    entry = KBReviewQueue(
        jurisdiction="India",
        topic="trust-taxation",
        content="Sample content for review.",
        web_url="https://example.com/x",
        current_status=status,
        **kwargs,
    )
    db_session.add(entry)
    await db_session.commit()
    await db_session.refresh(entry)
    return entry


@pytest.mark.asyncio
async def test_approve_from_resubmitted_lands_approved(async_client, auth_headers, db_session, kb_override):
    entry = await _seed_entry(db_session, status=ReviewStatus.RESUBMITTED)
    r = await async_client.post(
        f"/kb/review-queue/{entry.entry_id}/action",
        json={"action": "approve"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    await db_session.refresh(entry)
    assert entry.current_status == ReviewStatus.APPROVED


@pytest.mark.asyncio
async def test_reject_from_resubmitted_lands_re_rejected(async_client, auth_headers, db_session, kb_override):
    entry = await _seed_entry(db_session, status=ReviewStatus.RESUBMITTED)
    r = await async_client.post(
        f"/kb/review-queue/{entry.entry_id}/action",
        json={"action": "reject", "note": "still not credible"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    await db_session.refresh(entry)
    assert entry.current_status == ReviewStatus.RE_REJECTED


@pytest.mark.asyncio
async def test_resubmit_from_re_rejected_is_rejected(async_client, auth_headers, db_session, kb_override):
    entry = await _seed_entry(db_session, status=ReviewStatus.RE_REJECTED)
    r = await async_client.post(
        f"/kb/review-queue/{entry.entry_id}/action",
        json={"action": "resubmit", "note": "please reconsider"},
        headers=auth_headers,
    )
    assert r.status_code == 400, r.text
    await db_session.refresh(entry)
    assert entry.current_status == ReviewStatus.RE_REJECTED


@pytest.mark.asyncio
async def test_full_cycle_pending_rejected_resubmitted_approved(async_client, auth_headers, db_session, kb_override):
    entry = await _seed_entry(db_session, status=ReviewStatus.PENDING)
    eid = entry.entry_id

    r = await async_client.post(
        f"/kb/review-queue/{eid}/action",
        json={"action": "reject", "note": "n"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text

    r = await async_client.post(
        f"/kb/review-queue/{eid}/action",
        json={"action": "resubmit", "note": "n"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text

    r = await async_client.post(
        f"/kb/review-queue/{eid}/action",
        json={"action": "approve"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    await db_session.refresh(entry)
    assert entry.current_status == ReviewStatus.APPROVED

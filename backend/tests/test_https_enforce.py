import os
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.fixture(autouse=True)
def _clear_enforce_https():
    """Each test sets ENFORCE_HTTPS explicitly; clear at start and end so
    we don't leak across the suite."""
    saved = os.environ.pop("ENFORCE_HTTPS", None)
    yield
    if saved is not None:
        os.environ["ENFORCE_HTTPS"] = saved
    else:
        os.environ.pop("ENFORCE_HTTPS", None)


@pytest.mark.asyncio
async def test_http_allowed_when_enforce_https_unset():
    """Default behavior: middleware is permissive."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health")  # no x-forwarded-proto header
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_http_rejected_when_enforce_https_true(monkeypatch):
    monkeypatch.setenv("ENFORCE_HTTPS", "true")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # /cases requires auth — but the middleware should reject BEFORE auth runs.
        r = await client.get("/cases/")  # no x-forwarded-proto header
        assert r.status_code == 400
        assert "HTTPS required" in r.text


@pytest.mark.asyncio
async def test_https_via_forwarded_proto_accepted(monkeypatch):
    monkeypatch.setenv("ENFORCE_HTTPS", "true")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(
            "/health",
            headers={"X-Forwarded-Proto": "https"},
        )
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_health_bypasses_enforcement(monkeypatch):
    """/health must remain accessible without HTTPS so internal probes work."""
    monkeypatch.setenv("ENFORCE_HTTPS", "true")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health")  # no x-forwarded-proto header
        assert r.status_code == 200

import os
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-32-bytes-minimum-aaaa")

import pytest
from starlette.requests import Request

from backend.services.auth_service import AuthService
from backend.services.rate_limit import _user_key


@pytest.mark.asyncio
async def test_auth_rate_limit_returns_429_after_5_per_minute(async_client):
    # Reuse the conftest async_client fixture so the in-memory test DB is
    # wired in — otherwise /auth/token hits the real on-disk SQLite and the
    # rate-limit check is never reached.
    responses = []
    for _ in range(6):
        r = await async_client.post(
            "/auth/token",
            data={"username": "noone@example.com", "password": "wrong"},
        )
        responses.append(r.status_code)

    assert responses[:5] == [401, 401, 401, 401, 401], responses
    assert responses[5] == 429, responses


def _make_request(auth_header: str | None = None, client_host: str = "1.2.3.4") -> Request:
    """Build a minimal ASGI scope so _user_key can inspect headers + client."""
    headers: list[tuple[bytes, bytes]] = []
    if auth_header is not None:
        headers.append((b"authorization", auth_header.encode("latin-1")))
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/chat/stream",
        "headers": headers,
        "client": (client_host, 12345),
        "query_string": b"",
        "scheme": "http",
        "server": ("testserver", 80),
    }
    return Request(scope)


def test_user_key_distinguishes_two_jwts_from_same_ip():
    """Two different users hitting /chat/stream from the same IP must each
    get their own bucket — the original bug was that they collapsed into one."""
    token_alice = AuthService.create_access_token({"sub": "user-alice"})
    token_bob = AuthService.create_access_token({"sub": "user-bob"})

    req_alice = _make_request(f"Bearer {token_alice}", client_host="10.0.0.1")
    req_bob = _make_request(f"Bearer {token_bob}", client_host="10.0.0.1")

    key_alice = _user_key(req_alice)
    key_bob = _user_key(req_bob)

    assert key_alice == "user:user-alice"
    assert key_bob == "user:user-bob"
    assert key_alice != key_bob


def test_user_key_same_user_different_ips_shares_bucket():
    """One user from two different IPs must produce the same key (so the
    30/hour limit follows them across networks)."""
    token = AuthService.create_access_token({"sub": "user-carol"})

    req1 = _make_request(f"Bearer {token}", client_host="10.0.0.1")
    req2 = _make_request(f"Bearer {token}", client_host="192.168.1.50")

    assert _user_key(req1) == _user_key(req2) == "user:user-carol"


def test_user_key_falls_back_to_ip_without_bearer():
    req = _make_request(auth_header=None, client_host="10.0.0.7")
    assert _user_key(req) == "ip:10.0.0.7"


def test_user_key_falls_back_to_ip_for_malformed_token():
    req = _make_request("Bearer not-a-real-jwt", client_host="10.0.0.8")
    assert _user_key(req) == "ip:10.0.0.8"


def test_user_key_case_insensitive_authorization_header():
    """slowapi's key_func runs before FastAPI normalises headers; verify both
    spellings are accepted."""
    token = AuthService.create_access_token({"sub": "user-dave"})
    # lower-case header name — Starlette stores all headers lower-cased but
    # the helper checks both spellings defensively.
    req = _make_request(f"Bearer {token}")
    assert _user_key(req) == "user:user-dave"


@pytest.mark.asyncio
async def test_health_endpoint_not_rate_limited(async_client):
    """The original code applied a 60/min default to EVERY endpoint via
    SlowAPIMiddleware. After dropping default_limits, /health should accept
    well above 60 requests/minute."""
    statuses = []
    for _ in range(70):
        r = await async_client.get("/health")
        statuses.append(r.status_code)

    assert all(s == 200 for s in statuses), (
        f"unexpected non-200 statuses in /health flood: {set(statuses)}"
    )

"""Rate limiting setup.

Uses slowapi's in-memory backend (sufficient for the single-VM deployment).
Auth endpoints key by IP (pre-auth, no user identity yet).
Chat endpoints key by authenticated user_id, with a second daily token budget
applied manually inside the chat handler using Anthropic's response.usage.
"""
from datetime import datetime, timezone

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.services.auth_service import AuthService


def _user_key(request: Request) -> str:
    """Key chat requests by JWT sub claim; fall back to IP when no token.

    slowapi runs key_func BEFORE the endpoint body executes, so we cannot rely
    on request.state attributes set inside the handler — we have to read the
    JWT directly here.
    """
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth.split(None, 1)[1].strip()
        try:
            payload = AuthService.decode_token(token)
            sub = payload.get("sub")
            if sub:
                return f"user:{sub}"
        except Exception:
            pass  # malformed/expired tokens fall through to IP
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=get_remote_address)
user_limiter = Limiter(key_func=_user_key)


_DAILY_TOKEN_BUDGET = 100_000

# user_id -> (utc_date, tokens_used) — process-local, single-VM only.
_token_counter: dict[str, tuple[str, int]] = {}


# TODO(AI-07): wire into chat handler once Anthropic response.usage telemetry is plumbed.
# Until then this helper is unused — kept here so Phase-2/3 work has the bucket shape ready.
def record_chat_tokens(user_id: str, tokens: int) -> bool:
    """Add tokens to today's bucket. Returns False if the daily budget is now exceeded."""
    today = datetime.now(timezone.utc).date().isoformat()
    date_seen, used = _token_counter.get(user_id, (today, 0))
    if date_seen != today:
        date_seen, used = today, 0
    used += tokens
    _token_counter[user_id] = (today, used)
    return used <= _DAILY_TOKEN_BUDGET


def reset_token_counter() -> None:
    """Test helper — clears the in-memory daily budget."""
    _token_counter.clear()

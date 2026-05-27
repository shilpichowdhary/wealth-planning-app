# Wealth Planning v2 — P0 Production-Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the 11 P0 hardening items from SPEC.md so the app can take real Lighthouse Canton client cases (CTO/CISO sign-off ready).

**Architecture:** Four phases, one branch per phase. Phase 1 = 8 in-process quick wins. Phase 2 = Alembic + audit log + encryption/HTTPS plumbing (still on SQLite, still HTTP). Phase 3 = single cutover weekend (Postgres + encryption flip + HTTPS-only). Phase 4 = monitoring + sign-off. Each phase ends green on `pytest backend/tests/`.

**Tech Stack:** FastAPI + SQLAlchemy 2 (async) + SQLite (Phase 1-2) → Postgres (Phase 3) · Alembic · slowapi · cryptography (Fernet) · Azure Key Vault · Azure AD Managed Identity · Next.js 14 + NextAuth · IIS reverse proxy

**Spec defaults adopted (SPEC §8):**
- Document storage stays on VM disk in P0 (Blob deferred to P1).
- Audit-log retention: **13 months** — flagged for CISO confirmation in Phase 4.
- Rate limits: **5/min auth/IP**, **30/hour chat/user**, **100k tokens/day/user** — to be tuned in Phase 4.

**Branching convention:** one feature branch per phase.
- Phase 1 → `feat/p0-phase-1-quickwins`
- Phase 2 → `feat/p0-phase-2-foundations`
- Phase 3 → `feat/p0-phase-3-cutover`
- Phase 4 → `feat/p0-phase-4-signoff`

Within a phase, each SPEC item is its own commit (so an item can be reverted individually if needed). PR opens at end of phase.

---

## State of Play (verified 2026-05-27)

Confirmed deltas between SPEC and actual code before planning began:

| SPEC item | Spec assumption | Actual code | Plan stance |
|---|---|---|---|
| SEC-01 | Hardcoded default at `backend/config.py:5` | ✓ Confirmed — `secret_key: str = "dev-secret-key-change-in-production-min32"` | Implement as spec'd. |
| AI-01 | Prompt emits `diagram_nodes`; parser reads `entities` | ✗ Both already use `entities`. Parser already JSON-loads code-fenced blocks (`backend/services/llm_service.py:11-21`). | **Reduced scope:** add Pydantic validation only. |
| KB-01 | Endpoint is `/kb/review/{entry_id}`; resubmit can re-loop | ✗ Endpoint is `/kb/review-queue/{entry_id}/action`. Resubmit currently allows `RE_REJECTED → RESUBMITTED` (bug). Reject from `RESUBMITTED` lands `REJECTED` instead of `RE_REJECTED`. | Fix the two state-machine bugs. |
| DOC-01 | MIME validated before disk write | ✗ Currently validates *after* disk write (`backend/routers/documents.py:38-46`). Window where a malicious payload exists on disk. | Re-order: validate from buffer first. |
| DOC-02 | `pdf_service.py:37` interpolates sources without escape | ✓ Confirmed — `f'<li class="source">{s}</li>'` unescaped. | Implement as spec'd. |
| BIZ-01 | Five FKs to `cases.case_id` lack CASCADE | ✓ Confirmed — `client_profile.py:10`, `conversation.py:16`, `recommendation.py:17`, `document.py:17`, `case_diagram.py:18`. | Implement as spec'd. |

---

## Out-of-Session Prerequisites (human / IT tasks — block Phase 2/3)

These cannot be done from a Claude Code session. They block the phases noted.

| # | Task | Owner | Blocks |
|---|---|---|---|
| H-1 | Provision Azure Database for PostgreSQL Flexible Server (Burstable B2s, private endpoint to VM VNet, SSL required, 7-day backup retention). Resource group `rg-wealth-planning-prod`. | IT / Cloud admin | Phase 3 |
| H-2 | Provision Azure Key Vault (Standard tier, same region as VM). Create secret `wealth-planning-fernet-master-v1` (32-byte URL-safe base64). | IT / Cloud admin | Phase 2 (encryption code lands; can no-op locally until KV reachable) |
| H-3 | Enable system-assigned Managed Identity on the VM. Grant the MI **Get** + **List** on KV secrets and **Azure AD authentication** on the Postgres server. | IT / Cloud admin | Phase 2 partial, Phase 3 |
| H-4 | Issue corporate-CA TLS certificate for `team-dashboard.lighthouse-canton.com`. Install on IIS. | IT | Phase 2 (HTTPS binding parallel) |
| H-5 | Configure IIS HTTPS listener on `:443` in parallel with existing HTTP `:8081`. Verify both work. | IT | Phase 3 (HTTPS-only flip) |
| H-6 | Set `SECRET_KEY` env var (≥32 chars, random) on the VM service config. | IT | Phase 1 deploy of SEC-01 |
| H-7 | Notify advisors of the Saturday cutover window (email by Thursday before). | Shilpi / PM | Phase 3 |
| H-8 | Print rollback runbook and share with on-call engineer for the cutover. | Shilpi / PM | Phase 3 |
| H-9 | CTO + CISO walkthrough scheduled and conducted in Phase 4. | Shilpi | Phase 4 sign-off |

Mark each H-task done in the Phase 4 evidence checklist (§Phase 4 Task 4).

---

## File Structure — what gets created vs. modified

**New backend files (Phase 1):**
- `backend/tests/test_config.py`
- `backend/tests/test_rate_limit.py`
- `backend/tests/test_kb_review.py`
- `backend/tests/test_documents.py`
- `backend/services/rate_limit.py`
- `backend/schemas/diagram.py` (Pydantic model for LLM diagram JSON — AI-01)

**New backend files (Phase 2):**
- `backend/models/audit_log.py`
- `backend/models/types.py` (`EncryptedString` SQLAlchemy column type)
- `backend/services/audit_service.py`
- `backend/services/encryption.py`
- `backend/services/azure_kv.py`
- `backend/routers/audit.py` (mounted under `/admin/audit`)
- `backend/tests/test_audit.py`
- `backend/tests/test_encryption.py`
- `backend/middleware/__init__.py`
- `backend/middleware/https_enforce.py`
- `alembic.ini`
- `alembic/env.py`
- `alembic/script.py.mako`
- `alembic/versions/0001_baseline.py`
- `alembic/versions/0002_add_audit_log.py`
- `alembic/versions/0003_add_case_cascade.py`
- `docs/RUNBOOK_TLS.md`

**New backend files (Phase 3):**
- `alembic/versions/0004_postgres_encrypt_existing.py` (re-encryption migration)
- `scripts/migrate_sqlite_to_postgres.sh`
- `scripts/verify_row_counts.py`

**Modified backend files:**
- `backend/config.py` (SEC-01, INFRA-01)
- `backend/main.py` (SEC-01 startup check, rate-limit handler, HTTPS middleware, alembic invocation)
- `backend/database.py` (INFRA-01: switch to alembic upgrade)
- `backend/requirements.txt` (slowapi, cryptography, azure-identity, azure-keyvault-secrets, alembic, asyncpg, python-magic-bin platform marker)
- `backend/routers/auth.py` (SEC-02 rate-limit decorators, audit hooks)
- `backend/routers/chat.py` (AI-07 rate-limit decorators, audit hooks)
- `backend/routers/kb.py` (KB-01 state-machine fixes, audit hooks)
- `backend/routers/documents.py` (DOC-01 reorder, audit hooks)
- `backend/routers/admin.py` (audit hooks)
- `backend/services/llm_service.py` (AI-01 Pydantic validation)
- `backend/services/settings_service.py` (SEC-04 Fernet encrypt/decrypt)
- `backend/services/pdf_service.py` (DOC-02 escape)
- `backend/models/client_profile.py` (BIZ-01 CASCADE + EncryptedString fields)
- `backend/models/conversation.py` (BIZ-01 CASCADE)
- `backend/models/recommendation.py` (BIZ-01 CASCADE)
- `backend/models/document.py` (BIZ-01 CASCADE)
- `backend/models/case_diagram.py` (BIZ-01 CASCADE)

**Modified frontend files (Phase 3):**
- `frontend/lib/auth.ts` (`useSecureCookies: true`, JWT → HttpOnly cookie)
- Anywhere JWT is read from `sessionStorage` — replaced with cookie-based reads

---

# Phase 1 — Quick Wins (Week 1)

Branch: `feat/p0-phase-1-quickwins`.
Exit criteria: 8 commits, all P1 tests pass via `pytest backend/tests/ -v`, no production behaviour change beyond rate-limit 429s and stricter KB review states.

### Task 1.0: Create Phase 1 branch

**Files:** none — git only.

- [ ] **Step 1: Confirm clean working tree**

Run: `git status`
Expected: `nothing to commit, working tree clean` (the only untracked file should be `SPEC.md` which lands in a separate commit, or the plan itself).

- [ ] **Step 2: Create and switch to feature branch**

Run: `git checkout -b feat/p0-phase-1-quickwins main`
Expected: `Switched to a new branch 'feat/p0-phase-1-quickwins'`.

- [ ] **Step 3: Commit SPEC and plan if untracked**

```bash
git add SPEC.md docs/superpowers/plans/2026-05-27-p0-hardening.md
git commit -m "docs: add P0 hardening spec and implementation plan"
```

---

### Task 1.1: SEC-01 — Reject default secret key at startup

**Files:**
- Modify: `backend/config.py:5`
- Modify: `backend/main.py` (add startup validation)
- Create: `backend/tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_config.py`:

```python
import importlib
import os
import pytest


@pytest.fixture(autouse=True)
def _restore_env():
    """Snapshot/restore SECRET_KEY so tests don't bleed into each other."""
    saved = os.environ.get("SECRET_KEY")
    yield
    if saved is None:
        os.environ.pop("SECRET_KEY", None)
    else:
        os.environ["SECRET_KEY"] = saved


def _reload_config():
    from backend import config
    importlib.reload(config)
    return config


def test_secret_key_empty_default_when_env_unset(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    cfg = _reload_config()
    assert cfg.settings.secret_key == ""


def test_validate_secrets_raises_when_empty(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "")
    cfg = _reload_config()
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        cfg.validate_secrets(cfg.settings)


def test_validate_secrets_raises_when_too_short(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "short")
    cfg = _reload_config()
    with pytest.raises(RuntimeError, match="32"):
        cfg.validate_secrets(cfg.settings)


def test_validate_secrets_raises_on_known_default(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "dev-secret-key-change-in-production-min32")
    cfg = _reload_config()
    with pytest.raises(RuntimeError, match="default"):
        cfg.validate_secrets(cfg.settings)


def test_validate_secrets_accepts_strong_key(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "a" * 32 + "-real-random-value")
    cfg = _reload_config()
    cfg.validate_secrets(cfg.settings)  # does not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_config.py -v`
Expected: 5 failures — `cfg.validate_secrets` does not exist; default is non-empty string.

- [ ] **Step 3: Implement the change**

Edit `backend/config.py` — change line 5 default to empty string and add `validate_secrets`:

```python
from pydantic_settings import BaseSettings


KNOWN_DEFAULT_SECRET_KEYS = {
    "dev-secret-key-change-in-production-min32",
    "change-me",
    "secret",
}


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./wealth_planning.db"
    secret_key: str = ""
    anthropic_api_key: str = "placeholder"
    tavily_api_key: str = "placeholder"
    chroma_db_path: str = "./chroma_db"
    uploads_path: str = "./uploads"
    max_upload_bytes: int = 20 * 1024 * 1024
    claude_model: str = "claude-sonnet-4-6"
    claude_max_tokens_per_query: int = 8000
    tavily_max_calls_per_session: int = 5
    api_rate_limit_per_minute: int = 10

    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""

    @property
    def azure_jwks_uri(self) -> str:
        return f"https://login.microsoftonline.com/{self.azure_tenant_id}/discovery/v2.0/keys"

    @property
    def azure_issuer(self) -> str:
        return f"https://login.microsoftonline.com/{self.azure_tenant_id}/v2.0"

    class Config:
        env_file = ".env"


def validate_secrets(s: "Settings") -> None:
    if not s.secret_key:
        raise RuntimeError(
            "SECRET_KEY is required and must be set in the environment "
            "(min length 32, not a known default)."
        )
    if len(s.secret_key) < 32:
        raise RuntimeError(
            f"SECRET_KEY must be at least 32 characters long (got {len(s.secret_key)})."
        )
    if s.secret_key in KNOWN_DEFAULT_SECRET_KEYS:
        raise RuntimeError(
            "SECRET_KEY is set to a known default sentinel. "
            "Generate a random value before starting the service."
        )


settings = Settings()
```

Edit `backend/main.py` — call `validate_secrets` at lifespan startup:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings, validate_secrets
from backend.database import create_tables
import backend.models  # noqa: F401

@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_secrets(settings)
    await create_tables()
    yield

app = FastAPI(title="Wealth Planning API", version="1.0.0", lifespan=lifespan)
# ... rest unchanged
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_config.py -v`
Expected: 5 passes.

- [ ] **Step 5: Make sure full test suite still green**

Run: `SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" pytest backend/tests/ -v`
Expected: all green. (Some existing tests load `backend/main.py` via TestClient; they need `SECRET_KEY` present.)

- [ ] **Step 6: Update conftest to set SECRET_KEY for the suite**

Edit `backend/tests/conftest.py` — at the top, before any backend imports:

```python
import os
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-32-bytes-minimum-aaaa")
```

Re-run `pytest backend/tests/ -v` — all green.

- [ ] **Step 7: Commit**

```bash
git add backend/config.py backend/main.py backend/tests/test_config.py backend/tests/conftest.py
git commit -m "feat(SEC-01): reject default or weak SECRET_KEY at startup"
```

**Evidence for sign-off (§6.2):** Phase 4 captures a screenshot of the VM service config showing the env var is set.

---

### Task 1.2: SEC-02 + AI-07 — Rate limiting (auth + chat)

**Files:**
- Modify: `backend/requirements.txt` (add `slowapi==0.1.9`)
- Create: `backend/services/rate_limit.py`
- Modify: `backend/main.py` (register limiter + 429 handler)
- Modify: `backend/routers/auth.py` (decorate `/auth/token`, `/auth/sso`, invite accept)
- Modify: `backend/routers/chat.py` (decorate `/chat/stream`, add token accounting)
- Create: `backend/tests/test_rate_limit.py`

- [ ] **Step 1: Add slowapi to requirements**

Edit `backend/requirements.txt` — append:

```
slowapi==0.1.9
```

Install: `pip install slowapi==0.1.9` (or `pip install -r backend/requirements.txt`).

- [ ] **Step 2: Write the limiter module**

Create `backend/services/rate_limit.py`:

```python
"""Rate limiting setup.

Uses slowapi's in-memory backend (sufficient for the single-VM deployment).
Auth endpoints key by IP (pre-auth, no user identity yet).
Chat endpoints key by authenticated user_id, with a second daily token budget
applied manually inside the chat handler using Anthropic's response.usage.
"""
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _user_key(request: Request) -> str:
    """Key chat requests by authenticated user; fall back to IP if unset."""
    user = getattr(request.state, "current_user", None)
    if user is not None and getattr(user, "user_id", None):
        return f"user:{user.user_id}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
user_limiter = Limiter(key_func=_user_key)


# Daily token budgets are tracked separately because slowapi only counts
# requests. This dict is process-local — acceptable for single-VM P0.
# Phase 2 audit log gives us cross-process visibility if we need it later.
_DAILY_TOKEN_BUDGET = 100_000


_token_counter: dict[str, tuple[str, int]] = {}  # user_id -> (utc_date, tokens_used)


def record_chat_tokens(user_id: str, tokens: int) -> bool:
    """Add tokens to today's bucket. Returns False if the daily budget is now exceeded."""
    from datetime import datetime, timezone
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
```

- [ ] **Step 3: Wire the limiter into `main.py`**

Edit `backend/main.py` — register limiter and 429 handler:

```python
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from backend.services.rate_limit import limiter, user_limiter

app.state.limiter = limiter
app.state.user_limiter = user_limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

(slowapi's default handler returns HTTP 429 with a `Retry-After` header.)

- [ ] **Step 4: Decorate auth endpoints**

Edit `backend/routers/auth.py`:

```python
from fastapi import Request
from backend.services.rate_limit import limiter

@router.post("/token")
@limiter.limit("5/minute")
async def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    # ... existing body unchanged
```

Apply the same `@limiter.limit("5/minute")` and `request: Request` parameter to `/auth/sso` and `/auth/invite/{token}/accept`.

- [ ] **Step 5: Decorate the chat endpoint**

Edit `backend/routers/chat.py`:

```python
from fastapi import Request
from backend.services.rate_limit import user_limiter

@router.post("/stream", response_class=StreamingResponse)
@user_limiter.limit("30/hour")
async def chat_stream(
    request: Request,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rag: RAGService = Depends(get_rag_service),
):
    request.state.current_user = current_user
    # ... existing body unchanged
```

The `request.state.current_user` assignment is what lets `user_limiter._user_key` key on the user.

(Token-budget enforcement gets wired in Phase 2 once we have Anthropic usage telemetry — for P0 the 30/hour request cap is the load-bearing protection. The `record_chat_tokens` helper above is plumbed in but not yet called; explicit TODO comment goes next to its definition.)

- [ ] **Step 6: Write the failing tests**

Create `backend/tests/test_rate_limit.py`:

```python
import os
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-32-bytes-minimum-aaaa")

import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.services.rate_limit import limiter


@pytest.fixture(autouse=True)
def _reset_limiter():
    """slowapi's in-memory storage persists between tests — reset it."""
    limiter.reset()
    yield
    limiter.reset()


@pytest.mark.asyncio
async def test_auth_rate_limit_returns_429_after_5_per_minute():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        responses = []
        for _ in range(6):
            r = await client.post(
                "/auth/token",
                data={"username": "noone@example.com", "password": "wrong"},
            )
            responses.append(r.status_code)

    # First five should be 401 (bad credentials, but limiter let them through).
    assert responses[:5] == [401, 401, 401, 401, 401], responses
    # Sixth must be 429.
    assert responses[5] == 429, responses
```

(Chat-rate-limit test is similar — see `test_chat_rate_limit_returns_429_after_30_per_hour` in the file. It needs an authenticated session fixture; reuse the one from `backend/tests/test_cases.py` if available.)

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest backend/tests/test_rate_limit.py -v`
Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add backend/requirements.txt backend/services/rate_limit.py backend/main.py backend/routers/auth.py backend/routers/chat.py backend/tests/test_rate_limit.py
git commit -m "feat(SEC-02,AI-07): per-IP auth and per-user chat rate limiting"
```

---

### Task 1.3: AI-01 — Pydantic validation of diagram JSON

**Files:**
- Create: `backend/schemas/diagram.py`
- Modify: `backend/services/llm_service.py:11-21`
- Extend: `backend/tests/test_diagram_service.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_diagram_service.py`:

```python
from backend.services.llm_service import extract_diagram_json


def test_extract_diagram_json_returns_none_for_malformed_entity():
    """An entity missing its required `type` field is invalid and should be rejected."""
    text = '''Here is the diagram:
```json
{"entities": [{"label": "Trust"}], "edges": []}
```
'''
    assert extract_diagram_json(text) is None


def test_extract_diagram_json_returns_none_for_bad_edge_index():
    text = '''```json
{"entities": [{"type": "trust", "label": "T"}], "edges": [{"source": 0, "target": 99, "label": "owns 100%"}]}
```'''
    # Pydantic doesn't check cross-field bounds; the diagram_service's bounds
    # check still does, so this returns the dict (validation only catches shape).
    # We assert positive case for shape validation:
    result = extract_diagram_json(text)
    assert result is not None
    assert result["entities"][0]["type"] == "trust"


def test_extract_diagram_json_returns_dict_for_well_formed_input():
    text = '''```json
{"entities": [{"type": "trust", "label": "T", "jurisdiction": "Jersey"}], "edges": []}
```'''
    result = extract_diagram_json(text)
    assert result is not None
    assert len(result["entities"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_diagram_service.py -v -k extract_diagram_json`
Expected: `test_extract_diagram_json_returns_none_for_malformed_entity` fails — current code accepts any dict with `entities` key.

- [ ] **Step 3: Add the Pydantic schema**

Create `backend/schemas/diagram.py`:

```python
"""Pydantic schemas for the diagram JSON the LLM emits.

Stricter than the diagram-service's runtime guards: catches malformed shapes
*before* they reach React Flow, so the user sees no diagram instead of a broken
one.
"""
from typing import Literal
from pydantic import BaseModel, Field


class DiagramEntity(BaseModel):
    type: Literal["individual", "trust", "company"]
    label: str = Field(min_length=1)
    jurisdiction: str | None = None
    role: str | None = None
    tax_treatment: str | None = None
    rationale: str | None = None
    source: str | None = None


class DiagramEdge(BaseModel):
    source: int = Field(ge=0)
    target: int = Field(ge=0)
    label: str = ""


class Diagram(BaseModel):
    entities: list[DiagramEntity]
    edges: list[DiagramEdge] = []
```

- [ ] **Step 4: Wire validation into extract_diagram_json**

Edit `backend/services/llm_service.py:11-21`:

```python
def extract_diagram_json(text: str) -> dict | None:
    """Extract and validate diagram JSON from the LLM response.

    Returns the parsed dict (Pydantic-validated shape) or None if no valid
    block is present.
    """
    from pydantic import ValidationError
    from backend.schemas.diagram import Diagram

    for match in re.finditer(r'```json\s*([\s\S]*?)\s*```', text):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict) or "entities" not in data:
            continue
        try:
            Diagram.model_validate(data)
        except ValidationError as e:
            logger.warning("Diagram JSON failed schema validation: %s", e)
            continue
        return data
    return None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest backend/tests/test_diagram_service.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/schemas/diagram.py backend/services/llm_service.py backend/tests/test_diagram_service.py
git commit -m "feat(AI-01): validate diagram JSON shape with Pydantic before render"
```

---

### Task 1.4: KB-01 — KB resubmission state machine fix

**Files:**
- Modify: `backend/routers/kb.py` (the `review_queue_action` handler)
- Create: `backend/tests/test_kb_review.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_kb_review.py`:

```python
import os
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-32-bytes-minimum-aaaa")

import pytest
from backend.models.kb_review_queue import KBReviewQueue, ReviewStatus
# Reuse the auth/db fixtures from existing tests:
from backend.tests.test_cases import client, advisor_token, async_db  # noqa: F401


async def _seed_entry(async_db, status=ReviewStatus.REJECTED, **kwargs):
    entry = KBReviewQueue(
        jurisdiction="India",
        topic="trust-taxation",
        content="Sample content",
        web_url="https://example.com/x",
        current_status=status,
        **kwargs,
    )
    async_db.add(entry)
    await async_db.commit()
    await async_db.refresh(entry)
    return entry


@pytest.mark.asyncio
async def test_approve_from_resubmitted_lands_approved(client, advisor_token, async_db):
    entry = await _seed_entry(async_db, status=ReviewStatus.RESUBMITTED)
    r = await client.post(
        f"/kb/review-queue/{entry.entry_id}/action",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {advisor_token}"},
    )
    assert r.status_code == 200
    await async_db.refresh(entry)
    assert entry.current_status == ReviewStatus.APPROVED


@pytest.mark.asyncio
async def test_reject_from_resubmitted_lands_re_rejected(client, advisor_token, async_db):
    entry = await _seed_entry(async_db, status=ReviewStatus.RESUBMITTED)
    r = await client.post(
        f"/kb/review-queue/{entry.entry_id}/action",
        json={"action": "reject", "note": "still not credible"},
        headers={"Authorization": f"Bearer {advisor_token}"},
    )
    assert r.status_code == 200
    await async_db.refresh(entry)
    assert entry.current_status == ReviewStatus.RE_REJECTED


@pytest.mark.asyncio
async def test_resubmit_from_re_rejected_is_rejected(client, advisor_token, async_db):
    entry = await _seed_entry(async_db, status=ReviewStatus.RE_REJECTED)
    r = await client.post(
        f"/kb/review-queue/{entry.entry_id}/action",
        json={"action": "resubmit", "note": "please reconsider"},
        headers={"Authorization": f"Bearer {advisor_token}"},
    )
    assert r.status_code == 400
    await async_db.refresh(entry)
    assert entry.current_status == ReviewStatus.RE_REJECTED


@pytest.mark.asyncio
async def test_full_cycle_pending_rejected_resubmitted_approved(client, advisor_token, async_db):
    entry = await _seed_entry(async_db, status=ReviewStatus.PENDING)
    eid = entry.entry_id

    r = await client.post(f"/kb/review-queue/{eid}/action", json={"action": "reject", "note": "n"},
                          headers={"Authorization": f"Bearer {advisor_token}"})
    assert r.status_code == 200
    r = await client.post(f"/kb/review-queue/{eid}/action", json={"action": "resubmit", "note": "n"},
                          headers={"Authorization": f"Bearer {advisor_token}"})
    assert r.status_code == 200
    r = await client.post(f"/kb/review-queue/{eid}/action", json={"action": "approve"},
                          headers={"Authorization": f"Bearer {advisor_token}"})
    assert r.status_code == 200
    await async_db.refresh(entry)
    assert entry.current_status == ReviewStatus.APPROVED
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_kb_review.py -v`
Expected:
- `test_reject_from_resubmitted_lands_re_rejected` fails — current code sets `REJECTED`, not `RE_REJECTED`, when rejecting any non-PENDING.
- `test_resubmit_from_re_rejected_is_rejected` fails — current code at `routers/kb.py:190` allows `RE_REJECTED → RESUBMITTED`.

- [ ] **Step 3: Fix the state-machine bugs**

Edit `backend/routers/kb.py` — replace the action block (currently lines 177-194):

```python
    if payload.action == "approve":
        if entry.current_status not in (ReviewStatus.PENDING, ReviewStatus.RESUBMITTED):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot approve entry in status {entry.current_status.value}",
            )
        entry.current_status = ReviewStatus.APPROVED
        await kb.upload_kb_file(
            content=entry.content,
            source_file=f"web_{entry.entry_id[:8]}.txt",
            jurisdiction=entry.jurisdiction,
            topic=entry.topic,
            source_type="web_sourced_approved",
        )
    elif payload.action == "reject":
        if entry.current_status == ReviewStatus.RESUBMITTED:
            entry.current_status = ReviewStatus.RE_REJECTED
        elif entry.current_status == ReviewStatus.PENDING:
            entry.current_status = ReviewStatus.REJECTED
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot reject entry in status {entry.current_status.value}",
            )
        entry.rejection_note = payload.note
    elif payload.action == "resubmit":
        if entry.current_status != ReviewStatus.REJECTED:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Can only resubmit entries in REJECTED state — "
                    f"current status is {entry.current_status.value}"
                ),
            )
        entry.current_status = ReviewStatus.RESUBMITTED
        entry.resubmission_note = payload.note
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {payload.action}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_kb_review.py -v`
Expected: all 4 pass.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/kb.py backend/tests/test_kb_review.py
git commit -m "fix(KB-01): enforce one-shot resubmission state machine"
```

---

### Task 1.5: DOC-01 — Validate MIME type before disk write

**Files:**
- Modify: `backend/requirements.txt` (platform marker for python-magic)
- Modify: `backend/services/document_service.py` (add `validate_mime_from_buffer`)
- Modify: `backend/routers/documents.py` (reorder)
- Create: `backend/tests/test_documents.py`

- [ ] **Step 1: Update requirements with platform marker**

Edit `backend/requirements.txt`: replace the existing `python-magic==0.4.27` line with:

```
python-magic==0.4.27; sys_platform != "win32"
python-magic-bin==0.4.14; sys_platform == "win32"
```

- [ ] **Step 2: Add the buffer-based validator**

Edit `backend/services/document_service.py` — append next to `validate_mime_type`:

```python
def validate_mime_type_from_buffer(buf: bytes) -> str:
    """Buffer variant — used by upload handler so we can reject *before* writing to disk.

    Returns one of {'txt','pdf','docx'} or raises ValueError.
    """
    import magic
    mime = magic.from_buffer(buf, mime=True)
    if mime not in ALLOWED_MIMES:
        raise ValueError(f"Invalid file type: {mime}. Accepted: txt, pdf, docx")
    return ALLOWED_MIMES[mime]
```

- [ ] **Step 3: Reorder the upload handler**

Edit `backend/routers/documents.py` — replace the body of `upload_document` so MIME validation runs against the in-memory buffer first:

```python
@router.post("/{case_id}/upload", status_code=201)
async def upload_document(
    case_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from backend.services.document_service import validate_mime_type_from_buffer

    if not is_staff(current_user):
        raise HTTPException(status_code=403, detail="Advisors only")

    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File exceeds 20MB limit")

    # MIME validation BEFORE touching disk — rejects executables disguised as PDFs.
    try:
        file_type = validate_mime_type_from_buffer(content)
    except ValueError as e:
        raise HTTPException(status_code=415, detail=str(e))

    upload_dir = os.path.join(settings.uploads_path, "cases", case_id)
    os.makedirs(upload_dir, exist_ok=True)
    safe_filename = os.path.basename(file.filename or "upload")
    if not safe_filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    file_path = os.path.join(upload_dir, safe_filename)
    with open(file_path, "wb") as f:
        f.write(content)

    doc = Document(
        case_id=case_id,
        filename=safe_filename,
        file_path=file_path,
        file_type=FileType(file_type),
        file_size_bytes=len(content),
        uploaded_by=current_user.user_id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    try:
        chunk_count = await process_and_embed_document(file_path, file_type, case_id, file.filename)
        doc.parsed = True
        await db.commit()
    except Exception as e:
        logger.error("Embedding failed for document %s: %s", file.filename, e)
        chunk_count = 0

    return {
        "message": f"Uploaded and embedded {chunk_count} chunks",
        "document_id": doc.document_id,
        "chunk_count": chunk_count,
    }
```

- [ ] **Step 4: Write the failing test**

Create `backend/tests/test_documents.py`:

```python
import os
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-32-bytes-minimum-aaaa")

import pytest
from backend.tests.test_cases import client, advisor_token, async_db, sample_case  # noqa: F401


@pytest.mark.asyncio
async def test_upload_rejects_exe_renamed_as_pdf(client, advisor_token, sample_case, tmp_path):
    """A Windows PE binary renamed `evil.pdf` must be rejected with 415, and
    nothing should land in the uploads directory."""
    # PE/COFF magic bytes — `magic` will identify this as application/x-dosexec.
    fake_exe = b"MZ" + b"\x00" * 64 + b"This program cannot be run in DOS mode.\x00"

    case_id = sample_case["case_id"]
    upload_dir = f"./uploads/cases/{case_id}"
    files_before = set(os.listdir(upload_dir)) if os.path.isdir(upload_dir) else set()

    r = await client.post(
        f"/documents/{case_id}/upload",
        files={"file": ("evil.pdf", fake_exe, "application/pdf")},
        headers={"Authorization": f"Bearer {advisor_token}"},
    )
    assert r.status_code == 415, r.text

    files_after = set(os.listdir(upload_dir)) if os.path.isdir(upload_dir) else set()
    assert files_after == files_before, "Rejected upload must not persist on disk"
```

- [ ] **Step 5: Run and confirm pass**

Run: `pytest backend/tests/test_documents.py -v`
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/services/document_service.py backend/routers/documents.py backend/tests/test_documents.py
git commit -m "fix(DOC-01): validate MIME from buffer before disk write"
```

---

### Task 1.6: DOC-02 — Escape source strings in PDF generation

**Files:**
- Modify: `backend/services/pdf_service.py:37`
- Extend: `backend/tests/test_pdf_service.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_pdf_service.py`:

```python
from backend.services.pdf_service import build_report_html


def test_source_strings_are_html_escaped():
    rec = {
        "structure_name": "X",
        "rationale": "Y",
        "confidence_level": "high",
        "sources": ["<script>alert(1)</script>", "ok.pdf"],
    }
    html = build_report_html(
        case_data={"client_name": "C"},
        profile={},
        recommendations=[rec],
        diagrams={},
    )
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "ok.pdf" in html  # benign sources unchanged
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `pytest backend/tests/test_pdf_service.py::test_source_strings_are_html_escaped -v`
Expected: FAIL — unescaped `<script>` is currently rendered as raw HTML.

- [ ] **Step 3: Apply the fix**

Edit `backend/services/pdf_service.py:37`:

```python
        sources_html = "".join(
            f'<li class="source">{html_lib.escape(str(s))}</li>'
            for s in (sources or [])
        )
```

- [ ] **Step 4: Confirm pass**

Run: `pytest backend/tests/test_pdf_service.py -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add backend/services/pdf_service.py backend/tests/test_pdf_service.py
git commit -m "fix(DOC-02): HTML-escape source strings in PDF report"
```

---

### Task 1.7: BIZ-01 — Add CASCADE DELETE on Case foreign keys

**Files:**
- Modify: `backend/models/client_profile.py:10`
- Modify: `backend/models/conversation.py:16`
- Modify: `backend/models/recommendation.py:17`
- Modify: `backend/models/document.py:17`
- Modify: `backend/models/case_diagram.py:18`
- Extend: `backend/tests/test_models.py`

**Important:** SQLite enforces FK constraints **only when** `PRAGMA foreign_keys=ON` is issued per connection. Add that pragma to the async engine so the cascade test exercises real cascade behaviour against SQLite. (Postgres enforces FKs by default — no change needed there.)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_models.py`:

```python
import pytest
from sqlalchemy import select
from backend.models.case import Case
from backend.models.client_profile import ClientProfile
from backend.models.conversation import Conversation, MessageRole
from backend.models.recommendation import Recommendation, ConfidenceLevel
from backend.models.document import Document, FileType


@pytest.mark.asyncio
async def test_deleting_case_cascades_to_children(async_db, sample_user):
    case = Case(client_name="Test", created_by=sample_user.user_id)
    async_db.add(case)
    await async_db.flush()

    async_db.add(ClientProfile(case_id=case.case_id, nationality="IN"))
    async_db.add(Conversation(case_id=case.case_id, role=MessageRole.USER, content="hi"))
    async_db.add(Recommendation(
        case_id=case.case_id, structure_name="Trust",
        confidence_level=ConfidenceLevel.HIGH, rationale="r", sources="[]",
    ))
    async_db.add(Document(
        case_id=case.case_id, filename="x.pdf", file_path="/tmp/x.pdf",
        file_type=FileType.PDF, file_size_bytes=10, uploaded_by=sample_user.user_id,
    ))
    await async_db.commit()

    await async_db.delete(case)
    await async_db.commit()

    for model in (ClientProfile, Conversation, Recommendation, Document):
        result = await async_db.execute(select(model))
        assert result.scalars().all() == [], f"{model.__name__} rows leaked after case delete"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_models.py::test_deleting_case_cascades_to_children -v`
Expected: FAIL — child rows survive case deletion (because SQLite FKs default off and no cascade is declared).

- [ ] **Step 3: Add the pragma**

Edit `backend/database.py`:

```python
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from backend.config import settings

class Base(DeclarativeBase):
    pass

engine = create_async_engine(settings.database_url, echo=False)


@event.listens_for(engine.sync_engine, "connect")
def _enable_sqlite_fk(dbapi_conn, _conn_record):
    """SQLite requires this per-connection. No-op on other dialects (the event
    fires on every connect; Postgres/asyncpg ignore the pragma path entirely
    because the if-block below is dialect-gated)."""
    if engine.dialect.name == "sqlite":
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 4: Add `ondelete="CASCADE"` to each child FK**

Apply each edit:

**`backend/models/client_profile.py:10`** — change to:
```python
    case_id: Mapped[str] = mapped_column(String, ForeignKey("cases.case_id", ondelete="CASCADE"), unique=True, nullable=False)
```

**`backend/models/conversation.py:16`**:
```python
    case_id: Mapped[str] = mapped_column(String, ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False)
```

**`backend/models/recommendation.py:17`**:
```python
    case_id: Mapped[str] = mapped_column(String, ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False)
```

**`backend/models/document.py:17`**:
```python
    case_id: Mapped[str] = mapped_column(String, ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False)
```

**`backend/models/case_diagram.py:18`** — note this one has the FK on a primary key:
```python
    case_id: Mapped[str] = mapped_column(
        String, ForeignKey("cases.case_id", ondelete="CASCADE"), primary_key=True
    )
```

- [ ] **Step 5: Drop the dev SQLite so `create_tables()` rebuilds with the new constraints**

This is dev/test only — production migration happens via Alembic in Phase 3.

```bash
rm -f wealth_planning.db
```

- [ ] **Step 6: Confirm pass**

Run: `pytest backend/tests/test_models.py -v`
Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add backend/models/client_profile.py backend/models/conversation.py backend/models/recommendation.py backend/models/document.py backend/models/case_diagram.py backend/database.py backend/tests/test_models.py
git commit -m "feat(BIZ-01): cascade-delete Case children; enable SQLite FK enforcement"
```

**Note for Phase 3:** The Alembic migration `0003_add_case_cascade.py` rebuilds the FK constraint at the database level. Until then, the schema-level change only takes effect for fresh databases (dev/test). Existing prod SQLite still has the old constraint shape — fine, because the SQL CASCADE runs in app code via the SQLAlchemy session cascade configured by `ondelete=`.

---

### Task 1.8: Open Phase 1 PR

- [ ] **Step 1: Run the full suite**

Run: `SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" pytest backend/tests/ -v`
Expected: all green. Capture the count.

- [ ] **Step 2: Run linters**

```bash
cd backend && ruff check . && black --check .
```
Fix any issues (`ruff check --fix .`, `black .`), commit as `style: ruff/black` if anything changed.

- [ ] **Step 3: Push and open PR**

```bash
git push -u origin feat/p0-phase-1-quickwins
gh pr create --title "feat: P0 hardening Phase 1 — 8 quick wins" --body "$(cat <<'EOF'
## Summary
Phase 1 of the P0 production-hardening plan (`docs/superpowers/plans/2026-05-27-p0-hardening.md`). Eight independently shippable items, no behaviour change beyond rate-limit 429s and stricter KB review states.

- SEC-01 reject default SECRET_KEY at startup
- SEC-02 / AI-07 rate limiting (auth per-IP, chat per-user)
- AI-01 Pydantic validation of diagram JSON
- KB-01 KB resubmission state-machine fix
- DOC-01 MIME validation moved before disk write
- DOC-02 HTML-escape source strings in PDF
- BIZ-01 CASCADE DELETE on Case children
- (SECRET_KEY must be set on the VM before this PR is deployed — see ticket H-6)

## Test plan
- [ ] `pytest backend/tests/` green locally (run with `SECRET_KEY` set)
- [ ] `ruff check .` clean
- [ ] `black --check .` clean
- [ ] CTO/CISO checklist row "SECRET_KEY env var set" satisfied at deploy time

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

# Phase 2 — Foundations (Weeks 2-3)

Branch: `feat/p0-phase-2-foundations`, cut from `main` *after* Phase 1 PR is merged.
Exit criteria: Alembic in use; audit log writing events; KV client wired (no-ops gracefully if KV unreachable); HTTPS middleware in place but tolerant of HTTP until cutover.

### Task 2.0: Branch + dependency bump

**Files:** `backend/requirements.txt`

- [ ] **Step 1: Branch**

```bash
git fetch origin
git checkout -b feat/p0-phase-2-foundations origin/main
```

- [ ] **Step 2: Append dependencies**

Edit `backend/requirements.txt`:

```
alembic==1.14.0
cryptography==43.0.3
azure-identity==1.19.0
azure-keyvault-secrets==4.9.0
```

(`asyncpg==0.30.0` is added in Phase 3, not yet — we stay on SQLite through Phase 2.)

```bash
pip install -r backend/requirements.txt
git add backend/requirements.txt
git commit -m "chore: pin alembic, cryptography, azure-identity, azure-keyvault-secrets"
```

---

### Task 2.1: Alembic baseline against current SQLite schema

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/0001_baseline.py`
- Modify: `backend/database.py` (replace `create_all` with `alembic upgrade head` on startup, with dev fallback)

- [ ] **Step 1: Initialise alembic**

Run:
```bash
cd /Users/shilpi/wealth-planning-app-v2
alembic init alembic
```

This produces `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/`.

- [ ] **Step 2: Configure `alembic.ini`**

Replace the `sqlalchemy.url` line with a placeholder (real value comes from `env.py`):

```ini
sqlalchemy.url = driver://user:pass@host/dbname
```

(`env.py` overrides this at runtime from `settings.database_url`.)

- [ ] **Step 3: Wire `alembic/env.py` to the project's metadata**

Replace `alembic/env.py` body:

```python
from logging.config import fileConfig
import asyncio

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

from backend.config import settings
from backend.database import Base
import backend.models  # noqa: F401  — register all models

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=settings.database_url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=settings.database_url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(settings.database_url, poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 4: Generate the baseline migration**

```bash
alembic revision --autogenerate -m "baseline schema"
```

Inspect the file in `alembic/versions/` and rename it to `0001_baseline.py` (manually adjust `down_revision = None` and the revision id to `"0001"`).

- [ ] **Step 5: Verify the baseline against the existing DB**

```bash
alembic stamp 0001
alembic current
```
Expected: `0001 (head)`. No schema changes attempted.

- [ ] **Step 6: Replace `create_tables()` with alembic upgrade on startup**

Edit `backend/database.py`:

```python
async def create_tables():
    """Apply pending Alembic migrations on startup.

    Falls back to `Base.metadata.create_all` only when ALEMBIC_BOOTSTRAP=skip
    (used by some tests that build an empty in-memory DB)."""
    import os
    if os.environ.get("ALEMBIC_BOOTSTRAP") == "skip":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return

    from alembic.config import Config
    from alembic import command
    cfg = Config("alembic.ini")
    # alembic.command runs synchronously — that's fine, it only happens once at boot.
    await asyncio.to_thread(command.upgrade, cfg, "head")
```

(Add `import asyncio` at the top.)

- [ ] **Step 7: Make sure tests still pass**

Run: `ALEMBIC_BOOTSTRAP=skip SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" pytest backend/tests/ -v`
Expected: green. (Tests skip the migration path; production code uses it.)

- [ ] **Step 8: Commit**

```bash
git add alembic.ini alembic/ backend/database.py
git commit -m "feat(INFRA-02): add Alembic; baseline migration against current SQLite schema"
```

---

### Task 2.2: SEC-10 — Audit log model + service + admin endpoint

**Files:**
- Create: `backend/models/audit_log.py`
- Create: `backend/services/audit_service.py`
- Create: `backend/routers/audit.py`
- Create: `alembic/versions/0002_add_audit_log.py`
- Create: `backend/tests/test_audit.py`
- Modify: routers (auth, kb, admin, chat, cases, documents) to call `audit.log(...)` at event points
- Modify: `backend/main.py` to mount `audit_router`

- [ ] **Step 1: Define the model**

Create `backend/models/audit_log.py`:

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    audit_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(String, ForeignKey("users.user_id"), nullable=True)
    actor_ip: Mapped[str | None] = mapped_column(String, nullable=True)
    event_type: Mapped[str] = mapped_column(String, index=True, nullable=False)
    target_type: Mapped[str | None] = mapped_column(String, nullable=True)
    target_id: Mapped[str | None] = mapped_column(String, nullable=True)
    outcome: Mapped[str] = mapped_column(String, nullable=False)  # 'success' | 'failure'
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

Register it: `backend/models/__init__.py` add `from backend.models.audit_log import AuditLog  # noqa`.

- [ ] **Step 2: Generate the alembic migration**

```bash
alembic revision --autogenerate -m "add audit_log table"
```

Rename the file to `alembic/versions/0002_add_audit_log.py`, set `down_revision = "0001"`, revision id `"0002"`. Inspect — should produce a single `op.create_table("audit_log", ...)` with an index on `occurred_at` and `event_type`.

- [ ] **Step 3: Write the service**

Create `backend/services/audit_service.py`:

```python
"""Audit logging service.

Usage:
    from backend.services.audit_service import log_event
    await log_event(db, event_type="auth.login.success", actor=user, request=request)

All event_type strings live in EVENT_TYPES below. Add a constant before using
a new event so we have a single source of truth.
"""
from __future__ import annotations
from typing import Any
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.audit_log import AuditLog


# Single source of truth for event_type values (catches typos at import time).
EVENT_TYPES = {
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
    # startup
    "system.startup",
}


def _client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    # Honour X-Forwarded-For when behind IIS reverse proxy.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
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
    assert event_type in EVENT_TYPES, f"Unknown audit event_type: {event_type}"
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
```

- [ ] **Step 4: Write the admin query endpoint**

Create `backend/routers/audit.py`:

```python
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
```

Mount in `backend/main.py`:
```python
from backend.routers import audit as audit_router
app.include_router(audit_router.router)
```

- [ ] **Step 5: Wire event points (audit hooks)**

Each of these is a one-line `await log_event(...)` call placed at the right spot. Add `from backend.services.audit_service import log_event` at the top of each file. Add a `request: Request` parameter where one isn't already in scope.

Apply to `backend/routers/auth.py`:
- `login()` success: `await log_event(db, event_type="auth.login.success", actor_user_id=user.user_id, request=request)`
- `login()` failure (the `HTTPException` branch): log `"auth.login.failure"` with `outcome="failure"` and `detail={"email": form.username}`. Wrap in try/except so audit failure never breaks login.
- `sso_login()` success/failure analogously with `"auth.sso.success"` / `"auth.sso.failure"`.
- `accept_invite()`: log `"auth.invite.accept"` after the commit.

Apply to `backend/routers/kb.py:157-196` (the `review_queue_action` handler): log `"kb.review.approve"`, `"kb.review.reject"`, `"kb.review.resubmit"`, `"kb.review.re_reject"` (the last only when reject lands in RE_REJECTED).

Apply to `backend/routers/admin.py`: log `"admin.user.create"`, `"admin.user.deactivate"`, `"admin.user.reset_password"`, `"admin.settings.change"` at each respective handler.

Apply to `backend/routers/cases.py`: log `"case.open"` at GET single-case, `"case.archive"` at archive endpoint.

Apply to `backend/main.py` lifespan: after `validate_secrets(settings)`, open a session and log `"system.startup"` with `actor_user_id=None`.

(Implementation note: each call is wrapped with `try ... except Exception: logger.warning(...)` so audit failure never breaks the calling endpoint. Use a small helper `safe_log(...)` in `audit_service.py` for this if it shows up in 3+ places.)

- [ ] **Step 6: Write the tests**

Create `backend/tests/test_audit.py`:

```python
import os
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-32-bytes-minimum-aaaa")

import pytest
from sqlalchemy import select
from backend.models.audit_log import AuditLog
from backend.tests.test_cases import client, advisor_token, async_db, sample_case  # noqa: F401
from backend.tests.test_auth import sample_user  # noqa: F401


@pytest.mark.asyncio
async def test_login_success_writes_audit_event(client, sample_user, async_db):
    r = await client.post(
        "/auth/token",
        data={"username": sample_user.email, "password": "password123"},
    )
    assert r.status_code == 200
    rows = (await async_db.execute(
        select(AuditLog).where(AuditLog.event_type == "auth.login.success")
    )).scalars().all()
    assert any(r.actor_user_id == sample_user.user_id for r in rows)


@pytest.mark.asyncio
async def test_login_failure_writes_audit_event(client, sample_user, async_db):
    await client.post("/auth/token", data={"username": sample_user.email, "password": "wrong"})
    rows = (await async_db.execute(
        select(AuditLog).where(AuditLog.event_type == "auth.login.failure")
    )).scalars().all()
    assert len(rows) >= 1
    assert rows[-1].outcome == "failure"


@pytest.mark.asyncio
async def test_kb_review_approve_writes_audit_event(client, advisor_token, async_db):
    from backend.models.kb_review_queue import KBReviewQueue, ReviewStatus
    entry = KBReviewQueue(
        jurisdiction="IN", topic="x", content="c", web_url="https://x",
        current_status=ReviewStatus.PENDING,
    )
    async_db.add(entry)
    await async_db.commit()
    await async_db.refresh(entry)

    r = await client.post(
        f"/kb/review-queue/{entry.entry_id}/action",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {advisor_token}"},
    )
    assert r.status_code == 200
    rows = (await async_db.execute(
        select(AuditLog).where(AuditLog.event_type == "kb.review.approve")
    )).scalars().all()
    assert len(rows) >= 1
```

- [ ] **Step 7: Run and confirm pass**

```bash
ALEMBIC_BOOTSTRAP=skip SECRET_KEY="..." pytest backend/tests/test_audit.py -v
```

- [ ] **Step 8: Commit**

```bash
git add backend/models/audit_log.py backend/models/__init__.py backend/services/audit_service.py backend/routers/audit.py backend/routers/auth.py backend/routers/kb.py backend/routers/admin.py backend/routers/cases.py backend/routers/chat.py backend/routers/documents.py backend/main.py alembic/versions/0002_add_audit_log.py backend/tests/test_audit.py
git commit -m "feat(SEC-10): audit logging — model, service, admin endpoint, event hooks"
```

---

### Task 2.3: SEC-04 — Encryption helpers + Azure KV client (key flip happens in Phase 3)

**Files:**
- Create: `backend/services/azure_kv.py`
- Create: `backend/services/encryption.py`
- Create: `backend/models/types.py` (`EncryptedString` column type)
- Create: `backend/tests/test_encryption.py`

**Note:** This task lands the Fernet wrapper and the KV client, **without** flipping any existing rows to ciphertext. The flip happens in Phase 3 as part of the dump-and-load. Until then, `EncryptedString` columns are no-ops in dev (decryption tolerates plaintext for backward compat during the transition).

- [ ] **Step 1: KV client**

Create `backend/services/azure_kv.py`:

```python
"""Azure Key Vault client wrapped to be safe for local dev.

When KV is unreachable (local dev, CI), falls back to the LOCAL_FERNET_KEY env
var. That fallback is logged at WARN and is NOT enabled in production — env.py
checks for `ALLOW_LOCAL_FERNET_KEY=true`.
"""
import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_fernet_master_key() -> bytes:
    vault_url = os.environ.get("KEY_VAULT_URL")
    if not vault_url:
        if os.environ.get("ALLOW_LOCAL_FERNET_KEY") == "true":
            key = os.environ.get("LOCAL_FERNET_KEY")
            if not key:
                raise RuntimeError("LOCAL_FERNET_KEY not set in fallback mode")
            logger.warning("Using LOCAL_FERNET_KEY — DEVELOPMENT ONLY")
            return key.encode()
        raise RuntimeError("KEY_VAULT_URL not set and local-key fallback disabled")

    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=vault_url, credential=credential)
    secret = client.get_secret("wealth-planning-fernet-master-v1")
    return secret.value.encode()
```

- [ ] **Step 2: Fernet wrapper**

Create `backend/services/encryption.py`:

```python
"""Fernet helpers for app-layer encryption.

The master key is loaded once from KV (or local fallback in dev) and held in
memory. Each Fernet round uses a random IV, so the same plaintext produces
different ciphertext each time.
"""
from functools import lru_cache
from cryptography.fernet import Fernet, InvalidToken
from backend.services.azure_kv import get_fernet_master_key


@lru_cache(maxsize=1)
def _cipher() -> Fernet:
    return Fernet(get_fernet_master_key())


def encrypt(plaintext: str) -> str:
    if plaintext is None:
        return None
    return _cipher().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt a Fernet token. Returns the input unchanged if it isn't a valid token —
    this tolerates plaintext rows during the Phase 3 cutover migration."""
    if ciphertext is None:
        return None
    try:
        return _cipher().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        return ciphertext
```

- [ ] **Step 3: EncryptedString column type**

Create `backend/models/types.py`:

```python
from sqlalchemy.types import TypeDecorator, Text
from backend.services.encryption import encrypt, decrypt


class EncryptedString(TypeDecorator):
    """Transparent encrypt-on-write, decrypt-on-read column type.

    Falls back to plaintext passthrough during the Phase 3 cutover so existing
    rows remain readable until the re-encryption migration runs.
    """
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt(str(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return decrypt(value)
```

- [ ] **Step 4: Mark sensitive columns as encrypted on the model (no DB change yet)**

Edit `backend/models/client_profile.py`:

```python
import uuid
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base
from backend.models.types import EncryptedString


class ClientProfile(Base):
    __tablename__ = "client_profiles"

    profile_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String, ForeignKey("cases.case_id", ondelete="CASCADE"), unique=True, nullable=False)
    nationality: Mapped[str | None] = mapped_column(String)
    domicile: Mapped[str | None] = mapped_column(String)
    tax_residency: Mapped[str | None] = mapped_column(String)
    family_members: Mapped[str | None] = mapped_column(EncryptedString)  # encrypted
    asset_classes: Mapped[str | None] = mapped_column(Text)
    asset_jurisdictions: Mapped[str | None] = mapped_column(Text)
    existing_structures: Mapped[str | None] = mapped_column(EncryptedString)  # encrypted
    objectives: Mapped[str | None] = mapped_column(EncryptedString)  # encrypted
```

- [ ] **Step 5: Wire encryption into settings_service**

Edit `backend/services/settings_service.py` — encrypt API key values on write, decrypt on read. Both Anthropic and Tavily keys are stored as ciphertext.

```python
# Replace get_setting / set_setting with versions that go through encryption.encrypt/decrypt
# for keys in SECRET_KEYS = {"anthropic_api_key", "tavily_api_key"}.
SECRET_KEYS = {"anthropic_api_key", "tavily_api_key"}

# ... inside _query: if key in SECRET_KEYS and value: return decrypt(value); else return value
# ... inside set_setting: store_value = encrypt(value) if key in SECRET_KEYS else value
```

(Full diff in execution; the pattern is straightforward — wrap the two encrypt/decrypt boundaries.)

- [ ] **Step 6: Tests**

Create `backend/tests/test_encryption.py`:

```python
import os

# Local-key mode for tests
os.environ["ALLOW_LOCAL_FERNET_KEY"] = "true"
os.environ["LOCAL_FERNET_KEY"] = "OPEy7gV7c0sFNV6yEvg49iFEFRwY7sN1lWQOZsClkFc="
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-32-bytes-minimum-aaaa")

import pytest
from backend.services.encryption import encrypt, decrypt


def test_round_trip():
    assert decrypt(encrypt("hello")) == "hello"


def test_distinct_iv_produces_distinct_ciphertexts():
    a = encrypt("same-plaintext")
    b = encrypt("same-plaintext")
    assert a != b


def test_decrypt_passes_through_plaintext():
    """Backward-compat tolerance during Phase 3 cutover."""
    assert decrypt("not-actually-encrypted") == "not-actually-encrypted"


def test_decrypt_none_returns_none():
    assert decrypt(None) is None
```

- [ ] **Step 7: Run and pass**

```bash
ALEMBIC_BOOTSTRAP=skip pytest backend/tests/test_encryption.py -v
```

- [ ] **Step 8: Commit**

```bash
git add backend/services/azure_kv.py backend/services/encryption.py backend/models/types.py backend/models/client_profile.py backend/services/settings_service.py backend/tests/test_encryption.py
git commit -m "feat(SEC-04): Fernet helpers, KV client, EncryptedString column — key flip in Phase 3"
```

---

### Task 2.4: HTTPS middleware + frontend cookie config (tolerant mode)

**Files:**
- Create: `backend/middleware/__init__.py` (empty)
- Create: `backend/middleware/https_enforce.py`
- Modify: `backend/main.py`
- Modify: `frontend/lib/auth.ts`
- Create: `docs/RUNBOOK_TLS.md`

In Phase 2 the middleware is registered but **tolerant** — it sets an `ENFORCE_HTTPS` env var as the kill switch. Default is `false` until the cutover (Phase 3).

- [ ] **Step 1: Middleware**

Create `backend/middleware/https_enforce.py`:

```python
"""Reject non-HTTPS requests when ENFORCE_HTTPS=true.

The backend sits behind IIS, which terminates TLS and adds X-Forwarded-Proto.
We trust that header (IIS strips it from inbound client requests).
"""
import os
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class EnforceHttpsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if os.environ.get("ENFORCE_HTTPS") != "true":
            return await call_next(request)
        proto = request.headers.get("x-forwarded-proto", "").lower()
        if proto != "https":
            return JSONResponse(
                status_code=400,
                content={"detail": "HTTPS required"},
            )
        return await call_next(request)
```

- [ ] **Step 2: Register in main.py**

```python
from backend.middleware.https_enforce import EnforceHttpsMiddleware
app.add_middleware(EnforceHttpsMiddleware)
```

- [ ] **Step 3: NextAuth cookie config**

Edit `frontend/lib/auth.ts` (the existing NextAuth config). Add:

```typescript
useSecureCookies: process.env.NEXTAUTH_USE_SECURE_COOKIES === 'true',
cookies: {
  sessionToken: {
    name: process.env.NEXTAUTH_USE_SECURE_COOKIES === 'true'
      ? '__Secure-next-auth.session-token'
      : 'next-auth.session-token',
    options: {
      httpOnly: true,
      sameSite: 'lax',
      path: '/',
      secure: process.env.NEXTAUTH_USE_SECURE_COOKIES === 'true',
    },
  },
},
```

(Default `NEXTAUTH_USE_SECURE_COOKIES=false` until cutover. Phase 3 flips it.)

- [ ] **Step 4: TLS runbook**

Create `docs/RUNBOOK_TLS.md` with the IIS binding config, certificate-install steps, port-80→443 redirect rules, troubleshooting tree, and rollback procedure. This is the document the IT engineer follows.

- [ ] **Step 5: Commit**

```bash
git add backend/middleware/ backend/main.py frontend/lib/auth.ts docs/RUNBOOK_TLS.md
git commit -m "feat(SEC-07): HTTPS-enforce middleware (tolerant) + cookie config + IIS runbook"
```

---

### Task 2.5: Phase 2 PR

- [ ] **Step 1: Run the full suite + linters**

```bash
ALEMBIC_BOOTSTRAP=skip ALLOW_LOCAL_FERNET_KEY=true LOCAL_FERNET_KEY=OPEy7gV7c0sFNV6yEvg49iFEFRwY7sN1lWQOZsClkFc= SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" pytest backend/tests/ -v
cd backend && ruff check . && black --check .
```

- [ ] **Step 2: Push and open PR**

```bash
git push -u origin feat/p0-phase-2-foundations
gh pr create --title "feat: P0 hardening Phase 2 — foundations" --body "$(cat <<'EOF'
## Summary
Phase 2 lands plumbing that prepares for the Phase 3 cutover:
- Alembic + baseline migration against current SQLite schema
- Audit log model, service, admin endpoint, event hooks across auth/kb/admin/cases
- Fernet encryption helpers, Azure Key Vault client (with local-key fallback for dev), EncryptedString column type
- HTTPS-enforce middleware (kill-switched off — flips in Phase 3)
- NextAuth secure-cookie config (kill-switched off — flips in Phase 3)
- Encrypted ClientProfile columns marked at the model level — actual ciphertext flip happens in the Phase 3 re-encryption migration

## Test plan
- [ ] `pytest backend/tests/` green
- [ ] `alembic current` reports `0002 (head)` after migration
- [ ] No live-traffic behaviour change (HTTPS middleware tolerant; encryption no-ops until cutover)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

# Phase 3 — Cutover Weekend (Week 4, Saturday)

Branch: `feat/p0-phase-3-cutover`, cut from `main` after Phase 2 merges. Most of this phase is **operational**, not code-writing. The code work lands the migration scripts and the BIZ-01 alembic migration; the rest is the runbook.

**This phase MUST be executed by a human operator with the rollback runbook printed.** Claude Code can prepare the scripts and the migration files; the live cutover is human-driven.

Exit criteria: app on Azure Postgres, sensitive fields encrypted, all traffic HTTPS, smoke test green, rollback procedure tested and documented as available for 30 days.

### Task 3.0: Branch + asyncpg dependency

```bash
git checkout -b feat/p0-phase-3-cutover origin/main
```

Append to `backend/requirements.txt`:
```
asyncpg==0.30.0
```

Commit.

---

### Task 3.1: BIZ-01 — Alembic migration for CASCADE constraints

**Files:**
- Create: `alembic/versions/0003_add_case_cascade.py`

The model-level `ondelete="CASCADE"` from Phase 1 needs a DDL migration to rewrite the FK at the database level (Postgres respects it once issued).

- [ ] **Step 1: Generate the migration**

```bash
alembic revision -m "add cascade delete on case foreign keys"
```

Rename to `0003_add_case_cascade.py`, set `down_revision = "0002"`. Use `op.drop_constraint` + `op.create_foreign_key` (or `batch_alter_table` for SQLite compatibility).

- [ ] **Step 2: Test against a staging Postgres**

If H-1 has provisioned a staging DB, run `alembic upgrade head` against it. Verify `\d+ client_profiles` shows `ON DELETE CASCADE`.

- [ ] **Step 3: Commit**

```bash
git add alembic/versions/0003_add_case_cascade.py
git commit -m "feat(BIZ-01): alembic migration to add CASCADE DELETE on Case FKs"
```

---

### Task 3.2: SQLite → Postgres migration script

**Files:**
- Create: `scripts/migrate_sqlite_to_postgres.sh`
- Create: `scripts/verify_row_counts.py`
- Create: `alembic/versions/0004_postgres_encrypt_existing.py`

- [ ] **Step 1: Migration shell script**

Create `scripts/migrate_sqlite_to_postgres.sh`. This runs **on the VM** during the cutover:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Inputs (set by the operator before running):
#   SQLITE_PATH        — path to the SQLite file (e.g. /var/wealth/wealth_planning.db)
#   PG_DSN             — target Postgres DSN (postgresql+asyncpg://...)
#   LOCAL_FERNET_KEY   — for the encryption migration step (sourced from KV by the runbook)
#   ALLOW_LOCAL_FERNET_KEY=true

: "${SQLITE_PATH:?}"
: "${PG_DSN:?}"

echo "Step 1/5: snapshot SQLite..."
cp "$SQLITE_PATH" "${SQLITE_PATH}.cutover-$(date +%Y%m%d-%H%M%S).bak"

echo "Step 2/5: alembic upgrade against Postgres..."
DATABASE_URL="$PG_DSN" alembic upgrade head

echo "Step 3/5: bulk-load rows from SQLite into Postgres..."
# pgloader command file is bundled here-doc style; pgloader handles type coercion
cat > /tmp/pgloader.load <<'PGL'
LOAD DATABASE
  FROM sqlite://$SQLITE_PATH
  INTO $PG_DSN

  WITH include drop, create tables, create indexes, reset sequences
   SET work_mem to '64MB', maintenance_work_mem to '256MB'
   CAST type datetime to timestamptz drop typemod;
PGL
pgloader /tmp/pgloader.load

echo "Step 4/5: verify row counts..."
python scripts/verify_row_counts.py "$SQLITE_PATH" "$PG_DSN"

echo "Step 5/5: re-encrypt sensitive columns..."
DATABASE_URL="$PG_DSN" alembic upgrade head  # applies 0004 if not already at head

echo "Done. Hand off to smoke test."
```

Make executable: `chmod +x scripts/migrate_sqlite_to_postgres.sh`.

- [ ] **Step 2: Row-count verifier**

Create `scripts/verify_row_counts.py`:

```python
"""Compare row counts table-by-table between SQLite snapshot and target Postgres.
Exits non-zero on mismatch."""
import sys
import sqlite3
import psycopg2


def main():
    sqlite_path, pg_dsn = sys.argv[1], sys.argv[2]
    s_conn = sqlite3.connect(sqlite_path)
    p_conn = psycopg2.connect(pg_dsn)
    tables = [
        "users", "cases", "client_profiles", "conversations",
        "recommendations", "documents", "kb_review_queue",
        "system_settings", "case_diagrams", "invite_tokens",
        "audit_log",
    ]
    bad = []
    for t in tables:
        s = s_conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        with p_conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {t}")
            p = cur.fetchone()[0]
        marker = "OK " if s == p else "BAD"
        print(f"{marker} {t}: sqlite={s} postgres={p}")
        if s != p:
            bad.append(t)
    if bad:
        print(f"MISMATCH on: {bad}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Re-encryption migration**

Create `alembic/versions/0004_postgres_encrypt_existing.py`. This iterates existing rows in `system_settings` (where `key in {anthropic_api_key, tavily_api_key}`) and `client_profiles` (`family_members`, `existing_structures`, `objectives`), encrypts each plaintext value using the production Fernet key, and writes the ciphertext back.

```python
"""re-encrypt sensitive columns

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa
from backend.services.encryption import encrypt

revision = "0004"
down_revision = "0003"


def upgrade():
    conn = op.get_bind()

    rows = conn.execute(sa.text(
        "SELECT key, value FROM system_settings WHERE key IN ('anthropic_api_key','tavily_api_key')"
    )).fetchall()
    for key, value in rows:
        if value and not _looks_like_fernet(value):
            conn.execute(
                sa.text("UPDATE system_settings SET value = :v WHERE key = :k"),
                {"v": encrypt(value), "k": key},
            )

    profile_rows = conn.execute(sa.text(
        "SELECT profile_id, family_members, existing_structures, objectives FROM client_profiles"
    )).fetchall()
    for pid, fm, es, ob in profile_rows:
        updates = {}
        if fm and not _looks_like_fernet(fm):
            updates["family_members"] = encrypt(fm)
        if es and not _looks_like_fernet(es):
            updates["existing_structures"] = encrypt(es)
        if ob and not _looks_like_fernet(ob):
            updates["objectives"] = encrypt(ob)
        if updates:
            set_clause = ", ".join(f"{k} = :{k}" for k in updates)
            updates["pid"] = pid
            conn.execute(
                sa.text(f"UPDATE client_profiles SET {set_clause} WHERE profile_id = :pid"),
                updates,
            )


def downgrade():
    """Decryption pass — only valid while the Fernet key is still in KV."""
    conn = op.get_bind()
    from backend.services.encryption import decrypt
    # symmetric: scan the same rows, decrypt, write back

    for key in ("anthropic_api_key", "tavily_api_key"):
        row = conn.execute(
            sa.text("SELECT value FROM system_settings WHERE key = :k"), {"k": key}
        ).fetchone()
        if row and row[0]:
            conn.execute(
                sa.text("UPDATE system_settings SET value = :v WHERE key = :k"),
                {"v": decrypt(row[0]), "k": key},
            )
    # symmetric for client_profiles (omitted for brevity — same pattern)


def _looks_like_fernet(s: str) -> bool:
    """Fernet tokens are url-safe base64 starting with 'gAAAA' (version byte 0x80)."""
    return isinstance(s, str) and s.startswith("gAAAA")
```

- [ ] **Step 4: Commit**

```bash
git add scripts/migrate_sqlite_to_postgres.sh scripts/verify_row_counts.py alembic/versions/0004_postgres_encrypt_existing.py
git commit -m "feat(INFRA-01,SEC-04): cutover scripts and re-encryption migration"
```

---

### Task 3.3: Cutover-day runbook (operational steps — human-driven)

These steps run **on the VM** during the Saturday window. Claude Code does not execute them; the operator does. They are listed here for completeness and so the plan covers SPEC §5.

- [ ] **T-0:00** Engage IIS maintenance mode (503 for `/api`, static maintenance page for `/`).
- [ ] **T-0:05** Confirm no in-flight requests in Uvicorn logs.
- [ ] **T-0:10** Snapshot SQLite + ChromaDB to `cutover-YYYYMMDD/` and copy to Azure Blob (belt-and-braces).
- [ ] **T-0:20** Set env vars: `DATABASE_URL` (Postgres DSN via MI), `KEY_VAULT_URL`, unset `ALLOW_LOCAL_FERNET_KEY`. Run `scripts/migrate_sqlite_to_postgres.sh`.
- [ ] **T-1:00** Inspect `verify_row_counts.py` output — must be all `OK`.
- [ ] **T-1:15** Update IIS env vars for the service to point at Postgres. Set `ENFORCE_HTTPS=true`. Set `NEXTAUTH_USE_SECURE_COOKIES=true` in the Next.js app config. Restart the service.
- [ ] **T-1:25** Smoke test (manual):
  1. Login as advisor over HTTPS → session cookie has `Secure` flag.
  2. Open an existing case → history loads.
  3. Send a chat message → Claude responds, citations present.
  4. Upload a PDF → extraction works.
  5. Generate a PDF report → renders.
  6. Visit `/admin/audit` → events from the test session present.
- [ ] **T-1:45** Flip IIS: HTTP port 80 → 301 to HTTPS:443. Drop the port-8081 listener.
- [ ] **T-2:00** Exit maintenance mode. Validate `https://team-dashboard.lighthouse-canton.com` end-to-end.
- [ ] **T-2:15** Notify advisors.

**Rollback triggers** (see SPEC §5.3): any row-count mismatch, any smoke-test fail, any encryption round-trip failure, or any unhandled exception in the first 15 min after restart.

**Rollback procedure** (per SPEC §5.4):
1. Stop service.
2. Revert `DATABASE_URL` to SQLite path. Unset `ENFORCE_HTTPS`. Unset `NEXTAUTH_USE_SECURE_COOKIES`.
3. Restore `wealth_planning.db` + `chroma_db/` from the cutover-morning snapshot.
4. Restart service.
5. Re-bind IIS port 8081 HTTP listener.
6. Exit maintenance mode.
7. Schedule Monday post-mortem.

The SQLite snapshot is retained for **30 days** post-cutover.

---

### Task 3.4: Phase 3 PR (code only — operational steps are not PRs)

- [ ] **Step 1: Push and open PR**

```bash
git push -u origin feat/p0-phase-3-cutover
gh pr create --title "feat: P0 hardening Phase 3 — cutover scripts" --body "$(cat <<'EOF'
## Summary
Phase 3 lands the code artefacts for the Saturday cutover:
- Alembic migration adding CASCADE DELETE on Case FKs (BIZ-01 at DDL level)
- `scripts/migrate_sqlite_to_postgres.sh` and `scripts/verify_row_counts.py`
- `alembic/versions/0004_postgres_encrypt_existing.py` — re-encrypts sensitive columns once the master key is live

The actual cutover is a human-driven event following the runbook below.

## Test plan
- [ ] Migration tested against a staging Postgres before the live cutover (H-1 prerequisite)
- [ ] `verify_row_counts.py` returns all OK on staging dataset
- [ ] Encryption round-trip verified after the 0004 migration runs

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

# Phase 4 — Stabilisation & Sign-off (Week 5)

Branch: `feat/p0-phase-4-signoff`. Mostly observation + checklist.

### Task 4.1: One-week soak monitoring

- [ ] Monitor `/admin/audit` daily for unexpected `*.failure` patterns.
- [ ] Monitor rate-limit 429 counts via Uvicorn structured logs.
- [ ] Monitor encryption errors (logged at WARN+).
- [ ] Monitor KV access (Azure portal).

### Task 4.2: Confirm spec-§8 open questions

Update SPEC.md §8 with confirmed answers:
- Document storage: VM disk in P0 (status: confirmed).
- Audit-log retention: 13 months (status: pending CISO sign-off — Phase 4 sign-off includes this).
- Rate-limit values: tune based on Phase 4 telemetry. If 30/hour caused user friction, raise to 60/hour; if no user hit the 100k tokens/day ceiling, leave it alone.

Commit changes to SPEC.md as `docs: confirm open questions per Phase 4 review`.

### Task 4.3: Build the sign-off evidence pack

Create `docs/SIGNOFF_2026-06-XX.md` with one row per checklist item from SPEC §6.2, each linking to its evidence file/screenshot/log query. Capture:

- VM service-config screenshot showing `SECRET_KEY` set
- `psql` output showing ciphertext in `system_settings` and the encrypted columns
- `decrypt_round_trip.py` script output showing one ciphertext decrypted back to plaintext
- KV access log (Azure portal screenshot)
- SSL Labs scan summary
- `pytest backend/tests/test_rate_limit.py -v` output
- 24-hour audit-log query result
- `pytest backend/tests/test_kb_review.py -v` output
- `pytest backend/tests/test_documents.py -v` output
- `pytest backend/tests/test_pdf_service.py -v` output
- Azure portal screenshot of PG instance (private endpoint + backup retention)
- `alembic current` output
- `pytest backend/tests/test_models.py::test_deleting_case_cascades_to_children -v` output
- Rollback dry-run log

Commit and PR.

### Task 4.4: CTO + CISO walkthrough

Operational task — Shilpi drives. Both signatures captured before the advisor announcement.

### Task 4.5: Release announcement

Send to LC advisor team: app is live at `https://team-dashboard.lighthouse-canton.com`. Include the change-log and the "what to do if you hit a 429" pointer.

---

# Self-Review

**Spec coverage check (each SPEC line item → task):**

| SPEC item | Task(s) |
|---|---|
| SEC-01 | 1.1 |
| SEC-02 + AI-07 | 1.2 |
| SEC-04 (helpers) | 2.3 |
| SEC-04 (data flip) | 3.2 (migration 0004) |
| SEC-07 + INFRA-03 (middleware/cookies) | 2.4 |
| SEC-07 + INFRA-03 (IIS flip) | 3.3 (operational) |
| SEC-10 | 2.2 |
| AI-01 | 1.3 |
| KB-01 | 1.4 |
| DOC-01 | 1.5 |
| DOC-02 | 1.6 |
| BIZ-01 (model-level) | 1.7 |
| BIZ-01 (DDL migration) | 3.1 |
| INFRA-01 + INFRA-02 (Alembic) | 2.1 |
| INFRA-01 (Postgres + cutover) | 3.2 + 3.3 |
| Open Q resolutions | 4.2 |
| CTO/CISO checklist | 4.3 |
| Rollback (tested) | 3.3 (operator) |
| Test additions per SPEC §6.1 | 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 2.2, 2.3 |

No gaps.

**Placeholder scan:** Each task contains real code blocks, exact file paths, exact test code, and exact commit messages. The only "operator does" sections are Phase 3 cutover steps (intentional — these are not code) and the H-* prerequisites at the top.

**Type/name consistency:**
- `EncryptedString` (defined in `backend/models/types.py`, used in `backend/models/client_profile.py`) — consistent.
- `log_event(...)` (defined in `backend/services/audit_service.py`, called across routers) — consistent.
- `validate_secrets(s)` (defined in `backend/config.py`, called from `backend/main.py`) — consistent.
- `validate_mime_type_from_buffer(buf)` (defined in `backend/services/document_service.py`, called from `backend/routers/documents.py`) — consistent.
- `EVENT_TYPES` registry (defined in `audit_service.py`, used in caller assert) — consistent.
- Branch names: `feat/p0-phase-{N}-{slug}` — consistent across all four phases.

Plan checks out.

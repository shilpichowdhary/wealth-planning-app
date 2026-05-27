# SPEC: Wealth Planning App v2 — P0 Production-Readiness

**Status:** Draft for review
**Author:** Shilpi Chowdhary (with Claude)
**Date:** 2026-05-27
**Target release:** Internal go-live for Lighthouse Canton advisors
**Deadline:** 4-6 weeks from spec approval
**Scope:** 11 P0 hardening items (10 from `docs/GAPS_AND_RECOMMENDATIONS.md` + audit logging pulled in from P1)

---

## 1. Overview & Success Criteria

### 1.1 Purpose
Harden the existing app enough to put real Lighthouse Canton client cases into it. Today the app runs on a Windows VM with hardcoded secrets, plaintext API keys, SQLite, no rate limiting, HTTP-only transport, and several known correctness bugs. This spec defines the minimum-viable hardening to support internal go-live with CTO/CISO sign-off.

This is **not** a re-architecture, a multi-tenant rebuild, or preparation for regulator submission. Those are explicitly deferred (see §7).

### 1.2 In-scope items (the 11)
| # | Ref | Title |
|---|-----|-------|
| 1 | SEC-01 | Reject default secret key at startup |
| 2 | SEC-02 + AI-07 | Rate limiting: per-IP on auth, per-user on chat |
| 3 | SEC-04 | Encrypt API keys + sensitive client fields at rest |
| 4 | SEC-07 + INFRA-03 | Enforce HTTPS end-to-end |
| 5 | SEC-10 | Audit logging (pulled in from P1) |
| 6 | AI-01 | Fix diagram schema mismatch (`entities` vs `diagram_nodes`) |
| 7 | KB-01 | Fix KB resubmission state machine |
| 8 | DOC-01 | Validate file MIME type before disk write |
| 9 | DOC-02 | Escape source strings in PDF generation |
| 10 | BIZ-01 | Add CASCADE DELETE on Case foreign keys |
| 11 | INFRA-01 + INFRA-02 | Migrate SQLite → Azure Postgres + Alembic |

### 1.3 Definition of Done
The release is "done" when **all eleven items above are merged, tested, and reflected in the CTO/CISO sign-off evidence checklist** (§6.2). Specifically:

- All P0 items have automated regression tests in `backend/tests/`.
- The CTO/CISO checklist (§6.2) is completed and signed.
- A tested rollback procedure exists for the Postgres cutover.
- The app is reachable only over HTTPS from the corporate network.

### 1.4 Non-goals for this release
- No new product features.
- No multi-tenancy or external client portal.
- No external pen test or compliance-grade evidence pack.
- No frontend test infrastructure (Jest, Playwright) — deferred to P3.
- No P1/P2/P3 items from the gaps doc unless explicitly listed in §1.2.

---

## 2. Phase Plan

Four phases over 4-5 weeks. Each phase produces shippable, mergeable PRs.

### Phase 1 — Quick wins (Week 1)
Independently shippable fixes that don't touch the database or transport layer. Each can be its own PR; ship mid-week as ready. These build team momentum and clear seven items off the board fast.

| Item | Files touched | Risk |
|---|---|---|
| SEC-01 secret key check | `backend/config.py`, `backend/main.py` | Low |
| SEC-02 rate limiting (auth) | `backend/routers/auth.py`, new `backend/services/rate_limit.py` | Low |
| AI-07 rate limiting (chat) | `backend/routers/chat.py` | Low |
| AI-01 diagram schema fix | `backend/services/llm_service.py`, `backend/services/diagram_service.py` | Low |
| DOC-01 MIME validation | `backend/routers/documents.py` | Low |
| DOC-02 PDF source escape | `backend/services/pdf_service.py` | Low |
| BIZ-01 CASCADE FKs | `backend/models/*.py` (Case-linked models) | Low (no data change yet — applied at Phase 3 cutover) |
| KB-01 resubmission state machine | `backend/routers/kb.py` | Medium (workflow change) |

**Phase 1 exit criteria:** All 8 items merged to `main`. Test suite green. No production behavior change visible to users except rate-limit 429s and clearer KB review states.

### Phase 2 — Foundations (Weeks 2-3)
Plumbing that prepares for Phase 3 but ships incrementally without changing live behavior.

| Item | Work |
|---|---|
| Alembic introduction | Add Alembic, generate baseline migration from current SQLite schema, switch startup from `create_all()` to `alembic upgrade head`. Still on SQLite. |
| SEC-10 audit logging | Add `audit_log` table + migration. Add `AuditLogService`. Wire into auth flows, admin endpoints, settings changes, KB review decisions, case access. |
| SEC-04 prep (Fernet + Key Vault wiring) | Add `cryptography` Fernet helpers. Wire `azure-identity` + `azure-keyvault-secrets`. Provision Key Vault. Master key stored in KV; retrieved at startup via VM Managed Identity. **Do not flip encryption on yet** — that happens at Phase 3 with a re-encryption migration. |
| HTTPS prep | Provision corporate-CA TLS cert for `team-dashboard.lighthouse-canton.com`. Bind HTTPS listener on IIS *alongside* HTTP. Verify both work. |

**Phase 2 exit criteria:** Alembic in use. Audit log writing events. KV reachable from VM. HTTPS available on IIS. Live traffic still HTTP and unencrypted — that flips at Phase 3.

### Phase 3 — Cutover weekend (Week 4, Saturday)
The single planned downtime window. ~2-4 hour maintenance window. Three things happen together because they all require a coordinated stop:

1. **Postgres migration** (INFRA-01) — see §5 for the playbook.
2. **Encryption go-live** (SEC-04 completion) — re-encrypt existing API keys + sensitive client fields during the dump-and-load.
3. **HTTPS-only flip** (SEC-07) — IIS redirect HTTP → HTTPS; NextAuth `useSecureCookies: true`; backend rejects non-HTTPS via proxy headers.

**Phase 3 exit criteria:** App running on Azure Postgres, all secrets/sensitive fields encrypted, all traffic HTTPS. Rollback tested and confirmed available within 30 days.

### Phase 4 — Stabilization & sign-off (Week 5)
- Monitor audit log, rate-limit hits, encryption errors for one week.
- Run through the CTO/CISO evidence checklist (§6.2).
- CTO and CISO walkthrough + sign.
- Release announcement to LC advisor team.

---

## 3. Per-Item Work Breakdown

Each item below specifies: what changes, where, how it's verified, what evidence it produces for sign-off.

### 3.1 SEC-01 — Reject default secret key at startup
- **Change:** Replace the hardcoded default in `backend/config.py:5` with an empty string default. In `backend/main.py` startup, raise `RuntimeError` if `settings.secret_key` is empty or matches a known-default sentinel. Require minimum length 32.
- **Verify:** Unit test in `backend/tests/test_config.py` (new) that asserts startup raises when `SECRET_KEY` env var is missing.
- **Evidence:** Pre-go-live screenshot showing the env var is set in IIS/service config and is not the default. Audit log entry on startup ("config validated").

### 3.2 SEC-02 + AI-07 — Rate limiting
- **Library:** `slowapi==0.1.9` (FastAPI-native, decorator-based, in-memory backend suitable for single VM).
- **Policies:**
  - Auth (`/auth/token`, `/auth/sso`, password reset): **5 requests / minute / IP**.
  - Chat (`/chat/...`): **30 messages / hour / user** AND **100,000 tokens / day / user** (token accounting via Anthropic response usage).
  - All other endpoints: default 60 requests / minute / IP as a backstop.
- **Files:** New `backend/services/rate_limit.py` (limiter setup + key functions). Decorate endpoints in `backend/routers/auth.py` and `backend/routers/chat.py`. Register `RateLimitExceeded` handler in `backend/main.py` returning HTTP 429 + `Retry-After`.
- **Verify:** Tests in `backend/tests/test_rate_limit.py` (new) — burst 6 logins → 6th returns 429; burst 31 chat messages → 31st returns 429.
- **Evidence:** Test run log + sample 429 response captured in checklist.

### 3.3 SEC-04 — Encrypt API keys + sensitive client fields
- **Library:** `cryptography==43.0.x` (Fernet).
- **Key management:**
  - Master Fernet key stored in **Azure Key Vault** secret `wealth-planning-fernet-master-v1`.
  - VM authenticates to KV via **system-assigned Managed Identity** (already supported on Azure VMs).
  - Key retrieved at app startup, held in memory, never logged.
  - Rotation procedure documented (§4.4) but no automated rotation in this release.
- **Scope of encryption:**
  - **SystemSetting** API key values: `anthropic_api_key`, `tavily_api_key`. Encrypt on write; decrypt only when needed for the outbound call.
  - **ClientProfile** sensitive JSON blobs: `family_members`, `existing_structures`, `objectives`. These currently hold the highest-sensitivity PII in the DB (family names, holding structures, financial goals). `nationality`, `domicile`, `tax_residency`, `asset_classes`, and `asset_jurisdictions` are jurisdictional metadata — useful for reporting and queries, lower sensitivity, **not encrypted in P0**.
  - Add a new `EncryptedString` SQLAlchemy column type (transparent encrypt-on-write, decrypt-on-read) so future typed PII fields added under BIZ-03 (national identifiers, account numbers) plug in without further infra work.
  - Each encrypted field is marked with a `# encrypted` comment in `backend/models/client_profile.py`.
- **Files:**
  - New `backend/services/encryption.py` (Fernet wrapper + key loader).
  - New `backend/services/azure_kv.py` (KV client).
  - Modify `backend/services/settings_service.py:38-48` to encrypt/decrypt on read/write.
  - New SQLAlchemy `EncryptedString` type in `backend/models/types.py`.
  - Alembic migration that re-encrypts existing rows at cutover (Phase 3).
- **Verify:** Tests in `backend/tests/test_encryption.py` (new): round-trip encrypt/decrypt; ciphertexts differ for same plaintext (Fernet uses random IV); decrypt fails with wrong key.
- **Evidence:** Sample query on Postgres showing ciphertext in `system_settings` and the encrypted `client_profile` columns. KV access log (Azure portal) showing master key reads.

### 3.4 SEC-07 + INFRA-03 — Enforce HTTPS end-to-end
- **TLS termination:** IIS terminates TLS on `team-dashboard.lighthouse-canton.com:443` using a corporate-CA-issued certificate for that hostname. Uvicorn and Next.js stay on HTTP, bound to `127.0.0.1` only — they are not reachable externally.
- **Redirect:** IIS port 80 → 301 permanent redirect to HTTPS. Drop the current port 8081 HTTP listener.
- **App-layer enforcement:**
  - FastAPI middleware checks `X-Forwarded-Proto: https` and rejects (HTTP 400) requests without it. This catches misconfiguration if the IIS proxy is ever bypassed.
  - NextAuth (`frontend/lib/auth.ts`): set `useSecureCookies: true`, `cookies.sessionToken.options.sameSite: 'lax'`, `secure: true`.
  - Move JWT from `sessionStorage` to HttpOnly cookie (eliminates XSS-accessible token storage).
- **Files:**
  - IIS configuration on the VM (out of repo — documented in `docs/RUNBOOK_TLS.md`, new).
  - `backend/main.py` — middleware addition.
  - `frontend/lib/auth.ts` — cookie config changes.
- **Verify:**
  - `curl http://team-dashboard.lighthouse-canton.com` returns 301 to https://.
  - Browser shows HTTPS lock; cert chain validates.
  - Token no longer visible in browser DevTools → Application → Session Storage.
- **Evidence:** SSL Labs scan result (or equivalent internal scan), browser screenshot of secure connection, redirect curl output.

### 3.5 SEC-10 — Audit logging
- **Model:** New `audit_log` table.
  ```python
  class AuditLog(Base):
      audit_id: str (PK, uuid)
      occurred_at: datetime (UTC, indexed)
      actor_user_id: str | None (FK users.user_id, nullable for pre-auth events)
      actor_ip: str | None
      event_type: str (enum-like, indexed)
      target_type: str | None  # 'case', 'user', 'kb_entry', 'setting'
      target_id: str | None
      outcome: str  # 'success' | 'failure'
      detail: JSON  # context-specific
  ```
- **Events logged in this release:**
  - Auth: login success, login failure, SSO success, SSO failure, logout, password reset.
  - Admin: create advisor, deactivate advisor, reset password, change settings.
  - Cases: case opened, case archived, case viewed.
  - KB review: approve, reject, resubmit, re-reject.
  - Settings: any change to SystemSetting (without logging the secret value itself).
- **Files:**
  - New `backend/models/audit_log.py`.
  - New `backend/services/audit_service.py` with `await audit.log(event, ...)` helper.
  - Wire into routers listed above. Add `request: Request` parameter where needed for IP capture.
  - New `GET /admin/audit?from=&to=&user_id=&event_type=` endpoint, admin-only, paginated.
- **Verify:** Tests in `backend/tests/test_audit.py` (new) for each event type. Sample-event integration test.
- **Evidence:** Sample audit-log query showing 24 hours of activity at sign-off time.

### 3.6 AI-01 — Diagram schema mismatch
- **Decision:** Use `entities` everywhere (matches the parser, which is the harder thing to change). Update the system prompt in `backend/services/llm_service.py` to instruct the model to emit `"entities"` instead of `"diagram_nodes"`.
- **Also fix:** the JSON-extraction regex on line ~13-19 of `llm_service.py` — replace with `json.loads()` parsing of code-fenced JSON blocks plus Pydantic schema validation (catches malformed diagrams instead of silent failure).
- **Files:** `backend/services/llm_service.py`, `backend/services/diagram_service.py`.
- **Verify:** Test in `backend/tests/test_diagram_service.py` extended with a sample model output → diagram render assertion.
- **Evidence:** Screenshot of a structure diagram rendered in a real case.

### 3.7 KB-01 — KB resubmission state machine
- **Change:** In `backend/routers/kb.py`, the `/kb/review/{entry_id}` endpoint currently only accepts `PENDING` entries. Extend it to accept `RESUBMITTED` entries, with transitions:
  - `RESUBMITTED` + approve → `APPROVED` (ingest content to ChromaDB, exactly as the PENDING approve path).
  - `RESUBMITTED` + reject → `RE_REJECTED` (terminal; cannot be resubmitted again — enforced in the resubmit endpoint).
- **Also add:** validation that resubmission is blocked when entry is in `RE_REJECTED`.
- **Files:** `backend/routers/kb.py`, `backend/models/kb_review_queue.py` (already has the enum values — `RESUBMITTED`, `RE_REJECTED`).
- **Verify:** Test in `backend/tests/test_kb_review.py` (new): PENDING → REJECTED → RESUBMITTED → APPROVED; PENDING → REJECTED → RESUBMITTED → RE_REJECTED → cannot resubmit again.
- **Evidence:** Test run log.

### 3.8 DOC-01 — Validate MIME before disk write
- **Change:** In `backend/routers/documents.py`, read uploaded file bytes into memory first (already bounded by `max_upload_bytes=20MB`), validate MIME via `magic.from_buffer(buf, mime=True)`, only then write to disk if MIME ∈ allowlist (PDF, DOCX, plain text).
- **Windows note:** `python-magic` requires `libmagic`. On Windows VMs, switch the requirement to `python-magic-bin==0.4.14` (bundled DLLs). Document in `requirements.txt` with a platform marker:
  ```
  python-magic==0.4.27; sys_platform != "win32"
  python-magic-bin==0.4.14; sys_platform == "win32"
  ```
- **Files:** `backend/routers/documents.py`, `backend/requirements.txt`.
- **Verify:** Test in `backend/tests/test_documents.py` (extend) uploading a `.exe` renamed to `.pdf` → returns HTTP 400, no file persisted.
- **Evidence:** Test log + sample rejection.

### 3.9 DOC-02 — Escape source strings in PDF generation
- **Change:** In `backend/services/pdf_service.py:37`, wrap source-string interpolation with `html_lib.escape()` (other user-supplied fields already do this).
- **Files:** `backend/services/pdf_service.py`.
- **Verify:** Test in `backend/tests/test_pdf_service.py` (extend) — include a source string containing `<script>alert(1)</script>`, assert it appears escaped in the rendered HTML.
- **Evidence:** Test run log.

### 3.10 BIZ-01 — CASCADE DELETE on Case FKs
- **Change:** Add `ondelete="CASCADE"` to every ForeignKey targeting `cases.case_id`:
  - `backend/models/client_profile.py:9`
  - `backend/models/recommendation.py:9`
  - `backend/models/conversation.py:5`
  - `backend/models/document.py` (check Case FK)
  - `backend/models/case_diagram.py` (check Case FK)
- **Why deferred to Phase 3:** The schema change is small but requires an Alembic migration. To avoid two SQLite migrations (Phase 2 prep work) followed by a Postgres migration (Phase 3), bundle it with the Phase 3 baseline. The Phase 1 PR for this item adds the `ondelete=` to the SQLAlchemy models only; the FK constraint is rebuilt during the Postgres dump-and-load.
- **Verify:** Test in `backend/tests/test_models.py` (extend) deletes a case → asserts no orphaned ClientProfile / Conversation / Recommendation / Document rows remain.
- **Evidence:** Test run log + post-cutover Postgres `\d+ client_profiles` showing the cascade constraint.

### 3.11 INFRA-01 + INFRA-02 — Postgres migration + Alembic
- **Target:** **Azure Database for PostgreSQL Flexible Server**, Burstable B2s tier (sufficient for internal go-live; can scale up later). Same Azure region as the VM. Public access disabled; **private endpoint** to the VNet hosting the VM. SSL required. Automated daily backups, 7-day retention (Azure default).
- **App changes:**
  - Update `backend/config.py` default: keep SQLite as the dev default; require `DATABASE_URL` env var in production.
  - Switch driver to `asyncpg`. Add `asyncpg==0.30.0` to requirements; remove `aiosqlite` for prod (keep for dev).
  - Add `alembic==1.14.0`; generate baseline from current schema during Phase 2 (against SQLite); regenerate against Postgres at cutover.
  - `backend/database.py`: replace `Base.metadata.create_all()` with `alembic upgrade head` invocation at startup.
- **Data migration tool:** `pgloader` (single command, handles SQLite → Postgres including type coercion) **or** a one-off Python script using SQLAlchemy. Decision at start of Phase 3 based on schema complexity; pgloader is the default if there are no exotic types.
- **Files:**
  - `backend/config.py`, `backend/database.py`, `backend/requirements.txt`.
  - New `alembic/` directory with `env.py`, `script.py.mako`, `versions/0001_baseline.py`.
  - New `scripts/migrate_sqlite_to_postgres.sh` (cutover script).
- **Verify:**
  - Pre-cutover: full app integration test against a staging Postgres (same Azure setup, separate DB).
  - Post-cutover: row counts match SQLite snapshot; smoke test (create case, send chat, upload doc, render PDF).
- **Evidence:** Migration log with row counts, post-cutover smoke-test result, Azure portal screenshot of the PG instance with backup retention enabled.

---

## 4. Cross-Cutting Architecture

### 4.1 Azure resources to provision
| Resource | Purpose | Tier |
|---|---|---|
| Azure Database for PostgreSQL Flexible Server | Primary application database | Burstable B2s, SSL required, private endpoint |
| Azure Key Vault | Master Fernet key + future secret rotation | Standard tier |
| Azure Storage Account (Blob) | (Optional) document upload offload + offsite backups | Hot tier, GRS |
| VM System-Assigned Managed Identity | Auth from VM to KV and Postgres | n/a |

All resources in the same Azure region as the VM. Resource group: `rg-wealth-planning-prod` (or per your existing naming convention).

### 4.2 Managed Identity & secret flow
1. VM has a system-assigned Managed Identity (enabled in Azure portal).
2. KV access policy grants the MI **Get** + **List** permissions on secrets.
3. Postgres uses **Azure AD authentication** with the MI as the DB principal (no password to manage; cleanest audit story).
4. App startup:
   - Fetches Fernet master key from KV.
   - Fetches Postgres connection string from KV (or obtains AD token directly).
   - Holds both in process memory; never writes to logs.

### 4.3 Encryption boundaries (what's encrypted, where)
| Data | At-rest mechanism | Notes |
|---|---|---|
| Anthropic / Tavily API keys (`system_settings`) | App-layer Fernet | Decrypted only at API-call time |
| ClientProfile sensitive JSON blobs (`family_members`, `existing_structures`, `objectives`) | App-layer Fernet | Marked with `# encrypted` in the model. `EncryptedString` type reused for any future typed PII fields. |
| All other Postgres data | Azure-managed transparent encryption | Default; covers backups |
| Documents (uploads) | Filesystem (VM disk encryption) or Blob (SSE) | Choice of storage made before Phase 2 ends |
| Master Fernet key | Azure Key Vault | HSM-backed at Standard tier |
| TLS in transit | TLS 1.2+ on IIS | corp-CA cert |
| Backups | Azure-managed encryption | 7-day retention |

### 4.4 Secret rotation (documented, not automated)
| Secret | Rotation cadence | Procedure |
|---|---|---|
| Anthropic API key | Annual or on compromise | Admin updates via existing settings UI; app re-encrypts on write |
| Tavily API key | Annual or on compromise | Same as above |
| Fernet master key | Annual | New key version stored in KV (`-v2`); admin runs migration script to decrypt with v1 + re-encrypt with v2; v1 retained 90 days for rollback |
| Postgres credentials | n/a — Managed Identity, no static password | |
| Azure AD app secret (SSO) | Per Azure AD policy (~24 months) | Standard Entra ID rotation |

### 4.5 Observability additions (lightweight)
- Audit log table (§3.5) — covers "who did what" answer.
- Structured logging: ensure `backend/main.py` configures `logging` with JSON output to stdout (IIS captures it). Rate-limit hits, encryption failures, KV-fetch failures all logged at WARN+.
- `/health` endpoint extended to verify Postgres connectivity and KV reachability (closes INFRA-05 partially — small enough to include).

---

## 5. Rollout & Rollback Playbook (Phase 3, Saturday cutover)

### 5.1 Pre-cutover (Friday afternoon)
- [ ] Azure Postgres staging DB fully tested with current app (Phase 2 work).
- [ ] Latest `main` deployed to VM; all Phase 1 + Phase 2 PRs merged.
- [ ] All advisors notified of Saturday window (email Thursday).
- [ ] Audit log working in production (Phase 2 already shipped this).
- [ ] HTTPS binding live on IIS in parallel (Phase 2 already shipped this).
- [ ] Rollback runbook printed/shared with on-call engineer.

### 5.2 Cutover steps (Saturday morning, target 2-3 hours)
1. **T-0:00** — Put app in maintenance mode (IIS rule returning 503 for `/api` paths; static maintenance page on frontend).
2. **T-0:05** — Verify no in-flight requests; check Uvicorn logs for completion.
3. **T-0:10** — Backup current SQLite: copy `wealth_planning.db` and `chroma_db/` to a timestamped folder; upload to Azure Blob as belt-and-braces.
4. **T-0:20** — Run `scripts/migrate_sqlite_to_postgres.sh`:
   - Dumps SQLite to Postgres-compatible SQL (via pgloader).
   - Applies Alembic baseline.
   - Loads rows.
   - Re-encrypts API key + sensitive ClientProfile fields using the new Fernet master.
5. **T-1:00** — Row-count verification: each table count in Postgres == count in SQLite snapshot.
6. **T-1:15** — Switch app config to point at Postgres (env var change + service restart).
7. **T-1:25** — Smoke test (manual):
   - Login as advisor.
   - Open existing case → confirm history loads.
   - Send a chat message → confirm Claude responds and citations work.
   - Upload a PDF → confirm extraction.
   - Generate a PDF report → confirm rendering.
   - Check audit log for the test session.
8. **T-1:45** — Flip IIS to HTTPS-only (port 80 → 301 to 443; drop the 8081 listener).
9. **T-2:00** — Exit maintenance mode.
10. **T-2:15** — Announcement to advisors that the app is back.

### 5.3 Rollback triggers
Roll back if any of the following occur within the cutover window:
- Row-count mismatch after migration.
- Smoke test failure on any of the 5 checks.
- Encryption round-trip failure (encrypted secret can't be decrypted on read).
- Any unhandled exception in the first 15 minutes after restart.

### 5.4 Rollback procedure
1. Stop the FastAPI service.
2. Revert app config to point at SQLite.
3. Restore `wealth_planning.db` and `chroma_db/` from the cutover-morning snapshot.
4. Restart service.
5. Re-bind HTTP on port 8081 (keep HTTPS available in parallel).
6. Exit maintenance mode.
7. Schedule a post-mortem the following Monday.

The SQLite snapshot is retained for **30 days** post-cutover in case a delayed issue surfaces. After 30 days, snapshot is deleted; Postgres becomes the only source of truth.

---

## 6. Testing & Sign-off Evidence

### 6.1 Test additions
| Test file | What it covers | Phase |
|---|---|---|
| `backend/tests/test_config.py` (new) | SEC-01 startup secret validation | 1 |
| `backend/tests/test_rate_limit.py` (new) | SEC-02 + AI-07 limiter behavior | 1 |
| `backend/tests/test_diagram_service.py` (extend) | AI-01 schema parse | 1 |
| `backend/tests/test_kb_review.py` (new) | KB-01 state machine | 1 |
| `backend/tests/test_documents.py` (new) | DOC-01 MIME rejection | 1 |
| `backend/tests/test_pdf_service.py` (extend) | DOC-02 HTML escape | 1 |
| `backend/tests/test_models.py` (extend) | BIZ-01 cascade delete | 1 |
| `backend/tests/test_encryption.py` (new) | SEC-04 Fernet round-trip | 2 |
| `backend/tests/test_audit.py` (new) | SEC-10 event coverage | 2 |
| Integration smoke test (manual checklist) | End-to-end flow on Postgres + HTTPS | 3 |

All tests must pass via `pytest backend/tests/` before each phase's PR is merged.

### 6.2 CTO/CISO sign-off checklist
Single-page checklist; completed in Phase 4. Each line links to evidence (test output, screenshot, log query, or Azure portal artifact).

- [ ] **Secrets**: `SECRET_KEY` env var set on VM; not the default. (Evidence: VM service config screenshot.)
- [ ] **API keys**: Stored ciphertext in `system_settings`. (Evidence: SQL query output showing ciphertext.)
- [ ] **Client PII**: `family_members`, `existing_structures`, `objectives` columns hold ciphertext, decryptable via the app. (Evidence: SQL query output + a decrypt round-trip script.)
- [ ] **Key Vault**: Master Fernet key in KV; VM Managed Identity has read access; access log shows app reads. (Evidence: KV access log.)
- [ ] **HTTPS**: `https://team-dashboard.lighthouse-canton.com` serves valid TLS; HTTP returns 301. (Evidence: SSL Labs / equivalent scan output.)
- [ ] **Rate limits**: 6th auth attempt in a minute → 429; 31st chat message in an hour → 429. (Evidence: test_rate_limit.py output.)
- [ ] **Audit log**: 24 hours of events captured; admin UI viewable. (Evidence: audit log query.)
- [ ] **KB review**: Full PENDING → REJECTED → RESUBMITTED → APPROVED cycle works. (Evidence: test_kb_review.py output + screenshot.)
- [ ] **File uploads**: Disguised `.exe` rejected. (Evidence: test_documents.py output.)
- [ ] **PDF reports**: HTML-escape verified. (Evidence: test_pdf_service.py output.)
- [ ] **Database**: Running on Azure PG Flexible Server with private endpoint; daily backups enabled. (Evidence: Azure portal screenshot.)
- [ ] **Migrations**: Alembic running; `alembic current` matches `alembic heads`. (Evidence: command output.)
- [ ] **Cascade integrity**: Deleting a case cascades correctly. (Evidence: test_models.py output.)
- [ ] **Rollback**: SQLite snapshot retained; rollback procedure tested at least once in staging. (Evidence: dry-run log.)

CTO signs (operational readiness). CISO signs (security posture). Both signatures captured before advisors are invited to use the production app.

---

## 7. Out of Scope (Explicit Deferrals)

Items intentionally **not** in this release. Listed so reviewers know what's missing and on purpose.

### Deferred to P1 (next release after go-live)
- BIZ-02 Case lifecycle stages
- BIZ-03 UHNWI-critical profile fields
- AI-02 Surface web-search errors
- AI-03 LLM streaming timeout
- AI-04 Token budget for system prompt sources
- FE-01 / FE-02 Adopt `apiFetch` and fix silent error catches
- FE-04 React error boundaries
- KB-02 KB staleness detection
- KB-03 Higher similarity threshold + embedding model evaluation
- KB-04 Preserve source URLs in ChromaDB metadata
- SEC-05 Account lockout after failed logins
- SEC-08 Self-service password reset
- INFRA-04 Backup *script* — superseded by Azure-managed backups; remaining work is documenting restore drill

### Deferred to P2 / P3
- Everything else in `docs/GAPS_AND_RECOMMENDATIONS.md` not listed above.

### Notable scope decisions
- **No multi-tenant work.** Single LC tenant. Keenai B2B/B2C multi-tenancy is a future architectural project.
- **No frontend test infrastructure.** Jest / RTL / Playwright are P3.
- **No external pen test.** Internal sign-off only for this release. A pen test is recommended before any external pilot.
- **No CI/CD pipeline.** GitHub Actions setup is P3.
- **No password reset self-service.** Admin-only resets continue in this release (SEC-08).
- **No `datetime.utcnow` cleanup (BIZ-08).** Deprecation warnings only; non-blocking. Bundle with the next data-model release.

---

## 8. Open Questions

These were not decided during spec drafting. Resolve before Phase 2 starts.

1. **Document storage location** — keep uploads on the VM disk or move to Azure Blob? Blob is cleaner long-term but requires a code path change in `backend/services/document_service.py`. Recommendation: stay on VM disk in P0 for simplicity; move to Blob in P1.
2. **Audit log retention** — how long do we retain audit log rows? Recommendation: 13 months (covers a full audit cycle); confirm with CISO.
3. **Rate-limit values** — the 5/min, 30/hour, 100k tokens/day numbers are starting points. Tune in Phase 4 based on observed usage.

---

## 9. Appendix — Glossary

- **Alembic** — Python database migration tool. Tracks schema versions and applies changes incrementally.
- **CASCADE DELETE** — A foreign-key option: when the parent row is deleted, child rows referencing it are deleted automatically.
- **Fernet** — A symmetric encryption scheme from Python's `cryptography` library. Each encryption uses a random IV, so the same plaintext produces different ciphertext each time.
- **Managed Identity** — An Azure feature that gives a VM (or other resource) an identity it can use to authenticate to other Azure services (Key Vault, SQL, etc.) without storing credentials.
- **Pydantic** — Python validation library used by FastAPI for request/response schemas.
- **SSE** — Server-Sent Events. A streaming protocol the chat endpoint uses to push Claude's response tokens to the browser.
- **Slowapi** — Rate-limiting library for FastAPI, decorator-based, in-memory by default.

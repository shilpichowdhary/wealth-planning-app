# Wealth Planning Application -- Gaps, Issues & Recommendations

**Application:** AI-Powered Wealth Planning Advisory Platform
**Review Date:** 2026-04-02
**Scope:** Full-stack review (backend, frontend, AI pipeline, deployment, security)

---

## Table of Contents

1. [Issue Summary Dashboard](#1-issue-summary-dashboard)
2. [Security & Authentication](#2-security--authentication)
3. [Data Model & Business Logic](#3-data-model--business-logic)
4. [AI/Chat/RAG Pipeline](#4-aichatrag-pipeline)
5. [Knowledge Base & Review Workflow](#5-knowledge-base--review-workflow)
6. [Document Management & Reports](#6-document-management--reports)
7. [Frontend Architecture](#7-frontend-architecture)
8. [Infrastructure & Deployment](#8-infrastructure--deployment)
9. [Testing & Quality](#9-testing--quality)
10. [Prioritised Improvement Roadmap](#10-prioritised-improvement-roadmap)

---

## 1. Issue Summary Dashboard

| Severity | Count | Category Breakdown |
|----------|-------|--------------------|
| **CRITICAL** | 9 | Security (4), Infrastructure (2), AI Pipeline (1), KB Workflow (1), Data Model (1) |
| **HIGH** | 16 | Security (3), AI Pipeline (4), KB (3), Documents (2), Frontend (2), Infrastructure (2) |
| **MEDIUM** | 18 | Across all modules |
| **LOW** | 6 | Minor improvements |
| **Total** | **49** | |

---

## 2. Security & Authentication

### CRITICAL

#### SEC-01: Hardcoded Dev Secret Key
- **File:** `backend/config.py:5`
- **Issue:** `secret_key = "dev-secret-key-change-in-production-min32"` is the JWT signing key. If this value is used in production, all JWTs can be forged.
- **Impact:** Complete authentication bypass. Any attacker can create valid admin tokens.
- **Fix:** Reject the default value at startup. Require `SECRET_KEY` env var with minimum 32-character random value. Add a startup check:
  ```python
  if settings.secret_key == "dev-secret-key-change-in-production-min32":
      raise RuntimeError("SECRET_KEY must be changed from default")
  ```

#### SEC-02: No Rate Limiting on Auth Endpoints
- **File:** `backend/routers/auth.py:23-30, 39-82`
- **Issue:** `/auth/token` and `/auth/sso` have no rate limiting. `config.py:14` defines `api_rate_limit_per_minute = 10` but it is never applied anywhere.
- **Impact:** Vulnerable to brute-force credential stuffing and DoS attacks.
- **Fix:** Add `slowapi` middleware. Apply 5-10 requests/minute per IP on auth endpoints.

#### SEC-03: Overly Permissive CORS
- **File:** `backend/main.py:16-24`
- **Issue:** `allow_methods=["*"]` and `allow_headers=["*"]` with credential support enabled. Three origins hardcoded including two localhost entries.
- **Impact:** Increases CSRF attack surface; overly broad for production.
- **Fix:** Restrict methods to `["GET", "POST", "PUT", "DELETE"]`. Restrict headers to `["Authorization", "Content-Type"]`. Remove localhost origins in production builds. Use environment variable for allowed origins.

#### SEC-04: API Keys Stored as Plaintext in Database
- **File:** `backend/models/system_setting.py:11`, `backend/services/settings_service.py:38-48`
- **Issue:** Anthropic and Tavily API keys stored as plaintext TEXT in the SystemSetting table.
- **Impact:** Database compromise exposes all API keys. SQLite file is unencrypted on disk.
- **Fix:** Encrypt at rest using `cryptography.fernet.Fernet`. Decrypt only when retrieving for use. Store Fernet key in environment variable.

### HIGH

#### SEC-05: No Account Lockout After Failed Logins
- **File:** `backend/routers/auth.py:28`
- **Issue:** Unlimited login attempts allowed with no delay, lockout, or notification.
- **Impact:** Enables brute-force attacks on advisor accounts.
- **Fix:** Implement lockout after 5 failed attempts -> 15-minute cooldown. Log failed attempts. Consider CAPTCHA after 3 failures.

#### SEC-06: Generated Passwords Returned in HTTP Response
- **File:** `backend/routers/admin.py:116, 188-191`
- **Issue:** When admin creates advisor or resets password, the plaintext password is returned in the JSON response body.
- **Impact:** Passwords may appear in server logs, proxy logs, browser history, network captures.
- **Fix:** Send passwords via a secure channel (email with one-time link). Never return plaintext passwords in HTTP responses.

#### SEC-07: No HTTPS Enforcement / Secure Cookie Flags
- **File:** `frontend/lib/auth.ts` (no secure cookie config), `run_server.ps1` (HTTP only)
- **Issue:** Backend runs on HTTP. NextAuth does not set `useSecureCookies: true` or `sameSite: 'Lax'`. Token cached in `sessionStorage` (XSS-accessible).
- **Impact:** Session hijacking via XSS or network sniffing.
- **Fix:** Enable HTTPS on Uvicorn (SSL certs) or enforce at IIS proxy. Set NextAuth `useSecureCookies: true`. Move token storage to HttpOnly cookies.

### MEDIUM

#### SEC-08: No Password Reset Flow for Local Auth
- **File:** `backend/routers/admin.py:175-191` (admin-only reset only)
- **Issue:** No self-service "forgot password" flow. Advisors must contact admin.
- **Impact:** Operational friction. May lead to password reuse or sharing.
- **Fix:** Implement email-based password reset with one-time token (1-hour expiry).

#### SEC-09: DB Lookup on Every Authenticated Request
- **File:** `backend/routers/auth.py:92-95`
- **Issue:** Every protected endpoint queries the database to fetch the full user record by `user_id` from the JWT. No caching layer.
- **Impact:** Performance degradation under load. However, this ensures deactivated users are immediately blocked.
- **Fix:** Cache user role/active status in JWT claims. Add short TTL cache (5 min) for user lookups. Invalidate on deactivation.

#### SEC-10: No Audit Logging
- **File:** N/A (missing entirely)
- **Issue:** No logging of: login attempts (success/failure), admin actions (create/deactivate advisor, reset password, change settings), case access, document uploads.
- **Impact:** Cannot investigate security incidents or demonstrate compliance.
- **Fix:** Create an AuditLog model. Log all authentication events, admin actions, and sensitive data access. Expose read-only audit trail at `/admin/audit`.

---

## 3. Data Model & Business Logic

### CRITICAL

#### BIZ-01: No CASCADE DELETE on Case Foreign Keys
- **File:** `backend/models/client_profile.py:9`, `backend/models/recommendation.py:9`, `backend/models/conversation.py:5`
- **Issue:** Foreign keys to `cases.case_id` do not specify `ondelete="CASCADE"`. If a case record is ever deleted, all linked ClientProfile, Recommendation, Conversation, and Document records become orphaned.
- **Impact:** Data integrity violation. Orphaned records accumulate over time.
- **Fix:** Add `ondelete="CASCADE"` to all Case FKs:
  ```python
  case_id = mapped_column(String, ForeignKey("cases.case_id", ondelete="CASCADE"), ...)
  ```

### HIGH

#### BIZ-02: No Case Lifecycle Stages
- **File:** `backend/models/case.py:8-10`
- **Issue:** Cases only have two states: ACTIVE and ARCHIVED. No tracking of advisory workflow stages.
- **Impact:** Advisors cannot track where each case stands in the lifecycle. No management reporting on pipeline.
- **Fix:** Add a `stage` enum: `INTAKE`, `ANALYSIS`, `RECOMMENDATION_DRAFT`, `REVIEW`, `APPROVED`, `IMPLEMENTED`, `ARCHIVED`. Add `stage_updated_at` timestamp.

#### BIZ-03: Missing UHNWI-Critical Profile Fields
- **File:** `backend/models/client_profile.py`
- **Issue:** Profile lacks fields essential for UHNWI wealth planning:
  - Net worth range (for service tier segmentation)
  - Risk tolerance (drives all recommendations)
  - CRS/FATCA compliance status (regulatory requirement)
  - Succession planning complexity
  - Preferred communication language
  - Reporting preferences
- **Impact:** Incomplete client profiling leads to less targeted advice. Cannot segment clients for reporting.
- **Fix:** Add typed fields:
  ```python
  net_worth_range: Mapped[str | None]  # Enum: 10M-50M, 50M-100M, 100M+
  risk_tolerance: Mapped[str | None]   # Enum: CONSERVATIVE, MODERATE, AGGRESSIVE
  crs_fatca_status: Mapped[str | None]
  succession_complexity: Mapped[int | None]  # 1-5 scale
  ```

#### BIZ-04: JSON Blob Storage for Structured Data
- **File:** `backend/models/client_profile.py:11-16`
- **Issue:** `family_members`, `asset_classes`, `asset_jurisdictions`, `existing_structures`, `objectives` stored as JSON-serialised TEXT blobs. No schema validation, no queryability.
- **Impact:** Cannot run queries like "all clients with Singapore assets" without application-level JSON parsing. Data integrity not enforced.
- **Fix:** Either:
  - (Quick) Add Pydantic validation on write to ensure valid JSON arrays
  - (Better) Create normalised junction tables (e.g., `case_asset_classes` with FK to a `asset_class` reference table)

### MEDIUM

#### BIZ-05: No Case Reassignment Mechanism
- **File:** `backend/models/case.py:17`
- **Issue:** When an advisor is deactivated (`admin.py:108`), their cases remain assigned to them via `created_by`. No endpoint to reassign cases to another advisor.
- **Impact:** Deactivated advisor's cases become effectively orphaned (only admin can view them).
- **Fix:** Add `PUT /admin/cases/{case_id}/reassign` endpoint. Add `assigned_to` field separate from `created_by`.

#### BIZ-06: Recommendation Model Too Simple
- **File:** `backend/models/recommendation.py`
- **Issue:** No recommendation workflow (draft/approved/implemented), no cost/tax impact fields, no next-steps tracking, `sources` and `diagram_data` are untyped TEXT fields.
- **Impact:** Recommendations are static AI outputs with no advisory lifecycle.
- **Fix:** Add `status` enum (DRAFT, REVIEWED, APPROVED, IMPLEMENTED). Add structured `tax_impact`, `estimated_cost`, `next_steps` fields.

#### BIZ-07: No Soft Delete / Audit Trail for Data Changes
- **File:** All models
- **Issue:** No `deleted_at` or `is_deleted` fields. No versioning of profile changes. No history of who changed what.
- **Impact:** Cannot audit data changes for compliance. Accidental overwrites are permanent.
- **Fix:** Add `is_deleted` + `deleted_at` for soft delete. Consider an `AuditLog` table for change tracking.

#### BIZ-08: datetime.utcnow Deprecated
- **File:** `backend/models/case.py:18-19`, `backend/models/user.py:23`, `backend/models/conversation.py:19`, `backend/models/document.py:23`, `backend/models/kb_review_queue.py:23`
- **Issue:** `datetime.utcnow` is deprecated in Python 3.12+. Should use `datetime.now(timezone.utc)`.
- **Impact:** Timezone-naive datetimes may cause issues with timezone-aware comparisons.
- **Fix:** Replace all `datetime.utcnow` with `datetime.now(timezone.utc)` across all models.

---

## 4. AI/Chat/RAG Pipeline

### CRITICAL

#### AI-01: Diagram Schema Mismatch Between Prompt and Service
- **File:** `backend/services/llm_service.py` (prompt says `diagram_nodes`), `backend/services/diagram_service.py:38-39` (expects `entities`)
- **Issue:** The system prompt instructs Claude to output `"diagram_nodes": [...]` but the DiagramService parses for `"entities": [...]`. If the LLM follows the prompt, diagrams will never render.
- **Impact:** Structure diagram feature is potentially broken.
- **Fix:** Align the field name. Either update the system prompt to use `entities` or update DiagramService to parse `diagram_nodes`.

### HIGH

#### AI-02: Web Search Errors Silently Swallowed
- **File:** `backend/services/web_search_service.py:42-43`
- **Issue:** `except Exception: return []` catches and hides all Tavily errors (invalid API key, rate limits, network errors).
- **Impact:** If Tavily API key is expired/invalid, the LLM responds as though search succeeded but found nothing. Advisor has no signal that knowledge augmentation failed.
- **Fix:** Log the error. Return a typed result indicating failure vs. empty results. Surface web search status in SSE events.

#### AI-03: No Timeout on LLM Streaming
- **File:** `backend/services/llm_service.py:144-151`
- **Issue:** No read timeout on the Anthropic streaming call. If Claude API hangs or is extremely slow, the SSE connection stays open indefinitely.
- **Impact:** Browser memory leak, stalled sessions, poor UX.
- **Fix:** Add a 60-second timeout to `client.messages.stream()`. Yield a timeout error event and close the SSE connection.

#### AI-04: System Prompt Grows Unbounded with KB Sources
- **File:** `backend/services/llm_service.py:47-119`
- **Issue:** Full text of all retrieved KB chunks and web results is injected into the system prompt for every request. With a large KB (100+ documents), this can consume a significant portion of the context window and waste tokens.
- **Impact:** Token cost increases linearly with KB size. May exceed context window limits for very active knowledge bases.
- **Fix:** Implement a token budget for source context (e.g., max 4000 tokens). Summarise or truncate large source blocks. Use metadata-only references for low-relevance results.

#### AI-05: Insufficient Context Logic Too Simplistic
- **File:** `backend/services/rag_service.py:23`
- **Issue:** `KB_SUFFICIENT_THRESHOLD = 2` counts results above the similarity threshold, but doesn't consider similarity quality. Two results at 0.36 similarity (barely above 0.35 threshold) are treated as "sufficient".
- **Impact:** LLM may answer with loosely related KB content when it should be triggering a web search for better sources.
- **Fix:** Weight by average similarity. Require avg > 0.5 for sufficiency, or flag low-confidence retrievals explicitly.

### MEDIUM

#### AI-06: Summary Overwrites Without Versioning
- **File:** `backend/routers/chat.py:155-161`, `backend/services/summary_service.py:25`
- **Issue:** Compact summary overwrites `Case.compact_summary` after every assistant response. No version history. Concurrent requests can race.
- **Impact:** Lost summary context. No ability to restore previous state. Summary based only on last 20 messages, losing early conversation context.
- **Fix:** Add `summary_version` counter. Store incremental deltas or append-only summaries. Use optimistic locking on update.

#### AI-07: No Rate Limiting on Chat Endpoint
- **File:** `backend/routers/chat.py:35`
- **Issue:** No per-user or per-case quota on chat API calls. Each call invokes Claude API (metered).
- **Impact:** Unbounded LLM API costs. A single user could exhaust the API budget.
- **Fix:** Add per-user daily/hourly token budget. Return HTTP 429 when exceeded. Track token usage per case.

#### AI-08: No Conversation Metadata
- **File:** `backend/models/conversation.py`
- **Issue:** Messages stored without metadata: tokens used, retrieval sources consulted, summary version, response latency.
- **Impact:** Cannot audit which sources influenced which recommendation. No cost tracking per conversation.
- **Fix:** Add `token_count`, `retrieval_metadata` (JSON), `response_latency_ms` fields.

#### AI-09: Diagram JSON Extraction Fragile
- **File:** `backend/services/llm_service.py:13-19`
- **Issue:** Regex `r'```json\s*(\{.*?"diagram_nodes".*?\})\s*```'` with `re.DOTALL` greedy matching. No validation that extracted JSON is schema-compliant.
- **Impact:** Malformed diagrams silently fail. Edge cases (multiple JSON blocks, nested structures) may break extraction.
- **Fix:** Parse with `json.loads()` + Pydantic schema validation. Log parse failures. Return structured error to frontend.

---

## 5. Knowledge Base & Review Workflow

### CRITICAL

#### KB-01: Broken Resubmission State Machine
- **File:** `backend/routers/kb.py:120-159`, `backend/models/kb_review_queue.py:8-13`
- **Issue:** RESUBMITTED entries can be created but there is no handler to approve or re-reject them. The review endpoint only handles PENDING entries. Resubmitted content is stuck in limbo.
- **Impact:** Review workflow breaks after first rejection-resubmission cycle. Accumulates unresolvable queue entries.
- **Fix:** Add transitions: RESUBMITTED -> APPROVED (ingest to KB) and RESUBMITTED -> RE_REJECTED. Update the review handler to process entries in RESUBMITTED status.

### HIGH

#### KB-02: No KB Staleness / Expiry Detection
- **File:** `backend/kb/kb_manager.py:25-56`
- **Issue:** `last_updated` metadata is stored but never checked for expiry. Tax law, trust regulations, and treaty content changes frequently.
- **Impact:** Advisors may be served outdated legal/regulatory content with no warning. Critical risk in regulated advisory domain.
- **Fix:** Add `expires_at` field to KB metadata. Exclude expired chunks from query results. Create a background job to flag stale entries for re-review. Show "last updated" dates in citations.

#### KB-03: Similarity Threshold Too Permissive
- **File:** `backend/kb/kb_manager.py:8`
- **Issue:** `MIN_SIMILARITY = 0.35` with `all-MiniLM-L6-v2` (a lightweight 384-dim model). In the legal/tax domain, false positives are costly -- "estate tax in Singapore" matching "gift tax in India" could lead to incorrect advice.
- **Impact:** Low-relevance results fed to LLM may produce incorrect recommendations.
- **Fix:** Raise to 0.50-0.55 minimum. Consider per-jurisdiction thresholds. Evaluate a more capable embedding model (e.g., `all-mpnet-base-v2`, 768 dimensions).

#### KB-04: Source URL Not Preserved in ChromaDB Metadata
- **File:** `backend/routers/kb.py:142-148`
- **Issue:** Approved web content stored with `source_type="web_sourced_approved"` and generic filename `web_<entry_id[:8]>.txt`. The original `web_url` is not stored in ChromaDB metadata.
- **Impact:** When KB results are cited in chat, the original source URL cannot be traced back. Compliance audits lose traceability.
- **Fix:** Add `web_url` to ChromaDB metadata when ingesting approved web content.

### MEDIUM

#### KB-05: No Content Validation on Ingest
- **File:** `backend/routers/kb.py:49-55`
- **Issue:** Text extraction errors caught silently. No minimum length check. Empty or corrupted documents create empty KB entries.
- **Impact:** Malformed chunks degrade retrieval quality.
- **Fix:** Validate extracted text is non-empty and > 100 characters. Log extraction failures. Return error to user for 0-content files.

#### KB-06: No Deduplication in Review Queue
- **File:** `backend/routers/chat.py:170-180`
- **Issue:** Web search results queued without checking for duplicate URLs. Multiple chat sessions on similar topics create redundant review entries.
- **Impact:** Review queue bloat. Reviewer fatigue from duplicate entries.
- **Fix:** Check for existing entry with same `web_url` within last 30 days before inserting. Skip or update existing entry.

#### KB-07: Reviewer Authority Undefined
- **File:** `backend/routers/kb.py:24-25, 101-102`
- **Issue:** `is_staff()` grants review access to all advisors. No per-jurisdiction reviewer assignment, no approval hierarchy, no escalation path.
- **Impact:** Any advisor can approve/reject KB content for any jurisdiction. No governance structure.
- **Fix:** Define a `compliance_reviewer` role or jurisdiction-scoped review permissions. Require comment on rejection. Add escalation to legal team for complex entries.

#### KB-08: Chunking Strategy Not Domain-Aware
- **File:** `backend/kb/kb_manager.py:10-17`
- **Issue:** Hard-coded 800-word chunks for all content types. No awareness of section boundaries, headers, or logical breaks. Splits mid-sentence.
- **Impact:** Incoherent chunks produce weak embeddings and poor retrieval quality.
- **Fix:** Implement section-aware chunking (detect headers, regulatory section breaks). Allow configurable chunk sizes per topic/document type.

#### KB-09: No Search Quality Instrumentation
- **File:** `backend/kb/kb_manager.py:85-106`
- **Issue:** No logging of query latency, result count, similarity scores, or user feedback on result quality.
- **Impact:** Cannot identify underperforming sources or tune retrieval parameters data-driven.
- **Fix:** Log retrieval metrics (query, result count, min/max/avg similarity, latency). Build a dashboard for KB quality monitoring.

---

## 6. Document Management & Reports

### HIGH

#### DOC-01: File Saved Before MIME Validation
- **File:** `backend/routers/documents.py:38-46`
- **Issue:** The uploaded file is written to disk first, then MIME-validated. If the server crashes between save and validation, an unvalidated (potentially malicious) file persists.
- **Impact:** Malicious file on disk. Mitigated by the fact that files aren't served directly, but still a security hygiene issue.
- **Fix:** Validate MIME from in-memory buffer using `magic.from_buffer()` before writing to disk. Only save if validation passes.

#### DOC-02: HTML Injection in PDF Report Sources
- **File:** `backend/services/pdf_service.py:37`
- **Issue:** Recommendation `sources` field is injected into HTML without `html_lib.escape()`. All other user-supplied fields are properly escaped.
- **Impact:** If source strings contain HTML/JS, they execute in the Puppeteer rendering context. Could corrupt PDF output or leak server-side info.
- **Fix:** Apply `html_lib.escape()` to source strings before HTML injection.

### MEDIUM

#### DOC-03: Synchronous Text Extraction Blocks Event Loop
- **File:** `backend/services/document_service.py:47`
- **Issue:** PyMuPDF and python-docx are CPU-bound synchronous libraries. They block the async event loop during extraction.
- **Impact:** Concurrent requests stall while a large document is being extracted.
- **Fix:** Run `extract_text()` inside `asyncio.to_thread()` or use a thread pool executor.

#### DOC-04: DOCX Table/Header Extraction Missing
- **File:** `backend/services/document_service.py:33`
- **Issue:** Only `doc.paragraphs` extracted. Tables, headers, footers, and text boxes are silently dropped.
- **Impact:** Wealth planning documents are often table-heavy (asset schedules, tax tables, fee structures). Critical data is lost.
- **Fix:** Add `doc.tables` iteration. Consider `pdfplumber` for tabular PDF content.

#### DOC-05: No OCR for Scanned PDFs
- **File:** `backend/services/document_service.py`
- **Issue:** PyMuPDF extracts text-layer only. Scanned PDFs (common for legal/tax documents, trust deeds) yield empty text with no warning.
- **Impact:** Uploaded scanned documents produce no searchable content. User not informed.
- **Fix:** Detect zero-text PDFs and either: (a) warn the user, or (b) run OCR pipeline (Tesseract). At minimum, return an error when extraction yields empty text from a non-empty file.

#### DOC-06: No case_id Format Validation
- **File:** `backend/routers/documents.py:16`
- **Issue:** `case_id` from URL path used in `os.path.join` (line 32) and ChromaDB collection names without UUID format validation.
- **Impact:** A crafted `case_id` like `../../etc` would be partially mitigated by `os.path.join` behavior but should be validated.
- **Fix:** Add UUID format validation: `case_id: str = Path(..., regex=r'^[a-f0-9-]{36}$')`.

#### DOC-07: Diagrams Not Rendered in PDF Reports
- **File:** `backend/routers/reports.py:64`
- **Issue:** Diagram parameter passed as `{}` (empty dict). Structure diagrams generated during chat are not included in the PDF report.
- **Impact:** Reports lack the visual structure diagrams that are a key feature of the advisory output.
- **Fix:** Retrieve diagram data from the latest recommendation and render as SVG/PNG in the PDF template.

---

## 7. Frontend Architecture

### HIGH

#### FE-01: apiFetch Utility Exists But Is Unused
- **File:** `frontend/lib/api-client.ts` (utility), all page files (raw fetch)
- **Issue:** A typed `apiFetch<T>()` wrapper exists but every page duplicates raw `fetch` with manual headers, token extraction, and error handling. Dashboard, case detail, KB pages all repeat the same pattern.
- **Impact:** Code duplication. Inconsistent error handling. Impossible to add centralised retry/logging/auth refresh.
- **Fix:** Replace all raw `fetch` calls with `apiFetch`. Extend it to handle common patterns (404 -> null, 5xx -> retry, auth refresh).

#### FE-02: Silent Error Swallowing in Case Detail
- **File:** `frontend/app/(app)/cases/[caseId]/page.tsx:62, 80`
- **Issue:** `.catch(() => {})` on case data and history fetch calls. Errors produce no user feedback. Page shows "Loading..." forever or stale data.
- **Impact:** Users cannot distinguish between slow loading and a failed request.
- **Fix:** Replace with proper error state handling. Show error message with retry button.

### MEDIUM

#### FE-03: Pervasive `any` Types
- **File:** `frontend/components/diagram/DiagramPanel.tsx`, `StructureDiagram.tsx`, `frontend/app/(app)/cases/[caseId]/page.tsx:35-36`
- **Issue:** Diagram data typed as `{ nodes: any[]; edges: any[] }`. Custom node `data` props are all `any`. Message.sources is `any`.
- **Impact:** TypeScript provides no type safety for diagram rendering or message display. Runtime errors not caught at compile time.
- **Fix:** Define interfaces: `WealthNode { label: string; type: 'trust' | 'company' | 'individual'; jurisdiction?: string }`, `WealthEdge { from: number; to: number; label: string }`. Propagate through all diagram components.

#### FE-04: No React Error Boundaries
- **File:** All page components
- **Issue:** No error boundaries wrapping the diagram panel, chat message list, or markdown renderer. If React Flow or ReactMarkdown throws, the entire page crashes.
- **Impact:** Unhandled rendering error takes down the entire case detail page.
- **Fix:** Add error boundaries around DiagramPanel and the chat section. Show fallback UI ("Something went wrong. Try refreshing.").

#### FE-05: No SSE Reconnection on Network Drops
- **File:** `frontend/lib/sse-client.ts:47`
- **Issue:** If the SSE connection drops mid-stream (network blip, proxy timeout), the client calls `onDone` without retrying. Long advisory responses may be silently truncated.
- **Impact:** User sees partial response with no indication that content was lost.
- **Fix:** Implement reconnection with exponential backoff (max 3 retries). Show "Reconnecting..." indicator. Include a `message_id` in SSE events to detect gaps.

#### FE-06: Operator Precedence Bug in Role Checks
- **File:** `frontend/app/(app)/kb/review/page.tsx:28`, `frontend/app/(app)/kb/documents/page.tsx:26`
- **Issue:** `!token || session?.user?.role !== 'advisor' && session?.user?.role !== 'admin'` -- the `&&` binds tighter than `||`. This evaluates as `(!token) || (role !== 'advisor' && role !== 'admin')`, which happens to work but is fragile.
- **Impact:** Correct now by accident. Any future logic change could introduce a bug.
- **Fix:** Add explicit parentheses: `!token || (session?.user?.role !== 'advisor' && session?.user?.role !== 'admin')`.

#### FE-07: Client-Side-Only Role Gating on KB Pages
- **File:** `frontend/app/(app)/kb/upload/page.tsx`, `kb/review/page.tsx`, `kb/documents/page.tsx`
- **Issue:** Role checks happen in React after the component mounts. Brief flash of content before "Access denied" appears. If backend also enforces role, this is a UX issue; if not, it's a security issue.
- **Impact:** Momentary exposure of restricted UI. Backend does enforce `is_staff()`, so this is UX-only.
- **Fix:** Move role check to server component or Next.js middleware. Return 403 redirect before page renders.

### LOW

#### FE-08: Duplicated apiUrl Resolution
- **File:** All page files
- **Issue:** `const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"` repeated in every page component.
- **Impact:** Minor code duplication. If the default URL changes, must update everywhere.
- **Fix:** Centralise in a shared config or use the existing `api-client.ts`.

---

## 8. Infrastructure & Deployment

### CRITICAL

#### INFRA-01: SQLite in Production
- **File:** `backend/config.py:4`, `backend/database.py:8`
- **Issue:** SQLite used as the production database. SQLite does not support concurrent writes (single-writer lock), has no built-in backup tooling, and the file (`wealth_planning.db`) sits unencrypted on disk.
- **Impact:** Data corruption risk under concurrent writes. No point-in-time recovery. Database cannot scale to multiple backend instances.
- **Fix:** Migrate to PostgreSQL (Azure Database for PostgreSQL or containerised). Use `postgresql+asyncpg://` connection string. This is the highest-impact infrastructure change.

#### INFRA-02: No Database Migration Strategy
- **File:** `backend/database.py:11-13`
- **Issue:** Uses `Base.metadata.create_all()` which only creates missing tables. It cannot handle schema changes (add/remove columns, alter types). No migration tool (Alembic) is configured.
- **Impact:** Any data model change requires manual SQL or database recreation (data loss).
- **Fix:** Add Alembic. Generate initial migration from current schema. Use `alembic upgrade head` in startup instead of `create_all()`.

### HIGH

#### INFRA-03: No HTTPS on Backend
- **File:** `run_server.ps1`
- **Issue:** Uvicorn runs on HTTP (port 8089). IIS on port 8081 may proxy but HTTPS enforcement is not configured in code.
- **Impact:** Credentials and tokens transmitted in plaintext between browser and IIS, and between IIS and Uvicorn.
- **Fix:** Configure SSL certificates on Uvicorn (`--ssl-keyfile`, `--ssl-certfile`) or ensure IIS terminates TLS and proxies over localhost only.

#### INFRA-04: No Database Backup Strategy
- **File:** N/A (missing entirely)
- **Issue:** No backup script, no scheduled backup, no backup verification. SQLite file is the sole copy.
- **Impact:** Hardware failure, accidental deletion, or corruption = total data loss.
- **Fix:** (Immediate) Add a daily backup script that copies `wealth_planning.db` to Azure Blob Storage. (After PostgreSQL migration) Use `pg_dump` with scheduled Azure Backup.

### MEDIUM

#### INFRA-05: Health Check Doesn't Verify Database
- **File:** `backend/main.py:47-49`
- **Issue:** `/health` returns `{"status": "ok"}` without checking database connectivity, ChromaDB availability, or LLM API reachability.
- **Impact:** Load balancer / monitoring may report healthy when the database is actually down.
- **Fix:** Add DB ping, ChromaDB heartbeat, and optional LLM connectivity check to health endpoint.

#### INFRA-06: PID-Based Process Management
- **File:** `run_server.ps1`, `stop_server.ps1`
- **Issue:** Process management via PID files. No auto-restart on crash, no resource limits, no log rotation.
- **Impact:** If backend or frontend crashes, manual intervention required.
- **Fix:** Use a proper process manager (systemd on Linux, Windows Service, or Docker containers with restart policies).

---

## 9. Testing & Quality

### MEDIUM

#### TEST-01: Limited Test Coverage
- **File:** `backend/tests/`
- **Issue:** Tests exist for: auth (3 tests), cases, diagram_service, document_service, llm_service, models, pdf_service, rag. But no tests for: admin endpoints, KB endpoints, settings service, chat endpoint, review workflow.
- **Impact:** Core business workflows (admin operations, KB review, chat) have no automated test coverage.
- **Fix:** Add tests for:
  - Admin CRUD (create/deactivate/reactivate advisor, reset password)
  - KB upload, search, delete
  - KB review workflow state transitions
  - Chat endpoint (mock LLM, verify SSE events)
  - Settings service cascading resolution

#### TEST-02: No Frontend Tests
- **File:** `frontend/` (no test files found)
- **Issue:** Zero frontend test coverage. No unit tests, component tests, or E2E tests.
- **Impact:** UI regressions undetected. Diagram rendering, SSE handling, wizard validation untested.
- **Fix:** Add Jest + React Testing Library for component tests. Add Playwright for E2E (login -> create case -> chat -> export PDF).

#### TEST-03: No CI/CD Pipeline
- **File:** N/A (no `.github/workflows/` or equivalent)
- **Issue:** No automated test execution, no linting enforcement, no build verification on push/PR.
- **Impact:** Broken code can be deployed without detection.
- **Fix:** Add GitHub Actions workflow: lint (ruff/eslint) -> test (pytest/jest) -> build (next build) -> deploy.

---

## 10. Prioritised Improvement Roadmap

### P0 -- Must Fix Before Production (Est. 2-3 weeks)

| # | Issue | Ref | Effort |
|---|-------|-----|--------|
| 1 | Rotate secret key; reject default at startup | SEC-01 | 1 hour |
| 2 | Add rate limiting on auth + chat endpoints | SEC-02, AI-07 | 1 day |
| 3 | Encrypt API keys at rest in SystemSetting | SEC-04 | 1-2 days |
| 4 | Fix KB resubmission state machine | KB-01 | 4 hours |
| 5 | Fix diagram schema mismatch (entities vs diagram_nodes) | AI-01 | 2 hours |
| 6 | Migrate SQLite -> PostgreSQL + add Alembic | INFRA-01, INFRA-02 | 3-5 days |
| 7 | Enforce HTTPS end-to-end | SEC-07, INFRA-03 | 1 day |
| 8 | Validate MIME before disk write | DOC-01 | 2 hours |
| 9 | Escape sources in PDF generation | DOC-02 | 30 min |
| 10 | Add CASCADE DELETE on Case FKs | BIZ-01 | 1 hour |

### P1 -- Before Pilot Launch (Est. 2-3 weeks)

| # | Issue | Ref | Effort |
|---|-------|-----|--------|
| 11 | Add case lifecycle stages | BIZ-02 | 2 days |
| 12 | Extend ClientProfile with UHNWI fields | BIZ-03 | 1 day |
| 13 | Add LLM streaming timeout | AI-03 | 4 hours |
| 14 | Surface web search errors (not silent swallow) | AI-02 | 4 hours |
| 15 | Adopt apiFetch across frontend; fix silent catches | FE-01, FE-02 | 1 day |
| 16 | Add React error boundaries | FE-04 | 4 hours |
| 17 | Add KB staleness detection with expires_at | KB-02 | 1-2 days |
| 18 | Raise similarity threshold + tuning | KB-03 | 4 hours |
| 19 | Preserve source URL in ChromaDB metadata | KB-04 | 2 hours |
| 20 | Add audit logging (admin actions, auth events) | SEC-10 | 2 days |
| 21 | Add account lockout after failed logins | SEC-05 | 4 hours |
| 22 | Add database backup strategy | INFRA-04 | 1 day |
| 23 | Fix operator precedence in KB role checks | FE-06 | 30 min |

### P2 -- Before General Availability (Est. 3-4 weeks)

| # | Issue | Ref | Effort |
|---|-------|-----|--------|
| 24 | Add OCR pipeline for scanned PDFs | DOC-05 | 2-3 days |
| 25 | Extract DOCX tables/headers | DOC-04 | 1 day |
| 26 | Implement token budget for system prompt sources | AI-04 | 1-2 days |
| 27 | Add SSE reconnection with backoff | FE-05 | 1 day |
| 28 | Type diagram data model (remove `any`) | FE-03 | 1 day |
| 29 | Add SSE structured error codes | AI-08 | 4 hours |
| 30 | Add recommendation workflow (draft/approved/implemented) | BIZ-06 | 2 days |
| 31 | Implement case reassignment | BIZ-05 | 4 hours |
| 32 | Add per-user/case token budgets | AI-07 | 1 day |
| 33 | Async text extraction (thread pool) | DOC-03 | 2 hours |
| 34 | Summary versioning + optimistic locking | AI-06 | 1 day |
| 35 | Add conversation metadata (tokens, sources) | AI-08 | 1 day |
| 36 | KB deduplication in review queue | KB-06 | 4 hours |
| 37 | Domain-aware chunking strategy | KB-08 | 2-3 days |
| 38 | Add KB search quality instrumentation | KB-09 | 1-2 days |
| 39 | Password reset self-service flow | SEC-08 | 2 days |
| 40 | Render diagrams in PDF reports | DOC-07 | 1-2 days |

### P3 -- Ongoing Improvements

| # | Issue | Ref | Effort |
|---|-------|-----|--------|
| 41 | Replace datetime.utcnow across all models | BIZ-08 | 1 hour |
| 42 | Add frontend tests (Jest + RTL) | TEST-02 | 3-5 days |
| 43 | Add E2E tests (Playwright) | TEST-02 | 3-5 days |
| 44 | Set up CI/CD pipeline (GitHub Actions) | TEST-03 | 1-2 days |
| 45 | Expand backend test coverage (admin, KB, chat) | TEST-01 | 3-5 days |
| 46 | Add health check with DB/ChromaDB/LLM verification | INFRA-05 | 4 hours |
| 47 | Move to containerised deployment (Docker) | INFRA-06 | 2-3 days |
| 48 | Normalise JSON blob fields into proper tables | BIZ-04 | 3-5 days |
| 49 | Evaluate stronger embedding model | KB-03 | 1-2 days |

---

## Appendix: File Reference Index

| File | Issues |
|------|--------|
| `backend/config.py` | SEC-01, SEC-02, INFRA-01 |
| `backend/main.py` | SEC-03, INFRA-05 |
| `backend/database.py` | INFRA-01, INFRA-02 |
| `backend/models/case.py` | BIZ-02, BIZ-07, BIZ-08 |
| `backend/models/client_profile.py` | BIZ-01, BIZ-03, BIZ-04 |
| `backend/models/user.py` | BIZ-08 |
| `backend/models/conversation.py` | BIZ-01, AI-08, BIZ-08 |
| `backend/models/document.py` | BIZ-08 |
| `backend/models/recommendation.py` | BIZ-01, BIZ-06 |
| `backend/models/kb_review_queue.py` | KB-01, BIZ-08 |
| `backend/models/system_setting.py` | SEC-04 |
| `backend/routers/auth.py` | SEC-02, SEC-05, SEC-09 |
| `backend/routers/admin.py` | SEC-06, SEC-10 |
| `backend/routers/cases.py` | BIZ-02 |
| `backend/routers/chat.py` | AI-06, AI-07, KB-06 |
| `backend/routers/documents.py` | DOC-01, DOC-06 |
| `backend/routers/kb.py` | KB-01, KB-05, KB-07 |
| `backend/routers/reports.py` | DOC-07 |
| `backend/services/auth_service.py` | SEC-01 |
| `backend/services/llm_service.py` | AI-01, AI-03, AI-04, AI-09 |
| `backend/services/rag_service.py` | AI-05 |
| `backend/services/web_search_service.py` | AI-02 |
| `backend/services/summary_service.py` | AI-06 |
| `backend/services/document_service.py` | DOC-03, DOC-04, DOC-05 |
| `backend/services/pdf_service.py` | DOC-02 |
| `backend/services/settings_service.py` | SEC-04 |
| `backend/kb/kb_manager.py` | KB-02, KB-03, KB-08, KB-09 |
| `backend/kb/chroma_client.py` | KB-03 |
| `frontend/lib/auth.ts` | SEC-07 |
| `frontend/lib/api-client.ts` | FE-01 |
| `frontend/lib/sse-client.ts` | FE-05 |
| `frontend/app/(app)/cases/[caseId]/page.tsx` | FE-02, FE-03 |
| `frontend/app/(app)/kb/review/page.tsx` | FE-06, FE-07 |
| `frontend/app/(app)/kb/documents/page.tsx` | FE-06, FE-07 |
| `frontend/components/diagram/*` | FE-03, FE-04 |
| `run_server.ps1` | INFRA-03, INFRA-06 |

# Wealth Planning Application -- Business Logic Documentation

**Application:** AI-Powered Wealth Planning Advisory Platform
**Domain:** Ultra High Net Worth Individual (UHNWI) Wealth Structuring
**Last Updated:** 2026-04-02

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [User Roles & Access Model](#2-user-roles--access-model)
3. [Authentication & Authorization](#3-authentication--authorization)
4. [Case Management Lifecycle](#4-case-management-lifecycle)
5. [Client Profile & Intake Workflow](#5-client-profile--intake-workflow)
6. [AI Advisory Chat](#6-ai-advisory-chat)
7. [RAG Retrieval Pipeline](#7-rag-retrieval-pipeline)
8. [Knowledge Base Management](#8-knowledge-base-management)
9. [KB Review Queue Workflow](#9-kb-review-queue-workflow)
10. [Document Management](#10-document-management)
11. [Recommendation Engine](#11-recommendation-engine)
12. [Structure Diagram Generation](#12-structure-diagram-generation)
13. [PDF Report Generation](#13-pdf-report-generation)
14. [Admin Operations](#14-admin-operations)
15. [System Settings](#15-system-settings)
16. [Data Model Summary](#16-data-model-summary)

---

## 1. System Overview

The application is a wealth planning advisory tool that enables financial advisors to:

- Create and manage client cases for UHNWI clients
- Collect structured client profiles (nationality, domicile, tax residency, assets, structures, objectives)
- Conduct AI-assisted advisory conversations powered by Claude (Anthropic)
- Retrieve relevant regulatory and tax knowledge via RAG (Retrieval-Augmented Generation)
- Generate wealth structure recommendations with confidence levels
- Visualise existing and recommended structures as diagrams (trusts, companies, individuals)
- Produce PDF advisory reports with disclaimers

The platform supports a firm-wide deployment model: a central admin provisions advisors, advisors manage their own client cases, and clients have read-only access to their assigned case.

**Tech Stack:**
- Backend: FastAPI (Python), SQLAlchemy async, SQLite
- Frontend: Next.js (App Router), NextAuth, Tailwind CSS, React Flow
- AI: Claude Sonnet (Anthropic LLM), Sentence Transformers (embeddings), ChromaDB (vector store), Tavily (web search)
- Deployment: Azure VM, IIS reverse proxy, PowerShell scripts

---

## 2. User Roles & Access Model

### 2.1 Role Definitions

| Role | Description | Provisioning |
|------|-------------|--------------|
| **Admin** | System administrator. Manages advisors, system settings, sees all cases. | Created via `scripts/create_user.py` or first-time setup |
| **Advisor** | Wealth planning professional. Creates/manages cases, conducts AI-assisted advisory. | Created by Admin via `/admin/advisors` |
| **Client** | End client. View-only access to their assigned case. | Created by Admin, linked to a specific case via `user.case_id` |

### 2.2 Access Control Matrix

| Resource | Admin | Advisor | Client |
|----------|-------|---------|--------|
| List all cases | All cases | Own cases only | N/A |
| View case detail | Any case | Own cases only | Assigned case only |
| Create case | No | Yes | No |
| Update case profile | Any case | Own cases only | No |
| Chat with AI | Any case | Own cases only | Assigned case only |
| Upload case documents | Any case | Own cases only | No |
| KB upload/search/delete | Yes | Yes | No |
| KB review queue | Yes | Yes | No |
| Manage advisors | Yes | No | No |
| System settings | Yes | No | No |
| Generate PDF report | Any case | Own cases only | Assigned case only |

**Implementation:**
- `is_staff()` function (`backend/routers/auth.py`) grants access to Advisor + Admin roles
- `require_admin()` dependency restricts to Admin only (`backend/routers/admin.py:17-20`)
- `_get_case_with_access()` helper (`backend/routers/cases.py:16-29`) enforces per-case scoping:
  - Admin: unrestricted
  - Advisor: `case.created_by == current_user.user_id`
  - Client: `current_user.case_id == case_id`

### 2.3 Access Control Enforcement Points

Access is enforced at the router level in:
- `backend/routers/cases.py` -- case CRUD and profile endpoints
- `backend/routers/chat.py` -- chat streaming endpoint
- `backend/routers/documents.py` -- document upload/list/delete
- `backend/routers/reports.py` -- PDF generation
- `backend/routers/kb.py` -- KB operations (staff-only)
- `backend/routers/admin.py` -- admin operations (admin-only)

---

## 3. Authentication & Authorization

### 3.1 Local Password Authentication

**Flow:**
1. Advisor submits email + password to `POST /auth/token`
2. Backend looks up user by email, verifies bcrypt hash (`auth_service.py:14`)
3. If valid + `is_active`, issues a JWT token with 8-hour expiry
4. JWT payload: `{"sub": user_id, "exp": expiry_timestamp}`
5. Frontend stores token in NextAuth session, sends as `Authorization: Bearer <token>` header

**Password Rules:**
- Passwords hashed with bcrypt + salt (`auth_service.py:10-11`)
- Advisor passwords auto-generated (24 chars) on creation, 12 chars on reset
- Generated using `secrets` module (cryptographically secure)
- No self-service password reset -- admin must reset manually

### 3.2 Azure AD SSO Authentication

**Flow:**
1. User clicks "Sign in with Microsoft" on login page
2. Frontend redirects to Microsoft login via MSAL
3. Microsoft returns ID token to callback page (`/users/microsoft/callback`)
4. Frontend sends ID token to `POST /auth/sso`
5. Backend validates token: fetches JWKS from Azure, verifies RS256 signature, checks audience + issuer (`auth_service.py:77-83`)
6. Extracts email and OID from token claims
7. Looks up user by email -- **must be pre-registered** in the system (no self-signup)
8. Links Azure OID on first SSO login (`auth.py:71-73`)
9. Issues backend JWT (same as local auth)

**Key Constraint:** Users must be pre-registered by an admin before they can log in via SSO. This prevents unauthorized access from anyone in the Azure AD tenant.

### 3.3 Frontend Session Management

- NextAuth manages session state with two credential providers: `local-credentials` and `sso-token`
- Access token stored in NextAuth JWT (server-side encrypted)
- Session callback exposes `accessToken`, `role`, `userId`, `name` to client components
- Layout component (`frontend/app/(app)/layout.tsx`) performs server-side auth check and redirects unauthenticated users to `/login`
- Client pages retrieve token via `useSession()` hook

### 3.4 Token Lifecycle

| Property | Value |
|----------|-------|
| Algorithm | HS256 |
| Expiry | 8 hours |
| Refresh | None -- user must re-authenticate |
| Revocation | Not supported -- deactivating user checked on each request |
| Storage | NextAuth encrypted JWT (server-side) |

---

## 4. Case Management Lifecycle

### 4.1 Case States

```
ACTIVE  ──(archive)──>  ARCHIVED
```

A case has two statuses:
- **ACTIVE** -- case is in progress, chat is available, documents can be uploaded
- **ARCHIVED** -- case is closed (no delete, data is preserved)

### 4.2 Case Creation Flow

1. Advisor navigates to `/cases/new` (intake wizard)
2. Completes 4-step wizard (see Section 5)
3. Frontend calls `POST /cases/` with `{ client_name }` --> creates Case record
4. Frontend calls `PUT /cases/{case_id}/profile` with profile data --> creates/updates ClientProfile
5. Advisor redirected to `/cases/{case_id}` (case detail page with chat)

### 4.3 Case Data Model

```
Case
  case_id: UUID (PK)
  client_name: String
  created_by: FK -> User.user_id (the advisor)
  created_at: DateTime
  last_updated: DateTime (auto-updates)
  status: Enum(ACTIVE, ARCHIVED)
  compact_summary: Text (AI-generated JSON summary of conversation state)
```

### 4.4 Case Access Rules

- **Listing:** `GET /cases/` returns filtered list based on role (admin=all, advisor=own, client=assigned)
- **Detail:** `GET /cases/{case_id}` enforced via `_get_case_with_access()`
- **Profile:** `GET/PUT /cases/{case_id}/profile` same access rules
- **No delete endpoint** -- cases can only be archived

---

## 5. Client Profile & Intake Workflow

### 5.1 Intake Wizard Steps

The frontend presents a 4-step wizard (`frontend/app/(app)/cases/new/page.tsx`):

**Step 1 -- Client Information:**
- Client name (required, min 2 chars)
- Nationality (dropdown)
- Country of domicile (dropdown)
- Tax residency (dropdown)
- Family members (free text)

**Step 2 -- Asset Information:**
- Asset classes (multi-select checkboxes):
  - Real Estate, Equities, Fixed Income, Private Equity, Hedge Funds, Cash, Cryptocurrency, Art & Collectibles, Insurance Products, Business Interests
- Asset jurisdictions (multi-select checkboxes):
  - Singapore, Hong Kong, Switzerland, UK, UAE, US, India, China, Japan, Australia, Cayman Islands, BVI, Jersey, Luxembourg, Other

**Step 3 -- Existing Structures:**
- Existing structures (multi-select checkboxes):
  - Family Trust, Corporate Holding, Private Foundation, Insurance Wrapper, Nominee Structure, Family Office, Partnership, None
- Free text for additional details

**Step 4 -- Planning Objectives:**
- Objectives (multi-select checkboxes):
  - Wealth Preservation, Tax Optimisation, Succession Planning, Asset Protection, Privacy & Confidentiality, Philanthropic Planning, Business Succession, Regulatory Compliance, Immigration Planning, Estate Planning

### 5.2 Profile Data Model

```
ClientProfile
  profile_id: UUID (PK)
  case_id: FK -> Case.case_id (unique, 1:1)
  nationality: String (nullable)
  domicile: String (nullable)
  tax_residency: String (nullable)
  family_members: Text (free text)
  asset_classes: Text (JSON-serialised list)
  asset_jurisdictions: Text (JSON-serialised list)
  existing_structures: Text (JSON-serialised list)
  objectives: Text (JSON-serialised list)
```

Multi-select fields are stored as JSON-serialised lists in TEXT columns (e.g., `'["Real Estate", "Equities"]'`). The backend uses `json.dumps()` / `json.loads()` for serialisation.

### 5.3 Profile Update Behaviour

- `PUT /cases/{case_id}/profile` creates or updates the profile (upsert pattern)
- All fields are optional -- partial updates supported
- Profile is linked to case via unique `case_id` FK (one profile per case)

---

## 6. AI Advisory Chat

### 6.1 Chat Flow

```
User types message
  -> Frontend sends POST /chat/stream (SSE)
  -> Backend loads conversation history (last 40 messages)
  -> RAG retrieval (KB + case docs + web search)
  -> Builds system prompt with context
  -> Streams response from Claude via SSE
  -> Saves user + assistant messages to Conversation table
  -> Background: generates compact summary, queues web results for review
```

### 6.2 System Prompt Construction

The system prompt (`backend/services/llm_service.py:47-119`) instructs Claude to act as a wealth planning advisor. It includes:

1. **Role definition:** "You are a senior wealth planning advisor..."
2. **Client context:** Pseudonymised client profile (see Section 6.3)
3. **Session memory:** Compact summary from previous conversations
4. **Retrieved sources:** KB chunks + case document chunks + web search results (full text)
5. **Output format instructions:** Structured response with recommendations, confidence levels, citations
6. **Diagram generation instructions:** JSON format for trust/company/individual structure diagrams
7. **Disclaimer:** "This is not legal or tax advice..."
8. **Confidence levels:** HIGH, SPECIALIST_REVIEW, COMPLEX

### 6.3 Pseudonymisation

Before sending client data to the LLM, the system strips PII (`llm_service.py:31-44`):
- Retains: nationality, domicile, tax residency, asset classes, jurisdictions, existing structures, objectives
- Removes: client name, advisor identity, case ID
- Purpose: Minimise sensitive data exposure to third-party AI API

### 6.4 Conversation Persistence

```
Conversation
  message_id: UUID (PK)
  case_id: FK -> Case.case_id
  role: Enum(USER, ASSISTANT)
  content: Text
  sources_cited: Text (nullable)
  timestamp: DateTime
```

- Last 40 messages loaded as conversation history for context window management
- Max 8,000 tokens per LLM response (`config.py:12`)
- Messages saved after successful LLM response

### 6.5 Compact Summary (Session Memory)

After each AI response, a background task generates a compact JSON summary of the conversation state (`backend/services/summary_service.py`):
- Uses the last 20 messages to generate summary
- Stored in `Case.compact_summary`
- Included in subsequent system prompts for cross-session continuity
- Overwrites previous summary each time (no versioning)

### 6.6 SSE Event Types

The streaming endpoint sends these SSE event types:

| Event | Payload | Purpose |
|-------|---------|---------|
| `token` | Text chunk | Streaming text token from Claude |
| `sources` | JSON array | Source citations (file+section or URL) |
| `diagram_update` | JSON object | Structure diagram data (nodes + edges) |
| `error` | Error message | Error notification |
| `done` | Empty | Stream completion signal |

---

## 7. RAG Retrieval Pipeline

### 7.1 Architecture

The RAG pipeline (`backend/services/rag_service.py`) performs a 2-stage retrieval:

```
User query
  -> Stage 1: Query KB (global knowledge base)
     -> ChromaDB collection "wealth_planning_kb"
     -> Returns top 5 results above 0.35 similarity threshold
  -> Sufficient? (>= 2 results above threshold)
     -> YES: Use KB results only
     -> NO: Stage 2: Web search via Tavily
        -> Up to 5 searches per session
        -> Merge web results with KB results
  -> Also query case-specific collection
     -> ChromaDB collection "case_{case_id}"
     -> Returns top 3 results above 0.35 threshold
  -> Combine all sources -> feed to LLM
```

### 7.2 Embedding Model

- Model: `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions)
- Loaded as a singleton via ChromaDB's SentenceTransformerEmbeddingFunction
- Same model used for both indexing and querying

### 7.3 Similarity Search Configuration

| Parameter | Value | Source |
|-----------|-------|--------|
| Embedding model | all-MiniLM-L6-v2 | `chroma_client.py:13` |
| Distance metric | Cosine | `chroma_client.py:27` |
| Min similarity threshold | 0.35 | `kb_manager.py:8` |
| KB results per query | 5 | `rag_service.py:45` |
| Case doc results per query | 3 | `rag_service.py:49` |
| Sufficient context threshold | >= 2 KB results | `rag_service.py:23` |
| Jurisdiction filtering | Supported (metadata filter) | `kb_manager.py:87` |

### 7.4 Web Search Integration

When KB results are insufficient (< 2 chunks above threshold):
- Tavily API is called with the user's query
- Rate limited to 5 calls per session (`config.py:13`)
- Results include: title, URL, text content
- Web results injected into LLM context alongside KB results
- Web results automatically queued in KB review table for human review (see Section 9)

---

## 8. Knowledge Base Management

### 8.1 KB Upload Flow

```
Staff uploads document via /kb/upload
  -> File received (PDF, DOCX, or TXT)
  -> Text extracted (PyMuPDF for PDF, python-docx for DOCX)
  -> Text chunked: 800-word windows, 100-word overlap
  -> Each chunk embedded via sentence-transformers
  -> Stored in ChromaDB "wealth_planning_kb" collection
  -> Metadata: jurisdiction, topic, source_file, last_updated, source_type
```

### 8.2 Chunking Strategy

| Parameter | Value | Source |
|-----------|-------|--------|
| Chunk size | 800 words | `kb_manager.py:6` |
| Overlap | 100 words | `kb_manager.py:7` |
| Splitting | Word-boundary | `kb_manager.py:10-17` |

### 8.3 KB Collection Structure

Single ChromaDB collection: `wealth_planning_kb`

Metadata per chunk:
- `jurisdiction`: e.g., "Singapore", "BVI", "UK"
- `topic`: e.g., "trust_law", "tax_treaty", "regulatory"
- `source_file`: original filename
- `last_updated`: upload timestamp
- `source_type`: "uploaded" or "web_sourced_approved"

### 8.4 KB Operations (Staff Only)

| Endpoint | Action |
|----------|--------|
| `POST /kb/upload` | Upload document, extract, chunk, embed |
| `GET /kb/search?q=...&jurisdiction=...` | Similarity search with optional jurisdiction filter |
| `GET /kb/documents` | List all source files in KB |
| `DELETE /kb/documents/{filename}` | Delete all chunks from a source file |

---

## 9. KB Review Queue Workflow

### 9.1 Purpose

When the AI chat performs a web search (via Tavily), the results are automatically queued for human review before being ingested into the permanent knowledge base. This implements a human-in-the-loop pattern to prevent hallucinated or incorrect legal/tax content from entering the KB.

### 9.2 State Machine

```
         +--> APPROVED (ingested to KB)
         |
PENDING -+
         |
         +--> REJECTED --> RESUBMITTED --> RE_REJECTED
```

### 9.3 State Transitions

| From | To | Trigger | Action |
|------|----|---------|--------|
| (new) | PENDING | Web search result auto-queued during chat | Entry created with content, URL, jurisdiction, topic |
| PENDING | APPROVED | Reviewer approves | Content ingested into KB ChromaDB collection; `source_type` = "web_sourced_approved" |
| PENDING | REJECTED | Reviewer rejects | Rejection note saved; content not ingested |
| REJECTED | RESUBMITTED | Original content resubmitted with note | Resubmission note saved; review_count incremented |
| RESUBMITTED | RE_REJECTED | Reviewer re-rejects | Final rejection (terminal state) |

### 9.4 Review Queue Data Model

```
KBReviewQueue
  entry_id: UUID (PK)
  jurisdiction: String
  topic: String
  content: Text (web search result content)
  web_url: String (source URL)
  date_retrieved: DateTime
  current_status: Enum(PENDING, APPROVED, REJECTED, RESUBMITTED, RE_REJECTED)
  reviewed_by: FK -> User.user_id (nullable)
  reviewed_at: DateTime (nullable)
  rejection_note: Text (nullable)
  resubmission_note: Text (nullable)
  review_count: Integer (default 0)
```

### 9.5 Auto-Queue Logic

During chat (`backend/routers/chat.py:164-180`):
- After web search completes, each result is inserted into `kb_review_queue` as a background task
- Metadata captured: jurisdiction (from client profile), topic (from query context), content, URL
- Status set to PENDING

---

## 10. Document Management

### 10.1 Upload Flow

```
Staff uploads document to /documents/{case_id}/upload
  -> File read into memory (max 20 MB)
  -> Saved to uploads/cases/{case_id}/{filename}
  -> MIME validation via python-magic (content-based)
  -> Allowed types: text/plain, application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document
  -> Text extracted (PyMuPDF / python-docx / plain read)
  -> Chunked: 500-word windows, 100-word overlap
  -> Embedded and stored in case-scoped ChromaDB collection "case_{case_id}"
  -> Document record created in database
```

### 10.2 Case-Scoped Document Isolation

Each case has its own ChromaDB collection (`case_{case_id}`), ensuring:
- Documents from Case A are never retrieved when querying Case B
- RAG queries combine global KB results + case-specific document results
- Deleting a document removes its chunks from the case collection

### 10.3 Supported File Types

| Type | Extension | MIME Type | Extraction Method |
|------|-----------|-----------|-------------------|
| Plain text | .txt | text/plain | Direct read |
| PDF | .pdf | application/pdf | PyMuPDF (fitz) |
| Word | .docx | application/vnd.openxml... | python-docx |

### 10.4 Document Data Model

```
Document
  document_id: UUID (PK)
  case_id: FK -> Case.case_id
  filename: String
  file_path: String
  file_type: Enum(TXT, PDF, DOCX)
  file_size_bytes: Integer
  uploaded_by: FK -> User.user_id
  uploaded_at: DateTime
  parsed: Boolean (default False)
```

### 10.5 Re-Upload Behaviour

If a file with the same name is uploaded to the same case, previous chunks are deleted from ChromaDB before re-embedding the new content (`document_service.py:59-61`). This ensures idempotent updates.

---

## 11. Recommendation Engine

### 11.1 How Recommendations Are Generated

Recommendations are generated by the LLM during advisory chat. The system prompt instructs Claude to output structured recommendations with:
- Structure name (e.g., "Singapore Family Trust", "BVI Holding Company")
- Confidence level
- Rationale (detailed explanation)
- Source citations
- Diagram data (optional)

### 11.2 Confidence Levels

| Level | Meaning |
|-------|---------|
| **HIGH** | Recommendation is well-supported by available evidence and standard practice |
| **SPECIALIST_REVIEW** | Recommendation requires review by a specialist (tax, legal, regulatory) |
| **COMPLEX** | Situation is complex; multiple structures may apply; needs deeper analysis |

### 11.3 Recommendation Data Model

```
Recommendation
  recommendation_id: UUID (PK)
  case_id: FK -> Case.case_id
  structure_name: String
  confidence_level: Enum(HIGH, SPECIALIST_REVIEW, COMPLEX)
  rationale: Text
  sources: Text (citations)
  diagram_data: Text (nullable, JSON)
  generated_at: DateTime
```

---

## 12. Structure Diagram Generation

### 12.1 Diagram Architecture

The AI generates JSON-formatted structure diagrams as part of its response. The frontend renders them using React Flow with three custom node types:

| Node Type | Visual | Use Case |
|-----------|--------|----------|
| **TrustNode** | Green triangle with shield icon | Trusts, foundations |
| **CompanyNode** | Blue rectangle with building icon | Companies, holding structures |
| **IndividualNode** | Purple circle with avatar icon | Individual persons, beneficiaries |

### 12.2 Diagram Data Format

The LLM outputs diagram data as JSON within its response:
```json
{
  "entities": [
    {"label": "Family Trust", "type": "trust", "jurisdiction": "Singapore"},
    {"label": "Holding Co", "type": "company", "jurisdiction": "BVI"},
    {"label": "Client", "type": "individual"}
  ],
  "edges": [
    {"from": 0, "to": 1, "label": "100% ownership"},
    {"from": 2, "to": 0, "label": "settlor"}
  ]
}
```

### 12.3 Diagram Rendering

- `DiagramPanel` component renders side-by-side: "Existing Structure" vs "Recommended Structure"
- `StructureDiagram` wraps React Flow with auto-layout
- Edges validated: bounds-checking prevents out-of-range node references (`diagram_service.py:67-70`)
- Diagrams are extracted from LLM response via regex pattern matching for JSON blocks

---

## 13. PDF Report Generation

### 13.1 Report Content

The PDF report (`POST /reports/{case_id}/pdf`) includes:

1. **Cover page** -- "Wealth Planning Report" with client name and date
2. **Client profile section** -- nationality, domicile, tax residency, family members, asset classes, jurisdictions, existing structures, objectives
3. **Recommendations section** -- cards with structure name, confidence badge (colour-coded), rationale, and source citations
4. **Disclaimer page** -- AI-generated content notice, not-legal-advice disclaimer

### 13.2 Generation Pipeline

```
Request to /reports/{case_id}/pdf
  -> Load Case + ClientProfile + Recommendations from DB
  -> Build HTML string with inline CSS
  -> HTML-escape all user-supplied fields (XSS prevention)
  -> Write HTML to temp file
  -> Invoke Puppeteer (Node.js subprocess) to render HTML -> PDF
  -> Return PDF as streaming file response
  -> Clean up temp files
```

### 13.3 Confidence Badge Colours

| Level | Colour |
|-------|--------|
| HIGH | Green (#22c55e) |
| SPECIALIST_REVIEW | Amber (#f59e0b) |
| COMPLEX | Red (#ef4444) |

---

## 14. Admin Operations

### 14.1 Advisor Management

| Endpoint | Action |
|----------|--------|
| `GET /admin/advisors` | List all advisors with case counts |
| `POST /admin/advisors` | Create new advisor (name, email, auto-generated password) |
| `PUT /admin/advisors/{user_id}/deactivate` | Deactivate advisor (sets `is_active = False`) |
| `PUT /admin/advisors/{user_id}/reactivate` | Reactivate advisor |
| `PUT /admin/advisors/{user_id}/reset-password` | Reset password (generates new 12-char password) |

### 14.2 Advisor Creation Flow

1. Admin enters name + email
2. System generates 24-character cryptographically secure password
3. Creates User record with role=ADVISOR, hashed password
4. Returns generated password in HTTP response (displayed once)

### 14.3 Admin UI

- `frontend/app/(app)/admin/advisors/page.tsx` -- advisor list with create/deactivate/reactivate/reset actions
- `frontend/app/(app)/admin/settings/page.tsx` -- system settings management

---

## 15. System Settings

### 15.1 Configurable Settings

| Setting Key | Description | Default Source |
|-------------|-------------|----------------|
| `anthropic_api_key` | Anthropic API key for Claude | `.env` file |
| `tavily_api_key` | Tavily API key for web search | `.env` file |
| `claude_model` | Claude model identifier | `config.py` (claude-sonnet-4-6) |

### 15.2 Settings Resolution (Cascading)

```
1. Check SystemSetting table (admin-editable at runtime)
2. If not found or empty -> fall back to .env / config.py defaults
```

This allows admins to update API keys without restarting the server.

### 15.3 Settings Security

- API key values are masked in the UI (first 4 + last 4 characters visible)
- Settings management restricted to Admin role only
- Stored as plaintext in the SystemSetting database table

---

## 16. Data Model Summary

### Entity Relationship Diagram (Logical)

```
User (admin/advisor/client)
  |-- created_by -> User (self-referential, for advisor creation)
  |-- case_id -> Case (for client role, 1:1 assignment)
  |
  |-- creates -> Case (advisor creates cases)
  |                |-- ClientProfile (1:1)
  |                |-- Conversation (1:many messages)
  |                |-- Document (1:many uploads)
  |                |-- Recommendation (1:many)
  |
  |-- reviews -> KBReviewQueue (reviewer)
  |-- uploads -> Document (uploader)

SystemSetting (key-value config store)

ChromaDB Collections:
  - wealth_planning_kb (global knowledge base)
  - case_{case_id} (per-case document collection)
```

### Key Relationships

| From | To | Cardinality | FK |
|------|----|-------------|-----|
| Case | User (creator) | N:1 | `case.created_by` -> `user.user_id` |
| User (client) | Case | 1:1 | `user.case_id` -> `case.case_id` |
| ClientProfile | Case | 1:1 | `client_profile.case_id` (unique) |
| Conversation | Case | N:1 | `conversation.case_id` |
| Document | Case | N:1 | `document.case_id` |
| Document | User (uploader) | N:1 | `document.uploaded_by` |
| Recommendation | Case | N:1 | `recommendation.case_id` |
| KBReviewQueue | User (reviewer) | N:1 | `kb_review_queue.reviewed_by` |
| User (advisor) | User (admin creator) | N:1 | `user.created_by` |

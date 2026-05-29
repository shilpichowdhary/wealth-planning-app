# Azure Deployment & Portability Notes — Wealth Planning App

Branch: `feat/azure-portability`. The backend was made portable for distributed
Azure hosting. **Every change is config-driven and defaults to the previous
single-VM behaviour**, so an unconfigured checkout runs exactly as before.

## What changed

| Concern | Before (single VM) | Now (configurable) |
|---|---|---|
| Relational DB | SQLite file | SQLite **or** PostgreSQL — `DATABASE_URL` |
| Schema | `create_all()` at startup | **Alembic** migrations — `alembic upgrade head` |
| Vector store | embedded ChromaDB | embedded **or** Chroma server — `CHROMA_MODE=http` |
| File storage | local disk (`uploads/`, `data/reports/`) | local **or** Azure Blob — `STORAGE_BACKEND=azure` |

All four were validated end-to-end locally against real engines (Postgres + a
Chroma server + Azurite) before this handoff.

## Required environment variables (production)

| Variable | Value | Notes |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://USER:PWD@HOST:5432/DB` | async `asyncpg` driver required (not `postgres://`) |
| `RUN_CREATE_ALL_ON_STARTUP` | `false` | schema is managed by Alembic |
| `CHROMA_MODE` | `http` | |
| `CHROMA_HOST` / `CHROMA_PORT` / `CHROMA_SSL` | chroma service host / `8000` / `true` | shared Chroma service |
| `STORAGE_BACKEND` | `azure` | |
| `AZURE_STORAGE_CONNECTION_STRING` | (Key Vault) | real Storage account connection string |
| `AZURE_BLOB_CONTAINER` | `wpapp` | created automatically if missing |
| `SOFFICE_BIN` | `/usr/bin/soffice` | LibreOffice path on the image (PPTX→PDF) |
| `SECRET_KEY`, `ANTHROPIC_API_KEY`, `TAVILY_API_KEY` | (Key Vault) | unchanged |
| `AZURE_TENANT_ID` / `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` | (Key Vault) | Entra ID SSO |
| `SMTP_*` | (Key Vault) | transactional email |

Secrets must be supplied via **Azure Key Vault / pipeline secret variables** — never committed. `.env.example` documents every key (its Azurite value is the public emulator dev string, for local use only).

## Azure services to provision

1. **Azure Database for PostgreSQL (Flexible Server)** — relational DB.
2. **Chroma server** — run image `chromadb/chroma:0.5.20` (Container Apps / AKS) with a persistent volume; **pin the version** to match the client (`chromadb==0.5.20`).
3. **Azure Storage account** + a blob container — uploads + generated reports.

## Image / runtime OS dependencies

The backend image **must** include:
- **`libmagic1`** — document MIME validation (`python-magic`). *Note: this is not present on the current Windows VM, so document-upload MIME checks fail there; on Linux with `libmagic1` it works.*
- **LibreOffice** (`soffice`) — PPTX→PDF conversion.
- The ML stack (`torch`, `sentence-transformers`) for in-process embeddings (already in `requirements.txt`).

## Deploy steps

1. Build/ship the backend image with the OS deps above.
2. **Apply schema:** `alembic upgrade head` (once per deploy, before starting the app).
3. **(One-time) migrate existing data** — see below.
4. **Start:** `uvicorn backend.main:app --host 0.0.0.0 --port 8000` — multiple replicas are supported.

## One-time data migration from the VM

- **Relational:** with the existing `wealth_planning.db` available and `DATABASE_URL` pointed at the new Postgres, run `python scripts/migrate_sqlite_to_postgres.py` (idempotent; prints and asserts row counts).
- **Vector store:** either re-ingest the KB — `python scripts/ingest_kb_export.py --export-dir <export> --wipe` — or copy the existing `chroma_db/` contents into the Chroma server's persistent volume.
- Migrated deck rows have **null** `pptx_path`/`pdf_path` (legacy absolute paths are not portable); decks regenerate on demand.

## Distribution / scaling

With Postgres + Chroma server + Blob, the backend is **stateless** and can run multiple replicas behind a load balancer. The `sentence-transformers` embedding model loads in-process (CPU/RAM per replica) — size instances accordingly, or later move embeddings to a dedicated inference endpoint.

## Local dev harness (reproduces the target)

`docker compose up -d` starts Postgres (`localhost:5433`), Chroma (`localhost:8001`), and Azurite (`localhost:10000`). Copy `.env.example` → `.env`, then run `alembic upgrade head` and (optionally) the data-migration script. See `docker-compose.yml`.

## Compliance

- Source, DB data, and KB content are LC IP and may contain personal data — perform the data migration through approved channels and restrict repo, Storage, and database access to authorised personnel.
- Client-facing decks/reports still require Investments/Compliance review before external distribution.
- This document and the migration approach should be reviewed by infrastructure/security before go-live.

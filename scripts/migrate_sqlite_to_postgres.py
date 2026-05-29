"""One-off data migration: copy all rows from the local SQLite DB into the
Postgres DB pointed to by DATABASE_URL.

Run AFTER `alembic upgrade head` against the target Postgres (this script only
INSERTs data; it does not create schema). Idempotent: re-running skips rows that
already exist (ON CONFLICT DO NOTHING on the primary key).

Usage (PowerShell):
    $env:DATABASE_URL='postgresql+asyncpg://wpapp:...@localhost:5433/wealth_planning'
    venv/Scripts/python.exe scripts/migrate_sqlite_to_postgres.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from backend.config import settings
import backend.models  # noqa: F401 — register all models
from backend.models.case import Case
from backend.models.case_deck import CaseDeck
from backend.models.case_diagram import CaseDiagram
from backend.models.client_profile import ClientProfile
from backend.models.conversation import Conversation
from backend.models.document import Document
from backend.models.invite_token import InviteToken
from backend.models.kb_review_queue import KBReviewQueue
from backend.models.recommendation import Recommendation
from backend.models.system_setting import SystemSetting
from backend.models.user import User

SOURCE_URL = "sqlite+aiosqlite:///./wealth_planning.db"

# Parents before children. User is first but its circular case_id FK is filled
# in a second pass (see below), so Case can be inserted after User exists.
ORDER = [
    User, Case, ClientProfile, Conversation, Recommendation,
    KBReviewQueue, Document, SystemSetting, CaseDiagram, InviteToken, CaseDeck,
]


def _row_to_dict(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


async def main() -> None:
    if "postgresql" not in settings.database_url:
        raise SystemExit(f"DATABASE_URL must point at Postgres, got: {settings.database_url}")

    src_engine = create_async_engine(SOURCE_URL)
    dst_engine = create_async_engine(settings.database_url)
    SrcSession = sessionmaker(src_engine, class_=AsyncSession, expire_on_commit=False)

    # 1) Read everything from SQLite.
    data: dict = {}
    src_counts: dict = {}
    async with SrcSession() as src:
        for Model in ORDER:
            objs = (await src.execute(select(Model))).scalars().all()
            data[Model] = [_row_to_dict(o) for o in objs]
            src_counts[Model.__tablename__] = len(data[Model])

    # 2) Insert into Postgres in one transaction.
    async with dst_engine.begin() as conn:
        for Model in ORDER:
            rows = data[Model]
            if not rows:
                continue
            if Model is User:
                # Defer the circular case_id FK; backfilled after Cases exist.
                rows = [{**r, "case_id": None} for r in rows]
            await conn.execute(pg_insert(Model.__table__).values(rows).on_conflict_do_nothing())

        # Second pass: backfill users.case_id now that cases exist.
        for r in data[User]:
            if r.get("case_id"):
                await conn.execute(
                    update(User.__table__)
                    .where(User.__table__.c.user_id == r["user_id"])
                    .values(case_id=r["case_id"])
                )

        # Migrated deck rows hold absolute Windows paths (not portable storage keys);
        # null them so the UI prompts regeneration under the new storage backend.
        await conn.execute(update(CaseDeck.__table__).values(pptx_path=None, pdf_path=None))

    # 3) Verify counts.
    DstSession = sessionmaker(dst_engine, class_=AsyncSession, expire_on_commit=False)
    ok = True
    print(f"{'table':22}{'source':>8}{'dest':>8}")
    async with DstSession() as dst:
        for Model in ORDER:
            n = (await dst.execute(select(func.count()).select_from(Model.__table__))).scalar()
            src_n = src_counts[Model.__tablename__]
            flag = "" if n >= src_n else "  <-- MISMATCH"
            if n < src_n:
                ok = False
            print(f"{Model.__tablename__:22}{src_n:>8}{n:>8}{flag}")

    await src_engine.dispose()
    await dst_engine.dispose()
    print("\nRESULT:", "OK" if ok else "MISMATCH — investigate")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

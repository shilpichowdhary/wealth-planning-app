from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from backend.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, echo=False)


@event.listens_for(engine.sync_engine, "connect")
def _enable_sqlite_fk(dbapi_conn, _conn_record):
    """SQLite enforces FK constraints only when the per-connection PRAGMA is set.
    Postgres and other dialects ignore the pragma path entirely because of the
    dialect-name check below."""
    if engine.dialect.name == "sqlite":
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def create_tables():
    """On startup: apply pending Alembic migrations.

    Tests set ALEMBIC_BOOTSTRAP=skip; the conftest builds its own engine
    and calls Base.metadata.create_all directly. Production code path goes
    through Alembic so schema changes are versioned and reviewable.
    """
    import os
    if os.environ.get("ALEMBIC_BOOTSTRAP") == "skip":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return

    import asyncio as _asyncio
    from alembic.config import Config
    from alembic import command
    cfg = Config("alembic.ini")
    await _asyncio.to_thread(command.upgrade, cfg, "head")


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

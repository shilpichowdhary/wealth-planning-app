import os
# Set before any backend import so validate_secrets() doesn't trip in TestClient lifespan.
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-32-bytes-minimum-aaaa")

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from backend.main import app
from backend.database import Base, get_db
from backend.models.user import User, UserRole
from backend.services.auth_service import hash_password
from backend.services.rate_limit import limiter, user_limiter, reset_token_counter


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """slowapi keeps an in-memory counter that survives across tests; reset
    between each test so /auth/token calls in different tests don't bleed
    into each other's 5/minute budget. Also clear the daily token bucket so
    future AI-07 work doesn't inherit cross-test state."""
    limiter.reset()
    user_limiter.reset()
    reset_token_counter()
    yield
    limiter.reset()
    user_limiter.reset()
    reset_token_counter()

TEST_DB = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DB)

    # Mirror the production database.py PRAGMA listener so SQLite enforces
    # ondelete=CASCADE in tests. Without this, child rows survive parent
    # deletes silently and cascade tests would report false negatives.
    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_fk(dbapi_conn, _conn_record):
        if engine.dialect.name == "sqlite":
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    TestSession = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSession() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
async def async_client(db_session):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
async def auth_headers(db_session, async_client):
    user = User(name="Test Advisor", email="advisor@test.com", hashed_password=hash_password("TestPass123!"), role=UserRole.ADVISOR)
    db_session.add(user)
    await db_session.commit()
    resp = await async_client.post("/auth/token", data={"username": "advisor@test.com", "password": "TestPass123!"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

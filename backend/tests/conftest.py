import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from backend.main import app
from backend.database import Base, get_db
from backend.models.user import User, UserRole
from backend.services.auth_service import hash_password

TEST_DB = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DB)
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

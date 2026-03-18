import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from backend.models.user import User, UserRole
from backend.database import Base

@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as s:
        yield s

@pytest.mark.asyncio
async def test_create_advisor_user(session):
    user = User(
        name="Test Advisor",
        email="advisor@test.com",
        hashed_password="hashed",
        role=UserRole.ADVISOR,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    assert user.user_id is not None
    assert user.role == UserRole.ADVISOR
    assert user.is_active is True

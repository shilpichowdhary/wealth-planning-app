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


@pytest.mark.asyncio
async def test_deleting_case_cascades_to_children(db_session):
    """Deleting a Case removes its ClientProfile, Conversation, Recommendation,
    Document, and CaseDiagram rows. SQLite enforces FK constraints only with
    PRAGMA foreign_keys=ON (see database.py)."""
    from sqlalchemy import select
    from backend.models.case import Case
    from backend.models.client_profile import ClientProfile
    from backend.models.conversation import Conversation, MessageRole
    from backend.models.recommendation import Recommendation, ConfidenceLevel
    from backend.models.document import Document, FileType
    from backend.models.case_diagram import CaseDiagram

    user = User(
        name="Cascade Tester",
        email="cascade@test.com",
        hashed_password="hashed",
        role=UserRole.ADVISOR,
    )
    db_session.add(user)
    await db_session.flush()

    case = Case(client_name="Test", created_by=user.user_id)
    db_session.add(case)
    await db_session.flush()

    db_session.add(ClientProfile(case_id=case.case_id, nationality="IN"))
    db_session.add(Conversation(case_id=case.case_id, role=MessageRole.USER, content="hi"))
    db_session.add(Recommendation(
        case_id=case.case_id, structure_name="Trust",
        confidence_level=ConfidenceLevel.HIGH, rationale="r", sources="[]",
    ))
    db_session.add(Document(
        case_id=case.case_id, filename="x.pdf", file_path="/tmp/x.pdf",
        file_type=FileType.PDF, file_size_bytes=10, uploaded_by=user.user_id,
    ))
    db_session.add(CaseDiagram(case_id=case.case_id, nodes_json="[]", edges_json="[]"))
    await db_session.commit()

    await db_session.delete(case)
    await db_session.commit()

    for model in (ClientProfile, Conversation, Recommendation, Document, CaseDiagram):
        result = await db_session.execute(select(model))
        rows = result.scalars().all()
        assert rows == [], f"{model.__name__} rows leaked after case delete"

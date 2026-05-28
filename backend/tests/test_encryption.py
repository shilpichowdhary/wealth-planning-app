import pytest
from backend.services.encryption import encrypt, decrypt


def test_round_trip():
    assert decrypt(encrypt("hello")) == "hello"


def test_round_trip_handles_unicode():
    assert decrypt(encrypt("ünïcödé family — 中文")) == "ünïcödé family — 中文"


def test_distinct_iv_produces_distinct_ciphertexts():
    a = encrypt("same-plaintext")
    b = encrypt("same-plaintext")
    assert a != b


def test_decrypt_passes_through_plaintext():
    """Backward-compat tolerance during Phase 3 cutover."""
    assert decrypt("not-actually-encrypted") == "not-actually-encrypted"


def test_decrypt_passes_through_invalid_base64():
    """Pre-encrypted values may contain characters that aren't valid base64."""
    assert decrypt("totally !@#$ not base64") == "totally !@#$ not base64"


def test_decrypt_none_returns_none():
    assert decrypt(None) is None


def test_encrypt_none_returns_none():
    assert encrypt(None) is None


@pytest.mark.asyncio
async def test_settings_service_encrypts_anthropic_key(db_session):
    """Writing anthropic_api_key via set_setting stores ciphertext; reading via
    get_setting decrypts back."""
    from sqlalchemy import select
    from backend.services.settings_service import set_setting, get_setting
    from backend.models.system_setting import SystemSetting

    plaintext = "sk-ant-test-1234567890"
    await set_setting("anthropic_api_key", plaintext, db_session)

    raw = (await db_session.execute(
        select(SystemSetting.value).where(SystemSetting.key == "anthropic_api_key")
    )).scalar_one()
    assert raw != plaintext, "Value must be stored as ciphertext"
    assert raw.startswith("gAAAA"), "Fernet tokens start with gAAAA"

    decrypted = await get_setting("anthropic_api_key", db_session)
    assert decrypted == plaintext


@pytest.mark.asyncio
async def test_settings_service_does_not_encrypt_claude_model(db_session):
    """claude_model is not in SECRET_KEYS — stored as plaintext."""
    from sqlalchemy import select
    from backend.services.settings_service import set_setting
    from backend.models.system_setting import SystemSetting

    await set_setting("claude_model", "claude-opus-4-7", db_session)
    raw = (await db_session.execute(
        select(SystemSetting.value).where(SystemSetting.key == "claude_model")
    )).scalar_one()
    assert raw == "claude-opus-4-7"


@pytest.mark.asyncio
async def test_client_profile_encrypts_sensitive_columns(db_session):
    """Writing a ClientProfile through the ORM encrypts family_members,
    existing_structures, and objectives at the DB layer."""
    from sqlalchemy import text
    from backend.models.user import User, UserRole
    from backend.models.case import Case
    from backend.models.client_profile import ClientProfile

    user = User(
        name="Crypto Tester",
        email="crypto@test.com",
        hashed_password="hashed",
        role=UserRole.ADVISOR,
    )
    db_session.add(user)
    await db_session.flush()

    case = Case(client_name="X", created_by=user.user_id)
    db_session.add(case)
    await db_session.flush()

    cp = ClientProfile(
        case_id=case.case_id,
        nationality="IN",
        family_members='[{"name":"Spouse","relationship":"spouse"}]',
        existing_structures="Existing Jersey trust",
        objectives='["Succession planning"]',
    )
    db_session.add(cp)
    await db_session.commit()

    # Read raw bytes via raw SQL — bypass the ORM type marshalling.
    raw = (await db_session.execute(
        text("SELECT family_members, existing_structures, objectives, nationality FROM client_profiles WHERE case_id = :c"),
        {"c": case.case_id},
    )).one()
    fm, es, obj, nat = raw
    assert fm.startswith("gAAAA"), f"family_members should be ciphertext, got {fm[:30]}"
    assert es.startswith("gAAAA"), "existing_structures should be ciphertext"
    assert obj.startswith("gAAAA"), "objectives should be ciphertext"
    assert nat == "IN", "nationality is not encrypted"

    # Read via the ORM — should be decrypted back.
    await db_session.refresh(cp)
    assert cp.family_members == '[{"name":"Spouse","relationship":"spouse"}]'
    assert cp.existing_structures == "Existing Jersey trust"
    assert cp.objectives == '["Succession planning"]'

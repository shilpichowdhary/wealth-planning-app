from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.config import settings as env_settings
from backend.database import AsyncSessionLocal
from backend.models.system_setting import SystemSetting
from backend.services.encryption import encrypt, decrypt

# Keys that admins can manage from the UI
ADMIN_KEYS = {
    "anthropic_api_key": "Anthropic API Key",
    "tavily_api_key": "Tavily API Key",
    "claude_model": "Claude Model",
}

# Subset of ADMIN_KEYS whose VALUES are encrypted at rest.
SECRET_KEYS = {"anthropic_api_key", "tavily_api_key"}


async def get_setting(key: str, db: AsyncSession | None = None) -> str:
    """Return a setting value: DB first, then fall back to .env/config default.

    Values stored under SECRET_KEYS are decrypted on read; decrypt() passes
    through plaintext for backward compatibility during the Phase 3 cutover.
    """
    async def _query(session: AsyncSession) -> str | None:
        result = await session.execute(
            select(SystemSetting.value).where(SystemSetting.key == key)
        )
        row = result.scalar_one_or_none()
        return row if row else None

    db_value = None
    if db:
        db_value = await _query(db)
    else:
        async with AsyncSessionLocal() as session:
            db_value = await _query(session)

    if db_value:
        return decrypt(db_value) if key in SECRET_KEYS else db_value

    # Fall back to .env / config defaults
    return getattr(env_settings, key, "")


async def set_setting(key: str, value: str, db: AsyncSession) -> None:
    """Upsert a setting in the database. SECRET_KEYS get encrypted at write."""
    store_value = encrypt(value) if key in SECRET_KEYS else value
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == key)
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.value = store_value
    else:
        db.add(SystemSetting(key=key, value=store_value))
    await db.commit()


async def get_all_admin_settings(db: AsyncSession) -> dict:
    """Return all admin-manageable settings with masked values."""
    output = {}
    for key, label in ADMIN_KEYS.items():
        value = await get_setting(key, db)
        output[key] = {
            "label": label,
            "value": _mask(value) if "key" in key else value,
            "is_set": bool(value and value != "placeholder"),
        }
    return output


def _mask(value: str) -> str:
    if not value or len(value) < 8 or value == "placeholder":
        return ""
    return value[:4] + "*" * (len(value) - 8) + value[-4:]

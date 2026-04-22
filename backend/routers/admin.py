import os
import secrets
import string
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from backend.database import get_db
from backend.models.user import User, UserRole
from backend.models.case import Case
from backend.models.invite_token import InviteToken
from backend.routers.auth import get_current_user
from backend.services.auth_service import hash_password
from backend.services.settings_service import get_all_admin_settings, set_setting, ADMIN_KEYS

router = APIRouter(prefix="/admin", tags=["admin"])

# Invite tokens expire after this many days.
INVITE_TTL_DAYS = 7


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ── API Key / Settings management ──────────────────────────────


class UpdateSettingRequest(BaseModel):
    key: str
    value: str


@router.get("/settings")
async def list_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Return all admin-manageable settings (API keys masked)."""
    return await get_all_admin_settings(db)


@router.put("/settings")
async def update_setting(
    payload: UpdateSettingRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Set an API key or config value."""
    if payload.key not in ADMIN_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown setting: {payload.key}")
    await set_setting(payload.key, payload.value, db)
    return {"status": "saved", "key": payload.key}


# ── Invite helpers ─────────────────────────────────────────────


def _app_base_url(req: Request) -> str:
    """Derive the base URL to embed in the invite link.

    Priority: APP_BASE_URL env var (set this in prod) → Origin header from the
    admin's browser → request host. This lets dev (localhost:3001) and prod
    (lighthouse-canton.internal) work without code changes.
    """
    override = os.environ.get("APP_BASE_URL")
    if override:
        return override.rstrip("/")
    origin = req.headers.get("origin")
    if origin:
        return origin.rstrip("/")
    return str(req.base_url).rstrip("/")


def _generate_invite(db_user_id: str, created_by: str) -> InviteToken:
    """Mint a fresh InviteToken — 32-byte URL-safe random, 7-day TTL."""
    return InviteToken(
        token=secrets.token_urlsafe(32),
        user_id=db_user_id,
        expires_at=datetime.utcnow() + timedelta(days=INVITE_TTL_DAYS),
        created_by=created_by,
    )


async def _revoke_outstanding_invites(db: AsyncSession, user_id: str) -> None:
    """Mark any unused, non-revoked invites for this user as revoked."""
    await db.execute(
        update(InviteToken)
        .where(
            InviteToken.user_id == user_id,
            InviteToken.used_at.is_(None),
            InviteToken.revoked.is_(False),
        )
        .values(revoked=True)
    )


# ── Advisor management ─────────────────────────────────────────


class CreateAdvisorRequest(BaseModel):
    name: str
    email: EmailStr


class InviteAdvisorRequest(BaseModel):
    name: str
    email: EmailStr


class AdvisorResponse(BaseModel):
    user_id: str
    name: str
    email: str
    role: str
    is_active: bool
    created_at: str
    case_count: int = 0

    model_config = {"from_attributes": True}


@router.get("/advisors")
async def list_advisors(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """List all advisors with their case counts."""
    result = await db.execute(
        select(User).where(User.role == UserRole.ADVISOR).order_by(User.created_at.desc())
    )
    advisors = result.scalars().all()

    # Get case counts per advisor
    counts_result = await db.execute(
        select(Case.created_by, func.count(Case.case_id).label("cnt"))
        .group_by(Case.created_by)
    )
    case_counts = {row.created_by: row.cnt for row in counts_result}

    return [
        {
            "user_id": u.user_id,
            "name": u.name,
            "email": u.email,
            "role": u.role.value,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat(),
            "case_count": case_counts.get(u.user_id, 0),
        }
        for u in advisors
    ]


@router.post("/advisors", status_code=201)
async def create_advisor(
    payload: CreateAdvisorRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Create a new advisor account."""
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    auto_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24))
    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(auto_password),
        role=UserRole.ADVISOR,
        created_by=current_admin.user_id,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {
        "user_id": user.user_id,
        "name": user.name,
        "email": user.email,
        "role": user.role.value,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
        "case_count": 0,
    }


@router.post("/advisors/invite", status_code=201)
async def invite_advisor(
    payload: InviteAdvisorRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Create an advisor account and issue a magic-link invite token.

    The advisor is created with a random, unknown password (they cannot log in
    with password auth until they redeem the invite). Admin gets back the
    invite URL to share out-of-band.
    """
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    # Random password the admin never learns — advisor sets their own via invite.
    throwaway = secrets.token_urlsafe(24)
    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(throwaway),
        role=UserRole.ADVISOR,
        created_by=current_admin.user_id,
        is_active=True,
    )
    db.add(user)
    await db.flush()  # populate user.user_id without committing yet

    invite = _generate_invite(user.user_id, current_admin.user_id)
    db.add(invite)
    await db.commit()
    await db.refresh(user)

    base = _app_base_url(request)
    return {
        "advisor": {
            "user_id": user.user_id,
            "name": user.name,
            "email": user.email,
            "role": user.role.value,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat(),
            "case_count": 0,
        },
        "invite": {
            "token": invite.token,
            "url": f"{base}/invite/{invite.token}",
            "expires_at": invite.expires_at.isoformat(),
        },
    }


@router.post("/advisors/{user_id}/resend-invite")
async def resend_advisor_invite(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Issue a fresh invite for an existing advisor and revoke any outstanding ones.

    Useful when the original link expired or was lost.
    """
    result = await db.execute(
        select(User).where(User.user_id == user_id, User.role == UserRole.ADVISOR)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Advisor not found")

    await _revoke_outstanding_invites(db, user_id)
    invite = _generate_invite(user_id, current_admin.user_id)
    db.add(invite)
    await db.commit()

    base = _app_base_url(request)
    return {
        "token": invite.token,
        "url": f"{base}/invite/{invite.token}",
        "expires_at": invite.expires_at.isoformat(),
    }


@router.patch("/advisors/{user_id}/deactivate")
async def deactivate_advisor(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Deactivate an advisor — they can no longer log in."""
    result = await db.execute(
        select(User).where(User.user_id == user_id, User.role == UserRole.ADVISOR)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Advisor not found")
    user.is_active = False
    await db.commit()
    return {"status": "deactivated", "user_id": user_id}


@router.patch("/advisors/{user_id}/reactivate")
async def reactivate_advisor(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Reactivate a previously deactivated advisor."""
    result = await db.execute(
        select(User).where(User.user_id == user_id, User.role == UserRole.ADVISOR)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Advisor not found")
    user.is_active = True
    await db.commit()
    return {"status": "reactivated", "user_id": user_id}


@router.patch("/advisors/{user_id}/reset-password")
async def reset_advisor_password(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Issue a magic-link password reset for an advisor.

    Historically this generated a random password that the admin had to share.
    Now it uses the same single-use invite-token flow so admins never see (or
    need to email) a plaintext password. Any outstanding invites for this user
    are revoked so only the latest link can be redeemed.
    """
    result = await db.execute(
        select(User).where(User.user_id == user_id, User.role == UserRole.ADVISOR)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Advisor not found")

    await _revoke_outstanding_invites(db, user_id)
    invite = _generate_invite(user_id, current_admin.user_id)
    db.add(invite)
    await db.commit()

    base = _app_base_url(request)
    return {
        "token": invite.token,
        "url": f"{base}/invite/{invite.token}",
        "expires_at": invite.expires_at.isoformat(),
        "purpose": "reset",
    }

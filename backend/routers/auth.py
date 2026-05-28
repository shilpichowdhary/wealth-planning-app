import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database import get_db
from backend.models.user import User, UserRole
from backend.models.invite_token import InviteToken
from backend.services.auth_service import (
    verify_password,
    hash_password,
    AuthService,
    validate_azure_id_token_async,
)
from backend.services.rate_limit import limiter
from backend.services.audit_service import log_event

logger = logging.getLogger(__name__)


def is_staff(user: User) -> bool:
    """True for admin and advisor — both can manage cases and KB."""
    return user.role in (UserRole.ADMIN, UserRole.ADVISOR)

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

@router.post("/token")
@limiter.limit("5/minute")
async def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form.username, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        # Log the attempted email (not the password) so credential-stuffing
        # patterns can be spotted in the audit trail.
        await log_event(
            db,
            event_type="auth.login.failure",
            request=request,
            outcome="failure",
            detail={"email": form.username},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = AuthService.create_access_token({"sub": user.user_id, "role": user.role})
    await log_event(
        db,
        event_type="auth.login.success",
        actor_user_id=user.user_id,
        request=request,
    )
    return {"access_token": token, "token_type": "bearer"}


# ── SSO Login ─────────────────────────────────────────────────────

class SSORequest(BaseModel):
    id_token: str


@router.post("/sso")
@limiter.limit("5/minute")
async def sso_login(request: Request, payload: SSORequest, db: AsyncSession = Depends(get_db)):
    """Exchange an Azure AD ID token for an app JWT.

    Only users pre-created by an admin can log in via SSO.
    """
    try:
        claims = await validate_azure_id_token_async(payload.id_token)
    except Exception as e:
        logger.warning("SSO token validation failed: %s", e)
        await log_event(
            db,
            event_type="auth.sso.failure",
            request=request,
            outcome="failure",
            detail={"reason": "invalid_token"},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid SSO token")

    email = (claims.get("preferred_username") or claims.get("email") or "").lower()
    if not email:
        await log_event(
            db,
            event_type="auth.sso.failure",
            request=request,
            outcome="failure",
            detail={"reason": "no_email_in_token"},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No email in SSO token")

    # Only allow pre-created users
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        await log_event(
            db,
            event_type="auth.sso.failure",
            request=request,
            outcome="failure",
            detail={"reason": "account_not_registered", "email": email},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not registered. Contact your administrator.",
        )
    if not user.is_active:
        await log_event(
            db,
            event_type="auth.sso.failure",
            actor_user_id=user.user_id,
            request=request,
            outcome="failure",
            detail={"reason": "account_deactivated"},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact your administrator.",
        )

    # Link Azure OID on first SSO login
    azure_oid = claims.get("oid")
    if azure_oid and not user.azure_oid:
        user.azure_oid = azure_oid
        await db.commit()

    token = AuthService.create_access_token({"sub": user.user_id, "role": user.role})
    await log_event(
        db,
        event_type="auth.sso.success",
        actor_user_id=user.user_id,
        request=request,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role.value if hasattr(user.role, "value") else user.role,
        "name": user.name,
        "email": user.email,
    }


# ── Token helpers ─────────────────────────────────────────────────

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    try:
        payload = AuthService.decode_token(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    result = await db.execute(select(User).where(User.user_id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


# ---------------------------------------------------------------------------
# Magic-link invite endpoints (public — no auth required)
# ---------------------------------------------------------------------------


async def _lookup_valid_invite(
    token: str, db: AsyncSession
) -> tuple[InviteToken, User]:
    """Return (invite, user) if the token is valid to redeem, else 404/410."""
    result = await db.execute(select(InviteToken).where(InviteToken.token == token))
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.revoked:
        raise HTTPException(status_code=410, detail="Invite revoked")
    if invite.used_at is not None:
        raise HTTPException(status_code=410, detail="Invite already used")
    if invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Invite expired")

    user_result = await db.execute(select(User).where(User.user_id == invite.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Invite target no longer exists")
    return invite, user


@router.get("/invite/{token}")
async def preview_invite(token: str, db: AsyncSession = Depends(get_db)):
    """Public preview of an invite — returns the advisor's name/email/expiry so
    the acceptance page can render a proper welcome. Returns 410 for any token
    that can't be redeemed (expired, revoked, already used)."""
    invite, user = await _lookup_valid_invite(token, db)
    return {
        "name": user.name,
        "email": user.email,
        "role": user.role.value if hasattr(user.role, "value") else user.role,
        "expires_at": invite.expires_at.isoformat(),
    }


class AcceptInviteRequest(BaseModel):
    # 12-char floor — matches the firm's baseline IT policy and is still
    # easy to type/remember. Bcrypt silently truncates above 72 chars so we
    # cap there too.
    password: str = Field(min_length=12, max_length=72)


@router.post("/invite/{token}/accept")
@limiter.limit("5/minute")
async def accept_invite(
    request: Request,
    token: str,
    payload: AcceptInviteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Consume an invite: set the advisor's password and mark the token used.

    On success, returns the access token so the client can redirect straight
    to the dashboard without a second login round-trip — same shape as /auth/token.
    """
    invite, user = await _lookup_valid_invite(token, db)

    user.hashed_password = hash_password(payload.password)
    if not user.is_active:
        user.is_active = True
    invite.used_at = datetime.utcnow()
    await db.commit()

    access_token = AuthService.create_access_token({"sub": user.user_id, "role": user.role})
    await log_event(
        db,
        event_type="auth.invite.accept",
        actor_user_id=user.user_id,
        request=request,
        target_type="user",
        target_id=user.user_id,
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "user_id": user.user_id,
            "name": user.name,
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else user.role,
        },
    }

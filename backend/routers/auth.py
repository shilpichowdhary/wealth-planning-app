import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database import get_db
from backend.models.user import User, UserRole
from backend.services.auth_service import (
    verify_password, AuthService, validate_azure_id_token_async,
)

logger = logging.getLogger(__name__)


def is_staff(user: User) -> bool:
    """True for admin and advisor — both can manage cases and KB."""
    return user.role in (UserRole.ADMIN, UserRole.ADVISOR)

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

@router.post("/token")
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form.username, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = AuthService.create_access_token({"sub": user.user_id, "role": user.role})
    return {"access_token": token, "token_type": "bearer"}


# ── SSO Login ─────────────────────────────────────────────────────

class SSORequest(BaseModel):
    id_token: str


@router.post("/sso")
async def sso_login(payload: SSORequest, db: AsyncSession = Depends(get_db)):
    """Exchange an Azure AD ID token for an app JWT.

    Only users pre-created by an admin can log in via SSO.
    """
    try:
        claims = await validate_azure_id_token_async(payload.id_token)
    except Exception as e:
        logger.warning("SSO token validation failed: %s", e)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid SSO token")

    email = (claims.get("preferred_username") or claims.get("email") or "").lower()
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No email in SSO token")

    # Only allow pre-created users
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not registered. Contact your administrator.",
        )
    if not user.is_active:
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

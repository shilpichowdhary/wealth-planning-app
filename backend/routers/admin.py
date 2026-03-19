import secrets
import string
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.database import get_db
from backend.models.user import User, UserRole
from backend.models.case import Case
from backend.routers.auth import get_current_user
from backend.services.auth_service import hash_password

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


class CreateAdvisorRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


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

    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
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
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Generate a new random password for an advisor."""
    result = await db.execute(
        select(User).where(User.user_id == user_id, User.role == UserRole.ADVISOR)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Advisor not found")
    new_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
    user.hashed_password = hash_password(new_password)
    await db.commit()
    return {"new_password": new_password, "note": "Share this with the advisor securely. It will not be shown again."}

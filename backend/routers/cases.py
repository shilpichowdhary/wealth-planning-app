import json
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database import get_db
from backend.models.case import Case
from backend.models.client_profile import ClientProfile
from backend.models.conversation import Conversation
from backend.models.user import User, UserRole
from backend.schemas.case import CaseCreate, CaseResponse
from backend.routers.auth import get_current_user, is_staff

router = APIRouter(prefix="/cases", tags=["cases"])


async def _get_case_with_access(case_id: str, current_user: User, db: AsyncSession) -> Case:
    result = await db.execute(select(Case).where(Case.case_id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if is_staff(current_user) and current_user.role != UserRole.ADMIN and case.created_by != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if current_user.role == UserRole.CLIENT and current_user.case_id != case_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return case


class ProfilePayload(BaseModel):
    nationality: str | None = None
    domicile: str | None = None
    tax_residency: str | None = None
    family_members: list[dict[str, Any]] = []
    asset_classes: list[str] = []
    asset_jurisdictions: list[str] = []
    existing_structures: str | None = None
    objectives: list[str] = []

class SaveProfileResponse(BaseModel):
    status: str

@router.post("/", response_model=CaseResponse, status_code=201)
async def create_case(
    payload: CaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not is_staff(current_user):
        raise HTTPException(status_code=403, detail="Advisors only")
    case = Case(client_name=payload.client_name, created_by=current_user.user_id)
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return case

@router.get("/", response_model=list[CaseResponse])
async def list_cases(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not is_staff(current_user):
        raise HTTPException(status_code=403, detail="Advisors only")
    if current_user.role == UserRole.ADMIN:
        result = await db.execute(select(Case))
    else:
        result = await db.execute(select(Case).where(Case.created_by == current_user.user_id))
    return result.scalars().all()

@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(case_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await _get_case_with_access(case_id, current_user, db)


@router.post("/{case_id}/profile", status_code=200, response_model=SaveProfileResponse)
async def save_profile(
    case_id: str,
    payload: ProfilePayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_case_with_access(case_id, current_user, db)
    result = await db.execute(select(ClientProfile).where(ClientProfile.case_id == case_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = ClientProfile(case_id=case_id)
        db.add(profile)
    profile.nationality = payload.nationality
    profile.domicile = payload.domicile
    profile.tax_residency = payload.tax_residency
    profile.family_members = json.dumps(payload.family_members)
    profile.asset_classes = json.dumps(payload.asset_classes)
    profile.asset_jurisdictions = json.dumps(payload.asset_jurisdictions)
    profile.existing_structures = payload.existing_structures
    profile.objectives = json.dumps(payload.objectives)
    await db.commit()
    return {"status": "saved"}


@router.get("/{case_id}/profile")
async def get_profile(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_case_with_access(case_id, current_user, db)
    result = await db.execute(select(ClientProfile).where(ClientProfile.case_id == case_id))
    profile = result.scalar_one_or_none()
    if not profile:
        return {}

    def _loads(val: str | None, default: Any) -> Any:
        if not val:
            return default
        try:
            return json.loads(val)
        except (json.JSONDecodeError, ValueError):
            return default

    return {
        "nationality": profile.nationality,
        "domicile": profile.domicile,
        "tax_residency": profile.tax_residency,
        "family_members": _loads(profile.family_members, []),
        "asset_classes": _loads(profile.asset_classes, []),
        "asset_jurisdictions": _loads(profile.asset_jurisdictions, []),
        "existing_structures": profile.existing_structures,
        "objectives": _loads(profile.objectives, []),
    }


@router.get("/{case_id}/history")
async def get_history(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return full conversation history for a case, oldest first."""
    await _get_case_with_access(case_id, current_user, db)
    result = await db.execute(
        select(Conversation)
        .where(Conversation.case_id == case_id)
        .order_by(Conversation.timestamp.asc())
    )
    messages = result.scalars().all()
    return [
        {
            "role": msg.role.value if hasattr(msg.role, "value") else msg.role,
            "content": msg.content,
            "sources": json.loads(msg.sources_cited) if msg.sources_cited else [],
            "timestamp": msg.timestamp.isoformat(),
        }
        for msg in messages
    ]


@router.get("/{case_id}/summary")
async def get_summary(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the compact AI-generated summary of past sessions."""
    case = await _get_case_with_access(case_id, current_user, db)
    return {"summary": case.compact_summary or ""}

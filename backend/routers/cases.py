from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database import get_db
from backend.models.case import Case
from backend.models.user import User, UserRole
from backend.schemas.case import CaseCreate, CaseResponse
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/cases", tags=["cases"])

@router.post("/", response_model=CaseResponse, status_code=201)
async def create_case(
    payload: CaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.ADVISOR:
        raise HTTPException(status_code=403, detail="Advisors only")
    case = Case(client_name=payload.client_name, created_by=current_user.user_id)
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return case

@router.get("/", response_model=list[CaseResponse])
async def list_cases(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.ADVISOR:
        raise HTTPException(status_code=403, detail="Advisors only")
    result = await db.execute(select(Case).where(Case.created_by == current_user.user_id))
    return result.scalars().all()

@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(case_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Case).where(Case.case_id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if current_user.role == UserRole.ADVISOR and case.created_by != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if current_user.role == UserRole.CLIENT and current_user.case_id != case_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return case

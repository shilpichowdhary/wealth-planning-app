import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database import get_db
from backend.models.case import Case
from backend.models.client_profile import ClientProfile
from backend.models.recommendation import Recommendation
from backend.models.user import User, UserRole
from backend.routers.auth import get_current_user, is_staff
from backend.services.pdf_service import build_report_html, generate_pdf

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{case_id}/pdf")
async def download_pdf(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case_result = await db.execute(select(Case).where(Case.case_id == case_id))
    case = case_result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Access control
    if is_staff(current_user) and current_user.role != UserRole.ADMIN and case.created_by != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if current_user.role == UserRole.CLIENT and current_user.case_id != case_id:
        raise HTTPException(status_code=403, detail="Access denied")

    profile_result = await db.execute(select(ClientProfile).where(ClientProfile.case_id == case_id))
    profile_row = profile_result.scalar_one_or_none()
    profile_dict = {}
    if profile_row:
        profile_dict = {
            "domicile": profile_row.domicile,
            "nationality": profile_row.nationality,
            "tax_residency": profile_row.tax_residency,
            "objectives": profile_row.objectives,
        }

    rec_result = await db.execute(select(Recommendation).where(Recommendation.case_id == case_id))
    recommendations = [
        {
            "structure_name": r.structure_name,
            "confidence_level": r.confidence_level,
            "rationale": r.rationale,
            "sources": r.sources,
        }
        for r in rec_result.scalars().all()
    ]

    try:
        html = build_report_html(
            case_data={"client_name": case.client_name},
            profile=profile_dict,
            recommendations=recommendations,
            diagrams={},
        )
        pdf_bytes = await generate_pdf(html)
    except Exception as e:
        logger.error("PDF generation failed for case %s: %s", case_id, e)
        raise HTTPException(status_code=500, detail="Failed to generate PDF report")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=wealth-plan-{case_id[:8]}.pdf"},
    )

"""Deck generation + download endpoints.

Replaces the old mechanical HTML→Puppeteer /reports/{id}/pdf with an
agent-driven PowerPoint pipeline:

  POST /reports/{case_id}/deck/generate  → curator + render → CaseDeck row
  GET  /reports/{case_id}/deck            → metadata of latest version + staleness
  GET  /reports/{case_id}/deck.pptx       → download editable PowerPoint
  GET  /reports/{case_id}/deck.pdf        → download PDF (lazy soffice convert)

Access control mirrors the rest of the case API: admin sees all, advisor
sees own cases, client sees only their own case.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.case import Case
from backend.models.user import User, UserRole
from backend.routers.auth import get_current_user, is_staff
from backend.services import deck_service
from backend.storage import get_storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"])


async def _check_access(case_id: str, db: AsyncSession, user: User) -> Case:
    """Look up the case and enforce per-user access. Raises 404/403."""
    from sqlalchemy import select
    case = (
        await db.execute(select(Case).where(Case.case_id == case_id))
    ).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if (
        is_staff(user)
        and user.role != UserRole.ADMIN
        and case.created_by != user.user_id
    ):
        raise HTTPException(status_code=403, detail="Access denied")
    if user.role == UserRole.CLIENT and user.case_id != case_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return case


@router.get("/{case_id}/deck")
async def get_deck_status(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns metadata about the latest generated deck (or {none: true}).

    Used by the frontend to render the Generate / Download buttons and to
    show a 'inputs have changed since last generation' staleness pill.
    """
    await _check_access(case_id, db, current_user)
    deck = await deck_service.latest_deck(case_id, db)
    if not deck:
        return {"exists": False}
    stale = await deck_service.is_stale(case_id, db)
    return {
        "exists": True,
        "version": deck.version,
        "generated_at": deck.generated_at.isoformat() if deck.generated_at else None,
        "generated_by": deck.generated_by,
        "model_used": deck.model_used,
        "stale": stale,
        "has_pdf": bool(deck.pdf_path and get_storage().exists(deck.pdf_path)),
    }


@router.post("/{case_id}/deck/generate")
async def generate_deck_endpoint(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Curator + renderer pipeline. Synchronous (≈30s on Sonnet 4.6 + caching).

    Only staff can generate decks — clients can download but cannot regenerate.
    """
    await _check_access(case_id, db, current_user)
    if current_user.role == UserRole.CLIENT:
        raise HTTPException(status_code=403, detail="Only staff can generate decks")
    try:
        deck = await deck_service.generate_deck(
            case_id, db, generated_by=current_user.user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Deck generation failed for %s: %s", case_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Deck generation failed: {e}")
    return {
        "version": deck.version,
        "generated_at": deck.generated_at.isoformat(),
        "model_used": deck.model_used,
    }


@router.get("/{case_id}/deck.pptx")
async def download_pptx(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = await _check_access(case_id, db, current_user)
    deck = await deck_service.latest_deck(case_id, db)
    storage = get_storage()
    if not deck or not deck.pptx_path or not storage.exists(deck.pptx_path):
        raise HTTPException(status_code=404, detail="No deck generated yet")
    return storage.response(
        deck.pptx_path,
        media_type=(
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        ),
        download_name=f"wealth-plan-{(case.client_name or case_id)[:24]}.pptx",
    )


@router.get("/{case_id}/deck.pdf")
async def download_pdf(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = await _check_access(case_id, db, current_user)
    deck = await deck_service.latest_deck(case_id, db)
    if not deck:
        raise HTTPException(status_code=404, detail="No deck generated yet")
    try:
        pdf_key = await deck_service.ensure_pdf(deck, db)
    except (FileNotFoundError, RuntimeError) as e:
        logger.error("PDF conversion failed for %s: %s", case_id, e)
        raise HTTPException(status_code=500, detail="PDF conversion failed")
    return get_storage().response(
        pdf_key,
        media_type="application/pdf",
        download_name=f"wealth-plan-{(case.client_name or case_id)[:24]}.pdf",
    )

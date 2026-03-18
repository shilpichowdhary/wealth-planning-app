from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.kb.kb_manager import KBManager
from backend.routers.auth import get_current_user
from backend.models.user import User, UserRole
from backend.models.kb_review_queue import KBReviewQueue, ReviewStatus
from backend.database import get_db
from pydantic import BaseModel

router = APIRouter(prefix="/kb", tags=["knowledge-base"])

def get_kb_manager():
    return KBManager()

@router.post("/upload")
async def upload_kb_file(
    file: UploadFile = File(...),
    jurisdiction: str = Form(...),
    topic: str = Form(...),
    current_user: User = Depends(get_current_user),
    kb: KBManager = Depends(get_kb_manager),
):
    if current_user.role != UserRole.ADVISOR:
        raise HTTPException(status_code=403, detail="Advisors only")
    content = (await file.read()).decode("utf-8", errors="replace")
    count = await kb.upload_kb_file(
        content=content,
        source_file=file.filename,
        jurisdiction=jurisdiction,
        topic=topic,
    )
    return {"message": f"Uploaded {count} chunks", "source_file": file.filename}

@router.get("/search")
async def search_kb(
    q: str,
    jurisdiction: str | None = None,
    current_user: User = Depends(get_current_user),
    kb: KBManager = Depends(get_kb_manager),
):
    results = await kb.query(q, jurisdiction=jurisdiction)
    return {"results": results}

class ReviewAction(BaseModel):
    action: str  # "approve" | "reject" | "resubmit"
    note: str | None = None

@router.get("/review-queue")
async def list_review_queue(
    status: str = "pending",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.ADVISOR:
        raise HTTPException(status_code=403, detail="Advisors only")
    result = await db.execute(select(KBReviewQueue).where(KBReviewQueue.current_status == status))
    entries = result.scalars().all()
    return [
        {
            "entry_id": e.entry_id,
            "jurisdiction": e.jurisdiction,
            "topic": e.topic,
            "content": e.content[:500],
            "web_url": e.web_url,
            "date_retrieved": e.date_retrieved.isoformat() if e.date_retrieved else None,
            "current_status": e.current_status,
            "review_count": e.review_count,
            "rejection_note": e.rejection_note,
        }
        for e in entries
    ]

@router.post("/review-queue/{entry_id}/action")
async def review_queue_action(
    entry_id: str,
    payload: ReviewAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    kb: KBManager = Depends(get_kb_manager),
):
    if current_user.role != UserRole.ADVISOR:
        raise HTTPException(status_code=403, detail="Advisors only")
    result = await db.execute(select(KBReviewQueue).where(KBReviewQueue.entry_id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404)

    from datetime import datetime
    entry.reviewed_by = current_user.user_id
    entry.reviewed_at = datetime.utcnow()
    entry.review_count += 1

    if payload.action == "approve":
        entry.current_status = ReviewStatus.APPROVED
        await kb.upload_kb_file(
            content=entry.content,
            source_file=f"web_{entry.entry_id[:8]}.txt",
            jurisdiction=entry.jurisdiction,
            topic=entry.topic,
            source_type="web_sourced_approved",
        )
    elif payload.action == "reject":
        entry.current_status = ReviewStatus.REJECTED
        entry.rejection_note = payload.note
    elif payload.action == "resubmit":
        if entry.current_status not in (ReviewStatus.REJECTED, ReviewStatus.RE_REJECTED):
            raise HTTPException(status_code=400, detail="Can only resubmit rejected entries")
        entry.current_status = ReviewStatus.RESUBMITTED
        entry.resubmission_note = payload.note

    await db.commit()
    return {"status": entry.current_status}

from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.kb.kb_manager import KBManager
from backend.routers.auth import get_current_user, is_staff
from backend.models.user import User, UserRole
from backend.models.kb_review_queue import KBReviewQueue, ReviewStatus
from backend.database import get_db
from pydantic import BaseModel

router = APIRouter(prefix="/kb", tags=["knowledge-base"])

# Root for kb_l2_wiki source files — the ingest script extracts under
# kb_files/layer2_wiki_articles/, and source_file paths recorded in ChromaDB
# are relative to kb_files/. Resolving requested paths against this root
# (and rejecting anything that escapes it) prevents traversal attacks.
WIKI_ROOT = (Path(__file__).resolve().parents[2] / "kb_files").resolve()

def get_kb_manager():
    return KBManager()

@router.post("/upload")
async def upload_kb_file(
    file: UploadFile = File(...),
    jurisdiction: str = Form(...),
    topic: str = Form("general"),
    current_user: User = Depends(get_current_user),
    kb: KBManager = Depends(get_kb_manager),
):
    if not is_staff(current_user):
        raise HTTPException(status_code=403, detail="Advisors only")
    import tempfile, os
    from backend.services.document_service import extract_text

    raw = await file.read()
    filename = file.filename or "upload"
    suffix = os.path.splitext(filename)[1].lower() or ".txt"

    # Write to temp file so text extractors (PyMuPDF, python-docx) can open it
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name

    try:
        ext = suffix.lstrip(".")
        if ext == "pdf":
            content = extract_text(tmp_path, "pdf")
        elif ext in ("doc", "docx"):
            content = extract_text(tmp_path, "docx")
        else:
            content = raw.decode("utf-8", errors="replace")
    finally:
        os.unlink(tmp_path)

    count = await kb.upload_kb_file(
        content=content,
        source_file=filename,
        jurisdiction=jurisdiction,
        topic=topic,
    )
    return {"message": f"Uploaded {count} chunks", "chunks_added": count, "source_file": filename}

@router.get("/documents")
async def list_kb_documents(
    current_user: User = Depends(get_current_user),
    kb: KBManager = Depends(get_kb_manager),
):
    if not is_staff(current_user):
        raise HTTPException(status_code=403, detail="Advisors only")
    return await kb.list_documents()


@router.delete("/documents/{source_file:path}")
async def delete_kb_document(
    source_file: str,
    current_user: User = Depends(get_current_user),
    kb: KBManager = Depends(get_kb_manager),
):
    if not is_staff(current_user):
        raise HTTPException(status_code=403, detail="Advisors only")
    deleted = await kb.delete_document(source_file)
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted_chunks": deleted, "source_file": source_file}


@router.post("/rechunk")
async def rechunk_kb(
    current_user: User = Depends(get_current_user),
    kb: KBManager = Depends(get_kb_manager),
):
    """Re-chunk every KB document at the current chunk size.

    Maintenance op: reconstructs each document's text from its stored chunks
    and re-embeds it at the current (smaller) chunk size, so documents ingested
    under the old 800-word chunking gain the sharper retrieval of the new
    220-word chunking. Admin-only — it re-embeds the whole KB and briefly
    replaces each document's chunks."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    report = await kb.rechunk_all()
    total_old = sum(r.get("old_chunks", 0) for r in report.values())
    total_new = sum(max(r.get("new_chunks", 0), 0) for r in report.values())
    failed = [sf for sf, r in report.items() if r.get("new_chunks") == -1]
    return {
        "documents": len(report),
        "total_old_chunks": total_old,
        "total_new_chunks": total_new,
        "failed": failed,
        "detail": report,
    }


@router.get("/wiki/{path:path}")
async def read_wiki_file(
    path: str,
    current_user: User = Depends(get_current_user),
):
    """Return the raw markdown for an ingested Layer-2 wiki file.

    `path` is the source_file recorded in ChromaDB (e.g.
    "layer2_wiki_articles/wealth_planning/india/trust-taxation.md"), resolved
    against kb_files/ on disk. Only files under that root are served.
    """
    if not is_staff(current_user):
        raise HTTPException(status_code=403, detail="Advisors only")
    if not path.endswith(".md"):
        raise HTTPException(status_code=400, detail="Only markdown files are readable")

    candidate = (WIKI_ROOT / path).resolve()
    try:
        candidate.relative_to(WIKI_ROOT)
    except ValueError:
        raise HTTPException(status_code=400, detail="Path escapes wiki root")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Wiki file not found")

    return {
        "path": path,
        "content": candidate.read_text(encoding="utf-8", errors="replace"),
    }


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
    if not is_staff(current_user):
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
    if not is_staff(current_user):
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

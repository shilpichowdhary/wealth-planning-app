import logging
import os
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from backend.config import settings
from backend.database import get_db
from backend.models.document import Document, FileType
from backend.models.user import User, UserRole
from backend.routers.auth import get_current_user, is_staff
from backend.services.document_service import process_and_embed_document

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/{case_id}/upload", status_code=201)
async def upload_document(
    case_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from backend.services.document_service import validate_mime_type_from_buffer

    if not is_staff(current_user):
        raise HTTPException(status_code=403, detail="Advisors only")

    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File exceeds 20MB limit")

    # MIME validation BEFORE touching disk — rejects executables disguised as PDFs.
    try:
        file_type = validate_mime_type_from_buffer(content)
    except ValueError as e:
        raise HTTPException(status_code=415, detail=str(e))

    upload_dir = os.path.join(settings.uploads_path, "cases", case_id)
    os.makedirs(upload_dir, exist_ok=True)
    safe_filename = os.path.basename(file.filename or "upload")
    if not safe_filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    file_path = os.path.join(upload_dir, safe_filename)
    with open(file_path, "wb") as f:
        f.write(content)

    doc = Document(
        case_id=case_id,
        filename=safe_filename,
        file_path=file_path,
        file_type=FileType(file_type),
        file_size_bytes=len(content),
        uploaded_by=current_user.user_id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    try:
        chunk_count = await process_and_embed_document(file_path, file_type, case_id, file.filename)
        doc.parsed = True
        await db.commit()
    except Exception as e:
        logger.error("Embedding failed for document %s: %s", file.filename, e)
        chunk_count = 0

    return {
        "message": f"Uploaded and embedded {chunk_count} chunks",
        "document_id": doc.document_id,
        "chunk_count": chunk_count,
    }

import logging
import os
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from backend.config import settings
from backend.database import get_db
from backend.models.document import Document, FileType
from backend.models.user import User, UserRole
from backend.routers.auth import get_current_user, is_staff
from backend.services.document_service import process_and_embed_document, validate_mime_type
from backend.storage import get_storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/{case_id}/upload", status_code=201)
async def upload_document(
    case_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not is_staff(current_user):
        raise HTTPException(status_code=403, detail="Advisors only")

    # Read and size-check
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File exceeds 20MB limit")

    # Persist the upload via the storage backend (local filesystem or Azure Blob)
    safe_filename = os.path.basename(file.filename or "upload")
    if not safe_filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    storage = get_storage()
    key = f"uploads/cases/{case_id}/{safe_filename}"
    storage.save_bytes(key, content, content_type=file.content_type)

    # MIME validation + embedding need a real local path (python-magic / PyMuPDF / docx).
    with storage.as_local_path(key) as local_path:
        try:
            file_type = validate_mime_type(str(local_path))
        except ValueError as e:
            storage.delete(key)
            raise HTTPException(status_code=415, detail=str(e))

        # Save metadata to DB (file_path stores the portable storage key)
        doc = Document(
            case_id=case_id,
            filename=safe_filename,
            file_path=key,
            file_type=FileType(file_type),
            file_size_bytes=len(content),
            uploaded_by=current_user.user_id,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        # Process and embed (synchronous but acceptable for V1)
        try:
            chunk_count = await process_and_embed_document(str(local_path), file_type, case_id, file.filename)
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

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

ALLOWED_MIMES = {
    "text/plain": "txt",
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}


def validate_mime_type(file_path: str) -> str:
    """Returns file type string ('txt', 'pdf', 'docx') or raises ValueError."""
    import magic
    mime = magic.from_file(file_path, mime=True)
    if mime not in ALLOWED_MIMES:
        raise ValueError(f"Invalid file type: {mime}. Accepted: txt, pdf, docx")
    return ALLOWED_MIMES[mime]


def extract_text(file_path: str, file_type: str) -> str:
    if file_type == "txt":
        return Path(file_path).read_text(encoding="utf-8", errors="replace")
    elif file_type == "pdf":
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        return "\n".join(page.get_text() for page in doc)
    elif file_type == "docx":
        import docx
        d = docx.Document(file_path)
        return "\n".join(p.text for p in d.paragraphs)
    raise ValueError(f"Unsupported file type: {file_type}")


async def process_and_embed_document(
    file_path: str,
    file_type: str,
    case_id: str,
    filename: str,
) -> int:
    """Extract text, chunk, embed, store in case-scoped ChromaDB collection."""
    from backend.kb.chroma_client import get_chroma_client, get_case_collection, get_embedding_model
    from backend.kb.kb_manager import _chunk_text

    text = extract_text(file_path, file_type)
    chunks = _chunk_text(text)
    if not chunks:
        logger.warning("No chunks extracted from %s", filename)
        return 0

    model = get_embedding_model()
    embeddings = model.encode(chunks).tolist()
    client = get_chroma_client()
    collection = get_case_collection(client, case_id)

    # Replace existing chunks from same file
    existing = collection.get(where={"source_file": filename})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])

    ids = [f"{filename}_{i}_{hashlib.md5(c.encode()).hexdigest()[:8]}" for i, c in enumerate(chunks)]
    metadatas = [{"source_file": filename, "case_id": case_id, "source_type": "client_document"} for _ in chunks]
    collection.add(documents=chunks, embeddings=embeddings, ids=ids, metadatas=metadatas)
    return len(chunks)

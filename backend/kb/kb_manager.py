import hashlib
from datetime import datetime
from typing import Any
from backend.kb.chroma_client import get_embedding_model, get_chroma_client, get_kb_collection

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
MIN_SIMILARITY = 0.35

def _chunk_text(text: str) -> list[str]:
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunk = " ".join(words[i:i + CHUNK_SIZE])
        chunks.append(chunk)
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return [c for c in chunks if c.strip()]

class KBManager:
    def __init__(self, chroma_path: str | None = None):
        self.client = get_chroma_client(chroma_path)
        self.collection = get_kb_collection(self.client)
        self.model = get_embedding_model()

    async def upload_kb_file(
        self,
        content: str,
        source_file: str,
        jurisdiction: str,
        topic: str,
        last_updated: str | None = None,
        source_type: str = "kb_upload",
    ) -> int:
        # Delete existing chunks for this file
        existing = self.collection.get(where={"source_file": source_file})
        if existing["ids"]:
            self.collection.delete(ids=existing["ids"])

        chunks = _chunk_text(content)
        if not chunks:
            return 0

        embeddings = self.model.encode(chunks).tolist()
        ids = [f"{source_file}_{i}_{hashlib.md5(c.encode()).hexdigest()[:8]}" for i, c in enumerate(chunks)]
        metadatas = [
            {
                "source_file": source_file,
                "jurisdiction": jurisdiction,
                "topic": topic,
                "last_updated": last_updated or datetime.utcnow().isoformat(),
                "source_type": source_type,
            }
            for _ in chunks
        ]
        self.collection.add(documents=chunks, embeddings=embeddings, ids=ids, metadatas=metadatas)
        return len(chunks)

    async def list_documents(self) -> list[dict[str, Any]]:
        """Return one entry per unique source_file with metadata."""
        result = self.collection.get(include=["metadatas"])
        seen: dict[str, dict] = {}
        for meta in result["metadatas"]:
            sf = meta.get("source_file", "unknown")
            if sf not in seen:
                seen[sf] = {
                    "source_file": sf,
                    "jurisdiction": meta.get("jurisdiction", ""),
                    "topic": meta.get("topic", ""),
                    "last_updated": meta.get("last_updated", ""),
                    "source_type": meta.get("source_type", ""),
                    "chunk_count": 1,
                }
            else:
                seen[sf]["chunk_count"] += 1
        return sorted(seen.values(), key=lambda x: x["last_updated"], reverse=True)

    async def delete_document(self, source_file: str) -> int:
        """Delete all chunks for a given source_file. Returns number deleted."""
        existing = self.collection.get(where={"source_file": source_file})
        if not existing["ids"]:
            return 0
        self.collection.delete(ids=existing["ids"])
        return len(existing["ids"])

    async def query(self, query: str, n_results: int = 5, jurisdiction: str | None = None) -> list[dict[str, Any]]:
        embedding = self.model.encode([query]).tolist()
        where = {"jurisdiction": jurisdiction} if jurisdiction else None
        try:
            results = self.collection.query(
                query_embeddings=embedding,
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            return []
        output = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            similarity = 1 - dist
            if similarity >= MIN_SIMILARITY:
                output.append({"text": doc, "similarity": similarity, **meta})
        return output

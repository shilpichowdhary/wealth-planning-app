from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from backend.kb.kb_manager import KBManager
from backend.services.web_search_service import WebSearchService
from backend.config import settings

class RetrievalSource(str, Enum):
    KB = "kb"
    WEB = "web"
    NONE = "none"

@dataclass
class RetrievalResult:
    source: RetrievalSource
    chunks: list[dict[str, Any]] = field(default_factory=list)
    web_results: list[Any] = field(default_factory=list)
    has_sufficient_context: bool = False

KB_SUFFICIENT_THRESHOLD = 2

class RAGService:
    def __init__(self, kb_manager: KBManager | None = None):
        self.kb = kb_manager or KBManager()
        self.web = WebSearchService()

    async def retrieve(
        self,
        query: str,
        session_tavily_count: int,
        jurisdiction: str | None = None,
        case_id: str | None = None,
    ) -> RetrievalResult:
        # Stage 1: KB
        kb_chunks = await self.kb.query(query, n_results=5, jurisdiction=jurisdiction)

        # Also query case-specific collection if case_id provided
        if case_id:
            from backend.kb.chroma_client import get_chroma_client, get_case_collection
            try:
                client = get_chroma_client()
                case_col = get_case_collection(client, case_id)
                emb = self.kb.model.encode([query]).tolist()
                case_results = case_col.query(query_embeddings=emb, n_results=3, include=["documents", "metadatas", "distances"])
                for doc, meta, dist in zip(case_results["documents"][0], case_results["metadatas"][0], case_results["distances"][0]):
                    if (1 - dist) >= 0.35:
                        kb_chunks.append({"text": doc, "similarity": 1 - dist, "source_type": "client_document", **meta})
            except Exception:
                pass

        if len(kb_chunks) >= KB_SUFFICIENT_THRESHOLD:
            return RetrievalResult(source=RetrievalSource.KB, chunks=kb_chunks, has_sufficient_context=True)

        # Stage 2: Web search (if under session limit)
        if session_tavily_count >= settings.tavily_max_calls_per_session:
            if kb_chunks:
                return RetrievalResult(source=RetrievalSource.KB, chunks=kb_chunks, has_sufficient_context=False)
            return RetrievalResult(source=RetrievalSource.NONE)

        web_results = await self.web.search(query)
        if web_results:
            return RetrievalResult(
                source=RetrievalSource.WEB,
                chunks=kb_chunks,
                web_results=web_results,
                has_sufficient_context=True,
            )

        return RetrievalResult(source=RetrievalSource.NONE)

def get_rag_service():
    return RAGService()

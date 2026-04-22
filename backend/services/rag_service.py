import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from backend.kb.kb_manager import KBManager
from backend.services.web_search_service import WebSearchService
from backend.config import settings

logger = logging.getLogger(__name__)

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
    # Set when KB is thin AND the caller has not yet allowed the web or
    # asked for a best-effort answer. The chat router short-circuits and
    # asks the user for permission rather than calling Tavily silently.
    needs_web_approval: bool = False

# Minimum KB chunks above similarity floor to consider "sufficient".
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
        allow_web: bool = False,
        force_answer: bool = False,
    ) -> RetrievalResult:
        """KB-first retrieval.

        Order of preference:
        1. If KB has ≥ KB_SUFFICIENT_THRESHOLD chunks, use KB.
        2. Otherwise:
           - If caller set allow_web=True, fall through to Tavily.
           - If caller set force_answer=True, return whatever KB has (possibly empty).
           - Else set needs_web_approval=True so the chat router can prompt the user.
        """
        # Stage 1 — KB (main collection + case-specific collection)
        kb_chunks = await self.kb.query(query, n_results=5, jurisdiction=jurisdiction)
        if case_id:
            from backend.kb.chroma_client import get_chroma_client, get_case_collection
            try:
                client = get_chroma_client()
                case_col = get_case_collection(client, case_id)
                emb = self.kb.model.encode([query]).tolist()
                case_results = case_col.query(
                    query_embeddings=emb,
                    n_results=3,
                    include=["documents", "metadatas", "distances"],
                )
                for doc, meta, dist in zip(
                    case_results["documents"][0],
                    case_results["metadatas"][0],
                    case_results["distances"][0],
                ):
                    if (1 - dist) >= 0.35:
                        kb_chunks.append({
                            "text": doc,
                            "similarity": 1 - dist,
                            "source_type": "client_document",
                            **meta,
                        })
            except Exception as e:
                logger.warning("Case collection query failed for case_id=%s: %s", case_id, e)

        if len(kb_chunks) >= KB_SUFFICIENT_THRESHOLD:
            return RetrievalResult(
                source=RetrievalSource.KB,
                chunks=kb_chunks,
                has_sufficient_context=True,
            )

        # Stage 2 — KB is thin. Decide based on caller's approval flags.
        if force_answer:
            return RetrievalResult(
                source=RetrievalSource.KB if kb_chunks else RetrievalSource.NONE,
                chunks=kb_chunks,
                has_sufficient_context=False,
            )

        if not allow_web:
            return RetrievalResult(
                source=RetrievalSource.KB if kb_chunks else RetrievalSource.NONE,
                chunks=kb_chunks,
                needs_web_approval=True,
                has_sufficient_context=False,
            )

        # allow_web is True — run Tavily (subject to session cap)
        if session_tavily_count >= settings.tavily_max_calls_per_session:
            return RetrievalResult(
                source=RetrievalSource.KB if kb_chunks else RetrievalSource.NONE,
                chunks=kb_chunks,
                has_sufficient_context=False,
            )

        web_results = await self.web.search(query)
        if web_results:
            return RetrievalResult(
                source=RetrievalSource.WEB,
                chunks=kb_chunks,
                web_results=web_results,
                has_sufficient_context=True,
            )

        return RetrievalResult(source=RetrievalSource.NONE, chunks=kb_chunks)


def get_rag_service():
    return RAGService()

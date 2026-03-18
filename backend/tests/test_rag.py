import pytest
from backend.kb.kb_manager import KBManager

@pytest.fixture
def kb_manager(tmp_path):
    return KBManager(chroma_path=str(tmp_path / "chroma"))

@pytest.mark.asyncio
async def test_upload_and_retrieve(kb_manager):
    content = "Singapore trusts are exempt from income tax on foreign-sourced income under Section 13(8) of the Income Tax Act."
    await kb_manager.upload_kb_file(
        content=content,
        source_file="singapore_trust_law.txt",
        jurisdiction="Singapore",
        topic="Trust Law",
    )
    results = await kb_manager.query(
        query="Singapore trust income tax exemption",
        n_results=3,
    )
    assert len(results) > 0
    assert "Singapore" in results[0]["jurisdiction"]
    assert results[0]["source_file"] == "singapore_trust_law.txt"

@pytest.mark.asyncio
async def test_replace_on_reupload(kb_manager):
    await kb_manager.upload_kb_file("Old content about trusts v1", "india_tax.txt", "India", "Tax")
    first_result = kb_manager.collection.get(where={"source_file": "india_tax.txt"})
    first_ids = set(first_result["ids"])
    assert len(first_ids) > 0

    await kb_manager.upload_kb_file("New content about trusts v2 completely different", "india_tax.txt", "India", "Tax")
    second_result = kb_manager.collection.get(where={"source_file": "india_tax.txt"})
    second_ids = set(second_result["ids"])

    # All old IDs should be gone, replaced by new ones
    assert len(second_ids.intersection(first_ids)) == 0
    assert len(second_ids) > 0

from unittest.mock import AsyncMock, patch
from backend.services.rag_service import RAGService, RetrievalResult, RetrievalSource

@pytest.fixture
def rag_service(kb_manager):
    return RAGService(kb_manager=kb_manager)

@pytest.mark.asyncio
async def test_retrieval_uses_kb_when_available(rag_service, kb_manager):
    await kb_manager.upload_kb_file(
        "Singapore trusts are exempt from foreign income tax under s13(8).",
        "singapore_trust_law.txt", "Singapore", "Trust Law"
    )
    await kb_manager.upload_kb_file(
        "Additional Singapore trust rules for foreign settlors apply.",
        "singapore_trust_rules.txt", "Singapore", "Trust Law"
    )
    result = await rag_service.retrieve("Singapore trust tax exemption", session_tavily_count=0)
    assert result.source == RetrievalSource.KB
    assert len(result.chunks) > 0

@pytest.mark.asyncio
async def test_retrieval_respects_tavily_limit(rag_service):
    result = await rag_service.retrieve("anything", session_tavily_count=5)
    assert result.source != RetrievalSource.WEB

@pytest.mark.asyncio
async def test_retrieval_returns_none_when_no_context(rag_service):
    # Empty KB, tavily limit reached
    result = await rag_service.retrieve("obscure topic xyz abc def", session_tavily_count=5)
    assert result.source == RetrievalSource.NONE
    assert not result.has_sufficient_context

@pytest.mark.asyncio
async def test_retrieval_falls_back_to_web(rag_service):
    with patch("backend.services.rag_service.WebSearchService.search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = [{"text": "Web result", "url": "https://example.com", "title": "Test"}]
        result = await rag_service.retrieve("obscure liechtenstein foundation rule xyz", session_tavily_count=0)
        assert result.source == RetrievalSource.WEB

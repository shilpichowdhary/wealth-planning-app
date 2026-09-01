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

from backend.kb import kb_manager as _kbm


def _chunk_with(text: str, size: int, overlap: int) -> list[str]:
    """Reproduce the fixed-overlap chunker for an arbitrary size/overlap so we
    can test reconstruction against the OLD (800/100) scheme too."""
    words = text.split()
    out, i, step = [], 0, max(1, size - overlap)
    while i < len(words):
        piece = " ".join(words[i:i + size])
        if piece.strip():
            out.append(piece)
        i += step
    return out


def test_reconstruct_text_is_lossless_old_scheme():
    original = " ".join(f"w{n}" for n in range(2000))  # 2000 distinct words
    chunks = _chunk_with(original, size=800, overlap=100)  # old scheme
    assert len(chunks) > 1  # actually overlapping
    assert _kbm._reconstruct_text(chunks) == original


def test_reconstruct_text_is_lossless_new_scheme():
    original = " ".join(f"t{n}" for n in range(1000))
    chunks = _kbm._chunk_text(original)  # current 220/40 scheme
    assert len(chunks) > 1
    assert _kbm._reconstruct_text(chunks) == original


def test_reconstruct_single_chunk_and_empty():
    assert _kbm._reconstruct_text(["only one chunk here"]) == "only one chunk here"
    assert _kbm._reconstruct_text([]) == ""


def test_reconstruct_handles_repeated_words():
    # A document with a repeated phrase must not lose or duplicate words at the
    # join, even though shorter accidental overlaps exist.
    original = "the trust holds the shares the trust holds the assets " * 3
    original = original.strip()
    chunks = _chunk_with(original, size=8, overlap=3)
    assert len(chunks) > 1
    assert _kbm._reconstruct_text(chunks) == original


def test_chunk_index_parsing():
    assert _kbm._chunk_index("uk/bpr.md_0_ab12cd34", "uk/bpr.md") == 0
    assert _kbm._chunk_index("uk/bpr.md_12_ab12cd34", "uk/bpr.md") == 12
    # source_file with underscores stays robust
    assert _kbm._chunk_index("a_b_c.txt_3_deadbeef", "a_b_c.txt") == 3


@pytest.mark.asyncio
async def test_lexical_recall_for_number_and_acronym(kb_manager):
    """Regression for the '2.5mn UK business relief' gap: a query using the
    shorthand ('2.5mn') and a partial term ('business relief') must still
    retrieve an article written with the full term and spaced number."""
    await kb_manager.upload_kb_file(
        content=(
            "UK 2.5 Mn Business Property Relief (BPR). Business Property "
            "Relief provides relief from inheritance tax on qualifying "
            "business assets. The relevant threshold discussed here is "
            "GBP 2.5 million of qualifying business assets."
        ),
        source_file="uk_bpr.txt",
        jurisdiction="UK",
        topic="Inheritance Tax",
    )
    # A decoy so the target isn't the only document in the store.
    await kb_manager.upload_kb_file(
        content="Singapore GST registration rules and thresholds for traders.",
        source_file="sg_gst.txt",
        jurisdiction="Singapore",
        topic="GST",
    )
    results = await kb_manager.query("2.5mn UK business relief", n_results=3)
    assert results, "hybrid retrieval returned nothing"
    assert results[0]["source_file"] == "uk_bpr.txt"


@pytest.mark.asyncio
async def test_acronym_only_query_recall(kb_manager):
    """A bare acronym query ('BPR') should retrieve the BPR article via the
    lexical arm even though the embedding of a 3-letter token is weak."""
    await kb_manager.upload_kb_file(
        content="Business Property Relief (BPR) reduces inheritance tax.",
        source_file="uk_bpr.txt", jurisdiction="UK", topic="IHT",
    )
    await kb_manager.upload_kb_file(
        content="Singapore variable capital company fund structures overview.",
        source_file="sg_vcc.txt", jurisdiction="Singapore", topic="Funds",
    )
    results = await kb_manager.query("BPR", n_results=3)
    assert any(r["source_file"] == "uk_bpr.txt" for r in results)


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
async def test_retrieval_requires_permission_before_web(rag_service):
    """KB-first policy: thin KB coverage must NOT silently call web; instead
    retrieval flags needs_web_approval so the chat router can prompt the user."""
    result = await rag_service.retrieve("obscure liechtenstein foundation rule xyz", session_tavily_count=0)
    assert result.source == RetrievalSource.NONE
    assert result.needs_web_approval is True


@pytest.mark.asyncio
async def test_retrieval_falls_back_to_web_when_allowed(rag_service):
    with patch("backend.services.rag_service.WebSearchService.search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = [{"text": "Web result", "url": "https://example.com", "title": "Test"}]
        result = await rag_service.retrieve(
            "obscure liechtenstein foundation rule xyz",
            session_tavily_count=0,
            allow_web=True,
        )
        assert result.source == RetrievalSource.WEB


@pytest.mark.asyncio
async def test_retrieval_force_answer_returns_kb_without_web(rag_service):
    """force_answer path: no KB match, no web call, caller gets what's there."""
    with patch("backend.services.rag_service.WebSearchService.search", new_callable=AsyncMock) as mock_search:
        result = await rag_service.retrieve(
            "obscure liechtenstein foundation rule xyz",
            session_tavily_count=0,
            force_answer=True,
        )
        assert result.source in (RetrievalSource.KB, RetrievalSource.NONE)
        assert result.needs_web_approval is False
        mock_search.assert_not_called()

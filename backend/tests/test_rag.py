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

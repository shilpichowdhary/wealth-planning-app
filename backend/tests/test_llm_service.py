import pytest
from unittest.mock import patch, MagicMock
from backend.services.llm_service import LLMService, build_system_prompt, pseudonymise_profile
from backend.services.rag_service import RetrievalResult, RetrievalSource


def test_pseudonymise_strips_pii():
    profile = {
        "client_name": "Rajan Sharma",
        "nationality": "Indian",
        "domicile": "Singapore",
        "family_members": [{"name": "Priya Sharma", "relationship": "spouse"}],
        "asset_classes": ["real_estate", "equities"],
    }
    result = pseudonymise_profile(profile)
    assert "Rajan" not in str(result)
    assert "Priya" not in str(result)
    assert result["nationality"] == "Indian"
    assert result["domicile"] == "Singapore"
    assert result["family_members"][0]["name"] == "Spouse"


def test_pseudonymise_multiple_children():
    profile = {
        "client_name": "X",
        "family_members": [
            {"name": "A", "relationship": "child"},
            {"name": "B", "relationship": "child"},
        ]
    }
    result = pseudonymise_profile(profile)
    names = [m["name"] for m in result["family_members"]]
    assert names == ["Child", "Child 2"]


def test_system_prompt_includes_disclaimer():
    prompt = build_system_prompt(profile={}, kb_chunks=[], web_results=[])
    assert "not legal" in prompt.lower() or "not tax advice" in prompt.lower()


def test_system_prompt_includes_source_requirement():
    prompt = build_system_prompt(profile={}, kb_chunks=[], web_results=[])
    assert "cite" in prompt.lower() or "source" in prompt.lower()


@pytest.mark.asyncio
async def test_stream_chat_returns_warning_when_no_context():
    svc = LLMService()
    retrieval = RetrievalResult(source=RetrievalSource.NONE, has_sufficient_context=False)
    events = []
    async for event in svc.stream_chat(messages=[], retrieval=retrieval, profile={}):
        events.append(event)
    assert len(events) == 1
    assert events[0]["type"] == "text"
    assert "No knowledge base coverage" in events[0]["text"] or "⚠️" in events[0]["text"]


@pytest.mark.asyncio
async def test_stream_chat_error_yields_generic_message():
    svc = LLMService()
    retrieval = RetrievalResult(
        source=RetrievalSource.KB,
        chunks=[{"text": "x", "source_file": "f", "jurisdiction": "India", "topic": "Tax"}],
        has_sufficient_context=True,
    )

    with patch("anthropic.AsyncAnthropic") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        mock_instance.messages.stream.side_effect = Exception("API down")
        events = []
        async for event in svc.stream_chat(
            messages=[{"role": "user", "content": "test"}],
            retrieval=retrieval,
            profile={},
        ):
            events.append(event)
    full = "".join(e["text"] for e in events if e.get("type") == "text")
    assert "Error" in full or "Unable" in full

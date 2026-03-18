import pytest
from backend.services.llm_service import LLMService, build_system_prompt, pseudonymise_profile

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

def test_system_prompt_includes_disclaimer():
    prompt = build_system_prompt(profile={}, kb_chunks=[], web_results=[])
    assert "not legal" in prompt.lower() or "not tax advice" in prompt.lower()

def test_system_prompt_includes_source_requirement():
    prompt = build_system_prompt(profile={}, kb_chunks=[], web_results=[])
    assert "cite" in prompt.lower() or "source" in prompt.lower()

import json
import logging
from backend.config import settings

logger = logging.getLogger(__name__)

SUMMARY_PROMPT = """You are summarising a wealth planning advisory session.
Extract key facts into this compact JSON structure:
{
  "client": {"nationality": "", "domicile": "", "tax_residency": "", "family_structure": ""},
  "assets": {"jurisdictions": [], "approximate_value_range": "", "asset_classes": []},
  "existing_structures": "",
  "key_recommendations": [{"structure": "", "jurisdiction": "", "confidence": ""}],
  "open_questions": [],
  "last_updated": ""
}
Return ONLY valid JSON. Use "the Client" not their real name."""

async def generate_compact_summary(conversation_history: list[dict]) -> str:
    from anthropic import AsyncAnthropic
    from backend.services.settings_service import get_setting
    api_key = await get_setting("anthropic_api_key")
    model = await get_setting("claude_model")
    anthropic_client = AsyncAnthropic(api_key=api_key)
    messages = [{"role": m["role"], "content": m["content"]} for m in conversation_history[-20:]]
    try:
        response = await anthropic_client.messages.create(
            model=model,
            max_tokens=1000,
            system=SUMMARY_PROMPT,
            messages=messages,
        )
        text = response.content[0].text
        try:
            json.loads(text)  # validate
            return text
        except (json.JSONDecodeError, ValueError):
            logger.warning("Summary generation returned invalid JSON")
            return "{}"
    except Exception as e:
        logger.warning("Summary generation failed: %s", e)
        return "{}"

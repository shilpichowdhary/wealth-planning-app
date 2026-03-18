import logging
from anthropic import AsyncAnthropic
from backend.config import settings

logger = logging.getLogger(__name__)

client = AsyncAnthropic(api_key=settings.anthropic_api_key)

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
    messages = [{"role": m["role"], "content": m["content"]} for m in conversation_history[-20:]]
    try:
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=1000,
            system=SUMMARY_PROMPT,
            messages=messages,
        )
        return response.content[0].text
    except Exception as e:
        logger.warning("Summary generation failed: %s", e)
        return "{}"

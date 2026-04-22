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
    """Summarise the last 20 turns of a case into compact JSON.

    Implementation note: we serialise the transcript into a single user message
    rather than forwarding the raw [user, assistant, user, assistant, …] list.
    Sonnet 4.6 rejects a messages array that ends with an assistant turn
    ("does not support assistant message prefill"), which is what happens when
    the background task appends the latest assistant reply before summarising.
    """
    from anthropic import AsyncAnthropic

    if not conversation_history:
        return "{}"

    transcript_lines = []
    for msg in conversation_history[-20:]:
        role = str(msg.get("role", "user")).upper()
        content = str(msg.get("content", "")).strip()
        if content:
            transcript_lines.append(f"{role}: {content}")
    transcript = "\n\n".join(transcript_lines)
    if not transcript:
        return "{}"

    anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    try:
        response = await anthropic_client.messages.create(
            model=settings.claude_model,
            max_tokens=1000,
            system=SUMMARY_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Conversation transcript to summarise (oldest first):\n\n"
                        f"{transcript}\n\n"
                        "Return ONLY the compact JSON summary, no prose."
                    ),
                }
            ],
        )
        text = response.content[0].text.strip()
        # Strip any ```json fences the model occasionally adds
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        try:
            json.loads(text)
            return text
        except (json.JSONDecodeError, ValueError):
            logger.warning("Summary generation returned invalid JSON")
            return "{}"
    except Exception as e:
        logger.warning("Summary generation failed: %s", e)
        return "{}"

import json
import logging
import re
from typing import AsyncIterator
from backend.config import settings
from backend.services.rag_service import RetrievalResult, RetrievalSource

logger = logging.getLogger(__name__)


def extract_diagram_json(text: str) -> dict | None:
    """Extract diagram JSON from LLM response if present."""
    match = re.search(r'```json\s*(\{.*?"diagram_nodes".*?\})\s*```', text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


DISCLAIMER = "IMPORTANT: This is not legal or tax advice. Always verify recommendations with qualified counsel in the relevant jurisdiction."


REASONING_FIELDS = {
    "nationality", "domicile", "tax_residency", "asset_classes",
    "asset_jurisdictions", "existing_structures", "objectives", "family_members",
}


def pseudonymise_profile(profile: dict) -> dict:
    """Strip direct identifiers, retain only reasoning-relevant attributes."""
    result = {k: v for k, v in profile.items() if k in REASONING_FIELDS}
    if "family_members" in result and isinstance(result["family_members"], list):
        role_counts: dict[str, int] = {}
        cleaned = []
        for member in result["family_members"]:
            rel = member.get("relationship", "family_member").title()
            count = role_counts.get(rel, 0) + 1
            role_counts[rel] = count
            label = rel if count == 1 else f"{rel} {count}"
            cleaned.append({k: v for k, v in member.items() if k != "name"} | {"name": label})
        result["family_members"] = cleaned
    return result


def build_system_prompt(profile: dict, kb_chunks: list[dict], web_results: list) -> str:
    sources_text = ""
    if kb_chunks:
        sources_text += "\n\n## Knowledge Base Sources\n"
        for c in kb_chunks:
            sources_text += f"\n[Source: {c.get('source_file', 'KB')} | {c.get('jurisdiction', '')} | {c.get('topic', '')}]\n{c['text']}\n"
    if web_results:
        sources_text += "\n\n## Web Sources\n"
        for w in web_results:
            # Handle both WebResult dataclass and dict
            if hasattr(w, 'url'):
                url, title, retrieved_at, text = w.url, w.title, w.retrieved_at, w.text
            else:
                url = w.get('url', '')
                title = w.get('title', '')
                retrieved_at = w.get('retrieved_at', '')
                text = w.get('text', '')
            sources_text += f"\n[Web Source: {title} | {url} | Retrieved: {retrieved_at}]\n{text}\n"

    profile_text = json.dumps(pseudonymise_profile(profile), indent=2) if profile else "No profile yet."

    return f"""You are an expert wealth planning advisor assistant helping structure advice for Ultra High Net Worth Individuals (UHNWI) and families.

## Client Profile (pseudonymised)
{profile_text}
{sources_text}

## Rules you MUST follow
1. ONLY make recommendations you can cite from the sources provided above. If a source is not available for a claim, state: "I do not have sufficient knowledge base coverage on this topic."
2. For every recommendation, cite the exact source: file name and section (for KB sources) or URL and retrieval date (for web sources).
3. Assign a confidence level to each recommendation: high | specialist_review | complex
4. Refer to the client as "the Client" and family members by their relationship (Spouse, Child 1, etc.)
5. {DISCLAIMER}

When generating structured recommendations, output a JSON block with this format:
```json
{{
  "recommendation": "Structure name",
  "confidence": "high|specialist_review|complex",
  "rationale": "...",
  "sources": [{{"file": "...", "section": "...", "url": null}}],
  "diagram_nodes": []
}}
```"""


class LLMService:
    """Stateless LLM service — create per request."""

    async def stream_chat(
        self,
        messages: list[dict],
        retrieval: RetrievalResult,
        profile: dict,
    ) -> AsyncIterator[str]:
        from anthropic import AsyncAnthropic
        if not retrieval.has_sufficient_context:
            yield "⚠️ No knowledge base coverage found for this query. Please upload relevant documentation or consult a specialist directly."
            return

        system = build_system_prompt(
            profile=profile,
            kb_chunks=retrieval.chunks,
            web_results=retrieval.web_results,
        )
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        try:
            async with client.messages.stream(
                model=settings.claude_model,
                max_tokens=settings.claude_max_tokens_per_query,
                system=system,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.warning("LLM streaming failed: %s", e, exc_info=True)
            yield "\n\n[Error: Unable to complete the response. Please try again or contact support.]"


# Module-level convenience function (wraps LLMService)
async def stream_chat(
    messages: list[dict],
    retrieval: RetrievalResult,
    profile: dict,
) -> AsyncIterator[str]:
    svc = LLMService()
    async for token in svc.stream_chat(messages=messages, retrieval=retrieval, profile=profile):
        yield token

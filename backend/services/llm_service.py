import json
import logging
import re
from typing import AsyncIterator
from backend.config import settings
from backend.services.rag_service import RetrievalResult, RetrievalSource

logger = logging.getLogger(__name__)


def extract_diagram_json(text: str) -> dict | None:
    """Extract and validate diagram JSON from the LLM response.

    Returns the parsed dict (Pydantic-validated shape) or None if no valid
    block is present.
    """
    from pydantic import ValidationError
    from backend.schemas.diagram import Diagram

    for match in re.finditer(r'```json\s*([\s\S]*?)\s*```', text):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict) or "entities" not in data:
            continue
        try:
            Diagram.model_validate(data)
        except ValidationError as e:
            logger.warning("Diagram JSON failed schema validation: %s", e)
            continue
        return data
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


def build_system_prompt(profile: dict, kb_chunks: list[dict], web_results: list, prior_summary: str | None = None, kb_has_documents: bool = True) -> str:
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
    if not kb_has_documents:
        no_sources_note = (
            "\n\n⚠️ NOTE: The knowledge base is **empty** — no documents have been uploaded.\n"
            "You MUST refuse to answer the substantive question from your general training knowledge. "
            "Reply with exactly this structure instead:\n"
            "- Problem Statement: restate the advisor's question briefly.\n"
            "- Knowledge Base Status: state clearly that no KB documents are available.\n"
            "- Call to Action: ask the advisor to upload supporting materials under Knowledge base → Upload, or to approve a web search.\n"
            "Do not provide tax, legal, or planning reasoning beyond restating the question and requesting sources."
        )
    elif not kb_chunks and not web_results:
        no_sources_note = (
            "\n\n⚠️ NOTE: The knowledge base contains documents, but **none matched this specific query**, and no web sources have been authorised.\n"
            "You MUST refuse to answer from your general training knowledge. Reply with:\n"
            "- Problem Statement: restate the advisor's question.\n"
            "- Knowledge Base Status: say that no KB sources matched. Do NOT list or guess document names — you do not have the full index.\n"
            "- Call to Action: ask the advisor to upload relevant documents or approve a web search.\n"
            "Only the client profile (below) may inform your restatement of the question — do not reason about tax, legal, or structural matters without a cited source."
        )
    else:
        no_sources_note = ""
    prior_context = f"\n\n## Prior Session Memory\nThe following is a summary of previous conversations on this case. Use it to maintain continuity:\n{prior_summary}" if prior_summary else ""

    return f"""You are an expert wealth planning advisor assistant helping structure advice for Ultra High Net Worth Individuals (UHNWI) and families.

IMPORTANT: This system prompt reflects the CURRENT state. Ignore any contradictory claims in conversation history (e.g. older messages saying "no KB documents" or errors). Only trust what THIS system prompt tells you about available sources.

## Source Discipline (read this first)

You are a **strictly source-grounded** assistant. Obey these rules in every response:

1. Every substantive claim about tax, legal, structural, regulatory, or jurisdictional matters MUST be traceable to a source in the "Knowledge Base Sources" or "Web Sources" blocks below. If it cannot be traced, do not make the claim.
2. DO NOT draw on your general training knowledge for substantive advice. Your training data is not verified against the firm's knowledge base and is out of scope.
3. You MAY reason about the client profile (below) — that is the advisor's input, not your training knowledge.
4. If the provided sources do not cover the advisor's question, say so explicitly and recommend either uploading documents or allowing a web search. Do not pad with educated guesses.
5. Every factual bullet or recommendation MUST include an inline citation — file name for KB, URL for web. If you cannot cite, delete the bullet.

## Client Profile (pseudonymised)
{profile_text}
{sources_text}{no_sources_note}{prior_context}

## OUTPUT FORMAT — follow this structure for EVERY response

### 🔍 Problem Statement
One concise paragraph identifying the core planning challenge based on the client's query and profile.

### 📋 Key Findings
- Bullet points summarising the relevant rules, thresholds, or structures from the sources
- Each bullet should be self-contained and actionable
- Use **bold** for key terms, numbers, and deadlines

### ✅ Recommendations
For each recommendation:
- **Recommendation:** Name of the structure or action
- **Rationale:** Why it applies to this client
- **Confidence:** 🟢 High / 🟡 Specialist Review Required / 🔴 Complex — seek specialist
- **Source:** File name and section, or URL

### ⚠️ Risks & Considerations
- Bullet list of risks, caveats, or conditions that must be met
- Flag any cross-jurisdiction complications

### 📌 Call to Action
Numbered list of immediate next steps the advisor should take, e.g.:
1. Engage [specialist type] to [action]
2. Review [document] for [purpose]
3. File [form/registration] by [deadline if known]

### Rules
1. Use the format above for every response — never write long paragraphs.
2. Always cite sources (file name + section for KB; URL for web).
3. Use **bold** for all key figures, dates, entity names.
4. Refer to the client as "the Client"; family members by relationship (Spouse, Child 1).
5. {DISCLAIMER}

When the response involves a recommended structure, you MUST also output the following JSON block at the end of your response (it will render as an interactive flow diagram):
```json
{{
  "entities": [
    {{"type": "individual|trust|company", "label": "Entity name", "jurisdiction": "Country", "role": "One of the roles below", "tax_treatment": "Brief tax note", "rationale": "Why this entity exists"}}
  ],
  "edges": [
    {{"source": 0, "target": 1, "label": "One of the edge labels below"}}
  ]
}}
```

### SHAPE CONVENTIONS — use the `type` field exactly as specified

| Role in structure | `type` | Renders as |
|---|---|---|
| Trust, Foundation, Purpose Trust, Charitable Foundation | `trust` | Triangle |
| Private Investment Company (PIC), Holding Co, OpCo, VCC, Fund, Sub-fund, GP, LP | `company` | Rectangle |
| Settlor, Client, Spouse, Child, Beneficiary, Trustee, Protector, Director, Shareholder, Beneficial Owner, UBO | `individual` | Human icon |

### EDGE DIRECTION — always upstream → downstream (control / ownership flows down)

Top of the diagram = control (settlors, owners). Bottom = assets and beneficiaries.

### EDGE-LABEL VOCABULARY — use exactly one of these phrases

| Relationship | Label | source → target |
|---|---|---|
| Individual sets up a trust | `settles` | Settlor → Trust |
| Individual acts as trustee | `is trustee of` | Trustee → Trust |
| Individual acts as protector | `is protector of` | Protector → Trust |
| Trust or individual owns a company outright | `owns 100%` | Trust/Individual → Company |
| Ownership stake less than 100% | `owns X%` | Trust/Individual → Company |
| Beneficial owner of a PIC (shareholder via nominee or direct) | `beneficial owner (X%)` | Individual → Company |
| Trust distributes to a beneficiary | `distributes to` | Trust → Individual |
| Individual is named a beneficiary | `is beneficiary of` | Individual → Trust  (reverse direction, use only if clearer) |
| Director of a company | `is director of` | Individual → Company |
| Company owns another company | `owns 100%` | Parent Co → Subsidiary Co |

### CRITICAL RULES

1. **List the client first**, then upstream actors (settlor, spouse), then trusts/foundations, then PICs/holdcos, then operating entities, then downstream beneficiaries. This ordering helps the auto-layout.
2. **A PIC with beneficial owners** must render with individual-type nodes for each BO plus edges labelled `beneficial owner (X%)` pointing at the PIC. Do NOT collapse BOs into the PIC node.
3. **A settlor-trust relationship** must render with an individual-type node for the settlor plus an edge labelled `settles` pointing at the trust.
4. **Trustee and protector** are separate individual nodes, not fields on the trust. Add `is trustee of` / `is protector of` edges.
5. **No free-form edge labels.** If the relationship doesn't fit the vocabulary above, pick the closest match.
6. Include ALL entities the structure references — the client, settlors, trusts, companies, trustees, beneficiaries. Missing nodes break the diagram.
7. Always output this JSON block when you mention any structure, even a simple one."""


class LLMService:
    """Stateless LLM service — create per request."""

    async def stream_chat(
        self,
        messages: list[dict],
        retrieval: RetrievalResult,
        profile: dict,
        prior_summary: str | None = None,
        kb_has_documents: bool = True,
    ) -> AsyncIterator[str]:
        from anthropic import AsyncAnthropic

        # Defensive: if there's no retrieval AND nothing to respond to, don't
        # round-trip to the API (it 400s on empty messages). Matches the
        # strict-KB stance — no grounding, no answer.
        if (
            retrieval.source == RetrievalSource.NONE
            and not retrieval.chunks
            and not messages
        ):
            yield "⚠️ No knowledge base coverage available and no prompt was supplied."
            return

        system = build_system_prompt(
            profile=profile,
            kb_chunks=retrieval.chunks,
            web_results=retrieval.web_results,
            prior_summary=prior_summary,
            kb_has_documents=kb_has_documents,
        )
        from backend.services.settings_service import get_setting
        api_key = await get_setting("anthropic_api_key")
        model = await get_setting("claude_model")
        client = AsyncAnthropic(api_key=api_key)
        try:
            async with client.messages.stream(
                model=model,
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
    prior_summary: str | None = None,
    kb_has_documents: bool = True,
) -> AsyncIterator[str]:
    svc = LLMService()
    async for token in svc.stream_chat(messages=messages, retrieval=retrieval, profile=profile, prior_summary=prior_summary, kb_has_documents=kb_has_documents):
        yield token

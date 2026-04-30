import json
import logging
from typing import Any, AsyncIterator
from backend.config import settings
from backend.services.rag_service import RetrievalResult, RetrievalSource

logger = logging.getLogger(__name__)


# ── Tool: structure diagram ──────────────────────────────────────
#
# The LLM emits structure diagrams via this tool, never via prose JSON. The
# input schema IS the contract; the tool's `input` matches what
# DiagramService.build_diagram_data expects (entities + edges).

DIAGRAM_TOOL: dict = {
    "name": "record_structure_diagram",
    "description": (
        "Record the recommended legal/financial structure as a diagram for "
        "the advisor's Structure tab. **You MUST first write the full markdown "
        "response (Problem Statement → Key Findings → Recommendations → Risks "
        "& Considerations → Call to Action), and only AFTER all five sections "
        "are complete may you invoke this tool.** A response that contains "
        "this tool call without a preceding markdown narrative is invalid and "
        "will be rejected. The tool supplements the markdown — it never "
        "replaces it. Call this tool ONCE per response, ONLY when you propose "
        "a structure (a single trust, a PIC, or a multi-entity arrangement). "
        "All narrative — rationale, citations, risks — belongs in the markdown "
        "response, NOT inside this tool call. Do not invoke the tool for "
        "purely informational answers where no structure is being proposed."
    ),
    "input_schema": {
        "type": "object",
        "required": ["entities", "edges"],
        "properties": {
            "entities": {
                "type": "array",
                "description": (
                    "Every entity the structure references — client, settlors, "
                    "spouse, children, trustees, protectors, beneficiaries, "
                    "trusts/foundations, holdcos, opcos, funds. Order is "
                    "load-bearing for layout: client first, then upstream "
                    "actors (settlor, spouse), then trusts, then PICs/holdcos, "
                    "then operating entities, then beneficiaries."
                ),
                "items": {
                    "type": "object",
                    "required": ["type", "label", "jurisdiction", "role"],
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["individual", "trust", "company"],
                            "description": (
                                "individual = settlor/client/spouse/child/"
                                "beneficiary/trustee/protector/director/UBO. "
                                "trust = trust/foundation/purpose-trust/"
                                "charitable-foundation. "
                                "company = PIC/HoldCo/OpCo/VCC/fund/sub-fund/"
                                "GP/LP."
                            ),
                        },
                        "label": {
                            "type": "string",
                            "description": (
                                "Display name. Use generic titles for "
                                "individuals ('The Client', 'Spouse', 'Child 1') "
                                "rather than personal names."
                            ),
                        },
                        "jurisdiction": {
                            "type": "string",
                            "description": "Country of formation, residence, or incorporation.",
                        },
                        "role": {
                            "type": "string",
                            "description": (
                                "Functional role. Examples: Settlor, Trustee, "
                                "Protector, Beneficiary, Director, Shareholder, "
                                "UBO, Trust, PIC, HoldCo, OpCo, Fund, GP, LP."
                            ),
                        },
                        "tax_treatment": {
                            "type": "string",
                            "description": "Optional brief tax note relevant to this entity.",
                        },
                        "rationale": {
                            "type": "string",
                            "description": "Optional one-sentence note on why this entity is in the structure.",
                        },
                    },
                },
            },
            "edges": {
                "type": "array",
                "description": (
                    "Relationships between entities, indexed into the entities "
                    "array. Direction is upstream → downstream (control / "
                    "ownership flows down). Use ONLY canonical labels: "
                    "'settles', 'is trustee of', 'is protector of', 'owns 100%', "
                    "'owns X%' (substitute the real percentage), "
                    "'beneficial owner (X%)', 'distributes to', "
                    "'is beneficiary of', 'is director of'."
                ),
                "items": {
                    "type": "object",
                    "required": ["source", "target", "label"],
                    "properties": {
                        "source": {
                            "type": "integer",
                            "description": "Index into entities[] of the source entity (e.g. settlor, parent company).",
                        },
                        "target": {
                            "type": "integer",
                            "description": "Index into entities[] of the target entity (e.g. trust, subsidiary).",
                        },
                        "label": {
                            "type": "string",
                            "description": "Canonical relationship label.",
                        },
                    },
                },
            },
        },
    },
}


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


def build_system_prompt(
    profile: dict,
    kb_chunks: list[dict],
    web_results: list,
    prior_summary: str | None = None,
    kb_has_documents: bool = True,
) -> str:
    sources_text = ""
    if kb_chunks:
        sources_text += "\n\n## Knowledge Base Sources\n"
        # Header listing every retrieved file by name. The model previously
        # claimed "no article on Section 13U exists" while that very article
        # (fund-tax-incentives.md) was sitting in this Sources block. Spelling
        # out the file list up front makes the existence check explicit.
        seen_files: list[str] = []
        for c in kb_chunks:
            sf = c.get("source_file") or "KB"
            if sf not in seen_files:
                seen_files.append(sf)
        sources_text += (
            "Articles retrieved for this query (cite by filename):\n"
            + "\n".join(f"  - {f}" for f in seen_files)
            + "\n"
        )
        for c in kb_chunks:
            sources_text += f"\n[Source: {c.get('source_file', 'KB')} | {c.get('jurisdiction', '')} | {c.get('topic', '')}]\n{c['text']}\n"
    if web_results:
        sources_text += "\n\n## Web Sources\n"
        for w in web_results:
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
6. **Coverage claims must reflect what is actually in the Sources block.** Do NOT say "the knowledge base does not contain a dedicated article on X" or list specific files as not covering X unless you have verified by reading the Sources block above. The list of retrieved articles is enumerated at the top of the Knowledge Base Sources section — refer to that list before making any "not in KB" statement. If an article IS in the list, treat it as available coverage; if you find it under-detailed for the question, say "the retrieved article on X covers Y but does not drill into Z" — never "no article on X exists." If the list is empty, only then may you claim no KB coverage.

## Client Profile (pseudonymised)
{profile_text}
{sources_text}{no_sources_note}{prior_context}

## OUTPUT FORMAT — follow this structure for EVERY response

**Mandatory:** every response MUST include the five markdown sections below as TEXT before/alongside any `record_structure_diagram` tool call. The tool call is supplemental — it never replaces the markdown response. If you have nothing to say in a section (e.g. no risks identified), write a single bullet stating that — do not omit the section. A reply that contains only a tool call and no narrative is incomplete and will be rejected.

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

## Diagram emission

When you propose a recommended structure (any structure that involves entities and relationships — a trust, a PIC, a multi-tier holding arrangement), call the `record_structure_diagram` tool with the full set of entities and edges. The tool's input schema is the canonical format — do NOT emit JSON in the markdown body. Narrative explanations (rationale, jurisdictional notes, citations) belong in the Recommendations section above; the tool input is structural metadata only."""


# ── Streaming with tool support ──────────────────────────────────


class LLMService:
    """Stateless LLM service — create per request."""

    async def stream_chat(
        self,
        messages: list[dict],
        retrieval: RetrievalResult,
        profile: dict,
        prior_summary: str | None = None,
        kb_has_documents: bool = True,
    ) -> AsyncIterator[dict]:
        """Stream advisor reply.

        Yields event dicts:
          {"type": "text", "text": "..."}      — for each text delta
          {"type": "diagram", "diagram": {...}} — once, if the LLM calls the
                                                  record_structure_diagram tool

        Callers must demux on `type` rather than concatenating all values.
        """
        from anthropic import AsyncAnthropic

        # Defensive: if there's no retrieval AND nothing to respond to, don't
        # round-trip to the API (it 400s on empty messages).
        if (
            retrieval.source == RetrievalSource.NONE
            and not retrieval.chunks
            and not messages
        ):
            yield {"type": "text", "text": "⚠️ No knowledge base coverage available and no prompt was supplied."}
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
                tools=[DIAGRAM_TOOL],
            ) as stream:
                # text_stream only yields text-block deltas, not tool_use
                async for text in stream.text_stream:
                    yield {"type": "text", "text": text}
                # After streaming completes, walk content blocks for tool_use
                final = await stream.get_final_message()
                for block in final.content:
                    if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == DIAGRAM_TOOL["name"]:
                        diagram_input: Any = block.input
                        if isinstance(diagram_input, dict) and "entities" in diagram_input:
                            yield {"type": "diagram", "diagram": diagram_input}
        except Exception as e:
            logger.warning("LLM streaming failed: %s", e, exc_info=True)
            yield {"type": "text", "text": "\n\n[Error: Unable to complete the response. Please try again or contact support.]"}


# Module-level convenience function (wraps LLMService)
async def stream_chat(
    messages: list[dict],
    retrieval: RetrievalResult,
    profile: dict,
    prior_summary: str | None = None,
    kb_has_documents: bool = True,
) -> AsyncIterator[dict]:
    svc = LLMService()
    async for event in svc.stream_chat(
        messages=messages,
        retrieval=retrieval,
        profile=profile,
        prior_summary=prior_summary,
        kb_has_documents=kb_has_documents,
    ):
        yield event

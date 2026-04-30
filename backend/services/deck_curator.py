"""Claude-powered deck curator.

Reads a case's chat history + profile + diagram and asks Claude (Sonnet 4.6
by default) to produce a slide spec JSON conforming to the LC PowerPoint
skill (lighthouse-canton-ppt). The brand rules — vendored under
backend/skills/lighthouse-canton-ppt/SKILL.md — are inlined into the system
prompt with prompt caching so we only pay the read cost once per server
boot.

The model is forced to call a `compose_deck` tool whose input_schema
constrains the output to the catalogue of layouts the pptx_service knows
how to render. This avoids hallucinated layout names and ensures every
spec round-trips through the renderer cleanly.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic

from backend.services.settings_service import get_setting

logger = logging.getLogger(__name__)

SKILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "lighthouse-canton-ppt"

# Layouts that pptx_service.py currently knows how to render. The agent is
# constrained to this set — extend pptx_service first if you want the agent
# to reach for more variety.
ALLOWED_LAYOUTS = ["cover", "06", "07", "13", "structure"]

# JSON schema that gates the model's output. We use a tool so the model is
# *forced* into structured output (vs free-form prose JSON which is fragile).
COMPOSE_DECK_TOOL = {
    "name": "compose_deck",
    "description": (
        "Compose the slide deck spec for this advisory case. Call this tool "
        "exactly once with the complete spec. The Disclaimer and Offices "
        "slides are auto-appended by the renderer — do NOT include them in "
        "your spec."
    ),
    "input_schema": {
        "type": "object",
        "required": ["slides"],
        "properties": {
            "slides": {
                "type": "array",
                "minItems": 4,
                "maxItems": 12,
                "description": (
                    "Ordered list of slides. Aim for 6-10 slides total: a "
                    "cover, a profile snapshot, 3-6 analysis slides (using "
                    "layout 06 for parallel pillars or 07 for a single big "
                    "statement), one structure slide if a diagram exists, "
                    "and a closing recommendation."
                ),
                "items": {
                    "type": "object",
                    "required": ["layout"],
                    "properties": {
                        "layout": {
                            "type": "string",
                            "enum": ALLOWED_LAYOUTS,
                            "description": (
                                "cover = layout 02 (cover-alt, typography only, "
                                "use for slide 1). "
                                "06 = two-column pillars (eyebrow + serif title "
                                "+ N rows of label/red-rule/body — the hallmark "
                                "LC layout, ideal for 3-4 parallel findings). "
                                "07 = title + lede + red rule (one big serif "
                                "statement plus a supporting paragraph; ideal "
                                "for the recommendation or call-to-action). "
                                "13 = data table (label/value rows, use for "
                                "the client profile). "
                                "structure = embed the structure diagram PNG."
                            ),
                        },
                        "chapter": {
                            "type": "string",
                            "description": (
                                "Optional chapter-tab label shown at the top "
                                "of the slide (e.g. 'Advisory analysis', "
                                "'Client', 'Recommendation')."
                            ),
                        },
                        "eyebrow": {
                            "type": "string",
                            "description": (
                                "Small uppercase red label above the title "
                                "(e.g. 'Key findings', 'Recommendation'). "
                                "Sentence case for the value; renderer "
                                "uppercases it."
                            ),
                        },
                        "title": {
                            "type": "string",
                            "description": (
                                "Big serif slide title in sentence case, "
                                "often ending in a period. One clause."
                            ),
                        },
                        "lede": {
                            "type": "string",
                            "description": (
                                "Supporting paragraph below the title for "
                                "layout 07. 2-4 sentences."
                            ),
                        },
                        "rows": {
                            "type": "array",
                            "description": (
                                "For layout 06 (pillars): each row has "
                                "{label, body}. For layout 13 (table): "
                                "{label, value}. Aim for 3-5 rows."
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "label": {"type": "string"},
                                    "body": {"type": "string"},
                                    "value": {"type": "string"},
                                },
                            },
                        },
                        "client_name": {"type": "string"},
                        "subtitle": {"type": "string"},
                    },
                },
            },
        },
    },
}


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _build_static_system_block() -> str:
    """Static brand context — SKILL.md + key excerpts. Cacheable."""
    skill_md = _read(SKILL_DIR / "SKILL.md")
    return (
        "You are the Lighthouse Canton wealth-planning deck curator. Your job "
        "is to take a case's chat-history analysis and turn it into an editorial "
        "slide spec for an editable PowerPoint deck. The renderer is "
        "deterministic; your editorial choices (what's worth a slide, what's "
        "a callout, how to phrase the title) shape the output.\n\n"
        "You MUST follow the Lighthouse Canton brand contract below. Reproduced "
        "verbatim from the lighthouse-canton-ppt skill:\n\n"
        "=== SKILL.md ===\n" + skill_md + "\n=== end SKILL.md ===\n\n"
        "Concrete rules for THIS task:\n"
        "1. Output via the compose_deck tool ONLY. Do not write prose.\n"
        "2. Slide 1 is always layout 'cover' with the client_name set.\n"
        "3. Slide 2 should be a layout 13 (data table) with the client profile.\n"
        "4. Use layout 06 (pillars) for parallel findings or recommendations — "
        "ideal for 3-4 distinct pillars/themes.\n"
        "5. Use layout 07 (title + lede) for the headline recommendation or "
        "call-to-action — one big statement, one supporting paragraph.\n"
        "6. If a structure diagram exists in the input, include exactly ONE "
        "'structure' slide near the end (before the recommendation slide).\n"
        "7. Do NOT include disclaimer or offices slides — the renderer "
        "auto-appends those verbatim from the canonical deck.\n"
        "8. Titles are sentence case, one clause, often ending in a period. "
        "No exclamation marks, no question marks, no all-caps.\n"
        "9. Eyebrows are short (2-4 words). Sentence case; renderer uppercases.\n"
        "10. Body text per row should be 1-2 sentences, ~30-60 words. The "
        "renderer's column is wide; let body lines breathe.\n"
        "11. Drop secondary detail. A regulator-grade deck is sparse; if a "
        "fact didn't come up in the chat, it doesn't belong on a slide.\n"
        "12. Aim for 6-10 slides total (excluding auto-disclaimer + offices)."
    )


def _build_user_payload(
    *,
    client_name: str,
    profile: dict,
    chat_history: list[dict],
    diagram: dict | None,
) -> str:
    """Per-case dynamic content — assembled into a single user message."""
    lines: list[str] = []
    lines.append(f"# Case: {client_name}\n")

    lines.append("## Client profile")
    objectives_raw = profile.get("objectives") or "[]"
    try:
        objectives = json.loads(objectives_raw) if isinstance(objectives_raw, str) else objectives_raw
    except (json.JSONDecodeError, ValueError):
        objectives = []
    objectives_str = ", ".join(str(o) for o in objectives) if objectives else "—"
    lines.append(f"- Nationality: {profile.get('nationality') or '—'}")
    lines.append(f"- Domicile: {profile.get('domicile') or '—'}")
    lines.append(f"- Tax residency: {profile.get('tax_residency') or '—'}")
    lines.append(f"- Objectives: {objectives_str}")
    lines.append("")

    if diagram and diagram.get("nodes"):
        lines.append("## Structure diagram (already saved in the case)")
        lines.append(
            f"{len(diagram.get('nodes', []))} entities, "
            f"{len(diagram.get('edges', []))} relationships. The renderer "
            "will embed a high-resolution rendering of this diagram on a "
            "dedicated structure slide — you do not need to describe it in "
            "prose. Just include exactly one slide with layout='structure'."
        )
        lines.append("")
        lines.append("Entities:")
        for n in diagram.get("nodes", []):
            d = n.get("data") or {}
            lines.append(
                f"- {d.get('label','?')} ({n.get('type','?')}) — "
                f"{d.get('jurisdiction','?')} · {d.get('role','?')}"
            )
        lines.append("")

    lines.append("## Advisory chat history")
    lines.append(
        "The advisor's conversation with the AI assistant. Pull the editorial "
        "substance from these messages; ignore meta-conversation about how "
        "the assistant works."
    )
    lines.append("")
    for msg in chat_history:
        role = msg.get("role", "?")
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"### {role.upper()}")
        lines.append(content)
        lines.append("")

    lines.append(
        "## Your task\n"
        "Compose the deck via the compose_deck tool. Aim for 6-10 slides. "
        "Lead with cover + profile, then a small set of analysis slides "
        "drawing the most salient findings/recommendations from the chat, "
        "then the structure slide (if a diagram exists), then a closing "
        "recommendation slide (layout 07)."
    )
    return "\n".join(lines)


async def curate_deck(
    *,
    client_name: str,
    profile: dict,
    chat_history: list[dict],
    diagram: dict | None,
) -> dict:
    """Call Claude to produce a slide spec. Returns {slides: [...]}.

    chat_history items are {role: 'user'|'assistant', content: str}. Profile
    is the dict pulled from client_profiles. diagram is {nodes, edges} or
    None.
    """
    api_key = await get_setting("anthropic_api_key")
    model = (await get_setting("claude_model")) or "claude-sonnet-4-6"

    static_block = _build_static_system_block()
    user_payload = _build_user_payload(
        client_name=client_name,
        profile=profile,
        chat_history=chat_history,
        diagram=diagram,
    )

    client = AsyncAnthropic(api_key=api_key)
    response = await client.messages.create(
        model=model,
        max_tokens=8000,
        system=[
            # Brand rules — static across cases. Cached for 5 min after first
            # call so subsequent generations on the same server hit a warm
            # cache and only pay for the dynamic user payload.
            {
                "type": "text",
                "text": static_block,
                "cache_control": {"type": "ephemeral"},
            },
        ],
        tools=[COMPOSE_DECK_TOOL],
        tool_choice={"type": "tool", "name": "compose_deck"},
        messages=[{"role": "user", "content": user_payload}],
    )

    # Extract the tool_use block — given tool_choice it must be present.
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == "compose_deck":
            spec = block.input
            if isinstance(spec, dict) and "slides" in spec:
                # Stamp the cover with client_name if the model forgot to.
                slides = spec["slides"]
                if slides and (slides[0].get("layout") or "").lower() == "cover":
                    slides[0].setdefault("client_name", client_name)
                logger.info(
                    "Curator produced %d slides for %s (cache: in=%s, read=%s)",
                    len(slides), client_name,
                    getattr(response.usage, "cache_creation_input_tokens", None),
                    getattr(response.usage, "cache_read_input_tokens", None),
                )
                return spec

    raise RuntimeError(
        f"Curator did not produce a compose_deck tool call; got "
        f"{[getattr(b, 'type', None) for b in response.content]}"
    )


def hash_inputs(*, profile: dict, chat_history: list[dict], diagram: dict | None) -> str:
    """Stable hash of the curator's inputs. Used to detect drift — if the
    chat or diagram changes the UI shows a 'regenerate' affordance."""
    h = hashlib.sha256()
    h.update(json.dumps(profile, sort_keys=True).encode())
    for m in chat_history:
        h.update((m.get("role") or "").encode())
        h.update((m.get("content") or "").encode())
    if diagram:
        h.update(json.dumps(diagram.get("nodes") or [], sort_keys=True).encode())
        h.update(json.dumps(diagram.get("edges") or [], sort_keys=True).encode())
    return h.hexdigest()

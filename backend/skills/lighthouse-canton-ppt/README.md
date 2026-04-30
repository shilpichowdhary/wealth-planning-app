# Lighthouse Canton — PowerPoint Skill (for Claude Code)

A self-contained Claude Code skill that teaches Claude how to produce on-brand Lighthouse Canton 1920×1080 PowerPoint decks. Drop this folder into Claude Code's skills directory and Claude will auto-load it whenever you ask for an LC deck, pitch, presentation, or 16:9 deliverable.

## Install

Claude Code skills live in **`~/.claude/skills/`** (user-level, available to every project) or **`.claude/skills/`** (project-level, scoped to one repo).

```bash
# user-level — every project on this machine
mkdir -p ~/.claude/skills/
cp -r lighthouse-canton-ppt ~/.claude/skills/

# OR project-level — just this codebase
mkdir -p .claude/skills/
cp -r lighthouse-canton-ppt .claude/skills/
```

That's it. Restart Claude Code (or start a new session) and the skill is live. Claude Code reads the YAML frontmatter at the top of `SKILL.md` and invokes the skill automatically when your request matches the description ("LC deck", "Lighthouse Canton presentation", "investor slides for LC", etc).

## What's in the box

```
SKILL.md                                  ← instructions Claude follows
README.md                                 ← this file
templates/
  blank-deck-template.html                ← 15 blank layouts to fork for new content
  canonical-corporate-deck.html           ← verbatim source of truth for LC-about-LC copy
assets/
  tokens.css                              ← all design tokens
  ppt-template.css                        ← shared 1920×1080 slide styles
  deck-stage.js                           ← <deck-stage> web component
  fonts/                                  ← Frank Ruhl Libre + Public Sans (variable TTF)
  logo-red.png  logo-black.png  logo-white.png
  logo-wordmark-red.png  logo-wordmark.svg
```

## How to use it

Just ask in plain English. Claude Code matches your prompt against the skill description and pulls in `SKILL.md` automatically.

Examples:
- *"Build me a 12-slide LC capabilities deck for institutional investors."*
- *"Make an LC quarterly outlook for Q3 2026 — I'll paste the content."*
- *"Add a section divider and three new content slides to this LC deck."*

For LC-about-LC content (history, AUM, offices, awards), Claude will lift copy verbatim from `templates/canonical-corporate-deck.html` — never paraphrasing or fabricating figures.

For new content, Claude will scaffold from `templates/blank-deck-template.html` and stick to the 15-layout catalogue.

## Exporting to .pptx

The skill outputs HTML decks. To convert to PowerPoint, see **§6 of `SKILL.md`** — three paths covered:

1. **Print → PDF → PowerPoint** (image-per-slide, fastest, not editable).
2. **`python-pptx`** (native editable shapes, requires hand-translation of each layout — sample code in SKILL.md).
3. **`libreoffice --headless --convert-to pptx`** (image-per-slide via PDF).

## Brand contract — the five rules

Every LC deck must obey:

1. **Frank Ruhl Libre Light (300)** for titles, labels, numerals, quotes.
2. **Public Sans 400/500** for body, captions, table data.
3. The only red is **`#E50025`** — used as the signature 3–4 px vertical rule. Never as a fill behind text.
4. Backgrounds are **white**. Section dividers are **solid black** with a giant red serif numeral.
5. **No gradients. No drop-shadows. No rounded containers. No emoji. No decorative icons.**

The two mandatory slides for any external deck:
- **Disclaimer** (layout 04) — verbatim from canonical deck.
- **Offices / Contact** (layout 15) — verbatim, as the closing slide.

## Updating the skill

When the design system changes (new layouts, updated tokens, refreshed canonical copy), replace the relevant files in `assets/` or `templates/` and re-sync the skill folder. `SKILL.md` itself rarely needs editing — it's a stable contract.

## Tagline

> *"Where Insight Meets Opportunity."* — used at most once per deck.

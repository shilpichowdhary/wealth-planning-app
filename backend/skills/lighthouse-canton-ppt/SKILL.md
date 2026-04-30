---
name: lighthouse-canton-ppt
description: Create on-brand Lighthouse Canton PowerPoint decks (1920×1080, 16:9). Use whenever the user asks for an LC presentation, slides, pitch deck, investor deck, quarterly review, capabilities deck, or any 16:9 slide deliverable for Lighthouse Canton. Enforces the LC brand contract — Frank Ruhl Libre Light + Public Sans, Agile Red (#E50025) used only as the signature 3–4 px vertical rule, white/black backgrounds, no gradients/shadows/rounded containers.
---

# Lighthouse Canton — PowerPoint Skill

You are producing a 1920×1080 slide deck on the Lighthouse Canton brand. This skill bundles the design tokens, slide CSS, layout catalogue, and canonical corporate copy. Follow it; do not invent a new design.

---

## 0. THE MOST IMPORTANT RULE — Canonical content

`templates/canonical-corporate-deck.html` is the **single source of truth** for every factual statement about Lighthouse Canton.

When the user asks for a deck (or any subset of slides) **about Lighthouse Canton itself** — history, offices, AUM, awards, leadership, regulatory status, funds, investment philosophy, LC Vantage, or any other LC topic — you **MUST**:

1. **Open `templates/canonical-corporate-deck.html`** and lift copy **verbatim**. Do not paraphrase. Do not shorten.
2. **Never make up** AUM figures, founding dates, office addresses, milestone years, award citations, fund names, or investor names. They already exist in the canonical deck — use them exactly.
3. If the user asks for content **not** in the canonical deck, ask them for it. Do not fabricate.

### When the content IS new (not LC-about-LC)

Compose fresh slides using the layout catalogue in §3 and the blank template at `templates/blank-deck-template.html`. The user authors the words; you style.

**In every external deck, two slides are mandatory:**
- **Disclaimer** — verbatim from the canonical deck (slide 03 / layout 04).
- **Offices / Contact** — verbatim from the canonical deck (closing slide / layout 15).

---

## 1. Files in this skill

```
SKILL.md                                  ← this file
README.md                                 ← human overview
templates/
  blank-deck-template.html                ← 15 blank layouts — copy this for new content
  canonical-corporate-deck.html           ← the LC-about-LC source of truth (verbatim)
assets/
  tokens.css                              ← all design tokens (colour, type, spacing, motion)
  ppt-template.css                        ← shared 1920×1080 slide styles
  deck-stage.js                           ← <deck-stage> web component (scaling, nav, print)
  fonts/
    FrankRuhlLibre-VariableFont_wght.ttf
    PublicSans-VariableFont_wght.ttf
    PublicSans-Italic-VariableFont_wght.ttf
  logo-red.png  logo-black.png  logo-white.png
  logo-wordmark-red.png  logo-wordmark.svg
```

Canvas is **1920 × 1080** (16:9). Content safe zone is **120 px** from each edge.

---

## 2. Brand contract — five non-negotiables

| # | Rule |
|---|---|
| **1** | **Frank Ruhl Libre Light (300)** for titles, labels, numerals, quotes. Never Regular / Bold / Black. |
| **2** | **Public Sans 400/500** for body, captions, table data, eyebrows. |
| **3** | The only red is **`#E50025`**, used almost exclusively as a **3–4 px vertical rule** between a serif label and its sans-serif description. This is the signature visual device. Also acceptable: a thin red underline under a region name, a 3 px top border on a contact block, a single italic accent word. Never as a fill behind text, never as an ALL-CAPS banner. |
| **4** | Backgrounds are **white**. Section dividers are **solid black** (with a giant red serif numeral). Photos are sparing, soft, slightly desaturated. |
| **5** | **No gradients. No drop-shadows. No rounded containers. No emoji. No decorative icons. No coloured fills behind paragraphs.** |

Violating any of these means the deck is off-brand. If a user asks for something that breaks them (e.g. "make it more colourful", "add some icons"), explain the constraint and offer an on-brand alternative.

---

## 3. Layout catalogue (15 layouts)

Pick one of these for every slide. Don't invent new layouts. They live in `templates/blank-deck-template.html` — copy the section markup and replace placeholders.

| # | Layout | Use when you need to… |
|---|---|---|
| **01** | Cover — serif title + small red wordmark + photo | Open any deck |
| **02** | Cover (Alt) — typography only, white bg | Open a formal / financial deck |
| **03** | Table of Contents | Agenda slide, one per deck |
| **04** | **Disclaimer (MANDATORY)** — two-column legal text | Must appear in every external deck |
| **05** | Section Divider — black bg, giant red numeral, serif chapter | Mark the start of a chapter |
| **06** | Two-column: serif label / red rule / sans body × 3 rows | 2–4 parallel pillars (the hallmark LC layout) |
| **07** | Title + lede + red vertical rule | One clear statement + support paragraph |
| **08** | Four-region grid | Four offices / categories / regions |
| **09** | Quote / Mission — two red-rule blocks | Mission + vision, or pull-quote |
| **10** | Two-column text with red rule between | Compare two balanced ideas |
| **11** | Image left / text right | Feature spot |
| **12** | Awards / logo grid | Awards, partners, press |
| **13** | Data table (tabular-nums) | Numbers / monthly returns |
| **14** | Three-column process (serif 01/02/03) | 3-step framework |
| **15** | **Offices / Contact (MANDATORY)** — multi-city grid + Thank you | Closing slide of every external deck |

---

## 4. Copy voice

- Titles in **sentence case**, one clause, often ending in a period.
- Eyebrows are small (14 px), serif or sans, letter-spaced 0.18em, red or black-80.
- Body **18–22 px**, 400-weight, max 56–64ch.
- Prefer specific figures ("USD 5B+ AUM", "Q1 2026") over vague adjectives like "leading", "innovative", "world-class".
- Use the tagline **"Where Insight Meets Opportunity"** once per deck, never more.

---

## 5. How to build a deck

### Case A — deck IS about Lighthouse Canton
1. Copy `templates/canonical-corporate-deck.html` to a new file (e.g. `LC Capabilities — Q2 2026.html`).
2. Delete slides not needed for the brief. **Never edit surviving copy** — it is canonical.
3. Keep slides 03 (Disclaimer) and 35 (Offices). They are mandatory.
4. Renumber footer page numbers after deletions.

### Case B — deck is net-new content supplied by the user
1. Copy `templates/blank-deck-template.html` to a new file named after the deck.
2. Replace each `<span class="placeholder">…</span>` with the user's copy. Remove the `placeholder` class.
3. **Insert the Disclaimer slide (layout 04)** — copy the `<section data-label="04 Disclaimer">…</section>` block verbatim from `templates/canonical-corporate-deck.html`.
4. **Insert the Offices slide (layout 15)** — copy the closing offices `<section>` verbatim from `templates/canonical-corporate-deck.html`.
5. Pick layouts from the §3 catalogue; do not invent new ones.
6. Keep the `<link rel="stylesheet" href="assets/tokens.css">` and `<link rel="stylesheet" href="assets/ppt-template.css">` references intact, plus `<script src="assets/deck-stage.js" defer></script>`.

### File scaffold for a new deck

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>[Deck title]</title>
  <link rel="stylesheet" href="assets/tokens.css" />
  <link rel="stylesheet" href="assets/ppt-template.css" />
  <script src="assets/deck-stage.js" defer></script>
</head>
<body>
  <deck-stage width="1920" height="1080">
    <!-- One <section data-label="..."> per slide. -->
  </deck-stage>
</body>
</html>
```

Place the new deck file at the **same level as the `assets/` and `templates/` folders** so the relative paths resolve.

---

## 6. Exporting to .pptx

The deck is HTML; you (or the user) need to convert it. Two reliable paths:

### 6a. Manual — Print to PDF, then PowerPoint
1. Open the HTML in Chrome → Cmd/Ctrl-P → **Save as PDF** (page size: 1920×1080 px → set custom paper size, or use "fit to page" with a 16:9 layout).
2. In PowerPoint: *Insert → New Slide → from PDF* (or import each PDF page as an image on a 16:9 slide). Each slide becomes a flat image — no native text editing.

### 6b. Programmatic — `python-pptx` (editable native shapes)
For an editable .pptx with native PowerPoint text boxes, use [`python-pptx`](https://python-pptx.readthedocs.io/). This requires you to translate each `<section>` into PowerPoint shapes by hand — but the result is fully editable.

Minimal example:

```python
from pptx import Presentation
from pptx.util import Emu, Pt
from pptx.dgm.color import RGBColor

# 1920 × 1080 px at 96 DPI → 20" × 11.25"
prs = Presentation()
prs.slide_width  = Emu(20    * 914400)   # 18288000
prs.slide_height = Emu(11.25 * 914400)   # 10287000

LC_RED   = RGBColor(0xE5, 0x00, 0x25)
LC_BLACK = RGBColor(0x00, 0x00, 0x00)

slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank

# Title — Frank Ruhl Libre Light, 88 px ≈ 66 pt
tx = slide.shapes.add_textbox(Emu(120 * 9525), Emu(380 * 9525),
                              Emu(820 * 9525), Emu(120 * 9525))
p = tx.text_frame.paragraphs[0]
run = p.add_run(); run.text = "Where Insight Meets Opportunity."
run.font.name = "Frank Ruhl Libre"; run.font.size = Pt(66)
run.font.bold = False  # Light is weight 300; PowerPoint maps to "Light"

# Red vertical rule — 3 px wide, ~140 px tall
from pptx.shapes.autoshape import MSO_SHAPE
rule = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
       Emu(640 * 9525), Emu(560 * 9525),
       Emu(3   * 9525), Emu(140 * 9525))
rule.fill.solid(); rule.fill.fore_color.rgb = LC_RED
rule.line.fill.background()

prs.save("LC Deck.pptx")
```

**Conversion factor:** 1 px ≈ 9525 EMU (at 96 DPI), 1 pt ≈ 12700 EMU. Frank Ruhl Libre and Public Sans must be **installed on the machine that opens the .pptx** for the design to render correctly — embed them via PowerPoint's *File → Options → Save → Embed fonts in the file* if you'll be sending the deck to someone who doesn't have them.

### 6c. Alternative — `LibreOffice --convert-to pptx`
If you have a PDF export of the HTML, you can run:
```bash
libreoffice --headless --convert-to pptx "LC Deck.pdf"
```
Each slide becomes one image on one PowerPoint slide. Not editable, but pixel-faithful.

---

## 7. Quick checklist before delivering

- [ ] Frank Ruhl Libre Light on every title; Public Sans on every body.
- [ ] Red `#E50025` appears only as 3–4 px vertical rules, region underlines, contact-block top borders, or a single italic accent word.
- [ ] No gradients, shadows, rounded corners, emoji, or icons.
- [ ] Disclaimer slide (layout 04) is present, verbatim.
- [ ] Offices / Contact slide (layout 15) is the last slide, verbatim.
- [ ] Page numbers are renumbered after any deletion.
- [ ] All photos came from `assets/approved-images/` (skill ships with logos only — ask the user for approved photos if a deck needs imagery; do not source stock or AI imagery).
- [ ] Tagline "Where Insight Meets Opportunity" used at most once.

---

## 8. When in doubt

- Slide is about LC → copy verbatim from `templates/canonical-corporate-deck.html`.
- Slide is new content → use `templates/blank-deck-template.html` and pick a layout from §3.
- Slide doesn't fit any of the 15 layouts → it probably shouldn't be in the deck. Ask the user before inventing one.
- User asks for an image but you have none → leave a placeholder `<div data-image-todo>` and tell the user which subject/division/region the photo should cover. Do not source your own.

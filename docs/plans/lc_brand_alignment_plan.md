# LC Brand Alignment — Wealth Planning App

**Status:** Phase A audit complete. Plan drafted. **No edits made.** Awaiting user decision on scope before Phase C execution.

**Audit date:** 2026-04-29
**Auditor:** Claude Code, applying `lc-brand-adoption` skill discipline
**Reference benchmarks:**
- DCMS canonical: `C:\Deployment\document_management_system\static\css\dcms.css`
- LC tokens: `C:\Deployment\document_management_system\static\css\tokens.css`
- Skill bundle: `C:\Users\lc-admin\.claude\skills\lc-brand-adoption\references\canonical_components.md`

---

## TL;DR

This project is **already partially LC-branded** (good fonts, LC palette, LCLogoMark component, eyebrow patterns). It's not a generic-Tailwind sweep job.

Two structural issues stand out:

1. **It's a dark-mode interpretation of LC**, while the canonical (DCMS, Webflow styleguide) is light-mode. Decision required: keep dark, or migrate to light.
2. **Crimson is over-used as a fill** — the v1 PRMS lesson the skill warns about. **18 solid `bg-lc-red` button fills** vs. the discipline of "ONE ghost-crimson CTA per app."

Plus one fully off-brand outlier: `admin/settings` page is still on the original Tailwind slate/blue/green palette (never got the LC sweep).

---

## Phase A — Audit findings

### A1. Token plumbing (good)

| Asset | Status |
|---|---|
| Tailwind LC tokens (`lc-red`, `lc-black`, `lc-white`, `lc-grey`) | ✅ defined in `tailwind.config.ts` |
| Frank Ruhl Libre + Public Sans loaded via `next/font/google` | ✅ in `app/layout.tsx` |
| LC brand mark component (`LCLogoMark`, `LCWordmark`) | ✅ in `components/brand/LCLogo.tsx` |
| Display-font weight 300 enforcement | ✅ via `.font-display { font-weight: 300 !important }` in `globals.css` |
| Frank Ruhl Libre at non-300 weights | ✅ never used (validated via grep) |
| Decorative emojis in UI | ✅ none found |
| Hardcoded foreign hex literals | ✅ none in TSX |

### A2. Dark-mode vs canonical light-mode (**strategic question**)

The DCMS canonical pattern uses:
- `background: var(--white)` (white #FFFFFF) on body and cards
- `color: var(--black)` for text
- `var(--white-smoke)` (#f6f5f3) for surface elevation
- Crimson **only** as accent (left-borders, eyebrow, brand mark, link hover)

This project uses:
- `bg-lc-black` (#000000) on body
- `bg-ink-900` (warm-grey at 4% opacity over black) for cards
- `text-lc-white` for body
- Same crimson palette but applied as **fills** on primary actions

**Both are coherent design systems**, but they diverge structurally. The Webflow LC styleguide is light-mode; this project's dark mode is an unsanctioned interpretation. Cross-product alignment (gotcha #18) suggests light-mode is the firm's house style.

### A3. Crimson fill audit (the v1 PRMS lesson)

**18 solid `bg-lc-red text-lc-white` button fills** across 9 files:

| File | Line | Element | Discipline assessment |
|---|---|---|---|
| `app/(auth)/login/page.tsx:157` | Sign in (password fallback) | **Allowed**: this is the one ghost-crimson CTA candidate |
| `app/(auth)/invite/[token]/page.tsx:135` | Set password & sign in | Legacy redemption flow (now SSO-only); panel can ghost |
| `app/(app)/admin/advisors/page.tsx:193` | "Add advisor" header button | Should be **ghost-dark** |
| `app/(app)/admin/advisors/page.tsx:250` | "Send invite" form submit | Should be ghost-dark |
| `app/(app)/admin/advisors/page.tsx:376` | **Mode tab active state** | Should be 2px crimson **border** + neutral fill |
| `app/(app)/dashboard/page.tsx:69` | "New case" header button | Should be ghost-dark |
| `app/(app)/dashboard/page.tsx:161` | "Create your first case" empty state CTA | Should be ghost-dark |
| `app/(app)/cases/new/page.tsx:132` | Step indicator dot | Acceptable (dot accent, not fill) |
| `app/(app)/cases/new/page.tsx:254,263` | Stepper navigation buttons | Should be ghost-dark |
| `app/(app)/cases/[caseId]/page.tsx:382` | Chat send button | Acceptable (icon-only action button) |
| `app/(app)/cases/[caseId]/page.tsx:483` | Modal CTA | Should be ghost-dark |
| `app/(app)/kb/documents/page.tsx:105` | "Upload" header button | Should be ghost-dark |
| `app/(app)/kb/upload/page.tsx:179` | Submit upload | Should be ghost-dark |
| `components/diagram/StructureDiagram.tsx:189` | Toolbar button | Acceptable (active state, contained UI) |

**Rule of thumb to apply:** ghost-crimson = brand-action moment (Login SSO). Every other button = ghost-dark (border + transparent → black on hover).

### A4. Status / categorical systems

The project's status semantics are **collapsed to monochrome** by design:
- `jade-500` token = #FFFFFF (white) — used for "active" status
- `ember-500` token = #E50025 (crimson) — used for error states
- `brass-X` tokens = crimson at varying alphas — used for "active" highlights, accent dots

This is internally coherent ("the brand has no green, so success renders as white") but **dilutes signal**:

- An "active" pill rendered in white reads identical to a generic neutral-white badge
- An "error" panel in `bg-ember-500/10 text-ember-500` is **the same crimson** as the primary brand mark; nothing distinguishes "this is a problem" from "this is the brand"

The canonical `lc-pill-breach` is `#fdecec / #8a1b1b` — a **muted brick red distinct from brand crimson** for exactly this reason. Worth restoring semantic distinction even within the dark theme (e.g., breach = `text-red-300 bg-red-950/30`).

**Off-limits per discipline:** the moment any clinical/severity domain is added (e.g. compliance breach, AML alert), these pills MUST be semantically distinct from brand crimson.

### A5. Off-brand outlier pages

Two pages were **never swept** during the v1 LC brand commit (`0111ea1 feat: LC brand…`):

1. **`app/(app)/admin/settings/page.tsx`** — fully on Tailwind generic palette:
   - `text-slate-900`, `bg-slate-200`, `bg-white` (light-mode chrome inside a dark-mode app)
   - `bg-blue-600 hover:bg-blue-700` Save button (off-brand blue fill)
   - `bg-green-100 text-green-700`, `bg-amber-100 text-amber-700` status pills (semantic, but using non-LC palette)
   - `focus:ring-blue-500` on inputs

2. **`app/users/microsoft/callback/page.tsx`** — `text-blue-400` link, `text-red-400` error text (Tailwind generic)

Both need full chrome rewrite to match the rest of the app.

### A6. Component patterns (recurring; pick canonicals)

| Pattern | Occurrences | Current state | Canonical I'd recommend |
|---|---|---|---|
| Primary action button | 18 | Solid `bg-lc-red` | **Ghost-dark**: `border border-lc-white/30 text-lc-white bg-transparent hover:bg-lc-white hover:text-lc-black` (dark-mode equivalent of canonical ghost-dark) |
| Single brand-action CTA | 1 (Sign in) | Solid `bg-lc-red` | **Ghost-crimson**: `border border-lc-red text-lc-red bg-transparent hover:bg-lc-red hover:text-lc-white` |
| Secondary / table-row action | ~15 | `text-ink-300 hover:text-lc-red` | ✅ Keep — already correct |
| Mode tab active state | 1 (advisors form) | Solid crimson fill | **2px crimson left/bottom border + ink-100 text** |
| Eyebrow text (uppercase tracked) | ~12 | `text-ink-400` (mostly), `text-lc-red` (a few) | ✅ Mix is correct (subdued for navigation, crimson for brand-accent moments) |
| Brand mark | 3 places | `LCLogoMark` component | ✅ Keep |
| Card hover | Dashboard cards | `hover:border-lc-red/50` | Acceptable (subtle 50% alpha accent on hover) |
| Status pill (active/inactive) | Dashboard, Advisors | `border-jade-500/40 bg-jade-500/10 text-jade-500` (collapses to white) | Keep monochrome OR restore semantic green for "active". User preference. |
| Error panel | 5 places | `border-ember-500/40 bg-ember-500/10 text-ember-500` (= crimson) | **Use muted red distinct from brand crimson** to preserve signal |

### A7. Infrastructure detection

| Check | Finding |
|---|---|
| Build mode | `next build` then `next start` (production). **Mandatory rebuild after any TSX change.** |
| Tailwind manifest cache | Not applicable (Tailwind via PostCSS, regenerated each build) |
| Self-hosted LC fonts | **Not present.** Project uses `next/font/google` for Frank Ruhl Libre + Public Sans. DCMS bundles the variable TTFs locally for offline work. Optional alignment. |
| Logout view | NextAuth `signOut()` (POST internally); no Django-style POST-form needed |
| `tailwind.config.ts` | Clean, single source of truth for LC tokens. No rogue `:root` overrides in `globals.css` to fight against |
| Global red-font usage | None — body text uses `text-ink-100`/`text-ink-300`. Only `text-lc-red` for brand accents and `text-ember-500` for errors |

---

## Phase B — Plan / scope options

Three scopes, increasing in size. **The user picks one.**

### Scope 1 — Surgical (≤30 min, lowest risk)

**Goal:** Fix the most visible discipline violations without changing the dark-mode aesthetic.

- [ ] Sweep solid `bg-lc-red` primary buttons → **ghost-dark** variant (white border + transparent fill, hover fills to white-on-black). Add a `.lc-btn-primary` and `.lc-btn-cta` CSS utility class in `globals.css` so the pattern is named.
- [ ] Reserve **one** ghost-crimson `.lc-btn-cta` for the Login SSO button only.
- [ ] Mode-tab active state: solid crimson → **2px crimson bottom border + ink-100 text**.
- [ ] **Sweep `admin/settings/page.tsx`** to LC palette (slate→ink, blue→ghost-dark, settings status pills retain semantic green/amber but in LC-friendly muted tones).
- [ ] Sweep `users/microsoft/callback/page.tsx` to LC palette.
- [ ] Distinguish error red (`ember-500`) from brand red — introduce a muted breach red token `#8a1b1b` / `#fdecec/30` so error UI ≠ brand mark.
- [ ] Optional: hide the legacy `/invite/[token]` redemption page (link no longer used) or rebrand to gracefully redirect to `/login`.

### Scope 2 — Disciplined dark mode (1–2h)

Scope 1 + bring this project's dark-mode interpretation up to "canonical-grade":

- [ ] Promote ghost-dark, ghost-crimson, mode-tab active, eyebrow, section-head into named CSS classes (`globals.css` `@layer components`). Avoid Tailwind-class duplication.
- [ ] Inventory and reduce `bg-lc-red/X` low-alpha tints — the 5%/10% crimson backgrounds are mostly unnecessary chrome (success panels can use `bg-ink-900` with a 1.5% crimson left border).
- [ ] Re-introduce **semantic status pills** (green/amber/red) at low saturation so they read against dark background but remain semantically distinct.
- [ ] Add a `.lc-section-head` class with the 28×2 crimson tick before section titles (canonical pattern; currently missing).
- [ ] Add focus-ring discipline: `focus:ring-2 focus:ring-lc-red/20` on inputs (already done in places — make uniform).

### Scope 3 — Migrate to canonical light mode (4–8h, structural)

Scope 1+2 + flip the entire app to the light-mode canonical:

- [ ] Body bg: `bg-lc-black` → `bg-lc-white` (or `bg-white-smoke` #f6f5f3 for app shell)
- [ ] Text: `text-lc-white` → `text-lc-black`
- [ ] Cards: `bg-ink-900 border-ink-800` → `bg-white border-grey-200`
- [ ] All `text-ink-*` warm-grey tints → `text-grey-*` neutrals
- [ ] Sidebar: dark → white with grey-200 bottom border (DCMS pattern)
- [ ] Login: keep the dark editorial column but the auth column flips to white-smoke
- [ ] Re-test every page (10 routes) for contrast after the flip

**Recommendation:** unless leadership has explicitly endorsed the dark-mode interpretation as a Wealth Planning sub-brand, **Scope 3 is the strategically correct choice** — it aligns this product with DCMS, brings cross-product visual consistency for advisors who use both, and matches the LC Webflow styleguide. But it is not a 30-minute job.

---

## What is preserved (off-limits)

- LC token names in `tailwind.config.ts` (`lc-red`, `lc-black`, `lc-white`, `lc-grey`) — keep
- LCLogoMark + LCWordmark component contracts — keep
- Frank Ruhl Libre @ weight 300 only — enforce as-is
- Public Sans for body — keep
- The `chip`, `prose-chat`, `wiki-prose` classes — keep
- Sidebar layout + `Lighthouse · Canton` wordmark with crimson punctuation — keep
- The dot-after-display-headline pattern (`Cases<em className="...">.</em>`) — LC product convention
- Animation tokens (`animate-fade-in-up`, `animate-pulse-soft`) — keep
- Brand-accent crimson punctuation in editorial copy (`with <span className="text-lc-red">institutional</span> depth.`) — keep, this is the brand voice

## Verification gates (Phase D, before commit)

1. Frontend `tsc --noEmit` clean
2. `next build` clean (no warnings about purge / unused tokens)
3. Restart frontend (production build); hard-refresh with DevTools "Disable cache" checked
4. Manual route-walk: `/login`, `/dashboard`, `/cases/new`, `/cases/[id]`, `/kb/documents`, `/kb/upload`, `/kb/review`, `/admin/advisors`, `/admin/settings`, `/users/microsoft/callback` — each visually consistent
5. Count `bg-lc-red` (solid fill) usage post-sweep — should be ≤1 (the ghost-crimson Sign in CTA)
6. No `bg-blue-`, `bg-green-`, `bg-slate-` etc. anywhere in `app/` or `components/`
7. Status semantics still legible (active/inactive pills distinguishable)
8. Login page screenshot side-by-side with DCMS login (cross-product alignment check)

---

## Out of scope

- Backend Python files (no UI surface)
- The chat conversation rendering (`prose-chat`) — already disciplined
- The wiki viewer (`wiki-prose`) — already disciplined
- The case-builder diagram (`@xyflow/react` canvas) — domain UI, not chrome
- The auto-generated `.next/` artefacts (rebuild discards them)
- The `LCLogoMark` SVG path (it's text, not SVG; renders correctly across themes)

## Decision required from user

1. **Scope: 1, 2, or 3?**
2. If Scope 1 or 2: keep dark-mode? Confirm.
3. Should error states distinguish from brand crimson (muted breach red), or is the current `ember = lc-red` collapse acceptable?
4. Status pills: monochrome (jade=white) or semantic (green/amber/red)?
5. Anything off-limits beyond what's listed?

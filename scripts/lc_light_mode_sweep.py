"""One-shot Tailwind class swap to flip the wealth_planning_app frontend
from dark mode to LC-canonical light mode.

Two-pass with placeholders to avoid double-substitution
(e.g. text-ink-100 -> text-ink-900, then a naive second pass would
re-rewrite text-ink-900 -> text-ink-?). Run from project root:

    venv/Scripts/python scripts/lc_light_mode_sweep.py

Idempotent: rerunning yields no further diffs once converged.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

# Files that are intentionally allowed to keep dark surfaces (the
# editorial column of the login screen, the LC brand mark variants).
SKIP_FILES = {
    FRONTEND / "components" / "brand" / "LCLogo.tsx",  # brand-mark variants are intentional
}

GLOBS = ["app/**/*.tsx", "app/**/*.ts", "components/**/*.tsx", "components/**/*.ts"]

# Pass 1: rewrite to safe placeholders so pass 2 can substitute targets that
# would otherwise collide with other source tokens.
# (Substrings, so they match the alpha-modifier suffix forms too:
#  "text-ink-300/40", "placeholder:text-ink-500" etc.)
PASS_1 = [
    # text-ink-X — text colour rebalance for light bg
    ("text-ink-100", "text-ink-§§9"),  # primary text -> black
    ("text-ink-200", "text-ink-§§8"),  # strong text  -> deep ink
    ("text-ink-300", "text-ink-§§6"),  # body text    -> dim-grey-2
    ("text-ink-400", "text-ink-§§5"),  # subdued      -> dim-grey
    ("text-ink-500", "text-ink-§§4"),  # placeholder  -> grey-500
    ("text-ink-600", "text-ink-§§4"),  # secondary    -> grey-500
    # bg-ink-X — surface rebalance
    ("bg-ink-950", "bg-§§smoke"),      # page bg      -> white-smoke
    ("bg-ink-900", "bg-§§white"),       # card bg      -> white
    ("bg-ink-850", "bg-§§ink50"),      # elevated     -> grey-50
    ("bg-ink-800", "bg-§§ink100"),     # hover bg     -> grey-100
    ("bg-ink-700", "bg-§§ink200"),     # rare         -> grey-200
    # border-ink-X — border rebalance
    ("border-ink-800", "border-§§ink200"),
    ("border-ink-700", "border-§§ink300"),
    ("border-ink-650", "border-§§ink300"),
    ("border-ink-750", "border-§§ink300"),
    ("border-ink-600", "border-§§ink400"),
    # ring-ink-X (focus rings) — symmetric to border
    ("ring-ink-700", "ring-§§ink300"),
    ("ring-ink-800", "ring-§§ink200"),
    # divide-ink-X (table dividers)
    ("divide-ink-800", "divide-§§ink200"),
    ("divide-ink-700", "divide-§§ink300"),
    # from-/to-ink (gradients) — uncommon but possible
    ("from-ink-900", "from-§§white"),
    ("to-ink-900", "to-§§white"),
]

# Pass 2: placeholders -> final tokens
PASS_2 = [
    ("text-ink-§§9", "text-ink-900"),
    ("text-ink-§§8", "text-ink-800"),
    ("text-ink-§§6", "text-ink-600"),
    ("text-ink-§§5", "text-ink-500"),
    ("text-ink-§§4", "text-ink-400"),
    ("bg-§§smoke", "bg-smoke"),
    ("bg-§§white", "bg-white"),
    ("bg-§§ink50", "bg-ink-50"),
    ("bg-§§ink100", "bg-ink-100"),
    ("bg-§§ink200", "bg-ink-200"),
    ("border-§§ink200", "border-ink-200"),
    ("border-§§ink300", "border-ink-300"),
    ("border-§§ink400", "border-ink-400"),
    ("ring-§§ink200", "ring-ink-200"),
    ("ring-§§ink300", "ring-ink-300"),
    ("divide-§§ink200", "divide-ink-200"),
    ("divide-§§ink300", "divide-ink-300"),
    ("from-§§white", "from-white"),
    ("to-§§white", "to-white"),
]

# Standalone single-pass swaps that don't collide with anything else.
# Done separately so they don't need the placeholder dance.
SINGLE_PASS = [
    # Body bg / primary text — flip the global app shell.
    ("bg-lc-black", "bg-smoke"),
    ("text-lc-white", "text-lc-black"),
    # `bg-ink-900/X` alpha forms — translucent overlays that don't translate
    # well to white. Replace with subtle grey-50 (no alpha needed on light).
    ("bg-ink-900/50", "bg-white"),
    ("bg-ink-900/30", "bg-ink-50"),
    ("bg-white/50", "bg-white"),
    ("bg-ink-850/", "bg-ink-50/"),  # leftover alpha form
]


def sweep_file(path: Path) -> tuple[int, int]:
    """Apply all passes to one file. Returns (rules_applied, bytes_changed)."""
    text = path.read_text(encoding="utf-8")
    original_len = len(text)
    applied = 0
    for find, replace in PASS_1:
        if find in text:
            text = text.replace(find, replace)
            applied += 1
    for find, replace in PASS_2:
        if find in text:
            text = text.replace(find, replace)
            applied += 1
    for find, replace in SINGLE_PASS:
        if find in text:
            text = text.replace(find, replace)
            applied += 1
    if text != path.read_text(encoding="utf-8"):
        path.write_text(text, encoding="utf-8")
    return applied, len(text) - original_len


def main() -> int:
    files: list[Path] = []
    for pattern in GLOBS:
        files.extend(FRONTEND.glob(pattern))
    files = [f for f in files if f not in SKIP_FILES and ".next" not in f.parts]

    total_files = 0
    total_rules = 0
    for f in sorted(files):
        rules, _ = sweep_file(f)
        if rules:
            print(f"  {f.relative_to(FRONTEND)}: {rules} rules applied")
            total_files += 1
            total_rules += rules
    print(f"\nDone. {total_files} files updated, {total_rules} rules applied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

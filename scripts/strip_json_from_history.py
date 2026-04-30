"""One-time migration: strip diagram/recommendation JSON blobs from existing
assistant message rows in `conversations.content`.

Why: under the old text-only LLM flow, the LLM appended a JSON block to every
response containing structure data. After the switch to Anthropic tool use,
the diagram comes through a separate `tool_use` content block and the chat
text is pure markdown — but historical rows still have the JSON embedded.
This script strips it so the chat panel renders clean without any frontend-
side parsing.

Behaviour:
- Backs up the DB to wealth_planning.db.bak.before_json_strip_<timestamp>.
- Iterates ASSISTANT rows. For each row, applies `strip_diagram_json` (a
  port of frontend/lib/strip-diagram-json.ts).
- Updates rows whose content actually changed; counts and prints a summary.
- Idempotent: re-running yields zero updates once converged.

Usage:
    venv/Scripts/python.exe scripts/strip_json_from_history.py
    venv/Scripts/python.exe scripts/strip_json_from_history.py --dry-run
"""
from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "wealth_planning.db"


def strip_diagram_json(content: str) -> str:
    """Port of frontend/lib/strip-diagram-json.ts.

    Removes:
      1) Fenced JSON code blocks (```json ... ``` or ``` ... ```) where the
         block contains a multi-line top-level object.
      2) Bare top-level JSON objects that begin on their own line and have
         a key on the next line. String-aware brace counting so quoted "{"
         and "}" don't throw off the depth.

    Inline single-line `{"x": 1}` mentions in prose are NOT stripped.
    """
    if not content:
        return content
    out = content

    # 1) Fenced JSON / multi-line object inside a code fence
    out = re.sub(
        r"```(?:json|JSON)?\s*\n\{[\s\S]*?\n\}\s*\n?\s*```",
        "",
        out,
    )

    # 2) Bare top-level JSON objects
    for _ in range(6):
        m = re.search(r'(?:^|\n)[ \t]*\{[ \t]*\n[ \t]*"', out)
        if not m:
            break
        open_idx = out.find("{", m.start())
        if open_idx == -1:
            break

        depth = 0
        in_string = False
        escape = False
        close_idx = -1
        for i in range(open_idx, len(out)):
            c = out[i]
            if escape:
                escape = False
                continue
            if c == "\\":
                escape = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    close_idx = i
                    break
        if close_idx == -1:
            break

        out = out[:open_idx].rstrip() + "\n" + out[close_idx + 1 :].lstrip()

    return out.strip()


def backup_db(path: Path) -> Path:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(f"{path.name}.bak.before_json_strip_{ts}")
    shutil.copy2(path, backup)
    return backup


def main() -> int:
    # Force UTF-8 stdout — script prints arrows and other non-cp1252 chars
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Report what would change without writing")
    args = ap.parse_args()

    if not DB_PATH.exists():
        print(f"DB not found at {DB_PATH}", file=sys.stderr)
        return 2

    if not args.dry_run:
        backup = backup_db(DB_PATH)
        print(f"Backup written to: {backup}")

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT message_id, content FROM conversations WHERE role='ASSISTANT'"
    ).fetchall()

    total = len(rows)
    changed = 0
    bytes_removed = 0
    for r in rows:
        original = r["content"] or ""
        stripped = strip_diagram_json(original)
        if stripped == original:
            continue
        delta = len(original) - len(stripped)
        bytes_removed += delta
        changed += 1
        print(f"  msg {r['message_id']}: -{delta} chars ({len(original)} -> {len(stripped)})")
        if not args.dry_run:
            con.execute(
                "UPDATE conversations SET content=? WHERE message_id=?",
                (stripped, r["message_id"]),
            )
    if not args.dry_run:
        con.commit()
    con.close()

    verb = "would update" if args.dry_run else "updated"
    print(f"\n{verb} {changed} of {total} assistant rows; ~{bytes_removed:,} chars removed total")
    return 0


if __name__ == "__main__":
    sys.exit(main())

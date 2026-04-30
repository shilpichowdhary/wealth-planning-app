"""Restore the chat-recommended diagrams for UNS and ABCD into case_diagrams.

Background. Two ways the diagram tab can end up empty / wrong:

  - ABCD: the LLM proposed a 9-entity / 8-edge structure, but the advisor never
    clicked Save on the diagram toolbar, so it was never persisted.

  - UNS: someone clicked "+ Trust" / "+ PIC" on the toolbar a few times to add
    blank placeholder nodes, then saved that. The original 7-entity structure
    proposed by the LLM never reached case_diagrams.

The conversations table still carries the LLM's `{entities, edges}` JSON for
both cases — but only in the pre-strip backup, since the json-strip migration
removed those blobs from the live DB. This script reads the most-recent
diagram-shaped JSON from the BACKUP, converts it via DiagramService, and writes
it to the LIVE case_diagrams table.

For UNS we force-overwrite (the placeholder save is clearly junk). For ABCD we
insert. After this runs, both cases load with their proper structures.

Usage:
    venv/Scripts/python scripts/restore_case_diagrams.py
    venv/Scripts/python scripts/restore_case_diagrams.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

# Force UTF-8 stdout — outputs include non-cp1252 chars (LLM labels with em-dashes etc.)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.services.diagram_service import DiagramService  # noqa: E402

LIVE_DB = ROOT / "wealth_planning.db"
BACKUP_DB = ROOT / "wealth_planning.db.bak.before_json_strip_20260429_162544"

# Cases to restore. (label, force_overwrite_existing). Both forced now so
# we can re-run after fixing DiagramService to remove baked-in inline styles
# (which were causing a double-rectangle render artifact on company nodes).
TARGETS: list[tuple[str, bool]] = [
    ("UNS", True),
    ("ABCD", True),
]


def find_diagram_jsons(text: str) -> list[dict]:
    """Return any top-level JSON objects in `text` whose shape looks like a
    structure diagram — i.e. has an `entities` (or `diagram_nodes`) key.
    Handles both fenced and bare blocks. String-aware brace counting."""
    out: list[dict] = []

    # Fenced
    for m in re.finditer(r"```(?:json|JSON)?\s*\n(\{[\s\S]*?\n\})\s*\n?\s*```", text):
        try:
            obj = json.loads(m.group(1))
        except Exception:
            continue
        if isinstance(obj, dict) and ("entities" in obj or "diagram_nodes" in obj):
            out.append(obj)

    # Bare top-level
    pos = 0
    while True:
        m = re.search(r'(?:^|\n)[ \t]*\{[ \t]*\n[ \t]*"', text[pos:])
        if not m:
            break
        open_idx = text.find("{", pos + m.start())
        if open_idx == -1:
            break

        depth = 0
        in_str = False
        esc = False
        close_idx = -1
        for i in range(open_idx, len(text)):
            c = text[i]
            if esc:
                esc = False
                continue
            if c == "\\":
                esc = True
                continue
            if c == '"':
                in_str = not in_str
                continue
            if in_str:
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

        try:
            obj = json.loads(text[open_idx : close_idx + 1])
            if isinstance(obj, dict) and ("entities" in obj or "diagram_nodes" in obj):
                out.append(obj)
        except Exception:
            pass
        pos = close_idx + 1

    return out


def normalise_diagram_payload(payload: dict) -> dict | None:
    """The LLM emitted two schemas historically: {entities, edges} and the
    Shilpi-style {recommendation, diagram_nodes, ...}. Normalise both to the
    {entities, edges} shape that DiagramService.build_diagram_data expects.
    Returns None if the payload can't be normalised."""
    entities = payload.get("entities")
    edges = payload.get("edges")

    if entities is None and "diagram_nodes" in payload:
        # Shilpi-style: nodes and edges are mixed in one array. Demux by key
        # presence (nodes have `id`/`type`, edges have `edge`/`source`).
        nodes = []
        rels = []
        for item in payload["diagram_nodes"]:
            if not isinstance(item, dict):
                continue
            if "type" in item or "id" in item:
                nodes.append({
                    "type": item.get("type") or "company",
                    "label": item.get("label", ""),
                    "jurisdiction": item.get("jurisdiction", ""),
                    "role": item.get("role", ""),
                    "tax_treatment": item.get("tax_treatment", ""),
                    "rationale": item.get("rationale", ""),
                })
            elif "edge" in item or ("source" in item and "target" in item):
                rels.append(item)
        entities = nodes
        edges = rels  # may be label-only; DiagramService skips edges without source/target
    if not entities:
        return None
    return {"entities": entities, "edges": edges or []}


def latest_diagram_for_case(bak: sqlite3.Connection, case_id: str) -> dict | None:
    """Walk assistant messages newest-first; return the first parseable diagram payload."""
    rows = bak.execute(
        "SELECT message_id, content, timestamp FROM conversations "
        "WHERE case_id=? AND role='ASSISTANT' ORDER BY timestamp DESC",
        (case_id,),
    ).fetchall()
    for mid, content, ts in rows:
        for raw in find_diagram_jsons(content or ""):
            normalised = normalise_diagram_payload(raw)
            if normalised and normalised["entities"]:
                ent_n = len(normalised["entities"])
                edge_n = len(normalised["edges"])
                print(f"  using msg {mid[:8]} (ts={ts}) — {ent_n} entities / {edge_n} edges")
                return normalised
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Show what would be written, don't commit")
    args = ap.parse_args()

    if not BACKUP_DB.exists():
        print(f"Backup DB not found at {BACKUP_DB}", file=sys.stderr)
        return 2
    if not LIVE_DB.exists():
        print(f"Live DB not found at {LIVE_DB}", file=sys.stderr)
        return 2

    bak = sqlite3.connect(BACKUP_DB)
    bak.row_factory = sqlite3.Row
    live = sqlite3.connect(LIVE_DB)

    diagram_service = DiagramService()
    restored = 0
    skipped = 0

    for label, force_overwrite in TARGETS:
        print(f"\n=== {label} ===")
        case_row = bak.execute("SELECT case_id FROM cases WHERE client_name=?", (label,)).fetchone()
        if not case_row:
            print(f"  case '{label}' not found in backup — skipping")
            skipped += 1
            continue
        case_id = case_row["case_id"]

        payload = latest_diagram_for_case(bak, case_id)
        if not payload:
            print(f"  no diagram-shaped JSON found in backup chat history — skipping")
            skipped += 1
            continue

        diagram_data = diagram_service.build_diagram_data(payload)
        nodes_json = json.dumps(diagram_data["nodes"])
        edges_json = json.dumps(diagram_data["edges"])

        existing = live.execute(
            "SELECT case_id FROM case_diagrams WHERE case_id=?", (case_id,)
        ).fetchone()
        if existing and not force_overwrite:
            print(f"  case_diagrams row already exists; skipping (use force_overwrite to replace)")
            skipped += 1
            continue

        action = "UPDATE" if existing else "INSERT"
        print(f"  {action} into case_diagrams: {len(diagram_data['nodes'])} nodes, {len(diagram_data['edges'])} edges")

        if args.dry_run:
            continue

        if existing:
            live.execute(
                "UPDATE case_diagrams SET nodes_json=?, edges_json=?, updated_at=CURRENT_TIMESTAMP, updated_by='restore_script' WHERE case_id=?",
                (nodes_json, edges_json, case_id),
            )
        else:
            live.execute(
                "INSERT INTO case_diagrams (case_id, nodes_json, edges_json, updated_at, updated_by) "
                "VALUES (?, ?, ?, CURRENT_TIMESTAMP, 'restore_script')",
                (case_id, nodes_json, edges_json),
            )
        restored += 1

    if not args.dry_run:
        live.commit()
    bak.close()
    live.close()

    verb = "would restore" if args.dry_run else "restored"
    print(f"\n{verb} {restored} cases; skipped {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

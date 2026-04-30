"""Generate sample .pptx and .pdf decks for the UNS and ABCD cases.

Bypasses the HTTP router (and its auth) and calls the curator + renderer
directly so we can iterate on the deck pipeline without juggling tokens.
Each invocation makes one paid Claude API call per case (Sonnet 4.6,
~$0.20 with caching), then renders the deck and converts to PDF.

Outputs land at the project root:
  sample-deck-UNS.pptx   sample-deck-UNS.pdf
  sample-deck-ABCD.pptx  sample-deck-ABCD.pdf
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.config import settings  # noqa: E402
from backend.services.deck_curator import curate_deck  # noqa: E402
from backend.services.pptx_service import build_pptx  # noqa: E402

DB = ROOT / "wealth_planning.db"
RENDER_DIAGRAM = ROOT / "frontend" / "scripts" / "render-diagram.js"
SOFFICE = settings.soffice_bin

CASES = ["UNS", "ABCD"]


def load_inputs(client_name: str) -> dict:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        case = conn.execute(
            "SELECT case_id, client_name FROM cases WHERE client_name = ?",
            (client_name,),
        ).fetchone()
        if not case:
            raise SystemExit(f"No case found for {client_name}")
        case_id = case["case_id"]

        prof = conn.execute(
            "SELECT domicile, nationality, tax_residency, objectives "
            "FROM client_profiles WHERE case_id = ?",
            (case_id,),
        ).fetchone()
        profile = dict(prof) if prof else {}

        msgs = conn.execute(
            "SELECT role, content FROM conversations "
            "WHERE case_id = ? AND role IN ('USER','ASSISTANT') "
            "ORDER BY timestamp",
            (case_id,),
        ).fetchall()
        chat_history = [
            {"role": m["role"].lower(), "content": m["content"]}
            for m in msgs
            if (m["content"] or "").strip()
        ]

        diag = conn.execute(
            "SELECT nodes_json, edges_json FROM case_diagrams WHERE case_id = ?",
            (case_id,),
        ).fetchone()
        diagram = None
        if diag:
            try:
                diagram = {
                    "nodes": json.loads(diag["nodes_json"] or "[]"),
                    "edges": json.loads(diag["edges_json"] or "[]"),
                }
            except (json.JSONDecodeError, ValueError):
                pass

        return {
            "client_name": case["client_name"],
            "profile": profile,
            "chat_history": chat_history,
            "diagram": diagram,
        }
    finally:
        conn.close()


def render_diagram_png(diagram: dict, out_path: Path) -> bool:
    if not diagram or not diagram.get("nodes"):
        return False
    json_path = out_path.with_suffix(".json")
    json_path.write_text(json.dumps(diagram), encoding="utf-8")
    try:
        proc = subprocess.run(
            ["node", str(RENDER_DIAGRAM), str(json_path), str(out_path)],
            capture_output=True, text=True,
            cwd=str(ROOT / "frontend"),
            timeout=60,
        )
    finally:
        json_path.unlink(missing_ok=True)
    if proc.returncode != 0:
        print(f"  diagram render failed: {proc.stderr[:200]}")
        return False
    return out_path.exists()


def convert_to_pdf(pptx_path: Path) -> Path:
    pdf_path = pptx_path.with_suffix(".pdf")
    proc = subprocess.run(
        [SOFFICE, "--headless", "--convert-to", "pdf",
         "--outdir", str(pptx_path.parent), str(pptx_path)],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0 or not pdf_path.exists():
        raise SystemExit(f"soffice failed: {proc.stderr[:200]}")
    return pdf_path


async def render_one(client: str) -> None:
    print(f"\n=== {client} ===")
    inputs = load_inputs(client)
    diag_info = (
        f"yes ({len(inputs['diagram']['nodes'])} nodes)"
        if inputs["diagram"] else "no"
    )
    print(
        f"  inputs: profile={'yes' if inputs['profile'] else 'no'}  "
        f"chat={len(inputs['chat_history'])} msgs  "
        f"diagram={diag_info}"
    )

    diagram_png = ROOT / f"_diagram-{client}.png"
    has_png = render_diagram_png(inputs["diagram"], diagram_png) if inputs["diagram"] else False
    if has_png:
        print(f"  diagram --> {diagram_png.name}")

    # Cache the curator output to disk so layout-only iterations don't pay
    # the LLM cost again. Pass --refresh on the CLI (or delete the cache file)
    # to force a fresh curator run.
    spec_cache = ROOT / f"_spec-{client}.json"
    refresh = "--refresh" in sys.argv
    if spec_cache.exists() and not refresh:
        spec = json.loads(spec_cache.read_text(encoding="utf-8"))
        print(f"  curator --> using cached spec ({spec_cache.name})")
    else:
        print("  curator --> calling Claude (~30s)...")
        spec = await curate_deck(
            client_name=inputs["client_name"],
            profile=inputs["profile"],
            chat_history=inputs["chat_history"],
            diagram=inputs["diagram"],
        )
        spec_cache.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print(f"  spec: {len(spec['slides'])} slides + auto-disclaimer + offices")

    if has_png:
        for s in spec["slides"]:
            if (s.get("layout") or "").lower() == "structure":
                s["png_path"] = str(diagram_png.absolute())
                break

    pptx_path = ROOT / f"sample-deck-{client}.pptx"
    build_pptx(spec, pptx_path)
    print(f"  pptx --> {pptx_path.name} ({pptx_path.stat().st_size:,} bytes)")

    pdf_path = convert_to_pdf(pptx_path)
    print(f"  pdf --> {pdf_path.name} ({pdf_path.stat().st_size:,} bytes)")

    if has_png:
        diagram_png.unlink(missing_ok=True)


async def main() -> None:
    for client in CASES:
        await render_one(client)


if __name__ == "__main__":
    asyncio.run(main())

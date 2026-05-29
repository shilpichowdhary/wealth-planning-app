"""Orchestrates the deck-generation pipeline.

Pipeline:
  1. Pull case data (chat history, profile, diagram) from DB
  2. Render the structure diagram to PNG (skipped if no diagram)
  3. Call deck_curator → JSON slide spec
  4. Inject the PNG path into the structure slide
  5. Render to .pptx via pptx_service
  6. Persist to data/reports/{case_id}/deck-v{n}.pptx and a CaseDeck row
  7. PDF is rendered lazily on first /deck.pdf request via soffice

Concurrency note: each generation runs the (slow, ~30s) Claude call inline
in the request. For now this is fine since deck generation is an explicit
user click; if we need it to scale we'd move it to a background worker.
"""
from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.case import Case
from backend.models.case_deck import CaseDeck
from backend.models.case_diagram import CaseDiagram
from backend.models.client_profile import ClientProfile
from backend.models.conversation import Conversation, MessageRole
from backend.services.deck_curator import curate_deck, hash_inputs
from backend.services.pptx_service import build_pptx
from backend.storage import get_storage

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DIAGRAM_RENDER_SCRIPT = PROJECT_ROOT / "frontend" / "scripts" / "render-diagram.js"


async def _render_diagram_png(diagram: dict, out_path: Path) -> bool:
    """Run frontend/scripts/render-diagram.js to produce a high-res PNG.
    Returns False if the diagram has no nodes or the render failed."""
    if not diagram or not diagram.get("nodes"):
        return False
    if not DIAGRAM_RENDER_SCRIPT.exists():
        logger.warning("render-diagram.js missing; structure slide will lack image")
        return False

    with TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "diagram.json"
        json_path.write_text(json.dumps(diagram), encoding="utf-8")
        proc = await asyncio.create_subprocess_exec(
            "node", str(DIAGRAM_RENDER_SCRIPT), str(json_path), str(out_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(PROJECT_ROOT / "frontend"),
        )
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            logger.warning("Diagram render timed out")
            return False
    if proc.returncode != 0:
        logger.warning("Diagram render exit %d: %s", proc.returncode, (stderr or b"")[:300])
        return False
    return out_path.exists()


async def _gather_inputs(case_id: str, db: AsyncSession) -> dict:
    """Pull everything the curator needs."""
    case = (await db.execute(select(Case).where(Case.case_id == case_id))).scalar_one_or_none()
    if not case:
        raise ValueError(f"Case {case_id} not found")

    prof_row = (
        await db.execute(select(ClientProfile).where(ClientProfile.case_id == case_id))
    ).scalar_one_or_none()
    profile = {
        "domicile": prof_row.domicile if prof_row else None,
        "nationality": prof_row.nationality if prof_row else None,
        "tax_residency": prof_row.tax_residency if prof_row else None,
        "objectives": prof_row.objectives if prof_row else None,
    }

    msg_rows = (
        await db.execute(
            select(Conversation)
            .where(Conversation.case_id == case_id)
            .order_by(Conversation.timestamp)
        )
    ).scalars().all()
    chat_history = [
        {"role": ("user" if m.role == MessageRole.USER else "assistant"), "content": m.content}
        for m in msg_rows
        if (m.content or "").strip()
    ]

    diag_row = (
        await db.execute(select(CaseDiagram).where(CaseDiagram.case_id == case_id))
    ).scalar_one_or_none()
    diagram = None
    if diag_row:
        try:
            diagram = {
                "nodes": json.loads(diag_row.nodes_json or "[]"),
                "edges": json.loads(diag_row.edges_json or "[]"),
            }
        except (json.JSONDecodeError, ValueError):
            diagram = None

    return {
        "case": case,
        "profile": profile,
        "chat_history": chat_history,
        "diagram": diagram,
    }


async def _next_version(case_id: str, db: AsyncSession) -> int:
    row = (
        await db.execute(
            select(CaseDeck.version)
            .where(CaseDeck.case_id == case_id)
            .order_by(desc(CaseDeck.version))
            .limit(1)
        )
    ).scalar_one_or_none()
    return (row or 0) + 1


async def latest_deck(case_id: str, db: AsyncSession) -> CaseDeck | None:
    return (
        await db.execute(
            select(CaseDeck)
            .where(CaseDeck.case_id == case_id)
            .order_by(desc(CaseDeck.version))
            .limit(1)
        )
    ).scalar_one_or_none()


async def is_stale(case_id: str, db: AsyncSession) -> bool:
    """True if inputs have drifted since the latest deck was generated."""
    deck = await latest_deck(case_id, db)
    if not deck:
        return True
    inputs = await _gather_inputs(case_id, db)
    h = hash_inputs(
        profile=inputs["profile"],
        chat_history=inputs["chat_history"],
        diagram=inputs["diagram"],
    )
    return h != deck.spec_hash


async def generate_deck(case_id: str, db: AsyncSession, *, generated_by: str | None) -> CaseDeck:
    """End-to-end: gather → curator → render PNG → render PPTX → persist."""
    inputs = await _gather_inputs(case_id, db)
    case = inputs["case"]
    version = await _next_version(case_id, db)
    storage = get_storage()
    pptx_key = f"reports/{case_id}/deck-v{version}.pptx"

    # Render the diagram + PPTX inside a temp dir, then persist the .pptx via storage.
    # The PNG is a transient build input (consumed by build_pptx, never re-served).
    with TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        png_path: Path | None = None
        if inputs["diagram"] and inputs["diagram"].get("nodes"):
            candidate = tmp / f"diagram-v{version}.png"
            if await _render_diagram_png(inputs["diagram"], candidate):
                png_path = candidate

        spec = await curate_deck(
            client_name=case.client_name,
            profile=inputs["profile"],
            chat_history=inputs["chat_history"],
            diagram=inputs["diagram"],
        )
        # Inject PNG into the structure slide
        if png_path:
            for s in spec.get("slides", []):
                if (s.get("layout") or "").lower() == "structure":
                    s["png_path"] = str(png_path)
                    break

        tmp_pptx = tmp / f"deck-v{version}.pptx"
        build_pptx(spec, tmp_pptx)
        storage.save_bytes(
            pptx_key,
            tmp_pptx.read_bytes(),
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )

    deck = CaseDeck(
        deck_id=uuid.uuid4().hex,
        case_id=case_id,
        version=version,
        spec_json=json.dumps(spec),
        spec_hash=hash_inputs(
            profile=inputs["profile"],
            chat_history=inputs["chat_history"],
            diagram=inputs["diagram"],
        ),
        pptx_path=pptx_key,
        pdf_path=None,
        generated_at=datetime.utcnow(),
        generated_by=generated_by,
        model_used=(await __get_model_used()),
    )
    db.add(deck)
    await db.commit()
    await db.refresh(deck)
    logger.info("Deck v%d generated for case %s", version, case_id)
    return deck


async def __get_model_used() -> str:
    from backend.services.settings_service import get_setting
    return (await get_setting("claude_model")) or "claude-sonnet-4-6"


async def ensure_pdf(deck: CaseDeck, db: AsyncSession) -> str:
    """Lazy soffice convert .pptx → .pdf, persisted via storage. Returns the pdf key."""
    storage = get_storage()
    if deck.pdf_path and storage.exists(deck.pdf_path):
        return deck.pdf_path
    if not deck.pptx_path or not storage.exists(deck.pptx_path):
        raise FileNotFoundError(f"Deck PPTX missing for {deck.deck_id}")
    pdf_key = deck.pptx_path.rsplit(".", 1)[0] + ".pdf"
    # soffice needs real local files: materialize the pptx, convert into a temp dir.
    with storage.as_local_path(deck.pptx_path) as pptx_local, TemporaryDirectory() as outdir:
        proc = await asyncio.create_subprocess_exec(
            settings.soffice_bin, "--headless", "--convert-to", "pdf",
            "--outdir", outdir, str(pptx_local),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            raise RuntimeError("PDF conversion timed out")
        produced = Path(outdir) / (Path(pptx_local).stem + ".pdf")
        if proc.returncode != 0 or not produced.exists():
            raise RuntimeError(f"soffice failed: {(stderr or b'')[:300]!r}")
        storage.save_bytes(pdf_key, produced.read_bytes(), content_type="application/pdf")
    deck.pdf_path = pdf_key
    await db.commit()
    return pdf_key

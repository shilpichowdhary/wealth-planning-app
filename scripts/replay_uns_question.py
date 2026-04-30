"""Create a new case mirroring an existing one, then replay its chat questions.

Bypasses the HTTP /chat/stream router so we don't need auth, but uses the
exact services the router uses (rag.retrieve, llm.stream_chat) so the
output reflects the new prompt + retrieval changes.

The new case is created with `created_by` = the supplied user (Zijie by
default), so it shows up in his case list in the frontend exactly like a
case he authored himself.

Usage:
  python scripts/replay_uns_question.py [SOURCE_CASE_NAME]

Defaults to UNS. The script copies the source profile, replays every USER
message in order through the current chat pipeline (so multi-turn cases
like ABCD get full conversation history), and lands the new case named
"{SOURCE}-AFTER-FIX" in the dashboard.
"""
from __future__ import annotations

import asyncio
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from backend.database import AsyncSessionLocal  # noqa: E402
from backend.models.case import Case, CaseStatus  # noqa: E402
from backend.models.case_diagram import CaseDiagram  # noqa: E402
from backend.models.client_profile import ClientProfile  # noqa: E402
from backend.models.conversation import Conversation, MessageRole  # noqa: E402
from backend.models.user import User  # noqa: E402
from backend.services.diagram_service import DiagramService  # noqa: E402
from backend.services.llm_service import stream_chat  # noqa: E402
from backend.services.rag_service import RAGService  # noqa: E402

OWNER_EMAIL = "zijie.long@lighthouse-canton.com"


async def find_owner(db) -> User:
    user = (
        await db.execute(select(User).where(User.email == OWNER_EMAIL))
    ).scalar_one_or_none()
    if not user:
        raise SystemExit(f"Owner {OWNER_EMAIL} not found")
    return user


async def find_source_case(db, name: str) -> Case:
    src = (await db.execute(select(Case).where(Case.client_name == name))).scalar_one_or_none()
    if not src:
        raise SystemExit(f"Source case {name!r} not found")
    return src


async def find_source_profile(db, case_id: str) -> ClientProfile:
    prof = (
        await db.execute(select(ClientProfile).where(ClientProfile.case_id == case_id))
    ).scalar_one_or_none()
    if not prof:
        raise SystemExit(f"Source profile for case {case_id} not found")
    return prof


async def source_user_questions(db, case_id: str) -> list[str]:
    """All USER messages from the source case in chronological order. We
    skip duplicates (the original ABCD has the same question repeated) and
    purely meta messages so the replay focuses on substantive turns."""
    rows = (
        await db.execute(
            select(Conversation)
            .where(Conversation.case_id == case_id, Conversation.role == MessageRole.USER)
            .order_by(Conversation.timestamp)
        )
    ).scalars().all()
    out: list[str] = []
    for r in rows:
        c = (r.content or "").strip()
        if not c:
            continue
        # Skip duplicates of the immediately-preceding user turn (ABCD has one)
        if out and out[-1] == c:
            continue
        out.append(c)
    return out


async def create_case_with_profile(db, owner: User, src_profile: ClientProfile, client_name: str) -> Case:
    case_id = str(uuid.uuid4())
    case = Case(
        case_id=case_id,
        client_name=client_name,
        created_by=owner.user_id,
        created_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
        status=CaseStatus.ACTIVE,
        compact_summary=None,
    )
    db.add(case)
    profile = ClientProfile(
        profile_id=str(uuid.uuid4()),
        case_id=case_id,
        nationality=src_profile.nationality,
        domicile=src_profile.domicile,
        tax_residency=src_profile.tax_residency,
        family_members=src_profile.family_members,
        asset_classes=src_profile.asset_classes,
        asset_jurisdictions=src_profile.asset_jurisdictions,
        existing_structures=src_profile.existing_structures,
        objectives=src_profile.objectives,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(case)
    return case


def profile_to_dict(p: ClientProfile) -> dict:
    def _safe(s, fallback):
        try:
            return json.loads(s) if isinstance(s, str) else (s or fallback)
        except (json.JSONDecodeError, ValueError):
            return fallback
    return {
        "nationality": p.nationality,
        "domicile": p.domicile,
        "tax_residency": p.tax_residency,
        "asset_classes": _safe(p.asset_classes, []),
        "asset_jurisdictions": _safe(p.asset_jurisdictions, []),
        "objectives": _safe(p.objectives, []),
        "family_members": _safe(p.family_members, []),
        "existing_structures": p.existing_structures,
    }


async def run_one_turn(
    *, rag, owner, db, case, profile, history: list[dict], question: str, kb_has_documents: bool,
) -> tuple[str, dict | None]:
    """Send one user message through the chat pipeline; return (assistant_text, diagram_raw)."""
    # Save user message
    db.add(Conversation(case_id=case.case_id, role=MessageRole.USER, content=question))
    await db.commit()

    retrieval = await rag.retrieve(
        query=question,
        session_tavily_count=0,
        case_id=case.case_id,
        allow_web=False,
        force_answer=True,
    )
    print(
        f"    retrieval: {len(retrieval.chunks)} chunks, "
        f"sources={[c.get('source_file','?').split(chr(92))[-1].split('/')[-1] for c in retrieval.chunks[:3]]}"
    )

    full_text_parts: list[str] = []
    diagram_raw: dict | None = None
    async for event in stream_chat(
        messages=history + [{"role": "user", "content": question}],
        retrieval=retrieval,
        profile=profile,
        prior_summary=None,
        kb_has_documents=kb_has_documents,
    ):
        et = event.get("type")
        if et == "text":
            full_text_parts.append(event.get("text", ""))
        elif et == "diagram":
            diagram_raw = event.get("diagram")
    full_text = "".join(full_text_parts)
    print(f"    response: {len(full_text)} chars  diagram={'yes' if diagram_raw else 'no'}")

    # Save assistant message
    db.add(Conversation(
        case_id=case.case_id, role=MessageRole.ASSISTANT, content=full_text,
        sources_cited=json.dumps([c.get("source_file") for c in retrieval.chunks]),
    ))
    await db.commit()
    return full_text, diagram_raw


async def replay(source_name: str) -> None:
    new_name = f"{source_name}-Updated"
    async with AsyncSessionLocal() as db:
        owner = await find_owner(db)
        src_case = await find_source_case(db, source_name)
        src_profile = await find_source_profile(db, src_case.case_id)
        questions = await source_user_questions(db, src_case.case_id)
        if not questions:
            raise SystemExit(f"No USER messages in source case {source_name!r}")

        existing = (
            await db.execute(select(Case).where(Case.client_name.like(f"{new_name}%")))
        ).scalars().all()
        client_name = new_name if not existing else f"{new_name}-{len(existing) + 1}"
        case = await create_case_with_profile(db, owner, src_profile, client_name)
        print(f"Created case {client_name} (case_id={case.case_id[:8]}) owned by {owner.name}")
        print(f"Replaying {len(questions)} user turn(s) from {source_name}\n")

        rag = RAGService()
        kb_has_documents = rag.kb.collection.count() > 0
        profile = profile_to_dict(src_profile)
        history: list[dict] = []
        last_diagram: dict | None = None

        for i, q in enumerate(questions, 1):
            print(f"  Turn {i}/{len(questions)} — {q[:70]!r}")
            text, diag = await run_one_turn(
                rag=rag, owner=owner, db=db, case=case,
                profile=profile, history=history, question=q,
                kb_has_documents=kb_has_documents,
            )
            history.append({"role": "user", "content": q})
            history.append({"role": "assistant", "content": text})
            if diag:
                last_diagram = diag

        # Persist diagram. Prefer the latest one the LLM emitted across the
        # multi-turn replay; fall back to the source case's saved diagram so
        # the comparison case isn't empty when the model didn't produce one.
        if last_diagram:
            diagram_service = DiagramService()
            diagram_data = diagram_service.build_diagram_data(last_diagram)
            db.add(CaseDiagram(
                case_id=case.case_id,
                nodes_json=json.dumps(diagram_data["nodes"]),
                edges_json=json.dumps(diagram_data["edges"]),
                updated_by=owner.user_id,
            ))
            await db.commit()
            print(f"\n  saved diagram from LLM tool call: {len(diagram_data['nodes'])} nodes, {len(diagram_data['edges'])} edges")
        else:
            src_diag = (
                await db.execute(select(CaseDiagram).where(CaseDiagram.case_id == src_case.case_id))
            ).scalar_one_or_none()
            if src_diag:
                db.add(CaseDiagram(
                    case_id=case.case_id,
                    nodes_json=src_diag.nodes_json,
                    edges_json=src_diag.edges_json,
                    updated_by=owner.user_id,
                ))
                await db.commit()
                print(f"\n  copied source diagram from {source_name} (LLM did not emit one)")

        print(f"\nDone. New case {client_name!r} is ready — refresh the dashboard.")


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "UNS"
    asyncio.run(replay(src))

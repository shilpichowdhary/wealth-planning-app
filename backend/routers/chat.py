import asyncio
import json
import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database import get_db, AsyncSessionLocal
from backend.models.case import Case
from backend.models.conversation import Conversation, MessageRole
from backend.models.client_profile import ClientProfile
from backend.schemas.chat import ChatRequest
from backend.routers.auth import get_current_user
from backend.models.user import User, UserRole
from backend.services.rag_service import RAGService, get_rag_service
from backend.services.llm_service import stream_chat
from backend.services.summary_service import generate_compact_summary

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


def _safe_json_loads(s: str | None, default: Any) -> Any:
    if not s:
        return default
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return default


@router.post("/stream", response_class=StreamingResponse)
async def chat_stream(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rag: RAGService = Depends(get_rag_service),
):
    # Verify case exists and user has access
    result = await db.execute(select(Case).where(Case.case_id == payload.case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    # Access control
    if current_user.role == UserRole.ADVISOR and case.created_by != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if current_user.role == UserRole.CLIENT and current_user.case_id != payload.case_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Load conversation history (cap at last 40 messages to prevent huge context windows)
    hist_result = await db.execute(
        select(Conversation)
        .where(Conversation.case_id == payload.case_id)
        .order_by(Conversation.timestamp.desc())
        .limit(40)
    )
    history = list(reversed([
        {"role": msg.role.value if hasattr(msg.role, 'value') else msg.role, "content": msg.content}
        for msg in hist_result.scalars().all()
    ]))

    # Load client profile for pseudonymisation
    profile_result = await db.execute(
        select(ClientProfile).where(ClientProfile.case_id == payload.case_id)
    )
    profile_row = profile_result.scalar_one_or_none()
    profile = {}
    if profile_row:
        profile = {
            "nationality": profile_row.nationality,
            "domicile": profile_row.domicile,
            "tax_residency": profile_row.tax_residency,
            "asset_classes": _safe_json_loads(profile_row.asset_classes, []),
            "asset_jurisdictions": _safe_json_loads(profile_row.asset_jurisdictions, []),
            "objectives": _safe_json_loads(profile_row.objectives, []),
            "family_members": _safe_json_loads(profile_row.family_members, []),
            "existing_structures": profile_row.existing_structures,
        }

    # Save user message
    user_msg = Conversation(
        case_id=payload.case_id,
        role=MessageRole.USER,
        content=payload.message,
    )
    db.add(user_msg)
    await db.commit()

    # Retrieve context
    messages_for_llm = history + [{"role": "user", "content": payload.message}]
    retrieval = await rag.retrieve(
        query=payload.message,
        session_tavily_count=payload.session_tavily_count,
        case_id=payload.case_id,
    )

    async def event_stream():
        # Emit sources metadata first (synchronous serialisation — before try block)
        web_source_data = []
        for w in retrieval.web_results:
            if hasattr(w, 'url'):
                web_source_data.append({"url": w.url, "title": w.title, "retrieved_at": w.retrieved_at})
            else:
                web_source_data.append(w)

        source_event = {
            "type": "sources",
            "source": retrieval.source.value if hasattr(retrieval.source, 'value') else retrieval.source,
            "chunks": retrieval.chunks[:3],
            "web": web_source_data,
        }
        yield f"data: {json.dumps(source_event, default=str)}\n\n"

        try:
            # Stream LLM tokens
            full_response_parts = []
            async for token in stream_chat(
                messages=messages_for_llm,
                retrieval=retrieval,
                profile=profile,
            ):
                full_response_parts.append(token)
                yield f"data: {json.dumps({'type': 'token', 'text': token})}\n\n"

            full_text = "".join(full_response_parts)

            # Save assistant message using fresh session (not request-scoped db)
            async with AsyncSessionLocal() as bg_db:
                asst_msg = Conversation(
                    case_id=payload.case_id,
                    role=MessageRole.ASSISTANT,
                    content=full_text,
                    sources_cited=json.dumps([c.get("source_file") for c in retrieval.chunks]),
                )
                bg_db.add(asst_msg)
                await bg_db.commit()

            # Background: update case summary
            async def bg_update_summary():
                updated_history = messages_for_llm + [{"role": "assistant", "content": full_text}]
                summary = await generate_compact_summary(updated_history)
                async with AsyncSessionLocal() as bg_db:
                    res = await bg_db.execute(select(Case).where(Case.case_id == payload.case_id))
                    c = res.scalar_one_or_none()
                    if c:
                        c.compact_summary = summary
                        await bg_db.commit()

            # Background: queue web-sourced KB enrichment entries
            async def bg_queue_kb_enrichment():
                if not retrieval.web_results:
                    return
                from backend.models.kb_review_queue import KBReviewQueue
                jurisdiction = profile.get("domicile") or profile.get("tax_residency") or "Unknown"
                async with AsyncSessionLocal() as bg_db:
                    for web_result in retrieval.web_results:
                        text = web_result.text if hasattr(web_result, 'text') else web_result.get('text', '')
                        url = web_result.url if hasattr(web_result, 'url') else web_result.get('url', '')
                        entry = KBReviewQueue(
                            jurisdiction=jurisdiction,
                            topic=payload.message[:100],
                            content=text,
                            web_url=url,
                        )
                        bg_db.add(entry)
                    await bg_db.commit()

            asyncio.create_task(bg_update_summary())
            asyncio.create_task(bg_queue_kb_enrichment())

        except Exception as e:
            logger.error("event_stream error: %s", e, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': 'Internal server error'})}\n\n"

        finally:
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

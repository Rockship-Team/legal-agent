"""Chat API routes"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse

from legal_chatbot.api.schemas import (
    ChatAPIResponse,
    ChatRequest,
    HealthResponse,
    MessageItem,
    SessionInfo,
    SessionListItem,
    SessionListResponse,
    SessionMessagesResponse,
    SessionUpdateRequest,
)
from legal_chatbot.api.session_store import SessionStore

router = APIRouter()

# Global session store — initialized in app.py lifespan
store: SessionStore = SessionStore()

# Directory where contracts/PDFs are stored
CONTRACTS_DIR = Path("data/contracts")


def _build_session_info(entry) -> SessionInfo:
    """Build SessionInfo from a SessionEntry"""
    session = entry.service.session
    draft = session.current_draft

    info = SessionInfo(
        session_id=entry.session_id,
        mode=session.mode,
    )

    if draft and draft.template:
        required_fields = [f for f in draft.template.fields if f.required]
        current_idx = draft.current_field_index

        info.contract_type = draft.contract_type
        info.fields_total = len(required_fields)
        info.fields_completed = min(current_idx, len(required_fields))

        if draft.state == "collecting" and current_idx < len(required_fields):
            info.current_field = required_fields[current_idx].label

    return info


def _build_suggestions(
    action: str | None, session_mode: str, has_draft: bool,
    available_types: list[dict] | None = None,
) -> list[str]:
    """Generate contextual suggestions based on current state.

    Args:
        available_types: list of {"type": slug, "name": display_name} from DB.
    """
    suggestions = []

    if action == "contract_created" or action == "field_collected":
        suggestions.append("Hủy hợp đồng")
    elif action == "contract_ready":
        suggestions.extend(["Tạo hợp đồng mới", "Hỏi về luật"])
    elif action == "preview_opened":
        suggestions.extend(["Tạo hợp đồng mới", "Hỏi về luật"])
    elif action == "pdf_exported":
        suggestions.extend(["Tạo hợp đồng mới", "Hỏi về luật"])
    elif action == "ask_contract_type":
        # Dynamic suggestions from DB templates
        if available_types:
            suggestions.extend(t["name"] for t in available_types)
        else:
            suggestions.append("Tạo hợp đồng")
    elif session_mode == "normal" and not has_draft:
        suggestions.extend(["Tạo hợp đồng", "Hỏi về luật"])

    return suggestions


def _pdf_path_to_url(pdf_path: str | None) -> str | None:
    """Convert PDF path/URL to /api/files/{filename} download URL.

    Always routes through our proxy endpoint which generates fresh
    signed URLs on demand — avoids Supabase JWT expiration issues.
    """
    if not pdf_path:
        return None
    if pdf_path.startswith("https://") or pdf_path.startswith("http://"):
        # Extract filename from signed URL (path before query params)
        url_path = pdf_path.split("?")[0]
        filename = url_path.split("/")[-1]
        return f"/api/files/{filename}"
    filename = Path(pdf_path).name
    return f"/api/files/{filename}"


@router.post("/api/chat", response_model=ChatAPIResponse)
async def chat(request: ChatRequest):
    """Main chat endpoint — natural language router to all services"""
    entry = await store.get_or_create(request.session_id)

    try:
        response = await entry.service.chat(request.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý: {e}")

    # Persist messages to Supabase (non-blocking, best-effort)
    pdf_url = _pdf_path_to_url(response.pdf_path)
    await store.persist_messages(
        entry.session_id, request.message, response.message, pdf_url=pdf_url
    )

    session = entry.service.session
    has_draft = session.current_draft is not None and session.current_draft.state == "ready"

    # Get available contract types for dynamic suggestions
    available_types = None
    if response.action_taken == "ask_contract_type":
        available_types = entry.service._get_available_contract_types()

    return ChatAPIResponse(
        session_id=entry.session_id,
        message=response.message,
        action=response.action_taken,
        session_info=_build_session_info(entry),
        suggestions=_build_suggestions(
            response.action_taken, session.mode, has_draft,
            available_types=available_types,
        ),
        has_contract=has_draft,
        html_preview=response.html_preview,
        pdf_url=pdf_url,
    )


@router.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """SSE streaming chat — sends tokens as they're generated.

    Events:
      data: {"type":"session","session_id":"..."}
      data: {"type":"token","text":"..."}
      data: {"type":"done","message":"...","suggestions":[...]}
    """
    entry = await store.get_or_create(request.session_id)
    service = entry.service
    session = service.get_session()

    # Let the service decide: stream (legal Q&A) vs non-stream (contract, commands)
    use_streaming = service.should_stream(request.message)

    if not use_streaming:
        # Use service.chat() for contract interactions (handles all routing internally)
        try:
            response = await service.chat(request.message)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi: {e}")

        pdf_url = _pdf_path_to_url(response.pdf_path)
        await store.persist_messages(
            entry.session_id, request.message, response.message, pdf_url=pdf_url
        )

        # Get available contract types for dynamic suggestions
        available_types = None
        if response.action_taken == "ask_contract_type":
            available_types = service._get_available_contract_types()

        has_draft = session.current_draft is not None and session.current_draft.state == "ready"

        session_info = _build_session_info(entry).model_dump()

        async def non_stream():
            yield f"data: {json.dumps({'type': 'session', 'session_id': entry.session_id})}\n\n"
            yield f"data: {json.dumps({'type': 'token', 'text': response.message})}\n\n"
            meta = {
                "type": "done",
                "message": response.message,
                "action": response.action_taken,
                "session_info": session_info,
                "suggestions": _build_suggestions(
                    response.action_taken, session.mode, has_draft,
                    available_types=available_types,
                ),
                "pdf_url": pdf_url,
            }
            yield f"data: {json.dumps(meta)}\n\n"

        return StreamingResponse(non_stream(), media_type="text/event-stream")

    # Streaming flow for legal questions
    # Record user message (only for streaming path — service.chat() records its own)
    session.messages.append({"role": "user", "content": request.message})

    async def stream_response():
        # Send session ID immediately
        yield f"data: {json.dumps({'type': 'session', 'session_id': entry.session_id})}\n\n"

        # Build context (DB search) — this is the ~2-3s part
        try:
            llm_messages = await service._build_llm_messages(request.message)
        except Exception:
            llm_messages = None

        if not llm_messages:
            # Fallback: no context found
            llm_messages = [
                {"role": "system", "content": service.SYSTEM_PROMPT},
                {"role": "user", "content": request.message},
            ]

        # Stream LLM response token by token
        full_text = ""
        try:
            async for chunk in service.stream_llm_response(llm_messages):
                full_text += chunk
                yield f"data: {json.dumps({'type': 'token', 'text': chunk})}\n\n"
        except Exception as e:
            full_text = f"Xin lỗi, đã xảy ra lỗi: {e}"
            yield f"data: {json.dumps({'type': 'token', 'text': full_text})}\n\n"

        # Save to session + DB
        session.messages.append({"role": "assistant", "content": full_text})
        await store.persist_messages(entry.session_id, request.message, full_text)

        # Send done event with metadata
        meta = {
            "type": "done",
            "message": full_text,
            "action": None,
            "session_info": _build_session_info(entry).model_dump(),
            "suggestions": _build_suggestions(None, session.mode, False),
        }
        yield f"data: {json.dumps(meta)}\n\n"

    return StreamingResponse(stream_response(), media_type="text/event-stream")


# =========================================================
# Session management endpoints
# =========================================================

@router.get("/api/sessions", response_model=SessionListResponse)
async def list_sessions():
    """List all chat sessions (from Supabase)"""
    if not store.db:
        return SessionListResponse(sessions=[])

    try:
        sessions = store.db.list_chat_sessions(limit=50)
        items = [
            SessionListItem(
                session_id=s["id"],
                title=s.get("title", "Cuộc hội thoại mới"),
                created_at=s.get("created_at"),
                last_message_at=s.get("last_message_at"),
            )
            for s in sessions
        ]
        return SessionListResponse(sessions=items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tải danh sách: {e}")


@router.get("/api/sessions/{session_id}/messages", response_model=SessionMessagesResponse)
async def get_session_messages(session_id: str):
    """Get all messages for a chat session"""
    if not store.db:
        raise HTTPException(status_code=503, detail="Database không khả dụng")

    try:
        messages = store.db.get_chat_messages(session_id, limit=200)
        items = [
            MessageItem(
                id=m["id"],
                role=m["role"],
                content=m["content"],
                created_at=m.get("created_at"),
                pdf_url=_pdf_path_to_url((m.get("metadata") or {}).get("pdf_url")),
            )
            for m in messages
        ]
        return SessionMessagesResponse(session_id=session_id, messages=items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tải tin nhắn: {e}")


@router.patch("/api/sessions/{session_id}")
async def update_session(session_id: str, request: SessionUpdateRequest):
    """Update session metadata (e.g. rename title)"""
    if not store.db:
        raise HTTPException(status_code=503, detail="Database không khả dụng")

    try:
        update_kwargs = {}
        if request.title:
            update_kwargs["title"] = request.title
        store.db.update_chat_session(session_id, **update_kwargs)
        return {"message": "Đã cập nhật session", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi cập nhật: {e}")


@router.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session"""
    deleted = await store.delete(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session không tồn tại")
    return {"message": "Đã xóa session", "session_id": session_id}


# =========================================================
# File download (local fallback)
# =========================================================

@router.get("/api/files/{filename}")
async def download_file(filename: str):
    """Download a generated file (PDF or JSON).

    Tries local data/contracts/ first, then Supabase Storage.
    For Supabase, generates a fresh signed URL (avoids JWT expiration).
    """
    # Sanitize filename — prevent path traversal
    safe_name = Path(filename).name
    file_path = CONTRACTS_DIR / safe_name

    # Try local file first
    if file_path.exists():
        suffix = file_path.suffix.lower()
        media_types = {
            '.pdf': 'application/pdf',
            '.json': 'application/json',
        }
        media_type = media_types.get(suffix, 'application/octet-stream')
        return FileResponse(
            path=str(file_path),
            filename=safe_name,
            media_type=media_type,
        )

    # Fallback: Supabase Storage — download and serve directly
    if store.db:
        try:
            client = store.db._write()  # Service role key for storage access
            file_bytes = client.storage.from_("legal-contracts").download(safe_name)
            if file_bytes:
                suffix = Path(safe_name).suffix.lower()
                media_types = {
                    '.pdf': 'application/pdf',
                    '.json': 'application/json',
                }
                media_type = media_types.get(suffix, 'application/octet-stream')
                return Response(
                    content=file_bytes,
                    media_type=media_type,
                    headers={
                        "Content-Disposition": f'attachment; filename="{safe_name}"',
                    },
                )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Supabase Storage download failed for '{safe_name}': {e}")

    raise HTTPException(status_code=404, detail="File không tồn tại")


@router.get("/api/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    try:
        from legal_chatbot.utils.config import get_settings
        settings = get_settings()
        db_mode = settings.db_mode
        status = "ok"
    except Exception:
        db_mode = "unknown"
        status = "error"

    return HealthResponse(
        status=status,
        db_mode=db_mode,
        active_sessions=store.active_count,
    )

"""Chat API routes"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse

from legal_chatbot.api.auth import get_current_user, is_anonymous_user, _is_auth_disabled, get_device_id, device_id_to_uuid

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

logger = logging.getLogger(__name__)

router = APIRouter()

# Global session store — initialized in app.py lifespan
store: SessionStore = SessionStore()

# Directory where contracts/PDFs are stored
CONTRACTS_DIR = Path("data/contracts")

# Free question limit for anonymous users
FREE_QUESTION_LIMIT = 2  # TODO: set back to 4 after testing


def _get_allowed_user_ids(request: Request, user_id: str) -> set[str]:
    """Get all user IDs that should be allowed access (real user + device UUID)."""
    allowed = {user_id}
    did = get_device_id(request)
    if did:
        allowed.add(device_id_to_uuid(did))
    return allowed


def _check_anonymous_limit(request: Request):
    """Raise 429 if anonymous user exceeded free question limit.

    Only enforced when AUTH_DISABLED=true (anonymous/demo mode).
    Authenticated users (real JWT) are never limited.
    Always counts by device_uuid so the count persists even after migration/logout.
    """
    if not _is_auth_disabled():
        return  # auth enabled — all users have real JWT, no limit
    # Skip limit if user has a valid Authorization header (logged in)
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer ") and len(auth_header) > 20:
        return  # has JWT token — authenticated user, no limit
    if not store.db:
        return
    # Always count by device_uuid (not user_id) — survives migration/logout

    device_id = get_device_id(request)
    if not device_id:
        return  # no device tracking, skip
    device_uuid = device_id_to_uuid(device_id)
    count = store.db.count_user_messages(device_uuid)
    if count >= FREE_QUESTION_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Bạn đã sử dụng hết câu hỏi miễn phí. Vui lòng đăng ký để tiếp tục.",
        )


def _postprocess_llm_response(text: str) -> str:
    """Clean up formatting issues from non-Claude models (DeepSeek etc).

    Fixes:
    - ### markdown headings → bold text
    - --- horizontal rules → remove
    - <QUOTE> → [QUOTE]
    - Orphan [/SECTION] tags → remove
    - [QUOTE] not on its own line → fix for frontend parser
    """
    import re

    # 1. Remove markdown headings → bold text
    text = re.sub(r'^#{1,6}\s+(.+)$', r'**\1**', text, flags=re.MULTILINE)

    # 2. Remove horizontal rules (---, ___, ***, ===, ———)
    text = re.sub(r'^\s*[-_*=—]{3,}\s*$', '', text, flags=re.MULTILINE)

    # 3. Fix <QUOTE> → [QUOTE]
    text = text.replace('<QUOTE>', '[QUOTE]').replace('</QUOTE>', '[/QUOTE]')

    # 4. Fix "- [QUOTE]" → remove list dash before [QUOTE]
    text = re.sub(r'^(\s*)[-•]\s*\[QUOTE\]', r'\1[QUOTE]', text, flags=re.MULTILINE)

    # 5. Ensure [QUOTE] and [/QUOTE] are on their own lines
    text = re.sub(r'([^\n])\[QUOTE\]', r'\1\n[QUOTE]', text)
    # Remove stray punctuation right after [/QUOTE]
    text = re.sub(r'\[/QUOTE\]\s*([.),;:]+)', r'[/QUOTE]', text)
    # Remove parenthetical source after [/QUOTE] like "(Luật Đất đai 2024)"
    text = re.sub(r'\[/QUOTE\]\s*\([^)]*\)', r'[/QUOTE]', text)
    text = re.sub(r'\[/QUOTE\]([^\n])', r'[/QUOTE]\n\1', text)

    # 6. Remove lone list markers (dash/bullet on a line by itself)
    text = re.sub(r'^\s*[-•]\s*$', '', text, flags=re.MULTILINE)

    # 7. Fix nested [SECTION] — close open section before opening new one
    lines = text.split('\n')
    fixed_lines = []
    section_depth = 0
    for line in lines:
        stripped = line.strip()
        if re.match(r'\[SECTION:', stripped):
            while section_depth > 0:
                fixed_lines.append('[/SECTION]')
                section_depth -= 1
            fixed_lines.append(line)
            section_depth += 1
        elif stripped == '[/SECTION]':
            if section_depth > 0:
                fixed_lines.append(line)
                section_depth -= 1
        else:
            fixed_lines.append(line)
    while section_depth > 0:
        fixed_lines.append('[/SECTION]')
        section_depth -= 1
    text = '\n'.join(fixed_lines)

    # 8. Clean up multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def _friendly_error(exc: Exception) -> str:
    """Map raw API/LLM exceptions to user-friendly Vietnamese messages."""
    err_str = str(exc).lower()

    if "prompt is too long" in err_str or "too many tokens" in err_str:
        return (
            "Câu hỏi của bạn kèm ngữ cảnh quá dài, mình không xử lý được. "
            "Bạn thử hỏi ngắn gọn hơn hoặc bắt đầu cuộc trò chuyện mới nhé!"
        )
    if "rate_limit" in err_str or "rate limit" in err_str or "429" in err_str:
        return (
            "Hệ thống đang bận, bạn vui lòng đợi vài giây rồi thử lại nhé!"
        )
    if "authentication" in err_str or "401" in err_str or "api_key" in err_str:
        return "Hệ thống gặp lỗi xác thực. Vui lòng liên hệ quản trị viên."
    if "timeout" in err_str or "timed out" in err_str:
        return (
            "Yêu cầu mất quá nhiều thời gian. Bạn thử lại hoặc hỏi câu ngắn hơn nhé!"
        )
    if "connection" in err_str or "network" in err_str:
        return "Không thể kết nối đến máy chủ AI. Vui lòng thử lại sau."

    # Generic fallback — no raw error details
    return "Xin lỗi, mình gặp trục trặc khi xử lý. Bạn thử lại nhé!"


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
        # Show only top 6 common contract types to avoid UI clutter
        if available_types:
            suggestions.extend(t["name"] for t in available_types[:6])
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
async def chat(raw_request: Request, request: ChatRequest, user_id: str = Depends(get_current_user)):
    """Main chat endpoint — natural language router to all services"""
    _check_anonymous_limit(raw_request)
    entry = await store.get_or_create(request.session_id, user_id=user_id)

    try:
        response = await entry.service.chat(request.message)
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=_friendly_error(e))

    # Persist messages to Supabase (non-blocking, best-effort)
    pdf_url = _pdf_path_to_url(response.pdf_path)
    await store.persist_messages(
        entry.session_id, request.message, response.message,
        pdf_url=pdf_url, user_id=user_id,
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
async def chat_stream(raw_request: Request, request: ChatRequest, user_id: str = Depends(get_current_user)):
    """SSE streaming chat — sends tokens as they're generated.

    Events:
      data: {"type":"session","session_id":"..."}
      data: {"type":"token","text":"..."}
      data: {"type":"done","message":"...","suggestions":[...]}
    """
    _check_anonymous_limit(raw_request)
    entry = await store.get_or_create(request.session_id, user_id=user_id)
    service = entry.service
    session = service.get_session()

    # Let the service decide: stream (legal Q&A) vs non-stream (contract, commands)
    use_streaming = service.should_stream(request.message)

    if not use_streaming:
        # Use service.chat() for contract interactions (handles all routing internally)
        try:
            response = await service.chat(request.message)
        except Exception as e:
            logger.error(f"Chat stream (non-stream path) error: {e}", exc_info=True)
            friendly = _friendly_error(e)

            async def error_stream():
                yield f"data: {json.dumps({'type': 'session', 'session_id': entry.session_id})}\n\n"
                yield f"data: {json.dumps({'type': 'token', 'text': friendly})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'message': friendly, 'action': None, 'session_info': _build_session_info(entry).model_dump(), 'suggestions': []})}\n\n"

            return StreamingResponse(error_stream(), media_type="text/event-stream")

        pdf_url = _pdf_path_to_url(response.pdf_path)
        await store.persist_messages(
            entry.session_id, request.message, response.message,
            pdf_url=pdf_url, user_id=user_id,
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
            logger.error(f"LLM streaming error: {e}", exc_info=True)
            full_text = _friendly_error(e)
            yield f"data: {json.dumps({'type': 'token', 'text': full_text})}\n\n"

        # Post-process: clean up formatting issues from non-Claude models
        full_text = _postprocess_llm_response(full_text)

        # Save to session + DB
        session.messages.append({"role": "assistant", "content": full_text})
        await store.persist_messages(entry.session_id, request.message, full_text, user_id=user_id)

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
async def list_sessions(raw_request: Request, user_id: str = Depends(get_current_user)):
    """List all chat sessions (from Supabase).

    For authenticated users, also include sessions from their device_id
    (anonymous sessions created before login).
    """
    if not store.db:
        return SessionListResponse(sessions=[])

    try:
    
        user_ids = [user_id]
        # Also include device-based sessions for authenticated users
        device_id = get_device_id(raw_request)
        if device_id:
            device_uuid = device_id_to_uuid(device_id)
            if device_uuid != user_id:
                user_ids.append(device_uuid)
        sessions = store.db.list_chat_sessions(limit=50, user_ids=user_ids)
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
async def get_session_messages(raw_request: Request, session_id: str, user_id: str = Depends(get_current_user)):
    """Get all messages for a chat session"""
    if not store.db:
        raise HTTPException(status_code=503, detail="Database không khả dụng")

    # Verify session ownership (allow both real user_id and device_uuid)
    session = store.db.get_chat_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session không tồn tại")
    if not is_anonymous_user(user_id) and session.get("user_id") not in _get_allowed_user_ids(raw_request, user_id):
        raise HTTPException(status_code=404, detail="Session không tồn tại")

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
async def update_session(raw_request: Request, session_id: str, request: SessionUpdateRequest, user_id: str = Depends(get_current_user)):
    """Update session metadata (e.g. rename title)"""
    if not store.db:
        raise HTTPException(status_code=503, detail="Database không khả dụng")

    # Verify session ownership
    session = store.db.get_chat_session(session_id)
    if not session or (not is_anonymous_user(user_id) and session.get("user_id") not in _get_allowed_user_ids(raw_request, user_id)):
        raise HTTPException(status_code=404, detail="Session không tồn tại")

    try:
        update_kwargs = {}
        if request.title:
            update_kwargs["title"] = request.title
        store.db.update_chat_session(session_id, **update_kwargs)
        return {"message": "Đã cập nhật session", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi cập nhật: {e}")


@router.delete("/api/sessions/{session_id}")
async def delete_session(raw_request: Request, session_id: str, user_id: str = Depends(get_current_user)):
    """Delete a chat session"""
    # Verify session ownership before deleting
    if store.db:
        session = store.db.get_chat_session(session_id)
        if not session or (not is_anonymous_user(user_id) and session.get("user_id") not in _get_allowed_user_ids(raw_request, user_id)):
            raise HTTPException(status_code=404, detail="Session không tồn tại")

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


@router.post("/api/sessions/migrate")
async def migrate_sessions(request: Request, user_id: str = Depends(get_current_user)):
    """Migrate anonymous sessions to authenticated user.

    Called after magic-link login. Transfers all sessions created with
    the device_id to the now-authenticated user_id.
    """
    # Only works for authenticated users (not anonymous)
    if is_anonymous_user(user_id):
        return {"migrated": 0, "message": "Cần đăng nhập để migrate sessions"}

    device_id = get_device_id(request)
    if not device_id or not store.db:
        return {"migrated": 0}

    try:
        old_user_id = device_id_to_uuid(device_id)
        count = store.db.migrate_chat_sessions(old_user_id, user_id)
        return {"migrated": count, "message": f"Đã chuyển {count} cuộc hội thoại"}
    except Exception as e:
        logger.error(f"Session migration error: {e}")
        return {"migrated": 0, "error": str(e)}


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

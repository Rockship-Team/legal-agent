"""Contract Form API routes — create, submit, and edit contracts via form UI."""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from legal_chatbot.api.schemas import (
    ContractCreateRequest,
    ContractCreateResponse,
    ContractFieldGroup,
    ContractFieldItem,
    ContractSubmitRequest,
    ContractSubmitResponse,
    ContractTemplateItem,
    ContractTemplatesResponse,
)
from legal_chatbot.api.session_store import SessionStore

logger = logging.getLogger(__name__)

router = APIRouter()

# Shared session store — initialized in app.py, set via init_store()
store: SessionStore = SessionStore()


def init_store(shared_store: SessionStore):
    """Set the shared session store (called from app.py)."""
    global store
    store = shared_store


def _pdf_path_to_url(pdf_path: str | None) -> str | None:
    """Convert PDF path to /api/files/{filename} download URL."""
    if not pdf_path:
        return None
    if pdf_path.startswith("https://") or pdf_path.startswith("http://"):
        url_path = pdf_path.split("?")[0]
        filename = url_path.split("/")[-1]
        return f"/api/files/{filename}"
    filename = Path(pdf_path).name
    return f"/api/files/{filename}"


@router.get("/api/contract/templates", response_model=ContractTemplatesResponse)
async def list_templates():
    """List available contract templates from DB."""
    # Use a temporary service to access DB
    from legal_chatbot.services.interactive_chat import InteractiveChatService
    service = InteractiveChatService(api_mode=True)

    try:
        available = service._get_available_contract_types()
        templates = []
        for t in available:
            # Load template to get field count
            try:
                tmpl = service._load_template_from_db(t["type"])
                field_count = len([f for f in tmpl.fields if f.required])
                description = tmpl.description
            except Exception:
                field_count = 0
                description = ""

            templates.append(ContractTemplateItem(
                type=t["type"],
                name=t["name"],
                description=description,
                field_count=field_count,
            ))
        return ContractTemplatesResponse(templates=templates)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tải danh sách mẫu: {e}")


@router.post("/api/contract/create", response_model=ContractCreateResponse)
async def create_contract(request: ContractCreateRequest):
    """Create a contract draft and return field definitions for the form.

    If the session already has a draft (e.g. fields partially filled via chat),
    returns the existing draft with its current field_values instead of creating
    a new one.
    """
    entry = await store.get_or_create(request.session_id)
    service = entry.service

    # Check if session already has a draft for this contract type
    session = service.get_session()
    existing_draft = session.current_draft if session else None

    if existing_draft and existing_draft.template:
        # Return existing draft with its field_values (partially filled via chat)
        field_groups = _build_field_groups(existing_draft.template)
        return ContractCreateResponse(
            session_id=entry.session_id,
            draft_id=existing_draft.id,
            contract_type=existing_draft.contract_type,
            contract_name=existing_draft.template.name,
            field_groups=field_groups,
            field_values=existing_draft.field_values or {},
        )

    # Resolve contract type
    resolved_slug = await service._resolve_contract_type(request.contract_type)
    if not resolved_slug:
        available = service._get_available_contract_types()
        if available:
            type_list = ", ".join(t["name"] for t in available)
            raise HTTPException(
                status_code=400,
                detail=f"Không nhận diện được loại hợp đồng. Hiện tại hỗ trợ: {type_list}"
            )
        raise HTTPException(status_code=400, detail="Chưa có mẫu hợp đồng nào.")

    # Load template
    try:
        template = service._load_template_from_db(resolved_slug)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Create draft in session
    from uuid import uuid4
    from legal_chatbot.services.interactive_chat import ContractDraft

    draft = ContractDraft(
        id=str(uuid4()),
        contract_type=resolved_slug,
        template=template,
        field_values={},
        legal_basis=template.legal_references,
        current_field_index=0,
        state='collecting'
    )
    session.current_draft = draft
    session.mode = 'contract_creation'

    # Build field groups from template
    field_groups = _build_field_groups(template)

    return ContractCreateResponse(
        session_id=entry.session_id,
        draft_id=draft.id,
        contract_type=resolved_slug,
        contract_name=template.name,
        field_groups=field_groups,
        field_values={},
    )


@router.post("/api/contract/submit", response_model=ContractSubmitResponse)
async def submit_contract(request: ContractSubmitRequest):
    """Submit all field values and generate PDF."""
    entry = await store.get_or_create(request.session_id)
    session = entry.service.session

    if not session or not session.current_draft:
        raise HTTPException(status_code=404, detail="Không tìm thấy hợp đồng đang soạn.")

    draft = session.current_draft
    if draft.id != request.draft_id:
        raise HTTPException(status_code=404, detail="Draft ID không khớp.")

    # Set all field values
    draft.field_values = request.field_values
    draft.state = 'ready'
    draft.current_field_index = len(draft.template.fields)
    session.mode = 'normal'

    # Generate PDF
    response = entry.service._finalize_contract(draft)
    pdf_url = _pdf_path_to_url(response.pdf_path)

    # Persist to DB
    await store.persist_messages(
        entry.session_id,
        f"Tạo {draft.template.name}",
        response.message,
        pdf_url=pdf_url,
    )

    return ContractSubmitResponse(
        session_id=entry.session_id,
        draft_id=draft.id,
        message=response.message,
        pdf_url=pdf_url,
        field_values=draft.field_values,
    )


@router.patch("/api/contract/submit", response_model=ContractSubmitResponse)
async def update_contract(request: ContractSubmitRequest):
    """Update fields and regenerate PDF."""
    entry = await store.get_or_create(request.session_id)
    session = entry.service.session

    if not session or not session.current_draft:
        raise HTTPException(status_code=404, detail="Không tìm thấy hợp đồng đang soạn.")

    draft = session.current_draft
    if draft.id != request.draft_id:
        raise HTTPException(status_code=404, detail="Draft ID không khớp.")

    # Merge new field values into existing
    draft.field_values.update(request.field_values)
    draft.state = 'ready'
    # Clear previously generated articles so they get regenerated
    draft.articles = []

    # Regenerate PDF
    response = entry.service._finalize_contract(draft)
    pdf_url = _pdf_path_to_url(response.pdf_path)

    # Persist update
    await store.persist_messages(
        entry.session_id,
        f"Cập nhật {draft.template.name}",
        response.message,
        pdf_url=pdf_url,
    )

    return ContractSubmitResponse(
        session_id=entry.session_id,
        draft_id=draft.id,
        message="Đã cập nhật hợp đồng!",
        pdf_url=pdf_url,
        field_values=draft.field_values,
    )


def _build_field_groups(template) -> list[ContractFieldGroup]:
    """Build field groups from a DynamicTemplate.

    Uses template.field_groups if available (from DB JSONB),
    otherwise groups by field name prefix (ben_a_, ben_b_, etc.).
    """
    # Try DB-defined groups first
    if template.field_groups:
        return _groups_from_db(template)

    # Fallback: group by field name prefix
    return _groups_from_prefix(template)


def _groups_from_db(template) -> list[ContractFieldGroup]:
    """Build groups from template.field_groups (DB JSONB)."""
    groups = []
    used_fields = set()

    for group_def in template.field_groups:
        group_name = group_def.get("group", "Khác")
        prefix = group_def.get("prefix", "")
        field_items = []

        for field in template.fields:
            if prefix and field.name.startswith(prefix):
                field_items.append(_field_to_item(field))
                used_fields.add(field.name)

        if field_items:
            groups.append(ContractFieldGroup(group=group_name, fields=field_items))

    # Also process common_groups
    for group_def in template.common_groups:
        group_name = group_def.get("group", "Khác")
        prefix = group_def.get("prefix", "")
        field_items = []

        for field in template.fields:
            if field.name not in used_fields and prefix and field.name.startswith(prefix):
                field_items.append(_field_to_item(field))
                used_fields.add(field.name)

        if field_items:
            groups.append(ContractFieldGroup(group=group_name, fields=field_items))

    # Remaining ungrouped fields
    remaining = [f for f in template.fields if f.name not in used_fields]
    if remaining:
        groups.append(ContractFieldGroup(
            group="Thông tin khác",
            fields=[_field_to_item(f) for f in remaining],
        ))

    return groups


def _groups_from_prefix(template) -> list[ContractFieldGroup]:
    """Fallback grouping by field name prefix."""
    prefix_map = {
        "ben_a_": "Bên A",
        "ben_b_": "Bên B",
        "tai_san_": "Thông tin tài sản",
        "nha_": "Thông tin nhà",
        "dat_": "Thông tin đất",
    }

    groups_dict: dict[str, list[ContractFieldItem]] = {}
    used = set()

    for prefix, group_name in prefix_map.items():
        items = []
        for field in template.fields:
            if field.name.startswith(prefix):
                items.append(_field_to_item(field))
                used.add(field.name)
        if items:
            groups_dict[group_name] = items

    # Remaining fields
    remaining = [_field_to_item(f) for f in template.fields if f.name not in used]
    if remaining:
        groups_dict["Điều khoản hợp đồng"] = remaining

    return [
        ContractFieldGroup(group=name, fields=fields)
        for name, fields in groups_dict.items()
    ]


def _field_to_item(field) -> ContractFieldItem:
    """Convert DynamicField to ContractFieldItem."""
    return ContractFieldItem(
        name=field.name,
        label=field.label,
        field_type=field.field_type,
        required=field.required,
        description=field.description,
        default_value=field.default_value,
    )

"""Request/response schemas for the Chat API"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Chat request from client"""
    message: str = Field(..., min_length=1, max_length=2000, description="Vietnamese natural language message")
    session_id: Optional[str] = Field(None, description="Session ID. None = create new session")


class SessionInfo(BaseModel):
    """Current session state info"""
    session_id: str
    mode: str = "normal"  # "normal" | "contract_creation"
    current_field: Optional[str] = None
    fields_completed: int = 0
    fields_total: int = 0
    contract_type: Optional[str] = None


class ChatAPIResponse(BaseModel):
    """Unified chat API response"""
    session_id: str
    message: str
    action: Optional[str] = None
    session_info: SessionInfo
    suggestions: list[str] = []
    has_contract: bool = False
    html_preview: Optional[str] = None
    pdf_url: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class SessionListItem(BaseModel):
    """A session in the session list"""
    session_id: str
    title: str = "Cuộc hội thoại mới"
    created_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None


class SessionListResponse(BaseModel):
    """Response for listing sessions"""
    sessions: list[SessionListItem] = []


class MessageItem(BaseModel):
    """A single chat message"""
    id: str
    role: str
    content: str
    created_at: Optional[datetime] = None
    pdf_url: Optional[str] = None


class SessionMessagesResponse(BaseModel):
    """Response for getting session messages"""
    session_id: str
    messages: list[MessageItem] = []


class SessionUpdateRequest(BaseModel):
    """Request to update a session (e.g. rename)"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)


# =========================================================
# Contract Form API schemas
# =========================================================

class ContractTemplateItem(BaseModel):
    """A contract template in the templates list"""
    type: str
    name: str
    description: str = ""
    field_count: int = 0


class ContractTemplatesResponse(BaseModel):
    """Response for listing contract templates"""
    templates: list[ContractTemplateItem] = []


class ContractFieldItem(BaseModel):
    """A single field in a contract form"""
    name: str
    label: str
    field_type: str = "text"  # text, date, number, textarea
    required: bool = True
    description: Optional[str] = None
    default_value: Optional[str] = None


class ContractFieldGroup(BaseModel):
    """A group of fields (e.g. 'Bên A', 'Bên B', 'Thông tin tài sản')"""
    group: str
    fields: list[ContractFieldItem]


class ContractCreateRequest(BaseModel):
    """Request to create a contract draft via form"""
    session_id: Optional[str] = None
    contract_type: str


class ContractCreateResponse(BaseModel):
    """Response with field definitions for the form"""
    session_id: str
    draft_id: str
    contract_type: str
    contract_name: str
    field_groups: list[ContractFieldGroup]
    field_values: dict[str, str] = {}


class ContractSubmitRequest(BaseModel):
    """Submit all field values (POST) or partial update (PATCH)"""
    session_id: str
    draft_id: str
    field_values: dict[str, str]


class ContractSubmitResponse(BaseModel):
    """Response after submit/update with PDF URL"""
    session_id: str
    draft_id: str
    message: str
    pdf_url: Optional[str] = None
    field_values: dict[str, str] = {}


class HealthResponse(BaseModel):
    """Health check response"""
    status: str  # "ok" | "error"
    db_mode: str
    version: str = "0.1.0"
    active_sessions: int = 0

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


class HealthResponse(BaseModel):
    """Health check response"""
    status: str  # "ok" | "error"
    db_mode: str
    version: str = "0.1.0"
    active_sessions: int = 0

"""Chat-related models"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class MessageRole(str, Enum):
    """Role of a chat message sender"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Citation(BaseModel):
    """A citation to a legal article"""
    article_id: str
    article_number: int
    document_title: str
    relevance_score: float = 0.0
    excerpt: Optional[str] = None


class ChatMessage(BaseModel):
    """A single chat message"""
    id: str
    session_id: str
    role: MessageRole
    content: str
    citations: list[Citation] = []
    created_at: datetime = datetime.now()


class ChatSession(BaseModel):
    """A chat session with history"""
    id: str
    created_at: datetime = datetime.now()
    last_message_at: Optional[datetime] = None
    context: dict = {}  # Collected user data


class ChatResponse(BaseModel):
    """Response from the chat agent"""
    answer: str
    citations: list[Citation] = []
    suggested_templates: list[str] = []
    follow_up_questions: list[str] = []
    has_data: bool = True               # False when no data available for category
    category: Optional[str] = None      # Detected legal category


class SearchResult(BaseModel):
    """A search result from the knowledge base"""
    article: "ArticleWithContext"
    score: float
    highlights: list[str] = []


# Import ArticleWithContext to avoid circular import
from legal_chatbot.models.document import ArticleWithContext
SearchResult.model_rebuild()

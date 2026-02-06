"""Legal document models"""

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class DocumentType(str, Enum):
    """Types of legal documents"""
    BO_LUAT = "bo_luat"      # Code (e.g., Civil Code)
    LUAT = "luat"            # Law
    NGHI_DINH = "nghi_dinh"  # Decree
    THONG_TU = "thong_tu"    # Circular


class DocumentStatus(str, Enum):
    """Status of legal documents"""
    ACTIVE = "active"
    AMENDED = "amended"
    REPEALED = "repealed"


class LegalDocument(BaseModel):
    """A legal document (law, decree, etc.)"""
    id: str
    document_type: DocumentType
    document_number: str
    title: str
    effective_date: Optional[date] = None
    issuing_authority: Optional[str] = None
    source_url: Optional[str] = None
    status: DocumentStatus = DocumentStatus.ACTIVE
    raw_content: Optional[str] = None
    crawled_at: Optional[datetime] = None


class Article(BaseModel):
    """An article (Điều) within a legal document"""
    id: str
    document_id: str
    article_number: int
    title: Optional[str] = None
    content: str
    chapter: Optional[str] = None


class ArticleWithContext(Article):
    """Article with document context for display"""
    document_title: str
    document_type: DocumentType
    effective_date: Optional[date] = None

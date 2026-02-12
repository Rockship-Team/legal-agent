"""Legal document models"""

from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class DocumentType(str, Enum):
    """Types of legal documents"""
    BO_LUAT = "bo_luat"
    LUAT = "luat"
    NGHI_DINH = "nghi_dinh"
    THONG_TU = "thong_tu"
    QUYET_DINH = "quyet_dinh"
    NGHI_QUYET = "nghi_quyet"


class DocumentStatus(str, Enum):
    """Status of legal documents"""
    ACTIVE = "active"
    AMENDED = "amended"
    REPEALED = "repealed"
    EXPIRED = "expired"


class RelationType(str, Enum):
    """Types of document relationships"""
    REPLACES = "replaces"
    AMENDS = "amends"
    GUIDES = "guides"
    REFERENCES = "references"


class LegalCategory(BaseModel):
    """A legal category for organizing documents"""
    id: str = ""
    name: str
    display_name: str
    description: Optional[str] = None
    crawl_url: Optional[str] = None
    last_crawled_at: Optional[datetime] = None
    crawl_interval_hours: int = 168
    is_active: bool = True


class LegalDocument(BaseModel):
    """A legal document (law, decree, etc.)"""
    id: str = ""
    category_id: Optional[str] = None
    document_type: DocumentType
    document_number: str
    title: str
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    issuing_authority: Optional[str] = None
    source_url: Optional[str] = None
    raw_storage_path: Optional[str] = None
    status: DocumentStatus = DocumentStatus.ACTIVE
    replaces_document_id: Optional[str] = None
    amended_by_document_id: Optional[str] = None
    metadata: dict = {}
    content_hash: Optional[str] = None
    raw_content: Optional[str] = None
    crawled_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Article(BaseModel):
    """An article (Điều) within a legal document"""
    id: str = ""
    document_id: str
    article_number: int
    title: Optional[str] = None
    content: str
    chapter: Optional[str] = None
    section: Optional[str] = None
    part: Optional[str] = None
    embedding: Optional[List[float]] = None
    content_hash: Optional[str] = None
    chunk_index: int = 0


class ArticleWithContext(Article):
    """Article with document context for display"""
    document_title: str = ""
    document_type: DocumentType = DocumentType.LUAT
    document_number: str = ""
    effective_date: Optional[date] = None
    category_name: Optional[str] = None
    similarity: Optional[float] = None


class DocumentRelation(BaseModel):
    """Relationship between two legal documents"""
    id: str = ""
    source_document_id: str
    target_document_id: str
    relation_type: RelationType
    description: Optional[str] = None

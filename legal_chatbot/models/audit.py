"""Audit trail models for research and contract verification"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class LawVersion(BaseModel):
    """Version of a law used in a response"""
    document_id: str
    document_number: str
    title: str
    effective_date: Optional[str] = None
    status: str = "active"


class ArticleSource(BaseModel):
    """Article used as source in a response"""
    article_id: str
    article_number: int
    document_title: str
    similarity: float


class ResearchAudit(BaseModel):
    """Audit trail for a research/chat response"""
    id: str = ""
    session_id: Optional[str] = None
    query: str
    sources: List[ArticleSource] = []
    response: str = ""
    law_versions: List[LawVersion] = []
    confidence_score: Optional[float] = None
    created_at: Optional[datetime] = None


class ContractAudit(BaseModel):
    """Audit trail for a generated contract"""
    id: str = ""
    session_id: Optional[str] = None
    contract_type: str
    input_data: dict = {}
    generated_content: str = ""
    legal_references: List[ArticleSource] = []
    law_versions: List[LawVersion] = []
    pdf_storage_path: Optional[str] = None
    created_at: Optional[datetime] = None

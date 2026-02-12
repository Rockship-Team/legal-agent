"""Pipeline models for data ingestion"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class PipelineStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CategoryConfig(BaseModel):
    """Configuration for crawling a legal category"""
    name: str
    display_name: str
    description: str = ""
    crawl_url: str
    document_urls: List[str] = []
    max_pages: int = 20
    rate_limit_seconds: float = 4.0


class CrawlResult(BaseModel):
    """Result of crawling a single document"""
    url: str
    document_number: str
    title: str
    document_type: str
    effective_date: Optional[str] = None
    issuing_authority: Optional[str] = None
    status: str = "active"
    html_content: str = ""
    content_hash: str = ""
    is_new: bool = True
    articles_count: int = 0


class PipelineRun(BaseModel):
    """Record of a pipeline execution"""
    id: str = ""
    category_id: Optional[str] = None
    status: PipelineStatus = PipelineStatus.RUNNING
    documents_found: int = 0
    documents_new: int = 0
    documents_updated: int = 0
    articles_indexed: int = 0
    embeddings_generated: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

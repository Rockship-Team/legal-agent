"""Contract-related models for DB-only contract creation."""

from typing import List, Optional

from pydantic import BaseModel


class ContractTemplate(BaseModel):
    """Pre-configured contract template from DB."""
    id: Optional[str] = None
    category_id: str
    contract_type: str              # 'mua_ban_dat', 'cho_thue_nha'
    display_name: str               # 'Hợp đồng mua bán đất'
    description: Optional[str] = None
    search_queries: List[str]       # Pre-mapped vector search terms
    required_laws: List[str] = []   # Expected law documents
    min_articles: int = 5
    required_fields: Optional[dict] = None  # User data template
    article_outline: Optional[List[str]] = None  # ĐIỀU 1-9 skeleton
    is_active: bool = True


class CategoryInfo(BaseModel):
    """Category info for availability responses."""
    name: str
    display_name: str
    article_count: int = 0
    document_count: int = 0
    contract_types: List[str] = []


class DataAvailability(BaseModel):
    """Result of data availability check."""
    category: Optional[str] = None
    has_data: bool = False
    article_count: int = 0
    document_count: int = 0
    available_categories: List[CategoryInfo] = []
    available_contract_types: List[str] = []

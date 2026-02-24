"""Contract template models for DB-driven template system.

Models are used by interactive_chat.py for field collection flow.
Template data is loaded from Supabase contract_templates table (not hardcoded).
"""

from typing import Optional

from pydantic import BaseModel

class DynamicField(BaseModel):
    """A field in a contract template"""
    name: str
    label: str
    field_type: str = "text"
    required: bool = True
    default_value: Optional[str] = None
    description: Optional[str] = None
    legal_basis: Optional[str] = None


class LegalArticle(BaseModel):
    """A legal article with full content"""
    article_number: str
    article_title: str
    document_name: str
    content: str
    summary: str = ""


class DynamicTemplate(BaseModel):
    """Contract template loaded from Supabase contract_templates table.

    Fields:
        field_groups: Type-specific prefix→section mappings from DB
        common_groups: Shared financial/timeline field groups from DB
    """
    contract_type: str
    name: str
    description: str
    fields: list[DynamicField]
    legal_references: list[str] = []
    legal_articles: list[LegalArticle] = []
    generated_from: str = ""
    key_terms: list[str] = []
    field_groups: list[dict] = []
    common_groups: list[dict] = []



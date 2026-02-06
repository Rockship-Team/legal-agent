"""Contract template models"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class TemplateType(str, Enum):
    """Types of contract templates"""
    RENTAL = "rental"           # Hợp đồng thuê nhà
    SALE = "sale"               # Hợp đồng mua bán
    SERVICE = "service"         # Hợp đồng dịch vụ
    EMPLOYMENT = "employment"   # Hợp đồng lao động


class ContractField(BaseModel):
    """A field in a contract template"""
    name: str
    label: str
    field_type: str  # 'text', 'date', 'number', 'address', 'enum'
    required: bool = True
    default_value: Optional[str] = None
    validation: Optional[str] = None  # regex pattern


class ContractTemplate(BaseModel):
    """A contract template"""
    id: str
    template_type: TemplateType
    name: str
    description: str
    required_fields: list[ContractField]
    legal_references: list[str] = []  # Article IDs
    version: int = 1


class GeneratedContract(BaseModel):
    """A generated contract document"""
    template_id: str
    filled_fields: dict
    output_path: str
    generated_at: datetime = datetime.now()
    disclaimer: str = "Văn bản này chỉ mang tính chất tham khảo"

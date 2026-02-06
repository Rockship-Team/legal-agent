# Document Generator Module Contract

## Overview
The Document Generator creates PDF contracts and legal documents from templates.

## Interface

### DocumentGeneratorService

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from pydantic import BaseModel
from pathlib import Path

class TemplateField(BaseModel):
    name: str
    label: str
    field_type: str  # 'text', 'date', 'number', 'address', 'enum'
    required: bool = True
    default_value: Optional[str] = None
    validation: Optional[str] = None  # regex pattern

class Template(BaseModel):
    id: str
    type: str
    name: str
    description: str
    fields: List[TemplateField]
    legal_references: List[str]

class GenerationResult(BaseModel):
    success: bool
    output_path: Optional[Path]
    error: Optional[str]
    warnings: List[str]

class DocumentGeneratorService(ABC):
    @abstractmethod
    def list_templates(self, template_type: Optional[str] = None) -> List[Template]:
        """
        List available contract templates.

        Optionally filter by type (rental, sale, service, employment).
        """
        pass

    @abstractmethod
    def get_template(self, template_id: str) -> Template:
        """
        Get template details including required fields.
        """
        pass

    @abstractmethod
    def validate_data(self, template_id: str, data: Dict) -> List[str]:
        """
        Validate input data against template requirements.

        Returns list of validation errors (empty if valid).
        """
        pass

    @abstractmethod
    def generate(
        self,
        template_id: str,
        data: Dict,
        output_path: Path,
        options: Optional[Dict] = None
    ) -> GenerationResult:
        """
        Generate PDF document from template and data.

        Options:
        - watermark: bool (add DRAFT watermark)
        - include_disclaimer: bool (add legal disclaimer)
        - page_size: str (A4, Letter)
        """
        pass
```

## CLI Contract

```bash
# List available templates
legal-chatbot templates
╭─ Available Templates ─────────────────────────────────────╮
│ rental     - Hợp đồng thuê nhà                            │
│ sale       - Hợp đồng mua bán                             │
│ service    - Hợp đồng dịch vụ                             │
│ employment - Hợp đồng lao động                            │
╰───────────────────────────────────────────────────────────╯

# Show template fields
legal-chatbot template rental --fields
╭─ Hợp đồng thuê nhà ───────────────────────────────────────╮
│ Required fields:                                           │
│ - landlord_name: Tên bên cho thuê (text)                  │
│ - landlord_id: CCCD bên cho thuê (text)                   │
│ - tenant_name: Tên bên thuê (text)                        │
│ - tenant_id: CCCD bên thuê (text)                         │
│ - property_address: Địa chỉ nhà (address)                 │
│ - monthly_rent: Tiền thuê hàng tháng (number)             │
│ - deposit: Tiền đặt cọc (number)                          │
│ - start_date: Ngày bắt đầu (date)                         │
│ - duration_months: Thời hạn thuê (number)                 │
╰───────────────────────────────────────────────────────────╯

# Generate document
legal-chatbot generate --template rental --output contract.pdf \
  --data '{"landlord_name": "Nguyễn Văn A", ...}'

# Interactive mode (collects data via prompts)
legal-chatbot generate --template rental --interactive

# Output
✓ Contract generated: ./contract.pdf
⚠ Disclaimer: Văn bản này chỉ mang tính chất tham khảo
```

## Template Structure

```python
# templates/rental.json
{
    "id": "rental_v1",
    "type": "rental",
    "name": "Hợp đồng thuê nhà",
    "description": "Mẫu hợp đồng thuê nhà ở theo Luật Nhà ở 2014",
    "fields": [
        {
            "name": "landlord_name",
            "label": "Tên bên cho thuê",
            "field_type": "text",
            "required": true
        },
        {
            "name": "landlord_id",
            "label": "Số CCCD bên cho thuê",
            "field_type": "text",
            "required": true,
            "validation": "^[0-9]{12}$"
        },
        // ... more fields
    ],
    "legal_references": [
        "article_luat_nha_o_2014_121",
        "article_blds_2015_472"
    ],
    "content_template": "..."  // PDF generation template
}
```

## PDF Generation Flow

```
Template + Data
    │
    ▼
┌─────────────────┐
│ Validate Data   │ → Check required fields, formats
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ Merge Template  │ → Replace placeholders with data
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ Add Metadata    │ → Header, footer, page numbers
│ Add Disclaimer  │ → Legal disclaimer
│ Add Watermark   │ → DRAFT (optional)
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ ReportLab PDF   │ → Generate final PDF
└─────────────────┘
```

## Dependencies
- reportlab: PDF generation
- jinja2: Template rendering (optional)

## Testing Contract

```python
def test_list_templates_returns_all():
    """Should return all available templates"""
    templates = generator.list_templates()
    assert len(templates) >= 4
    types = [t.type for t in templates]
    assert "rental" in types

def test_validate_catches_missing_fields():
    """Should catch missing required fields"""
    errors = generator.validate_data("rental", {"landlord_name": "Test"})
    assert any("tenant_name" in e for e in errors)

def test_generate_creates_valid_pdf():
    """Should create valid PDF file"""
    result = generator.generate(
        "rental",
        valid_data,
        Path("./test.pdf")
    )
    assert result.success
    assert result.output_path.exists()
```

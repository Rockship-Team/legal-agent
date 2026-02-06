"""Document generator service for PDF contracts with Vietnamese support"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from legal_chatbot.models.template import ContractTemplate, ContractField, TemplateType, GeneratedContract
from legal_chatbot.utils.config import get_settings
from legal_chatbot.utils.pdf_fonts import register_vietnamese_fonts, get_font_name


class GeneratorService:
    """Service for generating PDF contracts from templates"""

    def __init__(self, templates_dir: Optional[str] = None):
        self.templates_dir = Path(templates_dir or "legal_chatbot/templates")
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self._templates: dict[str, ContractTemplate] = {}
        self._load_templates()
        # Register Vietnamese fonts on initialization
        register_vietnamese_fonts()

    def _load_templates(self):
        """Load all templates from JSON files"""
        for template_file in self.templates_dir.glob("*.json"):
            try:
                with open(template_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    template = ContractTemplate(**data)
                    self._templates[template.template_type.value] = template
            except Exception as e:
                print(f"Error loading template {template_file}: {e}")

    def list_templates(self, template_type: Optional[str] = None) -> list[ContractTemplate]:
        """List available contract templates"""
        if template_type:
            template = self._templates.get(template_type)
            return [template] if template else []
        return list(self._templates.values())

    def get_template(self, template_type: str) -> Optional[ContractTemplate]:
        """Get a specific template by type"""
        return self._templates.get(template_type)

    def validate_data(self, template_type: str, data: dict) -> list[str]:
        """
        Validate input data against template requirements.

        Returns list of validation errors (empty if valid).
        """
        template = self.get_template(template_type)
        if not template:
            return [f"Template '{template_type}' not found"]

        errors = []
        for field in template.required_fields:
            if field.required and field.name not in data:
                errors.append(f"Missing required field: {field.name} ({field.label})")

            if field.name in data and field.validation:
                import re
                if not re.match(field.validation, str(data[field.name])):
                    errors.append(f"Invalid format for {field.name}: {data[field.name]}")

        return errors

    def generate(
        self,
        template_type: str,
        data: dict,
        output_path: str,
        watermark: bool = False,
        skip_validation: bool = True,
    ) -> GeneratedContract:
        """
        Generate PDF document from template and data.
        """
        template = self.get_template(template_type)
        if not template:
            raise ValueError(f"Template '{template_type}' not found")

        # Validate data (optional)
        if not skip_validation:
            errors = self.validate_data(template_type, data)
            if errors:
                raise ValueError(f"Validation errors: {', '.join(errors)}")

        # Generate PDF
        self._generate_pdf(template, data, output_path, watermark)

        return GeneratedContract(
            template_id=template.id,
            filled_fields=data,
            output_path=output_path,
            generated_at=datetime.now(),
        )

    def _generate_pdf(
        self,
        template: ContractTemplate,
        data: dict,
        output_path: str,
        watermark: bool = False,
    ):
        """Generate the actual PDF file with Vietnamese support"""
        # Get Vietnamese fonts
        font_name = get_font_name()
        font_bold = get_font_name(bold=True)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
        )

        styles = getSampleStyleSheet()

        # Custom styles with Vietnamese font
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName=font_bold,
            fontSize=16,
            alignment=1,  # Center
            spaceAfter=20,
        )

        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=11,
            leading=16,
        )

        bold_style = ParagraphStyle(
            'CustomBold',
            parent=styles['Normal'],
            fontName=font_bold,
            fontSize=11,
            leading=16,
        )

        # Build document content
        story = []

        # Header - Vietnamese with diacritics
        story.append(Paragraph("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", title_style))
        story.append(Paragraph("Độc lập - Tự do - Hạnh phúc", normal_style))
        story.append(Spacer(1, 20))

        # Title
        story.append(Paragraph(template.name.upper(), title_style))
        story.append(Spacer(1, 10))

        # Contract parties
        if template.template_type == TemplateType.RENTAL:
            story.extend(self._build_rental_content(data, normal_style, font_name, font_bold))
        elif template.template_type == TemplateType.SALE:
            story.extend(self._build_sale_content(data, normal_style, font_name, font_bold))
        else:
            story.extend(self._build_generic_content(template, data, normal_style))

        # Signature section
        story.append(Spacer(1, 40))
        story.extend(self._build_signature_section(data, normal_style, font_name, font_bold))

        # Disclaimer
        story.append(Spacer(1, 20))
        disclaimer_style = ParagraphStyle(
            'Disclaimer',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=9,
            textColor=colors.gray,
        )
        story.append(Paragraph(
            "Lưu ý: Văn bản này chỉ mang tính chất tham khảo, không thay thế tư vấn pháp lý chuyên nghiệp.",
            disclaimer_style
        ))

        # Build PDF
        doc.build(story)

    def _build_rental_content(self, data: dict, style, font_name, font_bold) -> list:
        """Build content for rental contract - Vietnamese with diacritics"""
        content = []

        # Parties
        content.append(Paragraph("<b>BÊN CHO THUÊ (Bên A):</b>", style))
        content.append(Paragraph(f"Họ và tên: {data.get('landlord_name', '________________')}", style))
        content.append(Paragraph(f"Số CCCD: {data.get('landlord_id', '________________')}", style))
        content.append(Paragraph(f"Địa chỉ: {data.get('landlord_address', '________________')}", style))
        content.append(Spacer(1, 10))

        content.append(Paragraph("<b>BÊN THUÊ (Bên B):</b>", style))
        content.append(Paragraph(f"Họ và tên: {data.get('tenant_name', '________________')}", style))
        content.append(Paragraph(f"Số CCCD: {data.get('tenant_id', '________________')}", style))
        content.append(Paragraph(f"Địa chỉ: {data.get('tenant_address', '________________')}", style))
        content.append(Spacer(1, 20))

        # Terms
        content.append(Paragraph("<b>ĐIỀU 1: ĐỐI TƯỢNG HỢP ĐỒNG</b>", style))
        content.append(Paragraph(
            f"Bên A đồng ý cho Bên B thuê nhà tại địa chỉ: {data.get('property_address', '________________')}",
            style
        ))
        content.append(Spacer(1, 10))

        content.append(Paragraph("<b>ĐIỀU 2: THỜI HẠN THUÊ</b>", style))
        content.append(Paragraph(
            f"Thời hạn thuê là {data.get('duration_months', '____')} tháng, bắt đầu từ ngày {data.get('start_date', '____/____/____')}",
            style
        ))
        content.append(Spacer(1, 10))

        content.append(Paragraph("<b>ĐIỀU 3: GIÁ THUÊ VÀ PHƯƠNG THỨC THANH TOÁN</b>", style))
        content.append(Paragraph(
            f"Giá thuê: {data.get('monthly_rent', '________________')} đồng/tháng",
            style
        ))
        content.append(Paragraph(
            f"Tiền đặt cọc: {data.get('deposit', '________________')} đồng",
            style
        ))
        content.append(Paragraph("Phương thức thanh toán: Tiền mặt hoặc chuyển khoản vào đầu mỗi tháng.", style))
        content.append(Spacer(1, 10))

        content.append(Paragraph("<b>ĐIỀU 4: QUYỀN VÀ NGHĨA VỤ CỦA BÊN A</b>", style))
        content.append(Paragraph("- Giao nhà ở cho Bên B theo đúng thỏa thuận trong hợp đồng.", style))
        content.append(Paragraph("- Bảo đảm cho Bên B sử dụng ổn định nhà thuê trong thời hạn thuê.", style))
        content.append(Paragraph("- Bảo trì, sửa chữa nhà ở theo định kỳ hoặc theo thỏa thuận.", style))
        content.append(Spacer(1, 10))

        content.append(Paragraph("<b>ĐIỀU 5: QUYỀN VÀ NGHĨA VỤ CỦA BÊN B</b>", style))
        content.append(Paragraph("- Sử dụng nhà đúng mục đích đã thỏa thuận.", style))
        content.append(Paragraph("- Thanh toán tiền thuê đúng kỳ hạn.", style))
        content.append(Paragraph("- Giữ gìn nhà ở, không tự ý sửa chữa, cải tạo khi chưa có sự đồng ý của Bên A.", style))
        content.append(Paragraph("- Trả lại nhà ở đúng thời hạn và trong tình trạng ban đầu.", style))

        return content

    def _build_sale_content(self, data: dict, style, font_name, font_bold) -> list:
        """Build content for sale contract - Vietnamese with diacritics"""
        content = []

        content.append(Paragraph("<b>BÊN BÁN (Bên A):</b>", style))
        content.append(Paragraph(f"Họ và tên: {data.get('seller_name', '________________')}", style))
        content.append(Paragraph(f"Số CCCD: {data.get('seller_id', '________________')}", style))
        content.append(Spacer(1, 10))

        content.append(Paragraph("<b>BÊN MUA (Bên B):</b>", style))
        content.append(Paragraph(f"Họ và tên: {data.get('buyer_name', '________________')}", style))
        content.append(Paragraph(f"Số CCCD: {data.get('buyer_id', '________________')}", style))
        content.append(Spacer(1, 20))

        content.append(Paragraph("<b>ĐIỀU 1: ĐỐI TƯỢNG HỢP ĐỒNG</b>", style))
        content.append(Paragraph(
            f"Bên A đồng ý bán và Bên B đồng ý mua tài sản: {data.get('property_description', '________________')}",
            style
        ))
        content.append(Spacer(1, 10))

        content.append(Paragraph("<b>ĐIỀU 2: GIÁ BÁN</b>", style))
        content.append(Paragraph(
            f"Giá bán: {data.get('sale_price', '________________')} đồng",
            style
        ))

        return content

    def _build_generic_content(self, template: ContractTemplate, data: dict, style) -> list:
        """Build generic content for other contract types"""
        content = []

        content.append(Paragraph(f"<b>Mô tả:</b> {template.description}", style))
        content.append(Spacer(1, 20))

        for field in template.required_fields:
            value = data.get(field.name, '________________')
            content.append(Paragraph(f"<b>{field.label}:</b> {value}", style))
            content.append(Spacer(1, 5))

        return content

    def _build_signature_section(self, data: dict, style, font_name, font_bold) -> list:
        """Build signature section"""
        content = []

        content.append(Paragraph("<b>CHỮ KÝ CỦA CÁC BÊN</b>", style))
        content.append(Spacer(1, 10))

        # Create a simple table for signatures
        sig_data = [
            ['BÊN A', 'BÊN B'],
            ['(Ký và ghi rõ họ tên)', '(Ký và ghi rõ họ tên)'],
            ['', ''],
            ['', ''],
            ['', ''],
        ]

        sig_table = Table(sig_data, colWidths=[8*cm, 8*cm])
        sig_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTNAME', (0, 0), (-1, 0), font_bold),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
        ]))

        content.append(sig_table)

        return content


def generate_contract(
    template_type: str,
    data: dict,
    output_path: str,
) -> GeneratedContract:
    """Convenience function to generate a contract"""
    generator = GeneratorService()
    return generator.generate(template_type, data, output_path)

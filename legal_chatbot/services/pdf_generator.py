"""Universal PDF generator for all contract types with Vietnamese support

Supports two JSON formats:

Format 1 (With labels - recommended):
{
  "fields": {
    "ben_ban": {
      "_label": "BÊN BÁN (BÊN A)",
      "ho_ten": { "value": "Nguyễn Văn A", "label": "Họ và tên" }
    }
  }
}

Format 2 (Without labels - uses mapping):
{
  "fields": {
    "seller": {
      "full_name": "Nguyễn Văn A"
    }
  }
}
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Any
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from legal_chatbot.utils.pdf_fonts import register_vietnamese_fonts, get_font_name


def format_currency(amount: int | float | str) -> str:
    """Format number as Vietnamese currency"""
    try:
        num = float(str(amount).replace(",", "").replace(".", ""))
        return f"{num:,.0f}".replace(",", ".")
    except (ValueError, TypeError):
        return str(amount)


class UniversalPDFGenerator:
    """Generate PDF for any contract type based on JSON structure"""

    # Fallback mappings for old JSON format without labels
    SECTION_LABELS = {
        'seller': 'BÊN BÁN (BÊN A)', 'buyer': 'BÊN MUA (BÊN B)',
        'landlord': 'BÊN CHO THUÊ (BÊN A)', 'tenant': 'BÊN THUÊ (BÊN B)',
        'employer': 'NGƯỜI SỬ DỤNG LAO ĐỘNG', 'employee': 'NGƯỜI LAO ĐỘNG',
        'provider': 'BÊN CUNG CẤP DỊCH VỤ', 'client': 'BÊN SỬ DỤNG DỊCH VỤ',
        'land': 'THÔNG TIN THỬA ĐẤT', 'property': 'THÔNG TIN TÀI SẢN',
        'house': 'THÔNG TIN NHÀ Ở', 'transaction': 'GIÁ VÀ THANH TOÁN',
        'payment': 'THANH TOÁN', 'handover': 'BÀN GIAO', 'terms': 'ĐIỀU KHOẢN',
        'ben_ban': 'BÊN BÁN (BÊN A)', 'ben_mua': 'BÊN MUA (BÊN B)',
        'ben_cho_thue': 'BÊN CHO THUÊ (BÊN A)', 'ben_thue': 'BÊN THUÊ (BÊN B)',
        'nha_o': 'THÔNG TIN NHÀ Ở', 'nha': 'THÔNG TIN NHÀ Ở',
        'dat': 'THÔNG TIN THỬA ĐẤT', 'thua_dat': 'THÔNG TIN THỬA ĐẤT',
        'thoi_han': 'THỜI HẠN', 'tai_chinh': 'TÀI CHÍNH',
        'chi_phi_phu': 'CHI PHÍ PHỤ', 'dieu_khoan_khac': 'ĐIỀU KHOẢN KHÁC',
        'giay_to_phap_ly': 'GIẤY TỜ PHÁP LÝ',
        'ben_su_dung_lao_dong': 'BÊN SỬ DỤNG LAO ĐỘNG (BÊN A)',
        'nguoi_lao_dong': 'NGƯỜI LAO ĐỘNG (BÊN B)',
        'cong_viec': 'THÔNG TIN CÔNG VIỆC',
        'thoi_gian_lam_viec': 'THỜI GIỜ LÀM VIỆC, NGHỈ NGƠI',
        'bao_hiem': 'BẢO HIỂM XÃ HỘI, Y TẾ, THẤT NGHIỆP',
    }

    FIELD_LABELS = {
        'full_name': 'Họ và tên', 'ho_ten': 'Họ và tên',
        'date_of_birth': 'Ngày sinh', 'ngay_sinh': 'Ngày sinh',
        'id_number': 'Số CCCD', 'cccd': 'Số CCCD', 'so_cccd': 'Số CCCD',
        'id_issue_date': 'Ngày cấp CCCD', 'ngay_cap_cccd': 'Ngày cấp CCCD',
        'id_issue_place': 'Nơi cấp CCCD', 'noi_cap_cccd': 'Nơi cấp CCCD',
        'address': 'Địa chỉ', 'dia_chi': 'Địa chỉ',
        'dia_chi_thuong_tru': 'Địa chỉ thường trú',
        'phone': 'Điện thoại', 'so_dien_thoai': 'Số điện thoại',
        'ngay_bat_dau': 'Ngày bắt đầu', 'ngay_ket_thuc': 'Ngày kết thúc',
        'thoi_han': 'Thời hạn',
        'gia_thue_hang_thang': 'Giá thuê hàng tháng',
        'gia_thue_bang_chu': 'Giá thuê bằng chữ',
        'tien_dat_coc': 'Tiền đặt cọc',
        'tien_dat_coc_bang_chu': 'Tiền đặt cọc bằng chữ',
        'so_thang_dat_coc': 'Số tháng đặt cọc',
        'ngay_thanh_toan': 'Ngày thanh toán',
        'phuong_thuc_thanh_toan': 'Phương thức thanh toán',
        'ngan_hang': 'Ngân hàng', 'so_tai_khoan': 'Số tài khoản',
        'chu_tai_khoan': 'Chủ tài khoản',
        'tien_dien': 'Tiền điện', 'tien_nuoc': 'Tiền nước',
        'tien_internet': 'Tiền internet', 'phi_giu_xe': 'Phí giữ xe',
        'phi_ve_sinh': 'Phí vệ sinh',
        'cho_thue_lai': 'Cho thuê lại', 'nuoi_thu_cung': 'Nuôi thú cưng',
        'so_nguoi_o_toi_da': 'Số người ở tối đa',
        'gio_dong_cua': 'Giờ đóng cửa',
        'thong_bao_cham_dut_truoc': 'Thông báo chấm dứt trước',
        'sua_chua_nho_do_ben_thue': 'Sửa chữa nhỏ do bên thuê',
        'sua_chua_lon_do_ben_cho_thue': 'Sửa chữa lớn do bên cho thuê',
        'loai_nha': 'Loại nhà', 'so_tang': 'Số tầng',
        'dien_tich_dat': 'Diện tích đất',
        'dien_tich_san_xay_dung': 'Diện tích sàn xây dựng',
        'ket_cau': 'Kết cấu', 'huong_nha': 'Hướng nhà',
        'so_phong': 'Số phòng',
    }

    def __init__(self):
        register_vietnamese_fonts()
        self.font_name = get_font_name()
        self.font_bold = get_font_name(bold=True)
        self._init_styles()

    def _init_styles(self):
        """Initialize paragraph styles"""
        self.styles = {
            'header': ParagraphStyle('Header', fontName=self.font_name,
                fontSize=12, alignment=TA_CENTER, spaceAfter=2),
            'header_bold': ParagraphStyle('HeaderBold', fontName=self.font_bold,
                fontSize=12, alignment=TA_CENTER, spaceAfter=2),
            'title': ParagraphStyle('Title', fontName=self.font_bold,
                fontSize=14, alignment=TA_CENTER, spaceAfter=10, spaceBefore=15,
                textColor=colors.HexColor('#1a5f7a')),
            'section': ParagraphStyle('Section', fontName=self.font_bold,
                fontSize=11, spaceBefore=15, spaceAfter=8,
                textColor=colors.HexColor('#1a5f7a')),
            'normal': ParagraphStyle('Normal', fontName=self.font_name,
                fontSize=10, leading=14, alignment=TA_JUSTIFY),
            'small': ParagraphStyle('Small', fontName=self.font_name,
                fontSize=9, textColor=colors.gray),
            'disclaimer': ParagraphStyle('Disclaimer', fontName=self.font_name,
                fontSize=8, textColor=colors.HexColor('#e65100')),
        }

    def generate(self, contract_path: str, output_path: Optional[str] = None) -> str:
        """Generate PDF from contract JSON file"""
        with open(contract_path, 'r', encoding='utf-8') as f:
            contract = json.load(f)

        if output_path is None:
            output_path = str(Path(contract_path).with_suffix('.pdf'))

        doc = SimpleDocTemplate(output_path, pagesize=A4,
            rightMargin=2*cm, leftMargin=2*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)

        story = self._build_story(contract)
        doc.build(story)
        return output_path

    def _build_story(self, contract: dict) -> list:
        """Build PDF story from contract data"""
        story = []

        # Header
        story.extend([
            Paragraph("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", self.styles['header']),
            Paragraph("Độc lập - Tự do - Hạnh phúc", self.styles['header_bold']),
            Paragraph("---oOo---", self.styles['header']),
            Spacer(1, 15),
        ])

        # Title
        contract_type_vn = contract.get('contract_type_vn', 'Hợp đồng')
        story.append(Paragraph(contract_type_vn.upper(), self.styles['title']))
        story.append(Paragraph(
            f"(Bản nháp - Ngày tạo: {datetime.now().strftime('%d/%m/%Y')})",
            self.styles['small']))
        story.append(Spacer(1, 10))

        # Legal references
        if 'legal_references' in contract:
            story.append(Paragraph("CĂN CỨ PHÁP LÝ:", self.styles['section']))
            for ref in contract['legal_references']:
                if isinstance(ref, dict):
                    story.append(Paragraph(f"- {ref.get('article', '')} {ref.get('law', '')}", self.styles['normal']))
                else:
                    story.append(Paragraph(f"- {ref}", self.styles['normal']))
            story.append(Spacer(1, 10))

        # Fields
        fields = contract.get('fields', {})
        story.extend(self._build_fields(fields))

        # Articles from research (not hardcoded)
        articles = contract.get('articles', contract.get('dieu_khoan', []))
        if articles:
            story.extend(self._build_articles(articles))

        # Signatures
        story.extend(self._build_signatures(fields))

        # Disclaimer
        story.append(Paragraph(
            "<b>LƯU Ý:</b> Đây chỉ là BẢN NHÁP mang tính chất tham khảo. "
            "Không thay thế tư vấn pháp lý chuyên nghiệp.",
            self.styles['disclaimer']))

        return story

    def _build_fields(self, fields: dict) -> list:
        """Build fields sections"""
        story = []

        for section_key, section_value in fields.items():
            if not isinstance(section_value, dict):
                continue

            # Get section label: first try _label, then mapping, then format key
            section_label = section_value.get('_label')
            if not section_label:
                section_label = self.SECTION_LABELS.get(section_key)
            if not section_label:
                section_label = section_key.replace('_', ' ').upper()

            story.append(Paragraph(section_label, self.styles['section']))

            # Build table for fields
            table_data = []
            for field_key, field_value in section_value.items():
                if field_key == '_label':
                    continue  # Skip the label key itself

                # Check if field has label/value structure
                if isinstance(field_value, dict) and 'value' in field_value:
                    label = field_value.get('label', self._get_field_label(field_key))
                    value = self._format_value(field_value['value'])
                elif isinstance(field_value, dict):
                    # Nested section - skip for now
                    continue
                else:
                    label = self._get_field_label(field_key)
                    value = self._format_value(field_value)

                table_data.append([f"{label}:", value])

            if table_data:
                story.append(self._build_table(table_data))
            story.append(Spacer(1, 10))

        return story

    def _get_field_label(self, key: str) -> str:
        """Get Vietnamese label for field key"""
        if key in self.FIELD_LABELS:
            return self.FIELD_LABELS[key]
        # Convert snake_case to Title Case with proper Vietnamese
        return key.replace('_', ' ').title()

    def _build_table(self, data: list) -> Table:
        """Build a formatted table"""
        if not data:
            return Spacer(1, 0)

        table = Table(data, colWidths=[5*cm, 11*cm])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), self.font_name),
            ('FONTNAME', (0, 0), (0, -1), self.font_bold),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        return table

    def _format_value(self, value: Any) -> str:
        """Format field value for display"""
        if value is None:
            return "________________"
        if isinstance(value, bool):
            return "Có" if value else "Không"
        if isinstance(value, (int, float)) and value >= 1000:
            return f"{format_currency(value)} VNĐ"
        return str(value)

    def _extract_field(self, section: dict, field_key: str) -> str:
        """Extract a specific field value from section, handling both formats"""
        if field_key in section:
            field = section[field_key]
            if isinstance(field, dict) and 'value' in field:
                return str(field['value'])
            if isinstance(field, str):
                return field
        return ""

    def _extract_name(self, section: dict) -> str:
        """Extract name from section, handling both formats"""
        for key in ['ho_ten', 'full_name', 'ten']:
            if key in section:
                field = section[key]
                # Handle {value, label} format
                if isinstance(field, dict) and 'value' in field:
                    return str(field['value'])
                # Handle simple string format
                return str(field)
        return ""

    def _build_articles(self, articles: list) -> list:
        """Build contract articles from research data

        Expected format in JSON:
        "articles": [
            {
                "title": "ĐIỀU 1: QUYỀN VÀ NGHĨA VỤ CỦA BÊN CHO THUÊ",
                "content": [
                    "1.1. Bên cho thuê có nghĩa vụ...",
                    "1.2. Bên cho thuê có quyền..."
                ]
            }
        ]

        Or simple format:
        "articles": [
            "Điều 1: Nội dung điều 1",
            "Điều 2: Nội dung điều 2"
        ]
        """
        story = []

        for article in articles:
            if isinstance(article, dict):
                # Format with title and content
                title = article.get('title', '')
                content = article.get('content', [])

                if title:
                    story.append(Paragraph(title, self.styles['section']))

                if isinstance(content, list):
                    for line in content:
                        story.append(Paragraph(line, self.styles['normal']))
                elif isinstance(content, str):
                    story.append(Paragraph(content, self.styles['normal']))

            elif isinstance(article, str):
                # Simple string format
                story.append(Paragraph(article, self.styles['normal']))

        if story:
            story.append(Spacer(1, 30))
        return story

    def _build_signatures(self, fields: dict) -> list:
        """Build signature section"""
        # Try to get names
        name_a = name_b = ""
        for key in ['seller', 'landlord', 'employer', 'provider', 'ben_ban', 'ben_cho_thue', 'ben_su_dung_lao_dong']:
            if key in fields and isinstance(fields[key], dict):
                section = fields[key]
                # For companies, try representative name first
                name_a = self._extract_field(section, 'dai_dien') or self._extract_name(section)
                break
        for key in ['buyer', 'tenant', 'employee', 'client', 'ben_mua', 'ben_thue', 'nguoi_lao_dong']:
            if key in fields and isinstance(fields[key], dict):
                name_b = self._extract_name(fields[key])
                break

        sig_data = [
            ['BÊN A', 'BÊN B'],
            ['(Ký và ghi rõ họ tên)', '(Ký và ghi rõ họ tên)'],
            ['', ''], ['', ''], ['', ''],
            [name_a, name_b],
        ]

        sig_table = Table(sig_data, colWidths=[8*cm, 8*cm])
        sig_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), self.font_name),
            ('FONTNAME', (0, 0), (-1, 0), self.font_bold),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))

        return [sig_table, Spacer(1, 20)]


def generate_pdf(contract_path: str, output_path: Optional[str] = None) -> str:
    """Generate PDF from contract JSON file"""
    return UniversalPDFGenerator().generate(contract_path, output_path)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m legal_chatbot.services.pdf_generator <contract.json> [output.pdf]")
        sys.exit(1)
    result = generate_pdf(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(f"PDF generated: {result}")

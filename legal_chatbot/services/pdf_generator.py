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
        # Additional keys from contract JSONs
        'ben_a': 'BÊN A', 'ben_b': 'BÊN B',
        'nha_cho_thue': 'THÔNG TIN NHÀ CHO THUÊ',
        'trang_thiet_bi': 'TRANG THIẾT BỊ',
        'chi_phi_khac': 'CHI PHÍ KHÁC',
        'dieu_khoan_cham_dut': 'ĐIỀU KHOẢN CHẤM DỨT HỢP ĐỒNG',
        'xe': 'THÔNG TIN XE', 'xe_may': 'THÔNG TIN XE MÁY',
        'luong_thuong': 'LƯƠNG VÀ THƯỞNG', 'luong': 'LƯƠNG',
    }

    FIELD_LABELS = {
        # Person info
        'full_name': 'Họ và tên', 'ho_ten': 'Họ và tên', 'ten': 'Tên',
        'date_of_birth': 'Ngày sinh', 'ngay_sinh': 'Ngày sinh',
        'id_number': 'Số CCCD', 'cccd': 'Số CCCD', 'so_cccd': 'Số CCCD',
        'id_issue_date': 'Ngày cấp CCCD', 'ngay_cap_cccd': 'Ngày cấp CCCD',
        'id_issue_place': 'Nơi cấp CCCD', 'noi_cap_cccd': 'Nơi cấp CCCD',
        'so_cccd_dai_dien': 'Số CCCD người đại diện',
        'address': 'Địa chỉ', 'dia_chi': 'Địa chỉ',
        'dia_chi_thuong_tru': 'Địa chỉ thường trú',
        'phone': 'Điện thoại', 'so_dien_thoai': 'Số điện thoại',
        'dien_thoai': 'Điện thoại', 'gioi_tinh': 'Giới tính',
        'trinh_do_hoc_van': 'Trình độ học vấn',
        'ten_cong_ty': 'Tên công ty', 'ma_so_thue': 'Mã số thuế',
        'dai_dien': 'Người đại diện', 'chuc_vu_dai_dien': 'Chức vụ',
        # Land/property info
        'parcel_number': 'Số thửa đất', 'map_sheet_number': 'Số tờ bản đồ',
        'area_m2': 'Diện tích (m²)', 'land_use_purpose': 'Mục đích sử dụng đất',
        'certificate_number': 'Số giấy chứng nhận QSDĐ',
        'certificate_issue_date': 'Ngày cấp GCN',
        'certificate_issuer': 'Cơ quan cấp GCN',
        'so_giay_chung_nhan': 'Số giấy chứng nhận',
        'ngay_cap_gcn': 'Ngày cấp GCN', 'co_quan_cap': 'Cơ quan cấp',
        'loai_nha': 'Loại nhà', 'so_tang': 'Số tầng',
        'dien_tich': 'Diện tích', 'dien_tich_dat': 'Diện tích đất',
        'dien_tich_san_xay_dung': 'Diện tích sàn xây dựng',
        'ket_cau': 'Kết cấu', 'huong_nha': 'Hướng nhà',
        'so_phong': 'Số phòng', 'so_phong_ngu': 'Số phòng ngủ',
        'so_phong_tam': 'Số phòng tắm', 'tinh_trang': 'Tình trạng',
        'mo_ta': 'Mô tả', 'giay_chung_nhan': 'Giấy chứng nhận',
        # Financial/transaction
        'price_vnd': 'Giá bán', 'price_in_words': 'Bằng chữ',
        'deposit_vnd': 'Tiền đặt cọc', 'deposit_in_words': 'Đặt cọc bằng chữ',
        'so_tien': 'Số tiền', 'so_tien_bang_chu': 'Bằng chữ',
        'don_vi_tien': 'Đơn vị tiền', 'hinh_thuc': 'Hình thức',
        'gia_thue_hang_thang': 'Giá thuê hàng tháng',
        'gia_thue_bang_chu': 'Giá thuê bằng chữ',
        'tien_dat_coc': 'Tiền đặt cọc',
        'tien_dat_coc_bang_chu': 'Tiền đặt cọc bằng chữ',
        'dat_coc_bang_chu': 'Đặt cọc bằng chữ',
        'so_thang_dat_coc': 'Số tháng đặt cọc',
        'ngay_thanh_toan': 'Ngày thanh toán',
        'phuong_thuc_thanh_toan': 'Phương thức thanh toán',
        'tai_khoan_nhan': 'Tài khoản nhận',
        'ngan_hang': 'Ngân hàng', 'so_tai_khoan': 'Số tài khoản',
        'chu_tai_khoan': 'Chủ tài khoản',
        'phat_vi_pham': 'Phạt vi phạm', 'cong_chung_tai': 'Công chứng tại',
        # Rental/lease
        'ngay_bat_dau': 'Ngày bắt đầu', 'ngay_ket_thuc': 'Ngày kết thúc',
        'thoi_han': 'Thời hạn', 'thoi_han_thue': 'Thời hạn thuê',
        'muc_dich_thue': 'Mục đích thuê',
        'tien_dien': 'Tiền điện', 'tien_nuoc': 'Tiền nước',
        'tien_internet': 'Tiền internet', 'internet': 'Internet',
        'phi_giu_xe': 'Phí giữ xe', 'phi_ve_sinh': 'Phí vệ sinh',
        'phi_quan_ly': 'Phí quản lý',
        # Termination/other terms
        'cho_thue_lai': 'Cho thuê lại', 'nuoi_thu_cung': 'Nuôi thú cưng',
        'thu_cung': 'Thú cưng',
        'so_nguoi_o_toi_da': 'Số người ở tối đa', 'so_nguoi_o': 'Số người ở',
        'gio_dong_cua': 'Giờ đóng cửa',
        'thong_bao_cham_dut_truoc': 'Thông báo chấm dứt trước',
        'thong_bao_truoc': 'Thông báo trước',
        'phat_cham_dut_som': 'Phạt chấm dứt sớm',
        'hoan_tra_dat_coc': 'Hoàn trả đặt cọc',
        'sua_chua_nho_do_ben_thue': 'Sửa chữa nhỏ do bên thuê',
        'sua_chua_lon_do_ben_cho_thue': 'Sửa chữa lớn do bên cho thuê',
        'sua_chua_nho': 'Sửa chữa nhỏ', 'sua_chua_lon': 'Sửa chữa lớn',
        'giai_quyet_tranh_chap': 'Giải quyết tranh chấp',
        # Handover
        'land_handover_date': 'Ngày bàn giao đất',
        'certificate_handover_date': 'Ngày bàn giao giấy tờ',
        'tai_san_ban_giao': 'Tài sản bàn giao',
        # Vehicle
        'loai_xe': 'Loại xe', 'mau_son': 'Màu sơn', 'bien_so': 'Biển số',
        'so_khung': 'Số khung', 'so_may': 'Số máy',
        'dung_tich': 'Dung tích', 'nam_san_xuat': 'Năm sản xuất',
        'so_dang_ky': 'Số đăng ký', 'giay_to_kem_theo': 'Giấy tờ kèm theo',
        # Employment
        'chuc_danh': 'Chức danh', 'phong_ban': 'Phòng ban',
        'dia_diem_lam_viec': 'Địa điểm làm việc',
        'mo_ta_cong_viec': 'Mô tả công việc',
        'loai_hop_dong': 'Loại hợp đồng', 'thu_viec': 'Thử việc',
        'luong_thu_viec': 'Lương thử việc',
        'luong_co_ban': 'Lương cơ bản',
        'phu_cap_an_trua': 'Phụ cấp ăn trưa',
        'phu_cap_di_lai': 'Phụ cấp đi lại',
        'phu_cap_dien_thoai': 'Phụ cấp điện thoại',
        'hinh_thuc_tra_luong': 'Hình thức trả lương',
        'ky_han_tra_luong': 'Kỳ hạn trả lương',
        # Work schedule
        'gio_lam_viec': 'Giờ làm việc', 'ngay_lam_viec': 'Ngày làm việc',
        'nghi_hang_tuan': 'Nghỉ hàng tuần', 'nghi_phep_nam': 'Nghỉ phép năm',
        # Insurance
        'bhxh_nsdld': 'BHXH (người sử dụng LĐ)',
        'bhyt_nsdld': 'BHYT (người sử dụng LĐ)',
        'bhtn_nsdld': 'BHTN (người sử dụng LĐ)',
        'bhxh_nld': 'BHXH (người lao động)',
        'bhyt_nld': 'BHYT (người lao động)',
        'bhtn_nld': 'BHTN (người lao động)',
        # Payment phases
        'dot_1': 'Đợt 1', 'dot_2': 'Đợt 2', 'dot_3': 'Đợt 3',
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
            'table_label': ParagraphStyle('TableLabel', fontName=self.font_bold,
                fontSize=10, leading=14),
            'table_value': ParagraphStyle('TableValue', fontName=self.font_name,
                fontSize=10, leading=14),
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
            # Handle top-level list (e.g. trang_thiet_bi)
            if isinstance(section_value, list):
                label = self.SECTION_LABELS.get(section_key,
                    self._get_field_label(section_key))
                story.append(Paragraph(label, self.styles['section']))
                for item in section_value:
                    story.append(Paragraph(f"- {item}", self.styles['normal']))
                story.append(Spacer(1, 10))
                continue

            # Handle top-level string (e.g. muc_dich_thue)
            if isinstance(section_value, str):
                label = self._get_field_label(section_key)
                story.append(self._build_table([[f"{label}:", section_value]]))
                story.append(Spacer(1, 5))
                continue

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
                    continue

                # Handle payment_schedule or other list-of-dicts
                if isinstance(field_value, list) and field_value and isinstance(field_value[0], dict):
                    # Render as sub-table after the current table
                    if table_data:
                        story.append(self._build_table(table_data))
                        table_data = []
                    story.extend(self._build_payment_schedule(field_key, field_value))
                    continue

                # Handle simple list (e.g. list of strings)
                if isinstance(field_value, list):
                    if table_data:
                        story.append(self._build_table(table_data))
                        table_data = []
                    label = self._get_field_label(field_key)
                    story.append(Paragraph(f"<b>{label}:</b>", self.styles['normal']))
                    for item in field_value:
                        story.append(Paragraph(f"  - {item}", self.styles['normal']))
                    continue

                # Check if field has label/value structure
                if isinstance(field_value, dict) and 'value' in field_value:
                    label = field_value.get('label', self._get_field_label(field_key))
                    value = self._format_value(field_value['value'])
                elif isinstance(field_value, dict):
                    # Nested section - skip
                    continue
                else:
                    label = self._get_field_label(field_key)
                    value = self._format_value(field_value)

                table_data.append([f"{label}:", value])

            if table_data:
                story.append(self._build_table(table_data))
            story.append(Spacer(1, 10))

        return story

    def _build_payment_schedule(self, key: str, schedule: list) -> list:
        """Build a payment schedule table from list of phase dicts"""
        story = []
        label = self._get_field_label(key) if key != 'payment_schedule' else 'Lịch thanh toán'
        story.append(Paragraph(f"<b>{label}:</b>", self.styles['normal']))
        story.append(Spacer(1, 5))

        header = ['Đợt', 'Nội dung', 'Số tiền', 'Thời hạn']
        rows = [header]
        for item in schedule:
            phase = str(item.get('phase', item.get('dot', '')))
            desc = str(item.get('description', item.get('mo_ta', '')))
            amount = item.get('amount_vnd', item.get('so_tien', ''))
            if isinstance(amount, (int, float)) and amount >= 1000:
                amount = f"{format_currency(amount)} VNĐ"
            else:
                amount = str(amount)
            due = str(item.get('due_date', item.get('thoi_han', '')))
            rows.append([phase, desc, amount, due])

        col_widths = [1.5*cm, 5*cm, 4*cm, 5.5*cm]
        table = Table(rows, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), self.font_name),
            ('FONTNAME', (0, 0), (-1, 0), self.font_bold),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8f4f8')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(table)
        story.append(Spacer(1, 5))
        return story

    def _get_field_label(self, key: str) -> str:
        """Get Vietnamese label for field key"""
        if key in self.FIELD_LABELS:
            return self.FIELD_LABELS[key]
        # Convert snake_case to Title Case with proper Vietnamese
        return key.replace('_', ' ').title()

    def _build_table(self, data: list) -> Table:
        """Build a formatted table with text wrapping"""
        if not data:
            return Spacer(1, 0)

        # Wrap cells in Paragraph for proper text wrapping
        wrapped_data = []
        for row in data:
            label = Paragraph(str(row[0]), self.styles['table_label'])
            value = Paragraph(str(row[1]), self.styles['table_value'])
            wrapped_data.append([label, value])

        table = Table(wrapped_data, colWidths=[5*cm, 11*cm])
        table.setStyle(TableStyle([
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
        for key in ['seller', 'landlord', 'employer', 'provider', 'ben_ban', 'ben_cho_thue', 'ben_su_dung_lao_dong', 'ben_a']:
            if key in fields and isinstance(fields[key], dict):
                section = fields[key]
                # For companies, try representative name first
                name_a = self._extract_field(section, 'dai_dien') or self._extract_name(section)
                break
        for key in ['buyer', 'tenant', 'employee', 'client', 'ben_mua', 'ben_thue', 'nguoi_lao_dong', 'ben_b']:
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

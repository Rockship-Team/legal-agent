"""Dynamic template generator based on legal articles - Using Anthropic Claude"""

from typing import Optional
from pydantic import BaseModel

from legal_chatbot.utils.config import get_settings


class DynamicField(BaseModel):
    """A field in a dynamic template"""
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
    """A dynamically generated contract template"""
    contract_type: str
    name: str
    description: str
    fields: list[DynamicField]
    legal_references: list[str] = []
    legal_articles: list[LegalArticle] = []
    generated_from: str = ""
    key_terms: list[str] = []


def get_llm_client():
    """Get LLM client based on configuration"""
    settings = get_settings()

    if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        from anthropic import Anthropic
        return Anthropic(api_key=settings.anthropic_api_key), "anthropic"
    elif settings.groq_api_key:
        from groq import Groq
        return Groq(api_key=settings.groq_api_key), "groq"
    else:
        return None, None


class DynamicTemplateGenerator:
    """Generate contract templates dynamically from legal content"""

    # Detailed legal articles database
    LEGAL_ARTICLES = {
        # Luat Nha o 2014
        'dieu_121_nha_o': {
            'article_number': '121',
            'article_title': 'Dieu kien cua nha o tham gia giao dich',
            'document_name': 'Luat Nha o 2014 (65/2014/QH13)',
            'content': '''1. Nha o tham gia giao dich phai co du cac dieu kien sau:
a) Co giay chung nhan quyen su dung dat, quyen so huu nha o va tai san khac gan lien voi dat;
b) Khong thuoc dien dang co tranh chap, khieu nai, khieu kien ve quyen so huu;
c) Khong bi ke bien de thi hanh an hoac de chap hanh quyet dinh hanh chinh;
d) Khong thuoc dien da co quyet dinh thu hoi dat, co thong bao giai toa, pha do nha o.''',
            'summary': 'Dieu kien de nha o duoc tham gia giao dich'
        },
        'dieu_129_nha_o': {
            'article_number': '129',
            'article_title': 'Cho thue nha o',
            'document_name': 'Luat Nha o 2014 (65/2014/QH13)',
            'content': '''Hop dong cho thue nha o phai co cac noi dung co ban:
a) Ten, dia chi cua ben cho thue va ben thue;
b) Mo ta dac diem cua nha o cho thue;
c) Gia cho thue va phuong thuc thanh toan;
d) Thoi han cho thue;
e) Quyen va nghia vu cua cac ben;
f) Cam ket cua cac ben;
g) Cac thoa thuan khac.''',
            'summary': 'Noi dung bat buoc cua hop dong thue nha'
        },
        # Luat Dat dai 2024
        'dieu_45_dat_dai': {
            'article_number': '45',
            'article_title': 'Dieu kien chuyen nhuong quyen su dung dat',
            'document_name': 'Luat Dat dai 2024',
            'content': '''Nguoi su dung dat duoc chuyen nhuong quyen su dung dat khi co du dieu kien:
a) Co Giay chung nhan quyen su dung dat;
b) Dat khong co tranh chap;
c) Quyen su dung dat khong bi ke bien de bao dam thi hanh an;
d) Trong thoi han su dung dat.''',
            'summary': 'Dieu kien de chuyen nhuong quyen su dung dat'
        },
        # Bo luat Dan su 2015
        'dieu_430_dan_su': {
            'article_number': '430',
            'article_title': 'Hop dong mua ban tai san',
            'document_name': 'Bo luat Dan su 2015',
            'content': '''Hop dong mua ban tai san la su thoa thuan giua cac ben, theo do ben ban chuyen quyen so huu tai san cho ben mua va ben mua tra tien cho ben ban.
Hop dong mua ban nha o, cong trinh xay dung phai duoc lap thanh van ban, co cong chung hoac chung thuc.''',
            'summary': 'Dinh nghia hop dong mua ban'
        },
        'dieu_513_dan_su': {
            'article_number': '513',
            'article_title': 'Hop dong dich vu',
            'document_name': 'Bo luat Dan su 2015',
            'content': '''Hop dong dich vu la su thoa thuan giua cac ben, theo do ben cung ung dich vu thuc hien cong viec cho ben su dung dich vu, ben su dung dich vu phai tra tien dich vu.''',
            'summary': 'Dinh nghia hop dong dich vu'
        },
        # Bo luat Lao dong 2019
        'dieu_21_lao_dong': {
            'article_number': '21',
            'article_title': 'Noi dung hop dong lao dong',
            'document_name': 'Bo luat Lao dong 2019',
            'content': '''Hop dong lao dong phai co cac noi dung chu yeu:
a) Ten, dia chi nguoi su dung lao dong;
b) Ho ten, ngay sinh, gioi tinh, CCCD nguoi lao dong;
c) Cong viec va dia diem lam viec;
d) Thoi han hop dong;
e) Muc luong, hinh thuc tra luong;
f) Che do nang bac, nang luong;
g) Thoi gio lam viec, nghi ngoi;
h) Bao hiem xa hoi, bao hiem y te.''',
            'summary': 'Noi dung bat buoc cua hop dong lao dong'
        },
    }

    # Comprehensive templates with detailed fields for each type
    BASE_TEMPLATES = {
        # THUE NHA
        'rental': {
            'name': 'Hop dong thue nha o',
            'description': 'Hop dong cho thue nha o theo Luat Nha o 2014',
            'base_fields': [
                # Ben cho thue
                {'name': 'landlord_name', 'label': 'Ho ten ben cho thue', 'required': True},
                {'name': 'landlord_birth', 'label': 'Ngay sinh ben cho thue', 'required': True},
                {'name': 'landlord_id', 'label': 'So CCCD ben cho thue', 'required': True},
                {'name': 'landlord_id_date', 'label': 'Ngay cap CCCD', 'required': False},
                {'name': 'landlord_id_place', 'label': 'Noi cap CCCD', 'required': False},
                {'name': 'landlord_address', 'label': 'Dia chi thuong tru ben cho thue', 'required': True},
                {'name': 'landlord_phone', 'label': 'So dien thoai ben cho thue', 'required': True},
                # Ben thue
                {'name': 'tenant_name', 'label': 'Ho ten ben thue', 'required': True},
                {'name': 'tenant_birth', 'label': 'Ngay sinh ben thue', 'required': True},
                {'name': 'tenant_id', 'label': 'So CCCD ben thue', 'required': True},
                {'name': 'tenant_id_date', 'label': 'Ngay cap CCCD ben thue', 'required': False},
                {'name': 'tenant_id_place', 'label': 'Noi cap CCCD ben thue', 'required': False},
                {'name': 'tenant_address', 'label': 'Dia chi thuong tru ben thue', 'required': True},
                {'name': 'tenant_phone', 'label': 'So dien thoai ben thue', 'required': True},
                # Thong tin nha
                {'name': 'property_address', 'label': 'Dia chi nha cho thue', 'required': True},
                {'name': 'property_type', 'label': 'Loai nha (nha rieng/can ho/phong tro)', 'required': True},
                {'name': 'property_area', 'label': 'Dien tich su dung (m2)', 'required': True},
                {'name': 'property_floors', 'label': 'So tang', 'required': False},
                {'name': 'property_rooms', 'label': 'So phong', 'required': False},
                {'name': 'property_cert', 'label': 'So giay chung nhan QSDD', 'required': True},
                {'name': 'property_furniture', 'label': 'Trang bi noi that', 'required': False},
                # Dieu khoan thue
                {'name': 'monthly_rent', 'label': 'Gia thue (VND/thang)', 'required': True},
                {'name': 'deposit', 'label': 'Tien dat coc (VND)', 'required': True},
                {'name': 'payment_date', 'label': 'Ngay thanh toan hang thang', 'required': True},
                {'name': 'payment_method', 'label': 'Phuong thuc thanh toan (tien mat/chuyen khoan)', 'required': True},
                {'name': 'duration_months', 'label': 'Thoi han thue (thang)', 'required': True},
                {'name': 'start_date', 'label': 'Ngay bat dau thue', 'required': True},
                {'name': 'end_date', 'label': 'Ngay ket thuc thue', 'required': True},
                {'name': 'utilities_included', 'label': 'Chi phi dien nuoc tinh rieng hay gop', 'required': False},
            ],
            'legal_refs': ['Dieu 121 Luat Nha o 2014', 'Dieu 129 Luat Nha o 2014'],
            'legal_article_keys': ['dieu_121_nha_o', 'dieu_129_nha_o'],
            'key_terms': [
                'Ben cho thue phai la chu so huu hop phap hoac duoc uy quyen',
                'Nha o phai co giay chung nhan quyen so huu',
                'Hop dong phai lap thanh van ban',
                'Ben thue co quyen su dung on dinh trong thoi han thue',
                'Ben thue phai tra tien thue dung han',
                'Ben cho thue phai ban giao nha dung thoa thuan',
            ]
        },

        # MUA BAN NHA
        'sale_house': {
            'name': 'Hop dong mua ban nha o',
            'description': 'Hop dong mua ban nha o theo Bo luat Dan su 2015 va Luat Nha o 2014',
            'base_fields': [
                # Ben ban
                {'name': 'seller_name', 'label': 'Ho ten ben ban', 'required': True},
                {'name': 'seller_birth', 'label': 'Ngay sinh ben ban', 'required': True},
                {'name': 'seller_id', 'label': 'So CCCD ben ban', 'required': True},
                {'name': 'seller_id_date', 'label': 'Ngay cap CCCD ben ban', 'required': True},
                {'name': 'seller_id_place', 'label': 'Noi cap CCCD ben ban', 'required': True},
                {'name': 'seller_address', 'label': 'Dia chi thuong tru ben ban', 'required': True},
                {'name': 'seller_phone', 'label': 'So dien thoai ben ban', 'required': True},
                # Ben mua
                {'name': 'buyer_name', 'label': 'Ho ten ben mua', 'required': True},
                {'name': 'buyer_birth', 'label': 'Ngay sinh ben mua', 'required': True},
                {'name': 'buyer_id', 'label': 'So CCCD ben mua', 'required': True},
                {'name': 'buyer_id_date', 'label': 'Ngay cap CCCD ben mua', 'required': True},
                {'name': 'buyer_id_place', 'label': 'Noi cap CCCD ben mua', 'required': True},
                {'name': 'buyer_address', 'label': 'Dia chi thuong tru ben mua', 'required': True},
                {'name': 'buyer_phone', 'label': 'So dien thoai ben mua', 'required': True},
                # Thong tin nha
                {'name': 'house_address', 'label': 'Dia chi nha', 'required': True},
                {'name': 'house_type', 'label': 'Loai nha (biet thu/nha pho/can ho)', 'required': True},
                {'name': 'land_area', 'label': 'Dien tich dat (m2)', 'required': True},
                {'name': 'construction_area', 'label': 'Dien tich xay dung (m2)', 'required': True},
                {'name': 'floors', 'label': 'So tang', 'required': True},
                {'name': 'house_cert_no', 'label': 'So giay chung nhan QSDD va QSHNO', 'required': True},
                {'name': 'house_cert_date', 'label': 'Ngay cap giay chung nhan', 'required': True},
                {'name': 'house_cert_issuer', 'label': 'Co quan cap giay chung nhan', 'required': True},
                # Thong tin gia ca
                {'name': 'sale_price', 'label': 'Gia ban (VND)', 'required': True},
                {'name': 'price_in_words', 'label': 'Gia ban bang chu', 'required': True},
                {'name': 'deposit_amount', 'label': 'Tien dat coc (VND)', 'required': True},
                {'name': 'deposit_date', 'label': 'Ngay dat coc', 'required': True},
                {'name': 'payment_schedule', 'label': 'Lich thanh toan', 'required': True},
                {'name': 'handover_date', 'label': 'Ngay ban giao nha', 'required': True},
            ],
            'legal_refs': ['Dieu 430 BLDS 2015', 'Dieu 121 Luat Nha o 2014'],
            'legal_article_keys': ['dieu_430_dan_su', 'dieu_121_nha_o'],
            'key_terms': [
                'Ben ban phai la chu so huu hop phap',
                'Nha phai co giay chung nhan quyen so huu',
                'Nha khong co tranh chap, khong bi ke bien',
                'Hop dong phai cong chung hoac chung thuc',
                'Ben ban chiu trach nhiem hoan tat thu tuc sang ten',
            ]
        },

        # MUA BAN DAT
        'sale_land': {
            'name': 'Hop dong chuyen nhuong quyen su dung dat',
            'description': 'Hop dong chuyen nhuong QSDD theo Luat Dat dai 2024',
            'base_fields': [
                # Ben chuyen nhuong
                {'name': 'transferor_name', 'label': 'Ho ten ben chuyen nhuong', 'required': True},
                {'name': 'transferor_birth', 'label': 'Ngay sinh', 'required': True},
                {'name': 'transferor_id', 'label': 'So CCCD', 'required': True},
                {'name': 'transferor_id_date', 'label': 'Ngay cap CCCD', 'required': True},
                {'name': 'transferor_id_place', 'label': 'Noi cap CCCD', 'required': True},
                {'name': 'transferor_address', 'label': 'Dia chi thuong tru', 'required': True},
                {'name': 'transferor_phone', 'label': 'So dien thoai', 'required': True},
                # Ben nhan chuyen nhuong
                {'name': 'transferee_name', 'label': 'Ho ten ben nhan chuyen nhuong', 'required': True},
                {'name': 'transferee_birth', 'label': 'Ngay sinh', 'required': True},
                {'name': 'transferee_id', 'label': 'So CCCD', 'required': True},
                {'name': 'transferee_id_date', 'label': 'Ngay cap CCCD', 'required': True},
                {'name': 'transferee_id_place', 'label': 'Noi cap CCCD', 'required': True},
                {'name': 'transferee_address', 'label': 'Dia chi thuong tru', 'required': True},
                {'name': 'transferee_phone', 'label': 'So dien thoai', 'required': True},
                # Thong tin thua dat
                {'name': 'land_address', 'label': 'Dia chi thua dat', 'required': True},
                {'name': 'land_parcel_no', 'label': 'So thua dat', 'required': True},
                {'name': 'land_map_no', 'label': 'So to ban do', 'required': True},
                {'name': 'land_area', 'label': 'Dien tich (m2)', 'required': True},
                {'name': 'land_purpose', 'label': 'Muc dich su dung dat', 'required': True},
                {'name': 'land_use_term', 'label': 'Thoi han su dung dat', 'required': True},
                {'name': 'land_origin', 'label': 'Nguon goc su dung dat', 'required': True},
                {'name': 'land_cert_no', 'label': 'So giay chung nhan QSDD', 'required': True},
                {'name': 'land_cert_date', 'label': 'Ngay cap giay chung nhan', 'required': True},
                {'name': 'land_cert_issuer', 'label': 'Co quan cap giay chung nhan', 'required': True},
                # Gia ca
                {'name': 'transfer_price', 'label': 'Gia chuyen nhuong (VND)', 'required': True},
                {'name': 'price_in_words', 'label': 'Gia chuyen nhuong bang chu', 'required': True},
                {'name': 'deposit_amount', 'label': 'Tien dat coc (VND)', 'required': True},
                {'name': 'payment_schedule', 'label': 'Phuong thuc va lich thanh toan', 'required': True},
                {'name': 'handover_date', 'label': 'Ngay ban giao dat', 'required': True},
            ],
            'legal_refs': ['Dieu 45 Luat Dat dai 2024', 'Dieu 430 BLDS 2015'],
            'legal_article_keys': ['dieu_45_dat_dai', 'dieu_430_dan_su'],
            'key_terms': [
                'Dat phai co giay chung nhan QSDD',
                'Dat khong co tranh chap',
                'QSDD khong bi ke bien',
                'Con trong thoi han su dung dat',
                'Hop dong phai cong chung tai van phong cong chung',
                'Ben chuyen nhuong chiu trach nhiem hoan tat thu tuc sang ten',
            ]
        },

        # MUA BAN CHUNG (tai san khac)
        'sale': {
            'name': 'Hop dong mua ban tai san',
            'description': 'Hop dong mua ban tai san theo Bo luat Dan su 2015',
            'base_fields': [
                {'name': 'seller_name', 'label': 'Ho ten ben ban', 'required': True},
                {'name': 'seller_id', 'label': 'So CCCD ben ban', 'required': True},
                {'name': 'seller_address', 'label': 'Dia chi ben ban', 'required': True},
                {'name': 'seller_phone', 'label': 'So dien thoai ben ban', 'required': True},
                {'name': 'buyer_name', 'label': 'Ho ten ben mua', 'required': True},
                {'name': 'buyer_id', 'label': 'So CCCD ben mua', 'required': True},
                {'name': 'buyer_address', 'label': 'Dia chi ben mua', 'required': True},
                {'name': 'buyer_phone', 'label': 'So dien thoai ben mua', 'required': True},
                {'name': 'property_name', 'label': 'Ten tai san', 'required': True},
                {'name': 'property_description', 'label': 'Mo ta chi tiet tai san', 'required': True},
                {'name': 'property_condition', 'label': 'Tinh trang tai san', 'required': True},
                {'name': 'sale_price', 'label': 'Gia ban (VND)', 'required': True},
                {'name': 'payment_method', 'label': 'Phuong thuc thanh toan', 'required': True},
                {'name': 'delivery_date', 'label': 'Ngay giao tai san', 'required': True},
                {'name': 'warranty_terms', 'label': 'Dieu khoan bao hanh', 'required': False},
            ],
            'legal_refs': ['Dieu 430 BLDS 2015', 'Dieu 432 BLDS 2015'],
            'legal_article_keys': ['dieu_430_dan_su'],
            'key_terms': [
                'Ben ban phai co quyen so huu hop phap',
                'Tai san khong co tranh chap',
                'Gia ca phai ro rang',
            ]
        },

        # DICH VU
        'service': {
            'name': 'Hop dong dich vu',
            'description': 'Hop dong cung cap dich vu theo Bo luat Dan su 2015',
            'base_fields': [
                {'name': 'provider_name', 'label': 'Ten ben cung cap dich vu', 'required': True},
                {'name': 'provider_id', 'label': 'So CCCD/DKKD/MST', 'required': True},
                {'name': 'provider_address', 'label': 'Dia chi', 'required': True},
                {'name': 'provider_phone', 'label': 'So dien thoai', 'required': True},
                {'name': 'provider_rep', 'label': 'Nguoi dai dien (neu la cong ty)', 'required': False},
                {'name': 'client_name', 'label': 'Ten ben su dung dich vu', 'required': True},
                {'name': 'client_id', 'label': 'So CCCD/DKKD/MST', 'required': True},
                {'name': 'client_address', 'label': 'Dia chi', 'required': True},
                {'name': 'client_phone', 'label': 'So dien thoai', 'required': True},
                {'name': 'service_name', 'label': 'Ten dich vu', 'required': True},
                {'name': 'service_description', 'label': 'Mo ta chi tiet dich vu', 'required': True},
                {'name': 'service_scope', 'label': 'Pham vi cong viec', 'required': True},
                {'name': 'service_fee', 'label': 'Phi dich vu (VND)', 'required': True},
                {'name': 'payment_schedule', 'label': 'Lich thanh toan', 'required': True},
                {'name': 'duration', 'label': 'Thoi han hop dong', 'required': True},
                {'name': 'start_date', 'label': 'Ngay bat dau', 'required': True},
                {'name': 'deliverables', 'label': 'San pham ban giao', 'required': False},
                {'name': 'quality_standards', 'label': 'Tieu chuan chat luong', 'required': False},
            ],
            'legal_refs': ['Dieu 513 BLDS 2015', 'Dieu 514 BLDS 2015', 'Dieu 515 BLDS 2015'],
            'legal_article_keys': ['dieu_513_dan_su'],
            'key_terms': [
                'Ben cung cap phai thuc hien dung yeu cau',
                'Ben su dung phai thanh toan dung han',
                'Ben cung cap bao mat thong tin',
                'Dich vu phai dat tieu chuan da thoa thuan',
            ]
        },

        # LAO DONG
        'employment': {
            'name': 'Hop dong lao dong',
            'description': 'Hop dong lao dong theo Bo luat Lao dong 2019',
            'base_fields': [
                # Nguoi su dung lao dong
                {'name': 'employer_name', 'label': 'Ten nguoi su dung lao dong/Cong ty', 'required': True},
                {'name': 'employer_tax_id', 'label': 'Ma so thue', 'required': True},
                {'name': 'employer_address', 'label': 'Dia chi tru so', 'required': True},
                {'name': 'employer_phone', 'label': 'So dien thoai', 'required': True},
                {'name': 'employer_rep', 'label': 'Nguoi dai dien', 'required': True},
                {'name': 'employer_rep_position', 'label': 'Chuc vu nguoi dai dien', 'required': True},
                # Nguoi lao dong
                {'name': 'employee_name', 'label': 'Ho ten nguoi lao dong', 'required': True},
                {'name': 'employee_birth', 'label': 'Ngay thang nam sinh', 'required': True},
                {'name': 'employee_gender', 'label': 'Gioi tinh', 'required': True},
                {'name': 'employee_id', 'label': 'So CCCD', 'required': True},
                {'name': 'employee_id_date', 'label': 'Ngay cap CCCD', 'required': True},
                {'name': 'employee_id_place', 'label': 'Noi cap CCCD', 'required': True},
                {'name': 'employee_address', 'label': 'Dia chi thuong tru', 'required': True},
                {'name': 'employee_phone', 'label': 'So dien thoai', 'required': True},
                # Noi dung cong viec
                {'name': 'position', 'label': 'Vi tri/Chuc danh', 'required': True},
                {'name': 'job_description', 'label': 'Mo ta cong viec', 'required': True},
                {'name': 'work_location', 'label': 'Dia diem lam viec', 'required': True},
                {'name': 'contract_type', 'label': 'Loai hop dong (xac dinh/khong xac dinh thoi han)', 'required': True},
                {'name': 'contract_duration', 'label': 'Thoi han hop dong', 'required': True},
                {'name': 'start_date', 'label': 'Ngay bat dau lam viec', 'required': True},
                {'name': 'probation_period', 'label': 'Thoi gian thu viec', 'required': False},
                # Luong va phuc loi
                {'name': 'salary', 'label': 'Muc luong co ban (VND/thang)', 'required': True},
                {'name': 'allowances', 'label': 'Cac khoan phu cap', 'required': False},
                {'name': 'payment_date', 'label': 'Ngay tra luong', 'required': True},
                {'name': 'payment_method', 'label': 'Hinh thuc tra luong', 'required': True},
                {'name': 'working_hours', 'label': 'Thoi gio lam viec', 'required': True},
                {'name': 'annual_leave', 'label': 'So ngay nghi phep nam', 'required': True},
                {'name': 'insurance', 'label': 'Bao hiem (BHXH, BHYT, BHTN)', 'required': True},
            ],
            'legal_refs': ['Dieu 13 Bo luat Lao dong 2019', 'Dieu 21 Bo luat Lao dong 2019'],
            'legal_article_keys': ['dieu_21_lao_dong'],
            'key_terms': [
                'Hop dong phai lap thanh van ban',
                'Luong khong thap hon muc luong toi thieu vung',
                'Nguoi lao dong duoc dong BHXH, BHYT, BHTN',
                'Thoi gio lam viec khong qua 8 gio/ngay, 48 gio/tuan',
                'Nguoi lao dong duoc nghi phep nam co huong luong',
            ]
        }
    }

    def __init__(self):
        self.client, self.provider = get_llm_client()
        settings = get_settings()
        self.model = settings.llm_model

    def generate_template(
        self,
        contract_type: str,
        legal_content: Optional[str] = None,
        custom_requirements: Optional[str] = None
    ) -> DynamicTemplate:
        """Generate a contract template based on type and optional legal content"""

        if contract_type not in self.BASE_TEMPLATES:
            raise ValueError(f"Loai hop dong khong ho tro: {contract_type}")

        base = self.BASE_TEMPLATES[contract_type]

        # Start with base fields
        fields = [
            DynamicField(
                name=f['name'],
                label=f['label'],
                required=f.get('required', True),
                default_value=f.get('default_value'),
                description=f.get('description'),
            )
            for f in base['base_fields']
        ]

        # Get full legal articles
        legal_articles = []
        for key in base.get('legal_article_keys', []):
            if key in self.LEGAL_ARTICLES:
                article_data = self.LEGAL_ARTICLES[key]
                legal_articles.append(LegalArticle(
                    article_number=article_data['article_number'],
                    article_title=article_data['article_title'],
                    document_name=article_data['document_name'],
                    content=article_data['content'],
                    summary=article_data['summary']
                ))

        return DynamicTemplate(
            contract_type=contract_type,
            name=base['name'],
            description=base['description'],
            fields=fields,
            legal_references=base['legal_refs'],
            legal_articles=legal_articles,
            key_terms=base['key_terms'],
            generated_from=legal_content[:200] + '...' if legal_content else 'Base template'
        )

    def get_template_info(self, contract_type: str) -> dict:
        """Get basic template information"""
        if contract_type not in self.BASE_TEMPLATES:
            return None

        base = self.BASE_TEMPLATES[contract_type]
        return {
            'type': contract_type,
            'name': base['name'],
            'description': base['description'],
            'field_count': len(base['base_fields']),
            'legal_references': base['legal_refs'],
            'key_terms': base['key_terms']
        }

    def list_available_types(self) -> list[dict]:
        """List all available contract types"""
        return [
            self.get_template_info(ct)
            for ct in self.BASE_TEMPLATES.keys()
        ]

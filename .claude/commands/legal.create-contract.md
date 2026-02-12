---
description: Create a new legal contract interactively by researching laws and asking questions step-by-step
---

## User Input

```text
$ARGUMENTS
```

## Purpose

Tao hop dong phap ly moi bang cach:
1. **Research tu DB truoc** - Tim dieu luat lien quan trong co so du lieu da crawl
2. **Hoi-dap** - Hoi tung thong tin can thiet cho loai hop dong cu the
3. **Tao dieu khoan** - Dung ket qua research de tao cac Dieu (articles) hop dong
4. **Luu tru** - Luu du lieu hop dong thanh file JSON

## Workflow

### Step 1: Xac dinh loai hop dong

Neu `$ARGUMENTS` rong hoac khong ro, hoi nguoi dung:

```
Ban muon tao loai hop dong gi?

Vi du: thue nha, mua ban nha, mua ban dat, dich vu, lao dong, vay tien, uy quyen, hop tac kinh doanh, ...

Nhap loai hop dong:
```

### Step 2: Research (BAT BUOC - ca DB lan Web)

**QUAN TRONG** - PHAI search CA HAI nguon truoc khi lam bat ky gi khac:

#### 2a. Search Supabase articles - lay dieu luat da co trong DB:

Data articles nam trong bang `articles` tren Supabase (pgvector). Dung lenh search de truy van:

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot search "hop dong [loai hop dong] dieu kien" --top-k 10
python -m legal_chatbot search "quyen nghia vu [ben A/ben B] [loai hop dong]" --top-k 10
python -m legal_chatbot search "[loai hop dong] thanh toan giao nhan" --top-k 10
python -m legal_chatbot search "[loai hop dong] cham dut tranh chap" --top-k 10
```

Ghi nhan cac dieu luat da co trong Supabase (article_number, document_title, content) de so sanh o buoc 2d.

#### 2b. LUON search web - kiem tra luat moi nhat (luat co the update):

- `"hop dong [loai hop dong] theo luat Viet Nam [nam hien tai]"`
- `"dieu khoan bat buoc hop dong [loai hop dong] Bo luat Dan su 2015"`
- `"mau hop dong [loai hop dong] thuvienphapluat.vn"`
- `"luat [lien quan] moi nhat sua doi bo sung"`

#### 2c. Kiem tra hop dong cu cung loai trong Supabase:

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot audit list --type contract
```

Neu co hop dong cung loai:
- Xem `legal_references` va `law_versions` da dung
- So sanh voi ket qua web: luat co bi sua doi / thay the khong?
- Tham khao de tao hop dong moi nhat quan

#### 2d. BAT BUOC - So sanh va sync dieu luat moi vao Supabase:

**RULE**: Neu buoc 2a tra ve **0 ket qua** hoac **khong co dieu luat lien quan truc tiep** den loai hop dong dang tao => PHAI sync dieu luat tu web vao Supabase TRUOC KHI tiep tuc.

**QUY TRINH SYNC:**

**Buoc 1** - Xac dinh dieu luat can sync tu ket qua web (2b):
- Liet ke tat ca dieu luat lien quan (vi du: Dieu 463-471 BLDS 2015 cho vay tien)
- Kiem tra tung dieu da co trong Supabase chua (dua tren ket qua 2a)

**Buoc 2** - Voi MOI van ban luat chua co, tao file JSON va sync:

```bash
cd c:/Users/ADMIN/chatbot
```

Tao file `data/raw/sync_[ten_luat_viet_tat].json` voi format:
```json
{
  "document_id": "blds_2015",
  "document_title": "Bo luat Dan su 2015",
  "document_number": "91/2015/QH13",
  "document_type": "luat",
  "articles": [
    {
      "article_number": 463,
      "title": "Hop dong vay tai san",
      "content": "Noi dung DAY DU cua dieu luat, copy tu web..."
    },
    {
      "article_number": 466,
      "title": "Nghia vu tra no cua ben vay",
      "content": "Noi dung DAY DU..."
    }
  ]
}
```

**LUU Y**: `contract_type` KHONG can ghi trong JSON. Category se duoc tu dong xac dinh tu `document_title`:
- "Bo luat Dan su 2015" → category `dan_su`
- "Luat Dat dai 2024" → category `dat_dai`
- "Luat Duong bo 2024" → category `duong_bo`

Moi van ban luat se duoc gan category RIENG dua tren ten van ban, KHONG phai dua tren loai hop dong.

Sau do chay sync:
```bash
python -m legal_chatbot sync-articles "data/raw/sync_[ten_luat].json"
```

**Buoc 3** - VERIFY da sync thanh cong:
```bash
python -m legal_chatbot search "[loai hop dong] dieu kien" --top-k 5
```
Neu van tra ve 0 ket qua => sync that bai, phai kiem tra lai.

**KHONG can sync khi:**
- Buoc 2a da tra ve cac dieu luat lien quan truc tiep va con hieu luc
- Noi dung web khong dang tin cay

**Neu hop dong cu (2c) dung luat da het hieu luc / bi sua doi:**
- Thong bao nguoi dung: "Luat X da duoc cap nhat, se dung phien ban moi"
- Sync phien ban moi va dung cho hop dong dang tao

#### 2e. Tong hop - Phai co du thong tin de tao:

- `legal_references`: Cac dieu luat ap dung (phien ban moi nhat)
- `fields`: Cac truong thong tin can thu thap
- `articles`: Cac dieu khoan hop dong (QUAN TRONG NHAT)

### Step 3: Thong bao ket qua research

Truoc khi bat dau hoi, thong bao ngan gon:

```
Da tim trong co so du lieu phap luat!

Tim thay [N] dieu luat lien quan:
- Dieu [X] [Luat Y]: [mo ta ngan]
- Dieu [Z] [Luat W]: [mo ta ngan]
...

Se can thu thap [N] thong tin. Bat dau nhe!
```

### Step 4: Thu thap thong tin

Hoi TUNG CAU MOT, doi nguoi dung tra loi truoc khi hoi tiep.

Quy tac:
- Noi chuyen tu nhien, than thien (khong may moc)
- Goi y format neu can (ngay thang, so tien)
- Cho phep "bo qua" cau hoi khong bat buoc
- Cho phep "quay lai" de sua cau truoc

Vi du hoi-dap:
```
Bot: Ho ten day du cua ben [A] la gi?
User: Nguyen Van A

Bot: OK! Ngay sinh cua anh/chi Nguyen Van A?
User: 15/03/1985

Bot: So CCCD (12 so)?
User: 012345678901

...
```

### Step 5: Tao articles tu research (BAT BUOC)

**DAY LA BUOC QUAN TRONG NHAT** - Dung ket qua research o Step 2 de tao cac Dieu hop dong.

Moi hop dong PHAI co it nhat cac Dieu sau:
- **Doi tuong hop dong** (tai san, dich vu, cong viec)
- **Gia ca va phuong thuc thanh toan**
- **Thoi han** (thuc hien, giao nhan, v.v.)
- **Quyen va nghia vu cua Ben A**
- **Quyen va nghia vu cua Ben B**
- **Cam ket cua cac ben**
- **Trach nhiem do vi pham**
- **Giai quyet tranh chap**
- **Dieu khoan chung** (hieu luc, so ban, v.v.)

Format articles:
```json
"articles": [
  {
    "title": "ĐIỀU 1: ĐỐI TƯỢNG CỦA HỢP ĐỒNG",
    "content": [
      "1.1. Bên A đồng ý [hành động] và Bên B đồng ý [hành động]...",
      "1.2. [Chi tiết bổ sung dựa trên điều luật đã research]..."
    ]
  },
  {
    "title": "ĐIỀU 2: GIÁ CẢ VÀ PHƯƠNG THỨC THANH TOÁN",
    "content": [
      "2.1. Giá [mua bán/thuê/dịch vụ]: theo thỏa thuận đã ghi ở trên.",
      "2.2. Phương thức thanh toán: [theo thông tin đã thu thập].",
      "2.3. [Điều khoản bổ sung dựa trên luật]."
    ]
  }
]
```

**THAM KHAO** file `data/contracts/mua_ban_xe_may_20260206_103000.json` de xem vi du hoan chinh ve format articles.

### Step 6: Luu du lieu

Sau khi thu thap du, luu file JSON:

Duong dan: `data/contracts/[loai_hop_dong]_[YYYYMMDD_HHMMSS].json`

**QUAN TRONG** - JSON phai co format sau de PDF hien thi dung tieng Viet:

```json
{
  "contract_type": "rental",
  "contract_type_vn": "Hợp đồng thuê nhà",
  "created_at": "2026-02-06T10:30:00",
  "status": "draft",
  "legal_references": [
    {"article": "Điều 472", "law": "Bộ luật Dân sự 2015", "document_number": "91/2015/QH13", "description": "Hợp đồng thuê tài sản"},
    {"article": "Điều 121-122", "law": "Luật Nhà ở 2014", "document_number": "65/2014/QH13", "description": "Điều kiện giao dịch nhà ở"}
  ],
  "fields": {
    "ben_cho_thue": {
      "_label": "BÊN CHO THUÊ (BÊN A)",
      "ho_ten": {"value": "Nguyễn Văn A", "label": "Họ và tên"},
      "ngay_sinh": {"value": "01/01/1980", "label": "Ngày sinh"},
      "so_cccd": {"value": "012345678901", "label": "Số CCCD"}
    },
    "ben_thue": {
      "_label": "BÊN THUÊ (BÊN B)",
      "ho_ten": {"value": "Trần Văn B", "label": "Họ và tên"}
    },
    "nha_o": {
      "_label": "THÔNG TIN NHÀ Ở",
      "dia_chi": {"value": "123 Đường ABC", "label": "Địa chỉ"}
    },
    "tai_chinh": {
      "_label": "TÀI CHÍNH",
      "gia_thue": {"value": 5000000, "label": "Giá thuê hàng tháng"}
    }
  },
  "articles": [
    {
      "title": "ĐIỀU 1: ĐỐI TƯỢNG CỦA HỢP ĐỒNG",
      "content": [
        "1.1. Bên A đồng ý cho thuê và Bên B đồng ý thuê nhà ở tại địa chỉ nêu trên.",
        "1.2. Nhà ở thuộc quyền sở hữu hợp pháp của Bên A, không có tranh chấp."
      ]
    },
    {
      "title": "ĐIỀU 2: GIÁ THUÊ VÀ PHƯƠNG THỨC THANH TOÁN",
      "content": [
        "2.1. Giá thuê hàng tháng: theo thỏa thuận đã ghi ở phần tài chính.",
        "2.2. Bên B thanh toán đúng hạn theo phương thức đã thỏa thuận."
      ]
    },
    {
      "title": "ĐIỀU 3: THỜI HẠN THUÊ",
      "content": [
        "3.1. Thời hạn thuê theo thỏa thuận của hai bên.",
        "3.2. Khi hết hạn, nếu Bên B có nhu cầu tiếp tục thuê, hai bên thương lượng gia hạn."
      ]
    },
    {
      "title": "ĐIỀU 4: QUYỀN VÀ NGHĨA VỤ CỦA BÊN CHO THUÊ (BÊN A)",
      "content": [
        "4.1. Giao nhà đúng thời hạn và tình trạng đã thỏa thuận (Điều 131 Luật Nhà ở).",
        "4.2. Bảo đảm cho Bên B sử dụng ổn định nhà trong thời hạn thuê.",
        "4.3. Bảo trì, sửa chữa nhà theo định kỳ hoặc theo thỏa thuận."
      ]
    },
    {
      "title": "ĐIỀU 5: QUYỀN VÀ NGHĨA VỤ CỦA BÊN THUÊ (BÊN B)",
      "content": [
        "5.1. Sử dụng nhà đúng mục đích đã thỏa thuận.",
        "5.2. Thanh toán tiền thuê đầy đủ và đúng hạn.",
        "5.3. Bảo quản nhà, không tự ý sửa chữa, cải tạo khi chưa có sự đồng ý của Bên A."
      ]
    },
    {
      "title": "ĐIỀU 6: CHẤM DỨT HỢP ĐỒNG",
      "content": [
        "6.1. Hết thời hạn thuê mà không gia hạn.",
        "6.2. Hai bên thỏa thuận chấm dứt trước hạn.",
        "6.3. Một bên vi phạm nghiêm trọng nghĩa vụ hợp đồng."
      ]
    },
    {
      "title": "ĐIỀU 7: GIẢI QUYẾT TRANH CHẤP",
      "content": [
        "7.1. Mọi tranh chấp được giải quyết thông qua thương lượng, hòa giải.",
        "7.2. Nếu không giải quyết được, đưa ra Tòa án nhân dân có thẩm quyền."
      ]
    },
    {
      "title": "ĐIỀU 8: ĐIỀU KHOẢN CHUNG",
      "content": [
        "8.1. Hợp đồng có hiệu lực kể từ ngày hai bên ký.",
        "8.2. Hợp đồng được lập thành 02 bản có giá trị pháp lý như nhau."
      ]
    }
  ]
}
```

**Luu y ve `articles`:**
- BAT BUOC phai co - khong duoc bo qua
- Lay noi dung tu ket qua research o Step 2 (cac dieu luat da tim trong DB)
- Moi article co `title` (tieu de dieu khoan) va `content` (danh sach cac khoan)
- Noi dung phai dua tren luat phap Viet Nam, trich dan cu the dieu luat khi can
- Phai co it nhat 7-9 Dieu (doi tuong, gia ca, thoi han, quyen nghia vu A, quyen nghia vu B, cam ket, tranh chap, dieu khoan chung)
- Tham khao `data/contracts/mua_ban_xe_may_20260206_103000.json` de xem vi du hoan chinh

### Step 7: Luu hop dong vao Supabase (BAT BUOC)

Sau khi luu file JSON, **PHAI** luu vao Supabase `contract_audits` table:

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot save-contract "data/contracts/[filename].json"
```

Lenh nay se:
- Luu `fields`, `articles`, `legal_references` vao Supabase
- Tra ve `audit_id` de truy xuat sau nay
- Cho phep `/legal.audit` kiem tra va verify hop dong

### Step 8: Xac nhan

Sau khi luu, hien thi:

```
Da tao xong hop dong [loai]!

Thong tin chinh:
- Ben A: [ten]
- Ben B: [ten]
- [Thong tin quan trong khac]
- So dieu khoan: [N] dieu
- Audit ID: [audit_id]

File: data/contracts/[filename].json
Da luu vao Supabase!

Ban co the:
- Noi "xem truoc" hoac chay /legal.preview de xem tren web
- Noi "xuat pdf" hoac chay /legal.export-pdf de xuat file PDF
- Chay /legal.audit show [audit_id] de xem chi tiet
```

## Conversation Style

- Than thien, tu nhien nhu noi chuyen binh thuong
- KHONG dung ngon ngu "AI", "he thong", "xu ly"
- KHONG hoi nhieu cau cung luc
- Co the dung "OK!", "Da ghi nhan!", "Roi!", "Tiep nhe!"
- Neu nguoi dung nhap sai, nhe nhang hoi lai

## Error Handling

- Neu local DB khong co du lieu (chua crawl), thong bao: "Chua co du lieu trong DB. Ban co muon crawl truoc? (/legal.pipeline crawl [category])"
- Neu search khong tra ve ket qua, fallback sang WebSearch
- Neu nguoi dung muon huy, xac nhan truoc khi xoa du lieu
- Neu thu muc `data/contracts/` chua ton tai, tu dong tao

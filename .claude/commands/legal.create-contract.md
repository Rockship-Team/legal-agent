---
description: Create a new legal contract interactively by researching laws and asking questions step-by-step
---

## User Input

```text
$ARGUMENTS
```

## Purpose

Tao hop dong phap ly moi (DB-only, KHONG search, KHONG web search):
1. **contract-lookup** - 1 lenh duy nhat: doc template + cached articles tu DB
2. **Hoi-dap** - Hoi tung thong tin can thiet
3. **Tao dieu khoan** - Dung cached articles de tao cac Dieu hop dong
4. **Luu tru** - Luu file JSON + Supabase audit

## Workflow

### Step 1: Xac dinh loai hop dong

**TRUOC TIEN** - Query DB de lay danh sach hop dong da co du lieu:

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot contract-lookup --list
```

Lenh nay tra ve JSON:
```json
{
  "available": [
    {"contract_type": "cho_thue_dat", "display_name": "Hợp đồng cho thuê đất", "articles_count": 15, "cached": true},
    {"contract_type": "mua_ban_dat", "display_name": "Hợp đồng mua bán đất", "articles_count": 12, "cached": true}
  ]
}
```

Neu `available` rong → thong bao:
```
Hien tai minh chua co du lieu hop dong nao. Ban hay lien he quan tri vien de bo sung du lieu.
```

Neu `$ARGUMENTS` rong hoac khong ro, hoi nguoi dung voi danh sach tu DB:

```
Ban muon tao loai hop dong gi?

Hien tai minh da co du lieu cho:
- [display_name] ([articles_count] dieu luat)
- [display_name] ([articles_count] dieu luat)
...

Nhap loai hop dong:
```

Neu `$ARGUMENTS` co nhung KHONG match voi bat ky contract_type nao trong `available`:
```
Minh chua co du lieu de tao hop dong [loai nay].
Hien tai minh co the tao: [danh sach tu DB]
Ban muon tao loai nao?
```

Map input sang contract_type (chi khi co trong available):
- "mua ban dat", "mua dat" → `mua_ban_dat`
- "cho thue dat", "thue dat" → `cho_thue_dat`
- "chuyen nhuong dat" → `chuyen_nhuong_dat`
- "cho thue nha", "thue nha" → `cho_thue_nha`
- "mua ban nha", "mua nha" → `mua_ban_nha`
- "hop dong lao dong", "lao dong" → `hop_dong_lao_dong`
- "thu viec" → `thu_viec`
- "vay tien" → `vay_tien`
- "uy quyen" → `uy_quyen`
- "dich vu" → `dich_vu`

### Step 2: Lay template + dieu luat tu DB (1 LENH DUY NHAT)

**QUAN TRONG**: Chi chay 1 lenh `contract-lookup`. KHONG chay `search` hay `contract-search`.

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot contract-lookup [CONTRACT_TYPE]
```

Vi du:
```bash
python -m legal_chatbot contract-lookup cho_thue_dat
```

Lenh nay tra ve JSON gom:
- `display_name`: Ten hop dong
- `required_laws`: Cac luat can thiet
- `min_articles`: So dieu luat toi thieu
- `articles_count`: So dieu luat da cache
- `articles`: Danh sach dieu luat da duoc pre-compute khi crawl

**KHONG can load embedding model. KHONG can search. Chi doc tu DB.**

#### 2a. Neu KHONG co du lieu (template not found hoac no cache):

```
Minh chua co du lieu de tao hop dong [loai]. Ban hay lien he quan tri vien de bo sung.
```

**KHONG** co fallback sang WebSearch hay search. Neu khong co data → dung lai.

#### 2b. Kiem tra hop dong cu cung loai:

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot audit list --type contract
```

### Step 3: Thong bao ket qua

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

### Step 5: Tao articles tu cached data (BAT BUOC)

**DAY LA BUOC QUAN TRONG NHAT** - Dung cached articles tu Step 2 de tao cac Dieu hop dong.

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
  }
]
```

**THAM KHAO** file `data/contracts/mua_ban_xe_may_20260206_103000.json` de xem vi du hoan chinh.

### Step 6: Luu du lieu

Duong dan: `data/contracts/[loai_hop_dong]_[YYYYMMDD_HHMMSS].json`

**QUAN TRONG** - JSON phai co format nhu da dinh nghia (contract_type, contract_type_vn, legal_references, fields, articles).

**Luu y ve `articles`:**
- BAT BUOC phai co - khong duoc bo qua
- Lay noi dung tu cached articles o Step 2
- Moi article co `title` (tieu de dieu khoan) va `content` (danh sach cac khoan)
- Noi dung phai dua tren luat phap Viet Nam, trich dan cu the dieu luat khi can
- Phai co it nhat 7-9 Dieu
- Tham khao `data/contracts/mua_ban_xe_may_20260206_103000.json`

### Step 7: Luu hop dong vao Supabase (BAT BUOC)

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot save-contract "data/contracts/[filename].json"
```

### Step 8: Xac nhan

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

- Neu DB khong co du lieu → thong bao than thien. KHONG fallback sang WebSearch
- Neu articles < min_articles → canh bao + cho user quyet dinh
- Neu nguoi dung muon huy, xac nhan truoc khi xoa du lieu
- Neu thu muc `data/contracts/` chua ton tai, tu dong tao

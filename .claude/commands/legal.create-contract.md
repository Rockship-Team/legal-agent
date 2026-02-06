---
description: Create a new legal contract interactively by researching laws and asking questions step-by-step
---

## User Input

```text
$ARGUMENTS
```

## Purpose

Tao hop dong phap ly moi bang cach:
1. **Research truoc** - Tim hieu luat phap Viet Nam lien quan
2. **Hoi-dap** - Hoi tung thong tin can thiet cho loai hop dong cu the
3. **Luu tru** - Luu du lieu hop dong thanh file JSON

## Workflow

### Step 1: Xac dinh loai hop dong

Neu `$ARGUMENTS` rong hoac khong ro, hoi nguoi dung:

```
Ban muon tao loai hop dong gi?

Vi du: thue nha, mua ban nha, mua ban dat, dich vu, lao dong, vay tien, uy quyen, hop tac kinh doanh, ...

Nhap loai hop dong:
```

### Step 2: Research phap luat tu thuvienphapluat.vn

**BAT BUOC** - Truoc khi hoi bat ky thong tin nao:

1. **Fetch truc tiep tu thuvienphapluat.vn** - Su dung WebFetch de lay mau hop dong va dieu khoan:
   - URL mau: `https://thuvienphapluat.vn/van-ban/Bat-dong-san/...` (cho hop dong dat dai)
   - URL mau: `https://thuvienphapluat.vn/van-ban/Thuong-mai/...` (cho hop dong thuong mai)
   - URL mau: `https://thuvienphapluat.vn/van-ban/Lao-dong-Tien-luong/...` (cho hop dong lao dong)

2. **Search bo sung** neu can them thong tin:
   - `"hop dong [loai hop dong] theo luat Viet Nam yeu cau gi"`
   - `"dieu khoan bat buoc hop dong [loai hop dong] Bo luat Dan su 2015"`
   - `"mau hop dong [loai hop dong] thuvienphapluat.vn"`

3. **Tong hop tu research** - QUAN TRONG: Luu lai de dung trong JSON:
   - Cac dieu luat ap dung (vi du: Dieu 513 BLDS 2015)
   - Cac truong thong tin bat buoc
   - **Cac dieu khoan hop dong** (quyen va nghia vu cac ben, dieu kien, cam ket, v.v.)

### Step 3: Thong bao ket qua research

Truoc khi bat dau hoi, thong bao ngan gon:

```
Da tim hieu phap luat lien quan!

Cac dieu luat ap dung:
- [Dieu X Luat Y]
- [Dieu Z Luat W]

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

### Step 5: Luu du lieu

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
    {"article": "Điều 472", "law": "Bộ luật Dân sự 2015"},
    {"article": "Điều 121-122", "law": "Luật Nhà ở 2014"}
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
      "title": "ĐIỀU 1: QUYỀN VÀ NGHĨA VỤ CỦA BÊN CHO THUÊ",
      "content": [
        "1.1. Bên cho thuê có nghĩa vụ giao nhà đúng thời hạn và tình trạng đã thỏa thuận.",
        "1.2. Bên cho thuê có quyền yêu cầu bên thuê thanh toán tiền thuê đúng hạn."
      ]
    },
    {
      "title": "ĐIỀU 2: QUYỀN VÀ NGHĨA VỤ CỦA BÊN THUÊ",
      "content": [
        "2.1. Bên thuê có nghĩa vụ sử dụng nhà đúng mục đích.",
        "2.2. Bên thuê có quyền được sử dụng nhà ổn định trong thời hạn thuê."
      ]
    }
  ]
}
```

**Luu y ve `articles`:**
- Lay noi dung tu ket qua research o Step 2
- Khong duoc tu nghĩ ra - phai dua tren luat phap Viet Nam
- Moi article co `title` (tieu de dieu khoan) va `content` (danh sach cac khoan)
- Noi dung phai phu hop voi loai hop dong cu the

### Step 6: Xac nhan

Sau khi luu, hien thi:

```
Da tao xong hop dong [loai]!

Thong tin chinh:
- Ben A: [ten]
- Ben B: [ten]
- [Thong tin quan trong khac]

File: data/contracts/[filename].json

Ban co the:
- Noi "xem truoc" hoac chay /legal.preview de xem tren web
- Noi "xuat pdf" hoac chay /legal.export-pdf de xuat file PDF
```

## Conversation Style

- Than thien, tu nhien nhu noi chuyen binh thuong
- KHONG dung ngon ngu "AI", "he thong", "xu ly"
- KHONG hoi nhieu cau cung luc
- Co the dung "OK!", "Da ghi nhan!", "Roi!", "Tiep nhe!"
- Neu nguoi dung nhap sai, nhe nhang hoi lai

## Error Handling

- Neu khong tim duoc thong tin phap luat, thong bao va hoi nguoi dung co muon tiep tuc khong
- Neu nguoi dung muon huy, xac nhan truoc khi xoa du lieu
- Neu thu muc `data/contracts/` chua ton tai, tu dong tao

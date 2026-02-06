---
description: Export the current contract to a PDF file with proper formatting
---

## User Input

```text
$ARGUMENTS
```

## Purpose

Xuất hợp đồng đã tạo thành file PDF để in ấn và lưu trữ.

## Workflow

### Step 1: Find Contract

Check `data/contracts/` directory for the most recent contract JSON file.

If `$ARGUMENTS` contains a filename, use that file instead.

If no contracts found:
```
Chưa có hợp đồng nào. Chạy /legal.create-contract để tạo hợp đồng mới.
```

### Step 2: Generate PDF

Sử dụng UniversalPDFGenerator - xử lý tất cả loại hợp đồng tự động:

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot.services.pdf_generator "data/contracts/[FILENAME].json"
```

Hoặc trong Python:

```python
from legal_chatbot.services.pdf_generator import generate_pdf

# Tự động tạo PDF từ JSON (output cùng tên với .pdf)
result = generate_pdf("data/contracts/[FILENAME].json")

# Hoặc chỉ định output path
result = generate_pdf("data/contracts/[FILENAME].json", "output.pdf")
```

### Step 3: Report Result

On success:
```
Đã xuất hợp đồng thành công!

File PDF: data/contracts/[FILENAME].pdf
Kích thước: [SIZE] KB

Bạn có thể:
- Mở file PDF để xem và in
- Gửi cho các bên ký kết
- Lưu trữ làm hồ sơ

Lưu ý: Đây chỉ là mẫu hợp đồng tham khảo. Vui lòng kiểm tra kỹ trước khi sử dụng.
```

On error:
```
Lỗi khi xuất PDF: [ERROR_MESSAGE]

Thử:
1. Kiểm tra file hợp đồng tồn tại
2. Chạy /legal.preview để xem trước
3. Chạy lại /legal.export-pdf
```

## Features

UniversalPDFGenerator tự động:
- Đọc cấu trúc JSON và tạo PDF phù hợp
- Hiển thị tiếng Việt có dấu (font Times New Roman)
- Tạo các section dựa trên dữ liệu (seller/buyer/land/etc.)
- Format tiền tệ VNĐ
- Tạo bảng thanh toán nếu có payment_schedule
- Thêm điều khoản chuẩn
- Thêm phần chữ ký

## Supported Contract Types

Generator tự động xử lý tất cả loại hợp đồng:
- `rental` - Thuê nhà
- `sale_land` - Chuyển nhượng đất
- `sale_house` - Mua bán nhà
- `employment` - Lao động
- `service` - Dịch vụ
- Và bất kỳ loại hợp đồng nào khác với cấu trúc JSON hợp lệ

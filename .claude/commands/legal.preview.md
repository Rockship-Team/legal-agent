---
description: Preview the current contract in a web browser with formatted HTML
---

## User Input

```text
$ARGUMENTS
```

## Purpose

Xem truoc hop dong da tao tren trinh duyet web voi dinh dang HTML dep.

## Workflow

### Step 1: Find Latest Contract

Check `data/contracts/` directory for the most recent contract file.

If `$ARGUMENTS` contains a filename, use that file instead.

If no contracts found:
```
Chua co hop dong nao. Chay /legal.create-contract de tao hop dong moi.
```

### Step 2: Load Contract Data

Read the JSON contract file and extract:
- Contract type and name
- All field values
- Legal references

### Step 3: Generate HTML Preview

Create an HTML file at `data/contracts/preview_[timestamp].html` with the following structure:

```html
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Xem truoc: [Contract Name]</title>
    <style>
        body {
            font-family: 'Times New Roman', serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.8;
        }
        .header { text-align: center; margin-bottom: 30px; }
        .title { font-size: 24px; font-weight: bold; margin: 20px 0; text-transform: uppercase; }
        .section { margin: 20px 0; }
        .section-title { font-weight: bold; color: #1a5f7a; border-bottom: 1px solid #1a5f7a; padding-bottom: 5px; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; }
        td { padding: 8px; border: 1px solid #ddd; }
        td:first-child { width: 40%; font-weight: bold; background: #f5f5f5; }
        .legal-basis { background: #f8f9fa; padding: 15px; border-left: 4px solid #1a5f7a; margin: 20px 0; }
        .signature { display: flex; justify-content: space-between; margin-top: 50px; }
        .signature-box { width: 45%; text-align: center; }
        .disclaimer { color: #666; font-size: 12px; margin-top: 30px; padding: 15px; border: 1px dashed #ccc; }
        @media print { .no-print { display: none; } }
    </style>
</head>
<body>
    <div class="header">
        <div>CONG HOA XA HOI CHU NGHIA VIET NAM</div>
        <div><strong>Doc lap - Tu do - Hanh phuc</strong></div>
        <div>---oOo---</div>
    </div>

    <div class="title">[CONTRACT NAME]</div>

    <!-- Contract content sections -->

    <div class="section">
        <div class="section-title">BEN A (BEN [ROLE])</div>
        <table>
            <!-- Party A fields -->
        </table>
    </div>

    <div class="section">
        <div class="section-title">BEN B (BEN [ROLE])</div>
        <table>
            <!-- Party B fields -->
        </table>
    </div>

    <div class="section">
        <div class="section-title">DOI TUONG HOP DONG</div>
        <table>
            <!-- Property/Subject fields -->
        </table>
    </div>

    <div class="section">
        <div class="section-title">DIEU KHOAN HOP DONG</div>
        <table>
            <!-- Terms fields -->
        </table>
    </div>

    <div class="legal-basis">
        <strong>CO SO PHAP LY:</strong><br>
        <!-- Legal references -->
    </div>

    <div class="signature">
        <div class="signature-box">
            <strong>BEN A</strong><br>
            (Ky va ghi ro ho ten)<br><br><br><br>
        </div>
        <div class="signature-box">
            <strong>BEN B</strong><br>
            (Ky va ghi ro ho ten)<br><br><br><br>
        </div>
    </div>

    <div class="disclaimer">
        <strong>Luu y:</strong> Day chi la ban xem truoc mang tinh chat tham khao.
        Vui long kiem tra ky thong tin truoc khi su dung chinh thuc.
        Khong thay the tu van phap ly chuyen nghiep.
    </div>

    <div class="no-print" style="text-align: center; margin-top: 20px;">
        <button onclick="window.print()">In hop dong</button>
    </div>
</body>
</html>
```

### Step 4: Open in Browser

Use the appropriate command to open the HTML file:

**Windows:**
```powershell
Start-Process "data/contracts/preview_[timestamp].html"
```

**Mac/Linux:**
```bash
open "data/contracts/preview_[timestamp].html"
# or
xdg-open "data/contracts/preview_[timestamp].html"
```

### Step 5: Confirmation

```
Da mo xem truoc hop dong trong trinh duyet!

File: data/contracts/preview_[timestamp].html

Ban co the:
- Nhan Ctrl+P trong trinh duyet de in
- Chay /legal.export-pdf de xuat PDF chinh thuc
```

## Field Grouping by Contract Type

### Rental
- **Ben cho thue:** landlord_*
- **Ben thue:** tenant_*
- **Nha cho thue:** property_*
- **Dieu khoan thue:** monthly_rent, deposit, duration_*, payment_*

### Sale (House/Land)
- **Ben ban/chuyen nhuong:** seller_* or transferor_*
- **Ben mua/nhan:** buyer_* or transferee_*
- **Tai san:** house_*, land_*, property_*
- **Gia ca:** *_price, payment_*, deposit_*

### Employment
- **Nguoi su dung lao dong:** employer_*
- **Nguoi lao dong:** employee_*
- **Cong viec:** position, job_*, work_*
- **Che do:** salary, allowances, insurance, working_hours

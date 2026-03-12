# Data Model: Contract Suggestion Examples & Type Fix

**Date**: 2026-03-12 | **Feature**: 005-contract-suggestion-data

## Entity Changes

### ContractTemplate (modified)

Existing table `contract_templates` — add one new JSONB column:

| Field | Type | New? | Description |
|-------|------|------|-------------|
| id | UUID | No | Primary key |
| contract_type | TEXT | No | Slug (e.g., "cho_thue_xe") |
| display_name | TEXT | No | Vietnamese name |
| required_fields | JSONB | No | Field definitions |
| **sample_data** | **JSONB** | **Yes** | **Example data per field** |
| is_active | BOOLEAN | No | Active flag |

### SampleData JSONB Structure

```json
{
  "<field_name>": {
    "examples": ["example 1", "example 2"],
    "format_hint": "Brief format description"
  }
}
```

**Example for car rental template:**
```json
{
  "ben_a_ten": {
    "examples": ["Nguyễn Văn Minh", "Trần Thị Hoa"],
    "format_hint": "Họ và tên đầy đủ"
  },
  "ben_a_cccd": {
    "examples": ["001099012345", "079234567890"],
    "format_hint": "12 chữ số"
  },
  "ben_a_dia_chi": {
    "examples": [
      "123 Nguyễn Huệ, P. Bến Nghé, Q.1, TP.HCM",
      "45 Trần Phú, P. Mộ Lao, Q. Hà Đông, Hà Nội"
    ],
    "format_hint": "Số nhà, đường, phường/xã, quận/huyện, tỉnh/TP"
  },
  "mo_ta_tai_san": {
    "examples": [
      "Toyota Vios 1.5E 2024, BKS: 51A-12345, màu trắng, số tự động",
      "Honda City RS 2023, BKS: 30A-67890, màu đen, số tự động"
    ],
    "format_hint": "Hãng xe, dòng xe, năm SX, biển số, màu sắc"
  },
  "gia_thue": {
    "examples": ["800.000 VNĐ/ngày", "5.000.000 VNĐ/tháng"],
    "format_hint": "Số tiền + đơn vị thời gian"
  }
}
```

## Migration

```sql
-- 005_sample_data.sql
ALTER TABLE contract_templates
ADD COLUMN IF NOT EXISTS sample_data JSONB DEFAULT NULL;

COMMENT ON COLUMN contract_templates.sample_data IS
  'LLM-generated example data for each field. Structure: {field_name: {examples: [...], format_hint: "..."}}';
```

## State Transitions

### Seed Command Flow
```
Template (no sample_data) → seed-suggestions → Template (with sample_data)
Template (with sample_data) → seed-suggestions --force → Template (updated sample_data)
```

### Field Question Flow
```
Load template → Check sample_data[field_name] exists?
  → Yes: Show question + example from sample_data
  → No: Show question only (field.label, no example)
```

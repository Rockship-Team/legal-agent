# API Contracts: Contract Suggestion Examples & Type Fix

**Date**: 2026-03-12 | **Feature**: 005-contract-suggestion-data

## Modified Endpoints

### 1. Chat Endpoint (existing, behavior change)

**`POST /api/chat`** — Contract creation flow now includes suggestions in field questions.

**Response change**: When `action_taken` indicates field question, the response text includes example suggestions:

```
Before: "Tên bên A là gì?"
After:  "Tên bên A là gì?\n💡 Ví dụ: Nguyễn Văn A"
```

No schema change — suggestions are embedded in the response text.

---

### 2. Contract Create (existing, response extended)

**`POST /api/contract/create`**

**Response `ContractFieldItem` — add `suggestions` field:**

```json
{
  "name": "ben_a_ten",
  "label": "Tên bên A",
  "field_type": "text",
  "required": true,
  "description": "Họ và tên đầy đủ",
  "default_value": null,
  "suggestions": {
    "examples": ["Nguyễn Văn A", "Công ty TNHH ABC"],
    "format_hint": "Họ và tên đầy đủ hoặc tên doanh nghiệp"
  }
}
```

## New CLI Commands

### 3. Seed Suggestions

```bash
# Seed all templates
python -m legal_chatbot seed-suggestions

# Seed specific template
python -m legal_chatbot seed-suggestions --type cho_thue_xe

# Force regenerate
python -m legal_chatbot seed-suggestions --force

# Check status
python -m legal_chatbot seed-suggestions --status
```

**Output (status):**
```
┌─────────────────────┬──────────────────────────┬────────────┐
│ Contract Type       │ Display Name             │ Has Data   │
├─────────────────────┼──────────────────────────┼────────────┤
│ cho_thue_xe         │ Hợp đồng cho thuê xe     │ ✅ 12 fields│
│ cho_thue_nha        │ Hợp đồng cho thuê nhà    │ ❌ missing  │
│ mua_ban_dat         │ Hợp đồng mua bán đất     │ ✅ 15 fields│
└─────────────────────┴──────────────────────────┴────────────┘
```

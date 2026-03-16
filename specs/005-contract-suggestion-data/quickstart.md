# Quickstart: Contract Suggestion Examples & Type Fix

**Feature**: 005-contract-suggestion-data

## Prerequisites

- Python 3.11+ with venv activated
- Supabase DB with `contract_templates` table populated
- `ANTHROPIC_API_KEY` or `DEEPSEEK_API_KEY` in `.env`

## Setup

### 1. Run migration

Add `sample_data` column to `contract_templates`:

```sql
ALTER TABLE contract_templates
ADD COLUMN IF NOT EXISTS sample_data JSONB DEFAULT NULL;
```

Run this in Supabase SQL Editor.

### 2. Seed suggestion data

```bash
# Seed all templates
python -m legal_chatbot seed-suggestions

# Check status
python -m legal_chatbot seed-suggestions --status

# Seed specific type
python -m legal_chatbot seed-suggestions --type cho_thue_xe

# Force regenerate
python -m legal_chatbot seed-suggestions --force
```

### 3. Test contract creation

```bash
# Via CLI
python -m legal_chatbot chat "tạo hợp đồng cho thuê xe tự lái"

# Verify: should show car rental template (not money lending)
# Verify: field questions include suggestion examples
```

### 4. Test via API

```bash
# Start server
uvicorn legal_chatbot.api.app:create_app --factory --reload

# Chat endpoint
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "tạo hợp đồng cho thuê xe tự lái", "session_id": "test-1"}'
```

## Verification Checklist

- [ ] "cho thuê xe tự lái" → car rental template (not money lending)
- [ ] "thuê nhà" → house rental template
- [ ] "vay tiền" → money lending template
- [ ] Each field question shows suggestion example
- [ ] `seed-suggestions --status` shows all templates have data
- [ ] Templates without sample data still work (no crash)

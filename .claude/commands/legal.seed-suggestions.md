---
description: Generate suggestion examples for contract template fields using LLM
---

## User Input

```text
$ARGUMENTS
```

## Purpose

Dung LLM de generate du lieu mau (ten, dia chi, CCCD, so tien...) cho tung field cua contract template. Data duoc luu vao Supabase de hien thi suggestion khi user tao hop dong.

## Workflow

### Step 1: Xac dinh action

Parse `$ARGUMENTS` de xac dinh:
- `status` — Xem template nao da co suggestion data, template nao chua
- `seed [type]` — Generate suggestions cho 1 template cu the
- `seed --all` — Generate suggestions cho tat ca templates chua co data
- `seed --all --force` — Regenerate suggestions cho tat ca templates (ke ca da co)

Neu `$ARGUMENTS` rong, hoi nguoi dung:
```
Ban muon lam gi?
- Xem trang thai: /legal.seed-suggestions status
- Seed 1 template: /legal.seed-suggestions seed mua_ban_tai_san
- Seed tat ca: /legal.seed-suggestions seed --all
- Force regenerate: /legal.seed-suggestions seed --all --force
```

### Step 2: Kiem tra migration

Truoc khi seed, kiem tra bang cach chay status:
```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot seed-suggestions --status
```

Neu loi `column sample_data does not exist`:
1. Huong dan user chay migration `007_sample_data.sql` trong Supabase SQL Editor
2. Hien thi noi dung file migration:
```bash
cat c:/Users/ADMIN/chatbot/legal_chatbot/db/migrations/007_sample_data.sql
```

### Step 3: Thuc hien

#### Action: status

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot seed-suggestions --status
```

Bao cao dang bang:
```
Template Status:
| Contract Type | Display Name | Has Data | Fields |
|---------------|-------------|----------|--------|
| mua_ban       | Hop dong mua ban | Yes | 8 |
| cho_thue      | Hop dong cho thue | No | 0 |
```

#### Action: seed (1 template)

Parse contract_type tu `$ARGUMENTS`:
- `/legal.seed-suggestions seed mua_ban_tai_san` -> type=mua_ban_tai_san

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot seed-suggestions --type [CONTRACT_TYPE]
```

#### Action: seed --all

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot seed-suggestions
```

#### Action: seed --all --force

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot seed-suggestions --force
```

Bao cao ket qua:
```
Seed hoan thanh!

Templates seeded: N/M
- mua_ban_tai_san: 8 fields seeded
- cho_thue_tai_san: 6 fields seeded
- cho_vay: skipped (da co data)

Ban co the:
- Xem trang thai: /legal.seed-suggestions status
- Test tao hop dong: /legal.create-contract mua ban tai san
- Kiem tra DB: /legal.db status
```

### Step 4: Xu ly loi

Neu seed that bai:
1. Kiem tra Supabase connection: `/legal.db status`
2. Kiem tra templates da co trong DB: `/legal.seed-suggestions status`
3. Kiem tra migration: cot `sample_data` da ton tai chua
4. Neu chua co templates: chay `python -m legal_chatbot seed-templates` truoc
5. Kiem tra LLM API key (ANTHROPIC_API_KEY hoac OPENAI_API_KEY)

## Notes

- Suggestion data duoc LLM generate tu field definitions cua template
- Moi field se co 2-3 vi du thuc te bang tieng Viet (ten nguoi, dia chi, CCCD...)
- Data duoc cache trong Supabase `contract_templates.sample_data` (JSONB)
- Chi can seed 1 lan, sau do data duoc dung lai cho moi lan tao hop dong
- Dung `--force` de regenerate neu muon cap nhat vi du moi

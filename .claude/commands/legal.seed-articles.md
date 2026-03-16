---
description: Generate default article templates (DIEU 1-9) with placeholders for contract templates
---

## User Input

```text
$ARGUMENTS
```

## Purpose

Dung LLM de generate MAU DIEU KHOAN (DIEU 1-9) voi placeholders ({ben_a_ten}, {gia_tri}...) cho tung contract template. Data duoc luu vao Supabase `contract_templates.default_articles` de khi tao hop dong chi can substitute field values, KHONG can goi LLM nua.

## Workflow

### Step 1: Xac dinh action

Parse `$ARGUMENTS` de xac dinh:
- `status` — Xem template nao da co article templates, template nao chua
- `seed [type]` — Generate articles cho 1 template cu the
- `seed --all` — Generate articles cho tat ca templates chua co data
- `seed --all --force` — Regenerate articles cho tat ca templates (ke ca da co)

Neu `$ARGUMENTS` rong, hoi nguoi dung:
```
Ban muon lam gi?
- Xem trang thai: /legal.seed-articles status
- Seed 1 template: /legal.seed-articles seed mua_ban_tai_san
- Seed tat ca: /legal.seed-articles seed --all
- Force regenerate: /legal.seed-articles seed --all --force
```

### Step 2: Kiem tra migration

Truoc khi seed, kiem tra bang cach chay status:
```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot seed-articles --status
```

Neu loi `column default_articles does not exist`:
1. Huong dan user chay migration `008_default_articles.sql` trong Supabase SQL Editor
2. Hien thi noi dung file migration:
```bash
cat c:/Users/ADMIN/chatbot/legal_chatbot/db/migrations/008_default_articles.sql
```

### Step 3: Thuc hien

#### Action: status

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot seed-articles --status
```

Bao cao dang bang:
```
Template Article Templates Status:
| Contract Type | Display Name | Has Articles | Count |
|---------------|-------------|-------------|-------|
| mua_ban       | Hop dong mua ban | Yes (9 dieu) | 9 |
| cho_thue      | Hop dong cho thue | No | 0 |
```

#### Action: seed (1 template)

Parse contract_type tu `$ARGUMENTS`:
- `/legal.seed-articles seed mua_ban_tai_san` -> type=mua_ban_tai_san

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot seed-articles --type [CONTRACT_TYPE]
```

#### Action: seed --all

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot seed-articles
```

#### Action: seed --all --force

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot seed-articles --force
```

Bao cao ket qua:
```
Seed hoan thanh!

Templates seeded: N/M
- mua_ban_tai_san: 9 articles seeded
- cho_thue_tai_san: 9 articles seeded
- cho_vay: skipped (da co data)

Ban co the:
- Xem trang thai: /legal.seed-articles status
- Test tao hop dong: /legal.create-contract mua ban tai san
- Kiem tra DB: /legal.db status
```

### Step 4: Xu ly loi

Neu seed that bai:
1. Kiem tra Supabase connection: `/legal.db status`
2. Kiem tra templates da co trong DB: `/legal.seed-articles status`
3. Kiem tra migration: cot `default_articles` da ton tai chua
4. Neu chua co templates: chay `python -m legal_chatbot seed-templates` truoc
5. Kiem tra LLM API key (ANTHROPIC_API_KEY hoac OPENAI_API_KEY)

## Notes

- Article templates duoc LLM generate 1 LAN voi placeholders ({field_name})
- Khi tao hop dong, chi can substitute placeholders bang field values (instant, 0 token)
- Neu template chua co default_articles, he thong fallback goi LLM (30-60s)
- Data duoc cache trong Supabase `contract_templates.default_articles` (JSONB)
- Dung `--force` de regenerate neu muon cap nhat dieu khoan moi
- Nen chay `/legal.seed-suggestions seed --all` truoc de co du lieu mau cho fields

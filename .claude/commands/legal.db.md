---
description: Manage database connection, migration, and status check
---

## User Input

```text
$ARGUMENTS
```

## Purpose

Quan ly ket noi database (Supabase hoac SQLite). Ho tro:
- Kiem tra trang thai ket noi va thong ke du lieu
- Huong dan migrate schema len Supabase
- Hien thi thong tin cau hinh database

## Workflow

### Step 1: Xac dinh action

Neu `$ARGUMENTS` rong hoac la "status", chay kiem tra trang thai.

Cac action hop le:
- `status` (mac dinh) — Kiem tra ket noi va thong ke
- `migrate` — Huong dan migrate schema

### Step 2: Thuc hien

#### Action: status

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot db status
```

Hien thi ket qua:
```
Database Status:
- Mode: supabase | sqlite
- URL/Path: ...
- Documents: N
- Articles: N
- Status: connected | error
```

#### Action: migrate

Neu `DB_MODE=supabase`:

```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot db migrate
```

Se hien thi duong dan file SQL migration. Huong dan user:
1. Mo Supabase SQL Editor
2. Copy noi dung file `legal_chatbot/db/migrations/002_supabase.sql`
3. Chay SQL
4. Verify bang `/legal.db status`

Neu `DB_MODE=sqlite`:
```bash
cd c:/Users/ADMIN/chatbot
python -m legal_chatbot db migrate
```

Se tu dong tao tables trong SQLite.

### Step 3: Bao cao ket qua

Sau khi chay, tom tat:
```
Database [mode] da duoc kiem tra/migrate thanh cong.

Documents: N | Articles: N

Ban co the:
- Chay /legal.pipeline crawl de crawl du lieu moi
- Chay /legal.db status de kiem tra lai
```

## Error Handling

- Neu ket noi that bai, kiem tra SUPABASE_URL va SUPABASE_KEY trong `.env`
- Neu DB_MODE chua duoc set, mac dinh la `sqlite`
- Neu Supabase chua co schema, huong dan chay migrate truoc

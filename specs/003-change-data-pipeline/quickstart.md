# Quickstart: 003 - DB-First Pipeline + Background Worker

## Prerequisites

- Python 3.11+
- Supabase project with pgvector enabled (from 002)
- `.env` configured with `DB_MODE=supabase` (from 002)
- All 002 tables deployed (`legal_documents`, `articles`, `legal_categories`, etc.)

## Step 1: Run Migration

Run `003_worker.sql` in Supabase SQL Editor:

```bash
# View migration file
/legal.db migrate
# → Copy SQL from legal_chatbot/db/migrations/003_worker.sql
# → Paste in Supabase SQL Editor → Run
```

This creates:
- `document_registry` table
- `contract_templates` table
- New columns on `legal_categories` (worker_schedule, worker_time, etc.)
- New columns on `pipeline_runs` (trigger_type, documents_skipped, duration_seconds)
- `update_category_counts()` RPC function

## Step 2: Seed Data

```bash
# Seed contract templates
python -m legal_chatbot seed-templates

# Seed document registry (initial URLs for đất đai, dân sự, lao động)
python -m legal_chatbot seed-registry
```

## Step 3: Initial Pipeline Run

```bash
# Crawl luật đất đai (first time — full crawl)
/legal.pipeline crawl dat_dai

# Verify data
/legal.db status
# Expected: dat_dai has X documents, Y articles
```

## Step 4: Test DB-Only Chat

```bash
# Test with data (should use DB only, no web search)
# Chat: "Điều kiện chuyển nhượng quyền sử dụng đất?"
# → Expected: Response citing Luật Đất đai 2024 from DB

# Test without data (should return no-data message)
# Chat: "Quy định về bảo hiểm xã hội?"
# → Expected: "Chưa đủ dữ liệu" + list available categories
```

## Step 5: Test DB-Only Contract Creation

```bash
# Test with data
/legal.create-contract mua bán đất
# → Expected: Search DB → find 10+ articles → ask user info → generate

# Test without data
/legal.create-contract hợp đồng bảo hiểm
# → Expected: "Chưa đủ dữ liệu" + list available contract types
```

## Step 6: Start Background Worker

```bash
# Start worker (runs in foreground, Ctrl+C to stop)
/legal.pipeline worker start

# Check status
/legal.pipeline worker status

# View schedule
/legal.pipeline worker schedule
```

## Environment Variables (new)

```bash
# Add to .env
WORKER_ENABLED=true
WORKER_DEFAULT_SCHEDULE=weekly
WORKER_DEFAULT_TIME=02:00
WORKER_RETRY_COUNT=3
WORKER_RETRY_BACKOFF=30
CHAT_MODE=db_only
```

## Verify Everything Works

```bash
# 1. DB-only chat
python -m legal_chatbot chat "Điều kiện chuyển nhượng đất"
# → Should cite DB articles, NO web search

# 2. Contract creation
/legal.create-contract cho thuê nhà
# → Should use DB articles only

# 3. Incremental crawl
/legal.pipeline crawl dat_dai
# → Should skip unchanged docs (documents_skipped > 0)

# 4. Force re-crawl
/legal.pipeline crawl dat_dai --force
# → Should re-crawl all docs regardless of hash

# 5. Worker status
/legal.pipeline worker status
# → Shows scheduled jobs, next run times
```

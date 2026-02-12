# Quickstart: Kết nối Database & Data Pipeline

**Date**: 2026-02-10 | **Spec**: [spec.md](./spec.md)

## Prerequisites

- Python 3.11+
- Existing legal_chatbot setup (from 001-planning)
- Supabase account (free tier: https://supabase.com)
- ~2 GB free disk space (for embedding model cache)

## 1. Setup Supabase

### 1.1 Create Project

1. Go to https://supabase.com → New Project
2. Name: `legal-chatbot`
3. Region: Southeast Asia (Singapore)
4. Save your credentials:
   - Project URL: `https://xxxxx.supabase.co`
   - Anon Key: `eyJ...`
   - Service Role Key: `eyJ...` (Settings → API → Service Role)

### 1.2 Enable pgvector

In Supabase SQL Editor, run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 1.3 Run Schema Migration

```
/legal.db migrate
```

This creates all tables, indexes, RPC functions, and RLS policies.

## 2. Configure Environment

Update `.env` file:

```bash
# Existing
GROQ_API_KEY=gsk_...
DATABASE_PATH=./data/legal.db
CHROMA_PATH=./data/chroma
LOG_LEVEL=INFO

# New - Supabase
DB_MODE=supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJ...your-anon-key...
SUPABASE_SERVICE_KEY=eyJ...your-service-role-key...

# New - Pipeline
PIPELINE_CRAWL_INTERVAL=168
PIPELINE_RATE_LIMIT=4
PIPELINE_MAX_PAGES=20
EMBEDDING_MODEL=bkai-foundation-models/vietnamese-bi-encoder
EMBEDDING_DIMENSION=768
```

## 3. Install New Dependencies

```bash
pip install supabase>=2.0.0 sentence-transformers>=2.2.0 playwright-stealth>=1.0.0 apscheduler>=3.10.0

# Install Playwright browsers (if not done)
playwright install firefox
```

## 4. Verify Connection

```
/legal.db status
```

Expected output:
```
Mode: supabase
URL: https://xxxxx.supabase.co
Tables: 9 | RPC Functions: 2
Documents: 0 | Articles: 0
```

## 5. Run Data Pipeline

### 5.1 Crawl Land Law Documents

```
# Crawl Luật Đất đai 2024 and related regulations
/legal.pipeline crawl dat_dai --limit 3
```

Expected output:
```
Pipeline: Đất đai
Phase 1: Discovery... found 6 documents
Phase 2: Crawling... 3 new, 0 updated (3-5s between requests)
Phase 3: Indexing... 450 articles, 450 embeddings (768d)
Phase 4: Validation... ✓ passed
✓ Pipeline completed in ~4 minutes
```

### 5.2 Verify Data

```
/legal.db status
```

Expected:
```
Documents: 3 | Articles: 450+ | Embeddings: 450+
Storage: 3 raw HTML files
```

## 6. Test Semantic Search

```
/legal.research Điều kiện chuyển nhượng quyền sử dụng đất?
```

Expected: Response citing Luật Đất đai 2024, with specific article numbers.

```
# Check audit trail
/legal.audit list --limit 1
```

Expected: Audit entry showing query, sources, and law versions used.

## 7. Offline Mode (SQLite Fallback)

To work offline, change `DB_MODE`:

```bash
DB_MODE=sqlite
```

All existing slash commands work as before with local SQLite database.

## Usage Reference

### Pipeline Commands

```
# Crawl by category
/legal.pipeline crawl dat_dai
/legal.pipeline crawl dat_dai --limit 20
/legal.pipeline crawl nha_o --limit 10

# Check pipeline history
/legal.pipeline status

# List available categories
/legal.pipeline categories
```

### Database Commands

```
# Migrate schema
/legal.db migrate

# Connection status
/legal.db status
```

### Audit Commands

```
# List recent audits
/legal.audit list
/legal.audit list --limit 20

# Verify specific audit (check if laws are still current)
/legal.audit verify <audit-id>

# Show full audit details
/legal.audit show <audit-id>
```

### Existing Commands (unchanged)

```
/legal.research [topic]
/legal.create-contract [type]
/legal.preview
/legal.export-pdf
/legal.help
```

## Troubleshooting

### Supabase Connection Error

```
Error: Could not connect to Supabase
```

Solution: Verify `SUPABASE_URL` and `SUPABASE_KEY` in `.env`. Check Supabase dashboard is accessible.

### Cloudflare Block During Crawl

```
Error: Cloudflare challenge failed after 3 retries
```

Solution: Wait 5 minutes and retry. Ensure `playwright-stealth` is installed. Try: `playwright install firefox`.

### Embedding Model Download

First run downloads ~1.1 GB model to `~/.cache/huggingface/`. Requires internet connection.

```
Error: Connection error downloading model
```

Solution: Ensure internet access. Model is cached after first download.

### Wrong Vector Dimension

```
Error: expected 768 dimensions, got 384
```

Solution: Check `EMBEDDING_MODEL` in `.env` is set to `bkai-foundation-models/vietnamese-bi-encoder` (768d), not `paraphrase-multilingual-MiniLM-L12-v2` (384d).

### Out of Memory

```
Error: Cannot allocate memory for embedding model
```

Solution: Need ~1.6 GB free RAM. Close other applications. Or reduce batch size: set `EMBEDDING_BATCH_SIZE=32` in `.env`.

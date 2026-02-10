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

```bash
python -m legal_chatbot db migrate
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

```bash
python -m legal_chatbot db status
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

```bash
# Crawl Luật Đất đai 2024 and related regulations
python -m legal_chatbot pipeline crawl --category dat-dai --limit 3
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

```bash
python -m legal_chatbot db status
```

Expected:
```
Documents: 3 | Articles: 450+ | Embeddings: 450+
Storage: 3 raw HTML files
```

## 6. Test Semantic Search

```bash
python -m legal_chatbot chat "Điều kiện chuyển nhượng quyền sử dụng đất?"
```

Expected: Response citing Luật Đất đai 2024, with specific article numbers.

```bash
# Check audit trail
python -m legal_chatbot audit list --limit 1
```

Expected: Audit entry showing query, sources, and law versions used.

## 7. Offline Mode (SQLite Fallback)

To work offline, change `DB_MODE`:

```bash
DB_MODE=sqlite
```

All existing CLI commands work as before with local SQLite database.

## Usage Reference

### Pipeline Commands

```bash
# Crawl by category
python -m legal_chatbot pipeline crawl --category dat-dai --limit 20
python -m legal_chatbot pipeline crawl --category nha-o --limit 10

# Check pipeline history
python -m legal_chatbot pipeline status

# List available categories
python -m legal_chatbot pipeline categories
```

### Database Commands

```bash
# Migrate schema
python -m legal_chatbot db migrate

# Connection status
python -m legal_chatbot db status

# Sync local ↔ cloud
python -m legal_chatbot db sync
```

### Audit Commands

```bash
# List recent audits
python -m legal_chatbot audit list --limit 20

# Verify specific audit (check if laws are still current)
python -m legal_chatbot audit verify <audit-id>

# Show full audit details
python -m legal_chatbot audit show <audit-id>
```

### Existing Commands (unchanged)

```bash
python -m legal_chatbot chat "question"
python -m legal_chatbot interactive
python -m legal_chatbot research "topic"
python -m legal_chatbot generate --template rental --interactive
python -m legal_chatbot templates
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

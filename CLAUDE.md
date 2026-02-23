# Legal Chatbot Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-02-23

## Active Technologies
- Python 3.11+ (All modules)
- Supabase PostgreSQL + pgvector (production DB + vector search)
- SQLite (local fallback, no worker/template support)
- Groq API with LLaMA 3.3 70B (LLM)
- Typer + Rich (CLI framework)
- ReportLab (PDF generation)
- Playwright + BeautifulSoup + stealth (Web crawling)
- sentence-transformers / vietnamese-bi-encoder (Embeddings, 768d)
- APScheduler 3.10+ (Background worker)
- supabase-py (DB client)
- pytest (Testing)

## Project Structure

```text
legal_chatbot/
  __init__.py
  __main__.py           # CLI entry point
  cli/                  # Typer CLI commands
    main.py             # All commands: chat, pipeline, worker, db, audit, seed-*
    init_cmd.py
    chat_cmd.py
  services/             # Business logic
    chat.py             # DB-only RAG (no web search)
    research.py         # DB-only deep search (no web crawling)
    contract.py         # Contract creation (DB-only, template-based)
    pipeline.py         # Incremental crawl + document registry
    worker.py           # Background worker (APScheduler)
    crawler.py          # Playwright stealth crawl
    indexer.py          # HTML parsing
    embedding.py        # Embedding generation
    audit.py            # Audit trail
  models/               # Pydantic models
    document.py
    chat.py             # ChatResponse with has_data, category
    pipeline.py         # PipelineRun, DocumentRegistryEntry, WorkerStatus
    contract.py         # ContractTemplate, DataAvailability, CategoryInfo
    template.py
    audit.py
  db/                   # Database operations
    supabase.py         # Full CRUD + registry + templates + stats
    sqlite.py
    base.py
    migrations/
      002_supabase.sql  # Base schema
      003_worker.sql    # Worker + registry + templates
  utils/                # Shared utilities
    config.py           # Settings with worker/chat config

data/
  raw/                  # Crawled documents
  contracts/            # Generated contracts (JSON)
  legal.db             # SQLite database

specs/
  003-change-data-pipeline/  # Current feature spec
```

## Commands

```bash
# Setup
python -m venv venv
.\venv\Scripts\activate  # Windows
pip install -r requirements.txt

# DB setup (Supabase)
python -m legal_chatbot db migrate     # Shows migration SQL files
python -m legal_chatbot db status      # Check connection

# Seed data (run once after migration)
python -m legal_chatbot seed-templates   # Contract templates
python -m legal_chatbot seed-registry    # Document registry URLs

# Pipeline (incremental crawl)
python -m legal_chatbot pipeline crawl --category dat_dai
python -m legal_chatbot pipeline crawl --category dat_dai --force   # Re-crawl all
python -m legal_chatbot pipeline status        # Category stats + worker info
python -m legal_chatbot pipeline categories    # List categories
python -m legal_chatbot pipeline browse        # Browse data hierarchy

# Worker (background scheduled crawl)
python -m legal_chatbot pipeline worker --category start
python -m legal_chatbot pipeline worker --category stop
python -m legal_chatbot pipeline worker --category status
python -m legal_chatbot pipeline worker --category schedule

# Chat (DB-only RAG)
python -m legal_chatbot chat "Điều kiện cho thuê nhà là gì?"

# Search (vector search without LLM)
python -m legal_chatbot search "hợp đồng mua bán đất" --top-k 10

# Contract
python -m legal_chatbot save-contract "data/contracts/file.json"

# Audit
python -m legal_chatbot audit list --type contract
python -m legal_chatbot audit show <audit_id>

# Testing
pytest
pytest --cov=legal_chatbot
```

## Code Style

- Python: Black + isort, type hints with mypy
- Follow domain-driven design patterns
- Vietnamese text handling: Always use UTF-8, NFD normalization

## Environment Variables

```bash
# Required
GROQ_API_KEY=gsk_...
DB_MODE=supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...                    # anon key (reads)
SUPABASE_SERVICE_KEY=eyJ...            # service role key (writes)
LLM_MODEL=llama-3.3-70b-versatile

# Worker (optional)
WORKER_ENABLED=true
WORKER_DEFAULT_SCHEDULE=weekly
WORKER_DEFAULT_TIME=02:00
WORKER_RETRY_COUNT=3
WORKER_RETRY_BACKOFF=30

# Chat
CHAT_MODE=db_only
```

## Architecture (003)

- **DB-First**: All chat, research, contract creation use ONLY Supabase pgvector. No web search fallback.
- **No-Data Response**: Friendly Vietnamese message when category has no data. Never hallucinate.
- **Contract Templates**: Pre-configured in `contract_templates` DB table with search_queries per type.
- **Document Registry**: `document_registry` table tracks specific URLs to crawl per category.
- **Incremental Crawl**: Content hash (SHA-256) comparison. Skip unchanged documents.
- **Background Worker**: APScheduler cron jobs per category. Weekly by default. Not auto-started.

## Recent Changes
- 003-change-data-pipeline: DB-First architecture, background worker, contract templates, incremental crawl (2026-02-23)
- 002-connect-db-and-design-data-pipeline: Supabase + pgvector integration (2026-02-05)
- 001-planning: Simplified to Python-only CLI with Groq API (2026-02-05)

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->

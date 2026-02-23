# Research: 003 - Thiết kế lại Data Pipeline

**Date**: 2026-02-23 | **Branch**: `003-change-data-pipeline`

## Prior Work

### 001-planning (Foundation)
- Core CLI architecture: Typer + Rich, Groq API, Playwright crawler
- Basic data model: `legal_documents`, `articles` tables
- Contract templates: JSON-based, 4 types (rental, sale, service, employment)

### 002-connect-db-and-design-data-pipeline (Current)
- Supabase integration: PostgreSQL + pgvector + Storage
- Data pipeline: 4-phase (Discovery → Crawl → Index → Validate)
- Embedding service: `bkai-foundation-models/vietnamese-bi-encoder` (768d)
- Category system: 6 categories + LLM-validated auto-creation
- Audit trail: `research_audits`, `contract_audits` tables
- **Status**: Merged to main, fully implemented

### What 003 builds on
- All Supabase infrastructure from 002 (tables, RPC, RLS)
- Pipeline orchestrator (`pipeline.py`, `crawler.py`, `indexer.py`)
- Embedding service (`embedding.py`)
- Existing CLI commands (`pipeline crawl`, `search`, `sync-articles`)

---

## Decision 1: Scheduler Library

### Decision: APScheduler 3.11.x with AsyncIOScheduler

### Rationale
- Pipeline code uses async/await extensively (`pipeline.run()`, `crawler.crawl_with_stealth()`)
- `AsyncIOScheduler` runs jobs natively in the asyncio event loop
- APScheduler 3.x is battle-tested and stable; 4.x is not production-ready yet
- Already in `requirements.txt` (`apscheduler>=3.10.0`)

### Alternatives Considered
- **APScheduler 4.x**: Better async support but not stable yet (2026)
- **Celery + Redis**: Overkill for this use case, adds infrastructure complexity
- **schedule library**: No async support, no job persistence
- **cron (OS-level)**: Not portable (Windows), no job management

### Key Implementation Notes
- Use `AsyncIOScheduler` (not `BackgroundScheduler`) because pipeline is async
- Job persistence via `SQLAlchemyJobStore` (reuse SQLite for job metadata)
- `coalesce=True` to merge missed runs into one execution
- `max_instances=1` per category to prevent parallel crawls
- `misfire_grace_time=3600` (1 hour grace for missed jobs)

### Windows Graceful Shutdown
- Windows only supports `SIGINT` (Ctrl+C) and `SIGBREAK` (Ctrl+Break)
- Use `signal.signal()` + `scheduler.shutdown(wait=True)`
- Windows gives ~5 seconds for shutdown routines after Ctrl+C
- Recommend saving state on each job completion (not just at shutdown)

---

## Decision 2: Change Detection Strategy

### Decision: Content-based hash comparison (skip HTTP headers)

### Rationale
- **thuvienphapluat.vn does NOT return ETag or Last-Modified headers**
- Site returns `Cache-Control: private, max-age=0, no-store, no-cache`
- Cloudflare protection requires full browser rendering (Playwright) anyway
- HEAD requests would trigger same Cloudflare challenge as GET — no performance benefit

### Implementation
1. **Always do full crawl** (Playwright + stealth) — no HEAD request optimization
2. **Normalize HTML before hashing**: Strip scripts, ads, dynamic elements → extract `div.content1` → get text → SHA-256
3. **Compare hash with stored `content_hash`** in `legal_documents` table
4. **Only re-parse/re-embed if hash differs**
5. **Time-based scheduling**: Crawl active laws daily, expired laws monthly

### Normalization Steps
```
Raw HTML → BeautifulSoup
  → Remove: script, style, noscript, iframe
  → Remove: ad/tracking class elements
  → Extract: div.content1 or div.toanvancontent
  → Get text (separator=' ', strip=True)
  → Collapse whitespace → SHA-256
```

### Alternatives Considered
- **HTTP ETag/Last-Modified**: Not supported by target site
- **HEAD request pre-check**: Cloudflare blocks, no benefit
- **Diff-based detection**: More complex, hash comparison sufficient for legal docs

---

## Decision 3: Incremental Crawl Strategy

### Decision: Time-based scheduling + content hash + adaptive rate limiting

### Schedule by Document Status
| Status | Recrawl Interval | Rationale |
|--------|-----------------|-----------|
| active | 7 days | Laws change infrequently |
| draft/pending | 1 day | May be amended before effective |
| expired | 30 days | Unlikely to change |
| new (never crawled) | Immediate | First-time indexing |

### Rate Limiting
- **Base delay**: 4 seconds + random 0-2s jitter (unchanged from 002)
- **Adaptive backoff**: On 429/403/503 errors, increase delay exponentially
- **Max delay cap**: 60 seconds
- **Recovery**: Reduce delay by 10% on each success
- **Time window**: Crawl only 2:00-6:00 AM (Vietnam time) to minimize load

### Retry Logic
- 3 retries per document with exponential backoff (30s, 60s, 120s)
- If all retries fail → log error, skip document, continue next
- If entire category fails → log, continue to next category

---

## Decision 4: Contract Templates Storage

### Decision: Database table `contract_templates` with JSONB fields

### Rationale
- Templates need to be queryable (find by category + contract_type)
- JSONB allows flexible schema for `search_queries`, `required_fields`, `article_outline`
- Easier to seed/update than JSON files
- Supports future admin UI for template management

### Alternatives Considered
- **JSON files in `templates/`**: Current approach, but not queryable, no versioning
- **YAML config files**: More readable but still file-based, same limitations
- **Hardcoded in Python**: Not maintainable, requires code deploy for changes

### Key Fields
- `search_queries`: Pre-mapped vector search terms per contract type
- `required_laws`: Expected law documents (for validation)
- `min_articles`: Minimum articles needed for reliable contract generation
- `required_fields`: Template for user data collection (bên A, bên B, etc.)
- `article_outline`: Skeleton for ĐIỀU 1-9 structure

---

## Decision 5: DB-Only Chat Architecture

### Decision: Remove all web search, add category detection + data availability check

### Flow Change
```
BEFORE: query → vector search → (fallback) web search → LLM → response
AFTER:  query → detect category → check data → vector search → LLM → response
                                       ↓ (no data)
                                  "Chưa đủ dữ liệu" + list available categories
```

### Category Detection
1. **Keyword matching**: Extract legal domain keywords from query
2. **LLM classification** (fallback): Use Groq to classify if keyword matching fails
3. **Cache**: Keep category list in memory (6 categories, rarely changes)

### Data Availability Check
- Query `legal_categories` table for `article_count > 0`
- Cache counts (refresh every 5 minutes)
- If `article_count = 0` → return no-data message immediately

### Alternatives Considered
- **Hybrid mode** (DB + web search fallback): Defeats the purpose of reliable data
- **Always answer** (with disclaimer): Risk of hallucination, user confusion
- **Auto-crawl on demand**: Too slow (Playwright crawl takes 30-60s), blocks user

---

## Decision 6: Worker Process Architecture

### Decision: In-process AsyncIOScheduler (not separate daemon)

### Rationale
- CLI app context: Users start worker via `python -m legal_chatbot scheduler start`
- Worker runs in same process as scheduler — simple, no IPC needed
- APScheduler's `AsyncIOScheduler` manages its own event loop
- Job persistence via SQLAlchemy means jobs survive restarts

### How It Works
1. User runs `scheduler start` CLI command
2. AsyncIOScheduler starts with configured cron jobs
3. Process blocks on `loop.run_forever()`
4. Ctrl+C triggers graceful shutdown
5. On next start, SQLAlchemy job store resumes where it left off

### Alternatives Considered
- **Separate daemon process**: More complex, needs PID management, Windows service registration
- **systemd/NSSM service**: Platform-specific, harder to develop/debug
- **Docker container**: Adds container infrastructure dependency

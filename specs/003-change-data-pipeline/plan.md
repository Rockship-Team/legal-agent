# Implementation Plan: 003 - DB-First Pipeline + Background Worker

**Branch**: `003-change-data-pipeline` | **Date**: 2026-02-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-change-data-pipeline/spec.md`

## Summary

Redesign the data pipeline to be **DB-first**: all chat, research, and contract creation operations use only Supabase-indexed data (no web search). Add a **background worker** (APScheduler) that automatically crawls and updates legal documents on a daily schedule. Implement **contract templates** pre-mapped to specific law categories so contracts can be generated without real-time web crawling. Add **document registry** for targeted, incremental crawling of specific law documents.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: APScheduler 3.11.x (AsyncIOScheduler), supabase-py, sentence-transformers, Playwright + stealth, Typer + Rich
**Storage**: Supabase PostgreSQL + pgvector (production), SQLite (local dev — worker not supported)
**Testing**: pytest + pytest-asyncio
**Target Platform**: Windows 11 (development), any OS with Python 3.11+ (runtime)
**Project Type**: Single project (CLI application)
**Performance Goals**: Pipeline crawl completes within 30 min per category; chat response < 5s (DB-only, no web latency)
**Constraints**: Rate limit 4-6s between crawl requests; worker runs 2-6 AM (Vietnam time); max 50 docs per pipeline run
**Scale/Scope**: 6 law categories, ~500-3000 articles per category, 15+ contract templates

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Note: Project constitution is not yet configured (template placeholder). Checks evaluated against project conventions from CLAUDE.md and existing specs.

- [x] **Specification-First**: spec.md complete with 5 use case scenarios, 14 sections, DB schema, flow diagrams
- [x] **Test-First**: Test strategy defined in spec.md Section 12 (unit + integration + acceptance tests)
- [x] **Code Quality**: Black + isort + mypy type hints (from CLAUDE.md)
- [x] **UX Consistency**: User flows documented in spec.md Section 1.3 (5 scenarios) and Section 7 (response templates)
- [x] **Performance**: Rate limits, crawl intervals, and chat response constraints defined
- [x] **Observability**: Pipeline logging via `pipeline_runs` table, audit trail for research/contracts
- [ ] **Issue Tracking**: No Beads epic (project does not use Beads)

**Complexity Violations**: None identified

## Previous Work

| Feature | Status | Relevance |
|---------|--------|-----------|
| 001-planning | Complete | Foundation: CLI, crawler, indexer, chat, PDF gen |
| 002-connect-db-and-design-data-pipeline | Merged to main | All Supabase infrastructure, pipeline, embeddings, audit trail |

All 002 infrastructure is reused. 003 modifies behavior (DB-only) and adds new modules (worker, contract service).

## Project Structure

### Documentation (this feature)

```text
specs/003-change-data-pipeline/
├── spec.md              # Feature specification (complete)
├── plan.md              # This file
├── research.md          # Phase 0: Research findings
├── data-model.md        # Phase 1: Entity schemas + Pydantic models
├── quickstart.md        # Phase 1: Setup guide
├── contracts/           # Phase 1: Module interface contracts
│   ├── worker.md
│   ├── contract-service.md
│   ├── chat-db-only.md
│   └── pipeline-incremental.md
└── tasks.md             # Phase 2: Task breakdown (via /specledger.tasks)
```

### Source Code (repository root)

```text
legal_chatbot/
├── services/
│   ├── chat.py              # MODIFY: DB-only, no web search, + no-data handling
│   ├── research.py          # MODIFY: DB-only deep search, no crawl
│   ├── contract.py          # NEW: Contract creation service (DB-only, template-based)
│   ├── worker.py            # NEW: Background worker (APScheduler AsyncIOScheduler)
│   ├── pipeline.py          # MODIFY: incremental update, document registry
│   ├── crawler.py           # UNCHANGED (used by worker/pipeline)
│   ├── indexer.py           # UNCHANGED
│   ├── embedding.py         # UNCHANGED
│   └── audit.py             # UNCHANGED
├── db/
│   ├── supabase.py          # MODIFY: + document_registry CRUD, contract_templates CRUD, category stats
│   └── migrations/
│       └── 003_worker.sql   # NEW: Schema changes + new tables
├── models/
│   ├── pipeline.py          # MODIFY: + WorkerStatus, DocumentRegistryEntry
│   ├── contract.py          # NEW: ContractTemplate, DataAvailability, CategoryInfo
│   └── chat.py              # MODIFY: + has_data field
├── cli/
│   └── main.py              # MODIFY: + worker commands, + seed commands
└── utils/
    └── config.py            # MODIFY: + worker settings, CHAT_MODE

.claude/commands/
└── legal.create-contract.md # MODIFY: Remove WebSearch steps

tests/
├── unit/
│   ├── test_worker.py                  # NEW
│   ├── test_chat_db_only.py            # NEW
│   ├── test_contract_db_only.py        # NEW
│   └── test_pipeline_incremental.py    # NEW
└── integration/
    ├── test_worker_e2e.py              # NEW
    ├── test_no_data_response.py        # NEW
    └── test_contract_db_only_e2e.py    # NEW
```

**Structure Decision**: Single project, extending existing `legal_chatbot/` package. No new top-level directories needed. All changes fit within existing service/model/CLI/DB layer separation.

## Phase Breakdown

### Phase 1: DB-Only Chat + Create-Contract (Priority: Highest)

**Goal**: Remove all web search from chat and contract creation flows.

| Task | Files | Type |
|------|-------|------|
| Modify `chat.py` — remove web search, add `_detect_category()` | `services/chat.py` | Modify |
| Add `_check_data_availability()` with category stats caching | `services/chat.py` | Modify |
| Implement no-data response templates | `services/chat.py` | Modify |
| Modify `research.py` — DB-only deep search | `services/research.py` | Modify |
| Create `services/contract.py` — DB-only contract creation | `services/contract.py` | New |
| Add `ContractTemplate`, `DataAvailability` models | `models/contract.py` | New |
| Extend `ChatResponse` with `has_data` field | `models/chat.py` | Modify |
| Update `legal.create-contract.md` — remove WebSearch steps | `.claude/commands/` | Modify |

### Phase 2: Contract Templates + Document Registry

**Goal**: Create database infrastructure for templates and targeted crawling.

| Task | Files | Type |
|------|-------|------|
| Write `003_worker.sql` migration | `db/migrations/003_worker.sql` | New |
| Add `contract_templates` CRUD to `supabase.py` | `db/supabase.py` | Modify |
| Add `document_registry` CRUD to `supabase.py` | `db/supabase.py` | Modify |
| Implement `update_category_counts()` RPC call | `db/supabase.py` | Modify |
| Seed contract templates (4 categories, 15+ types) | `cli/main.py` | Modify |
| Seed document registry (đất đai, dân sự, lao động URLs) | `cli/main.py` | Modify |
| Implement multi-query search in `contract.py` | `services/contract.py` | Modify |
| Modify `pipeline.py` — read URLs from registry | `services/pipeline.py` | Modify |
| Implement content hash normalization | `services/pipeline.py` | Modify |

### Phase 3: Background Worker

**Goal**: Automated daily pipeline runs per category.

| Task | Files | Type |
|------|-------|------|
| Create `services/worker.py` with AsyncIOScheduler | `services/worker.py` | New |
| Load schedule from `legal_categories` table | `services/worker.py` | New |
| Implement retry logic (3x, exponential backoff) | `services/worker.py` | New |
| Graceful shutdown (SIGINT/SIGBREAK on Windows) | `services/worker.py` | New |
| Add `WorkerStatus`, `WorkerJob` models | `models/pipeline.py` | Modify |
| Add CLI commands: worker start/stop/status/schedule | `cli/main.py` | Modify |
| Add worker settings to config | `utils/config.py` | Modify |

### Phase 4: Listing Page Discovery

**Goal**: Auto-detect new law documents from category listing pages.

| Task | Files | Type |
|------|-------|------|
| Worker crawl listing pages for new URLs | `services/worker.py` | Modify |
| Auto-add new URLs to document_registry | `services/pipeline.py` | Modify |
| Auto-crawl + index new documents | `services/pipeline.py` | Modify |
| Update status of replaced/amended documents | `services/pipeline.py` | Modify |

### Phase 5: Polish & Monitoring

**Goal**: Production readiness.

| Task | Files | Type |
|------|-------|------|
| Category stats dashboard in CLI | `cli/main.py` | Modify |
| Contract templates management CLI | `cli/main.py` | Modify |
| Worker health check endpoint | `services/worker.py` | Modify |
| End-to-end testing | `tests/` | New |
| Update CLAUDE.md with new architecture | `CLAUDE.md` | Modify |

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scheduler | APScheduler 3.11.x AsyncIOScheduler | Pipeline is async; stable; already in deps |
| Change detection | Content hash (SHA-256), no HTTP headers | thuvienphapluat.vn doesn't support ETag |
| HEAD request | Skip (always full crawl) | Cloudflare requires full browser rendering |
| Contract templates | DB table with JSONB | Queryable, updatable without code deploy |
| Worker architecture | In-process scheduler | Simple, no IPC; job persistence via SQLAlchemy |
| Chat mode | DB-only, no fallback | Reliable data > possibly-wrong web results |

See [research.md](research.md) for detailed analysis of each decision.

## Complexity Tracking

> No complexity violations identified. All changes follow existing patterns.

| Aspect | Approach | Justification |
|--------|----------|---------------|
| New table `contract_templates` | JSONB fields for flexibility | Templates vary per contract type, rigid schema would be limiting |
| AsyncIOScheduler in CLI | In-process, not daemon | Avoids platform-specific service management (Windows/Linux) |

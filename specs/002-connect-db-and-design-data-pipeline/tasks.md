# Tasks: Kết nối Database & Thiết kế Data Pipeline

**Epic**: `chatbot-m3x` | **Branch**: `002-connect-db-and-design-data-pipeline` | **Date**: 2026-02-10
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Summary

| Metric | Count |
|--------|-------|
| Features | 6 |
| Tasks | 33 |
| Priority 1 (Critical) | 24 |
| Priority 2 (Important) | 7 |
| Priority 3 (Nice-to-have) | 2 |

## Dependency Graph

```
Phase 0: Setup
  chatbot-4m1 (Setup & Dependencies)
    ├── chatbot-b0j  Update requirements.txt
    └── chatbot-wsi  Update .env.example
          │
Phase 1: Supabase Foundation ──────────────────────────
  chatbot-3mo (US1: Supabase Integration)       │
    ├── chatbot-3la  Extend config               │
    ├── chatbot-pfr  Extend Pydantic models       │
    │     ├── chatbot-42t  DatabaseInterface ABC   │
    │     │     └── chatbot-cut  SupabaseClient ◄──┘
    │     └── chatbot-l8c  SQL migration script
    └── chatbot-mbp  CLI db commands (depends: cut, l8c)
          │
Phase 2: Embedding Service ────────────────────────────
  chatbot-v0a (US2: Embedding Service)           │
    ├── chatbot-3hv  normalize_for_embedding()    │
    ├── chatbot-lwh  EmbeddingService core         │
    ├── chatbot-80j  split_long_article()          │
    ├── chatbot-8ai  embed_and_store() ◄───────────┘
    └── chatbot-hbt  Unit tests
          │
Phase 3: Data Pipeline ───────────────────────────────
  chatbot-4sx (US3: Data Pipeline Core)          │
    ├── chatbot-m2e  models/pipeline.py            │
    ├── chatbot-ua0  Playwright stealth crawler    │
    ├── chatbot-k5b  PipelineService orchestrator  │
    ├── chatbot-dp9  Extend indexer ◄──────────────┘
    └── chatbot-kzy  Pipeline CLI commands
          │
Phase 4: Test Case ───────────────────────────────────
  chatbot-1xb (US4: Land Law Crawl)             │
    ├── chatbot-70w  Configure đất đai category    │
    ├── chatbot-9z4  HTML parser for TVPL          │
    ├── chatbot-b1l  Run pipeline (3 docs min)     │
    └── chatbot-v7m  Test semantic search          │
          │                                         │
Phase 5: Audit Trail ─────────────────────────────────
  chatbot-w4o (US5: Audit Trail)                 │
    ├── chatbot-57z  models/audit.py               │
    ├── chatbot-gd2  AuditService                  │
    ├── chatbot-3p5  Integrate → ChatService       │
    ├── chatbot-db6  Integrate → GeneratorService  │
    ├── chatbot-6y7  Audit CLI commands            │
    └── chatbot-57d  Unit tests                    │
          │                                         │
Phase 6: Integration & Polish ────────────────────────
  chatbot-shq (US6: Integration & Polish)
    ├── chatbot-v7e  Update ChatService for Supabase RAG
    ├── chatbot-vhq  End-to-end integration test
    ├── chatbot-sdk  Scheduler (optional)
    └── chatbot-uvu  Final docs update
```

## Phase 0: Setup & Dependencies

### Feature: `chatbot-4m1` — Setup & Dependencies

| ID | Task | Priority | Depends On | File(s) |
|----|------|----------|------------|---------|
| `chatbot-b0j` | Update requirements.txt | P1 | — | `requirements.txt` |
| `chatbot-wsi` | Update .env.example with Supabase vars | P1 | — | `.env.example` |

**New dependencies**: `supabase>=2.0.0`, `sentence-transformers>=2.2.0`, `playwright-stealth>=1.0.0`, `apscheduler>=3.10.0`
**New env vars**: `DB_MODE`, `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY`, `PIPELINE_CRAWL_INTERVAL`, `PIPELINE_RATE_LIMIT`, `PIPELINE_MAX_PAGES`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION`

---

## Phase 1: US1 — Supabase Integration

### Feature: `chatbot-3mo` — US1: Supabase Integration

| ID | Task | Priority | Depends On | File(s) |
|----|------|----------|------------|---------|
| `chatbot-3la` | Extend config with Supabase settings | P1 | — | `utils/config.py` |
| `chatbot-pfr` | Extend Pydantic models for new schema | P1 | — | `models/document.py`, `models/pipeline.py`, `models/audit.py` |
| `chatbot-42t` | Implement abstract DatabaseInterface | P1 | `chatbot-pfr` | `db/base.py` |
| `chatbot-cut` | Implement SupabaseClient | P1 | `chatbot-42t`, `chatbot-3la` | `db/supabase.py` |
| `chatbot-l8c` | Create SQL migration script | P1 | `chatbot-pfr` | `db/migrations/002_supabase.sql` |
| `chatbot-mbp` | Add CLI db command group | P2 | `chatbot-cut`, `chatbot-l8c` | `cli/main.py` |

**Contract**: [contracts/supabase-client.md](./contracts/supabase-client.md)

**Key decisions**:
- Strategy pattern: `DatabaseInterface` ABC with `SupabaseClient` and `SQLiteClient` implementations
- Factory function `get_database(mode)` returns correct backend based on `DB_MODE`
- Service role client for writes (bypasses RLS), anon client for reads
- Vector search via RPC function `match_articles()` (PostgREST doesn't support pgvector operators)

---

## Phase 2: US2 — Embedding Service

### Feature: `chatbot-v0a` — US2: Embedding Service

| ID | Task | Priority | Depends On | File(s) |
|----|------|----------|------------|---------|
| `chatbot-3hv` | Add normalize_for_embedding() NFC function | P1 | — | `utils/vietnamese.py` |
| `chatbot-lwh` | Implement EmbeddingService core | P1 | — | `services/embedding.py` |
| `chatbot-80j` | Implement split_long_article() for token limit | P2 | — | `services/embedding.py` |
| `chatbot-8ai` | Implement embed_and_store() for Supabase | P1 | `chatbot-cut` | `services/embedding.py` |
| `chatbot-hbt` | Unit tests for embedding service | P2 | — | `tests/unit/test_embedding.py` |

**Contract**: [contracts/embedding.md](./contracts/embedding.md)

**Key decisions**:
- Model: `bkai-foundation-models/vietnamese-bi-encoder` (768d, 93.59% Acc@10 on legal retrieval)
- NFC normalization (NOT NFD) — PhoBERT tokenizer trained on NFC text
- Lazy-load model (~1.1 GB RAM), singleton per process
- Sort by length before batch encode (20-30% throughput improvement)
- Split articles >380 chars (~256 PhoBERT tokens) by Khoản, prepend Điều header

---

## Phase 3: US3 — Data Pipeline Core

### Feature: `chatbot-4sx` — US3: Data Pipeline Core

| ID | Task | Priority | Depends On | File(s) |
|----|------|----------|------------|---------|
| `chatbot-m2e` | Create models/pipeline.py | P1 | `chatbot-pfr` | `models/pipeline.py` |
| `chatbot-ua0` | Extend crawler with Playwright stealth + Cloudflare bypass | P1 | — | `services/crawler.py` |
| `chatbot-k5b` | Implement PipelineService orchestrator | P1 | `chatbot-cut`, `chatbot-v0a` | `services/pipeline.py` |
| `chatbot-dp9` | Extend indexer to use embedding service + Supabase | P1 | `chatbot-8ai`, `chatbot-cut` | `services/indexer.py` |
| `chatbot-kzy` | Add pipeline CLI command group | P2 | — | `cli/main.py` |

**Contract**: [contracts/pipeline.md](./contracts/pipeline.md)

**Key decisions**:
- 4-phase pipeline: Discovery → Crawl & Parse → Index & Embed → Validate
- Playwright + Firefox + `playwright-stealth` for Cloudflare bypass
- Rate limiting: 3-5s + 0-2s random jitter between requests
- SHA-256 content hash for change detection (skip unchanged documents)
- Pipeline runs logged to `pipeline_runs` table

---

## Phase 4: US4 — Land Law Crawl Test Case

### Feature: `chatbot-1xb` — US4: Land Law Crawl Test Case

| ID | Task | Priority | Depends On | File(s) |
|----|------|----------|------------|---------|
| `chatbot-70w` | Configure đất đai category with verified URLs | P1 | `chatbot-m2e` | config |
| `chatbot-9z4` | Implement HTML parser for thuvienphapluat.vn | P1 | — | `services/indexer.py` |
| `chatbot-b1l` | Run pipeline on đất đai category (3 docs min) | P1 | `chatbot-k5b` | integration |
| `chatbot-v7m` | Test semantic search with land law queries | P1 | — | integration |

**Verified URLs** (from research.md):
- Luật Đất đai 2024: `31/2024/QH15`
- NĐ 102/2024: Hướng dẫn Luật Đất đai
- NĐ 101/2024: Đăng ký, cấp giấy chứng nhận QSDĐ

**Success criteria**:
- 3+ documents crawled, 200+ articles parsed
- All articles have 768d embeddings
- Query "Điều kiện chuyển nhượng quyền sử dụng đất?" returns relevant Luật Đất đai 2024 articles

---

## Phase 5: US5 — Audit Trail

### Feature: `chatbot-w4o` — US5: Audit Trail

| ID | Task | Priority | Depends On | File(s) |
|----|------|----------|------------|---------|
| `chatbot-57z` | Create models/audit.py | P1 | — | `models/audit.py` |
| `chatbot-gd2` | Implement AuditService | P1 | `chatbot-cut` | `services/audit.py` |
| `chatbot-3p5` | Integrate audit into ChatService | P2 | — | `services/chat.py` |
| `chatbot-db6` | Integrate audit into GeneratorService | P2 | — | `services/generator.py` |
| `chatbot-6y7` | Add audit CLI command group | P2 | — | `cli/main.py` |
| `chatbot-57d` | Unit tests for audit service | P2 | — | `tests/unit/test_audit.py` |

**Contract**: [contracts/audit.md](./contracts/audit.md)

**Key decisions**:
- Audit failure must NOT prevent main operation (chat/generate) from completing
- Track law versions used in each research/contract for later verification
- `verify_audit()` checks if cited laws are still current
- Two audit types: `research_audits` (from chat/research) and `contract_audits` (from generator)

---

## Phase 6: US6 — Integration & Polish

### Feature: `chatbot-shq` — US6: Integration & Polish

| ID | Task | Priority | Depends On | File(s) |
|----|------|----------|------------|---------|
| `chatbot-v7e` | Update ChatService to query Supabase for RAG | P1 | `chatbot-cut`, `chatbot-v0a` | `services/chat.py` |
| `chatbot-vhq` | End-to-end integration test | P1 | `chatbot-b1l`, `chatbot-gd2` | `tests/integration/test_pipeline_e2e.py` |
| `chatbot-sdk` | Implement services/scheduler.py (optional) | P3 | `chatbot-k5b` | `services/scheduler.py` |
| `chatbot-uvu` | Final dependency and documentation updates | P3 | — | docs |

**E2E test flow**: Crawl đất đai → Verify articles indexed → Chat query → Verify audit trail → Verify law versions current

---

## Parallel Opportunities

These task groups can be worked on simultaneously:

1. **Phase 0 + Phase 1 config**: `chatbot-b0j`, `chatbot-wsi`, `chatbot-3la`, `chatbot-pfr` (no deps)
2. **US1 DB + US2 Embedding** (partially): `chatbot-3hv`, `chatbot-lwh`, `chatbot-80j` can start while US1 is in progress
3. **US3 Crawler + US4 Parser**: `chatbot-ua0` (stealth crawler) and `chatbot-9z4` (HTML parser) are independent
4. **US5 Models + US5 Integrations**: `chatbot-57z` (models) can start immediately; integrations after AuditService

## MVP Scope

**Minimum viable**: Phases 0-4 (28 tasks) — Supabase connected, embeddings working, pipeline crawls land law, semantic search returns relevant results.

**Full scope**: All 6 phases (33 tasks) — adds audit trail, scheduled runs, e2e tests.

**Optional/Deferrable**: `chatbot-sdk` (scheduler), `chatbot-uvu` (docs) — can ship without these.

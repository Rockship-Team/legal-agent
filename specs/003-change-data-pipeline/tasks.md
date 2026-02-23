# Tasks Index: 003 - DB-First Pipeline + Background Worker

Beads Issue Graph Index into the tasks and phases for this feature implementation.
This index does **not contain tasks directly**—those are fully managed through Beads CLI.

## Feature Tracking

* **Beads Epic ID**: `chatbot-5ht`
* **User Stories Source**: `specs/003-change-data-pipeline/spec.md`
* **Research Inputs**: `specs/003-change-data-pipeline/research.md`
* **Planning Details**: `specs/003-change-data-pipeline/plan.md`
* **Data Model**: `specs/003-change-data-pipeline/data-model.md`
* **Contract Definitions**: `specs/003-change-data-pipeline/contracts/`

## Beads Query Hints

Use the `bd` CLI to query and manipulate the issue graph:

```bash
# Find all open tasks for this feature
bd list --label "spec:003-change-data-pipeline" --status open -n 10

# Find ready tasks to implement
bd ready --label "spec:003-change-data-pipeline" -n 5

# See dependencies for issue
bd dep tree chatbot-5ht

# View issues by component
bd list --label "component:chat" --label "spec:003-change-data-pipeline" -n 5

# Show all phases (features)
bd list --type feature --label "spec:003-change-data-pipeline"

# Show tasks for a specific user story
bd list --label "story:US1" --label "spec:003-change-data-pipeline"
```

## Tasks and Phases Structure

```
Epic: chatbot-5ht (003 DB-First Pipeline + Background Worker)
├── Phase 1: Setup (chatbot-cp6) — Migration & Configuration
│   ├── T001: Write 003_worker.sql migration (chatbot-djs)
│   ├── T002: Add worker and chat settings to config.py (chatbot-5m7)
│   ├── T003: Create contract.py Pydantic models (chatbot-x9y)
│   ├── T004: Add pipeline models: WorkerStatus, DocumentRegistryEntry (chatbot-nqn)
│   └── T005: Add has_data field to ChatResponse model (chatbot-05y)
│
├── Phase 2: Foundational (chatbot-3zg) — DB CRUD & Seed Data
│   ├── T006: Add document_registry CRUD to supabase.py (chatbot-1a6)
│   ├── T007: Add contract_templates CRUD to supabase.py (chatbot-0hu)
│   ├── T008: Add category stats methods to supabase.py (chatbot-8o9)
│   ├── T009: Seed contract templates for 4 categories (chatbot-lhi)
│   └── T010: Seed document registry for initial categories (chatbot-09d)
│
├── Phase 3: US1 (chatbot-xkn) — DB-Only Chat & Research
│   ├── T011: Implement _detect_category() in chat.py (chatbot-bg4)
│   ├── T012: Implement _check_data_availability() in chat.py (chatbot-vpk)
│   ├── T013: Remove web search from chat.py, add no-data responses (chatbot-tul6)
│   └── T014: Convert research.py to DB-only deep search (chatbot-4lo2)
│
├── Phase 4: US2 (chatbot-dhm) — DB-Only Contract Creation
│   ├── T015: Create ContractService with DB-only logic (chatbot-skv9)
│   └── T016: Update legal.create-contract.md slash command (chatbot-dfhi)
│
├── Phase 5: US3 (chatbot-9ep) — Incremental Pipeline & Document Registry
│   ├── T017: Implement content hash normalization in pipeline.py (chatbot-91f8)
│   └── T018: Modify pipeline.run() to use document registry (chatbot-o331)
│
├── Phase 6: US4 (chatbot-7fr) — Background Worker
│   ├── T019: Create worker.py with AsyncIOScheduler (chatbot-rz5b)
│   ├── T020: Implement retry logic with exponential backoff (chatbot-ww1a)
│   ├── T021: Graceful shutdown with signal handling (chatbot-vvug)
│   ├── T022: Add WorkerStatus and WorkerJob models (chatbot-41ax)
│   ├── T023: Add worker CLI commands (chatbot-wbg6)
│   └── T024: Add worker settings to config (chatbot-neti)
│
└── Phase 7: US5 (chatbot-yqh) — Listing Discovery & Polish
    ├── T025: Listing page discovery (chatbot-1c5j)
    ├── T026: Auto-crawl and index new discovered documents (chatbot-twjw)
    ├── T027: Category stats dashboard in CLI (chatbot-mxhb)
    ├── T028: Update replaced/amended document status (chatbot-13gu)
    └── T029: Update CLAUDE.md with new architecture (chatbot-5w52)
```

## Convention Summary

| Type    | Description                  | Labels                                          |
| ------- | ---------------------------- | ----------------------------------------------- |
| epic    | Full feature epic            | `spec:003-change-data-pipeline`                 |
| feature | Implementation phase / story | `phase:<name>`, `story:US#`                     |
| task    | Implementation task          | `component:<area>`, `story:US#`                 |

## Dependency Graph — Execution Order

```
T001 (migration) ──┬─→ T006 (registry CRUD) ──→ T010 (seed registry) ──→ T018 (pipeline registry)
                   ├─→ T007 (templates CRUD) ──→ T009 (seed templates)
                   └─→ T008 (category stats)

T002 (config) ─────→ T024 (worker config) ──→ T019 (worker.py)

T003 (contract models) ──→ T015 (ContractService)
T005 (chat model) ───────→ T013 (chat DB-only)

T011 (detect category) ──→ T012 (check availability) ──→ T013 (chat DB-only)
T015 (ContractService) ──→ T016 (slash command)

T017 (hash) ──→ T018 (pipeline registry) ──→ T019 (worker.py) ──→ T020 (retry)
                                                                  ──→ T023 (CLI)
                                                                  ──→ T025 (discovery)
```

### Parallel Execution Opportunities

**Setup phase (all 5 parallel)**:
```bash
# T001, T002, T003, T004, T005 can all run in parallel
bd ready --label "phase:setup" --label "spec:003-change-data-pipeline"
```

**Foundational phase (T006, T007, T008 parallel after T001)**:
```bash
bd ready --label "phase:foundational" --label "spec:003-change-data-pipeline"
```

**US1 and US2 can run in parallel** (independent user stories):
```bash
bd ready --label "story:US1" --label "spec:003-change-data-pipeline"
bd ready --label "story:US2" --label "spec:003-change-data-pipeline"
```

**US3 and US4 partially parallel** (US4 depends on T018 from US3, but T022/T024 are independent):
```bash
bd ready --label "story:US3" --label "spec:003-change-data-pipeline"
bd ready --label "story:US4" --label "spec:003-change-data-pipeline"
```

## Implementation Strategy

### MVP (Minimum Viable Product) — US1 + US2

**Goal**: DB-only chat and contract creation working end-to-end.

**Scope**: Phases 1-4 (Setup → Foundational → US1 → US2)
- Tasks: T001-T016 (16 tasks)
- Chat queries use DB only, no web search
- Contract creation uses pre-mapped templates from DB
- No-data responses when category has no indexed articles

**Verification**:
```bash
# Chat with data → DB response
python -m legal_chatbot chat "Điều kiện chuyển nhượng đất"

# Chat without data → no-data message
python -m legal_chatbot chat "Quy định bảo hiểm xã hội"

# Contract with data → template-based
/legal.create-contract mua bán đất

# Contract without data → no-data message
/legal.create-contract hợp đồng bảo hiểm
```

### Increment 2 — Incremental Pipeline (US3)

**Goal**: Pipeline skips unchanged documents using content hash.

**Scope**: Phase 5 (T017-T018)

### Increment 3 — Background Worker (US4)

**Goal**: Automated daily pipeline runs per category.

**Scope**: Phase 6 (T019-T024)

### Increment 4 — Polish & Discovery (US5)

**Goal**: Auto-discover new law documents, stats dashboard, docs update.

**Scope**: Phase 7 (T025-T029)

## Story Testability

| Story | Independent? | Test Criteria |
|-------|-------------|---------------|
| US1   | Yes (after Setup + Foundational) | Chat returns DB-only response; no-data message for missing categories |
| US2   | Yes (after Setup + Foundational) | ContractService finds template + articles from DB; no-data for missing |
| US3   | Yes (after Foundational) | Pipeline skips unchanged docs; documents_skipped > 0 on re-run |
| US4   | Depends on US3 | Worker starts, runs scheduled jobs, retries on failure, stops gracefully |
| US5   | Depends on US4 | Listing pages discovered; new docs auto-indexed; stats dashboard works |

## Agent Execution Flow

MCP agents and AI workflows should:

1. **Assume `bd init` already done** by `specify init`
2. **Use `bd create`** to directly generate Beads issues
3. **Set metadata and dependencies** in the graph, not markdown
4. **Use this markdown only as a navigational anchor**

> Agents MUST NOT output tasks into this file. They MUST use Beads CLI to record all task and phase structure.

## Links

- [spec.md](spec.md) — Feature specification
- [plan.md](plan.md) — Implementation plan
- [research.md](research.md) — Technical research decisions
- [data-model.md](data-model.md) — Entity schemas & Pydantic models
- [quickstart.md](quickstart.md) — Setup guide
- [contracts/](contracts/) — Module interface contracts

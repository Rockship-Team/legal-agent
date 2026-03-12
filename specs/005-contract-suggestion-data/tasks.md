# Tasks Index: Contract Suggestion Examples & Type Fix

Beads Issue Graph Index into the tasks and phases for this feature implementation.
This index does **not contain tasks directly**—those are fully managed through Beads CLI.

## Feature Tracking

* **Beads Epic ID**: `chatbot-fz7s`
* **User Stories Source**: `specs/005-contract-suggestion-data/spec.md`
* **Research Inputs**: `specs/005-contract-suggestion-data/research.md`
* **Planning Details**: `specs/005-contract-suggestion-data/plan.md`
* **Data Model**: `specs/005-contract-suggestion-data/data-model.md`
* **Contract Definitions**: `specs/005-contract-suggestion-data/contracts/`

## Beads Query Hints

```bash
# Find all open tasks for this feature
bd list --label "spec:005-contract-suggestion-data" -n 20

# Find ready tasks to implement
bd ready --label "spec:005-contract-suggestion-data" -n 10

# See full dependency tree
bd dep tree --reverse chatbot-fz7s

# View tasks by user story
bd list --label "story:US1" --label "spec:005-contract-suggestion-data"
bd list --label "story:US2" --label "spec:005-contract-suggestion-data"
bd list --label "story:US3" --label "spec:005-contract-suggestion-data"

# Show all phases
bd list --type feature --label "spec:005-contract-suggestion-data"
```

## Tasks and Phases Structure

* **Epic**: `chatbot-fz7s` — Contract Suggestion Examples & Type Fix
* **Phases** (Beads features, children of epic):
  * `chatbot-ss4e` — Setup: DB Migration for sample_data column
  * `chatbot-d23d` — US1: Fix Contract Type Resolution (P1)
  * `chatbot-zers` — US3: Seed Suggestion Data via CLI Command (P2)
  * `chatbot-bfkp` — US2: Field Suggestion Examples During Contract Creation (P1)

## Convention Summary

| Type    | Description                  | Labels                                         |
| ------- | ---------------------------- | ---------------------------------------------- |
| epic    | Full feature epic            | `spec:005-contract-suggestion-data`             |
| feature | Implementation phase / story | `phase:<name>`, `story:US#`                    |
| task    | Implementation task          | `component:<area>`, `fr:FR-###`                |

---

## Phase 1: Setup (DB Infrastructure)

**Feature**: `chatbot-ss4e`
**Purpose**: Add sample_data column to contract_templates table

| Task ID | Title | Component | Priority |
|---------|-------|-----------|----------|
| `chatbot-w94p` | Create migration file 005_sample_data.sql | db | P1 |
| `chatbot-2tmv` | Add DB methods for sample_data CRUD | db | P1 |

**Dependencies**: `chatbot-2tmv` depends on `chatbot-w94p`

---

## Phase 2: US1 — Fix Contract Type Resolution (P1) — MVP

**Feature**: `chatbot-d23d`
**Goal**: Fix bug where system maps "cho thuê xe tự lái" to wrong contract type
**Independent Test**: Send requests for each contract type and verify 100% correct mapping
**Can run in parallel with**: Setup phase (no DB dependency)

| Task ID | Title | Component | Priority |
|---------|-------|-----------|----------|
| `chatbot-2f0c` | Replace substring matching with word-overlap scoring | services | P1 |

**Checkpoint**: Contract type resolution works correctly for all template types

---

## Phase 3: US3 — Seed Suggestion Data via CLI (P2)

**Feature**: `chatbot-zers`
**Goal**: CLI command to generate and persist sample data per template using LLM
**Independent Test**: Run seed command, verify data in DB
**Depends on**: Setup phase (needs sample_data column + DB methods)

| Task ID | Title | Component | Priority |
|---------|-------|-----------|----------|
| `chatbot-sz3u` | Create SuggestionSeeder service | services | P2 |
| `chatbot-pmhp` | Add seed-suggestions CLI command | cli | P2 |

**Dependencies**: `chatbot-pmhp` depends on `chatbot-sz3u`

**Checkpoint**: `python -m legal_chatbot seed-suggestions` works end-to-end

---

## Phase 4: US2 — Field Suggestion Examples (P1)

**Feature**: `chatbot-bfkp`
**Goal**: Show suggestion examples when asking for contract fields
**Independent Test**: Start contract creation, verify every field question shows example
**Depends on**: US3 (needs sample data in DB)

| Task ID | Title | Component | Priority |
|---------|-------|-----------|----------|
| `chatbot-gvy4` | Add suggestions to chat-mode field questions | services | P1 |
| `chatbot-wksy` | Add suggestions to API ContractFieldItem response | api | P1 |

**Dependencies**: Both tasks can run in parallel (different files)

**Checkpoint**: Both chat and API paths show field suggestions

---

## Dependencies & Execution Order

### Dependency Graph

```
chatbot-fz7s (Epic)
├── chatbot-ss4e (Setup) ─────────────────────────┐
│   ├── chatbot-w94p (Migration SQL)               │
│   └── chatbot-2tmv (DB methods) ← w94p           │
│                                                   │
├── chatbot-d23d (US1: Type Fix) [PARALLEL]         │
│   └── chatbot-2f0c (Word-overlap scoring)         │
│                                                   │
├── chatbot-zers (US3: Seed Command) ← ss4e ────────┘
│   ├── chatbot-sz3u (Seeder service) ← 2tmv
│   └── chatbot-pmhp (CLI command) ← sz3u
│
└── chatbot-bfkp (US2: Show Suggestions) ← zers
    ├── chatbot-gvy4 (Chat-mode suggestions) [PARALLEL]
    └── chatbot-wksy (API suggestions) [PARALLEL]
```

### Parallel Opportunities

1. **US1 (type fix)** can run in parallel with **Setup phase** — no DB dependency
2. **US2 tasks** (chat + API suggestions) can run in parallel with each other
3. **MVP = US1 alone** — fixes the critical bug independently

### Implementation Strategy

1. **MVP**: US1 (fix type resolution) — delivers immediate value, no infrastructure needed
2. **Increment 1**: Setup + US3 (migration + seed command) — builds data pipeline
3. **Increment 2**: US2 (show suggestions) — completes the full feature

---

> This file is intentionally light and index-only. Implementation data lives in Beads. Update this file only to point humans and agents to canonical query paths and feature references.

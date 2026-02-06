# Tasks Index: Legal Chatbot

Beads Issue Graph Index for the Legal Chatbot feature implementation.
This index does **not contain tasks directly**—those are fully managed through Beads CLI.

## Feature Tracking

* **Beads Epic ID**: `chatbot-bzv`
* **User Stories Source**: `specs/001-planning/spec.md`
* **Research Inputs**: `specs/001-planning/research.md`
* **Planning Details**: `specs/001-planning/plan.md`
* **Data Model**: `specs/001-planning/data-model.md`
* **Contract Definitions**: `specs/001-planning/contracts/`

## Beads Query Hints

Use the `bd` CLI to query and manipulate the issue graph:

```bash
# Find all open tasks for this feature
bd list --label spec:001-planning --status open --limit 10

# Find ready tasks to implement (no blocking dependencies)
bd ready --label spec:001-planning --limit 5

# See dependency tree from epic
bd dep tree --reverse chatbot-bzv

# View issues by phase
bd list --label "phase:setup" --label "spec:001-planning"
bd list --label "phase:foundational" --label "spec:001-planning"
bd list --label "phase:us1" --label "spec:001-planning"
bd list --label "phase:us2" --label "spec:001-planning"
bd list --label "phase:us3" --label "spec:001-planning"
bd list --label "phase:us4" --label "spec:001-planning"
bd list --label "phase:polish" --label "spec:001-planning"

# View issues by component
bd list --label "component:crawler" --label "spec:001-planning"
bd list --label "component:indexer" --label "spec:001-planning"
bd list --label "component:chat" --label "spec:001-planning"
bd list --label "component:generator" --label "spec:001-planning"
```

## Tasks and Phases Structure

This feature follows Beads' 2-level graph structure:

* **Epic**: `chatbot-bzv` → Legal Chatbot (full feature)
* **Phases**: Beads issues of type `feature`, children of the epic
* **Tasks**: Issues of type `task`, children of each feature issue (phase)

### Phase Overview

| Phase | ID | Description | Tasks | Priority |
|-------|-----|-------------|-------|----------|
| Setup | `chatbot-rvm` | Project initialization | 5 | P1 |
| Foundational | `chatbot-t2s` | Data layer infrastructure | 5 | P1 |
| US1: Crawler | `chatbot-8ir` | Web crawling from thuvienphapluat.vn | 4 | P1 |
| US2: Indexer | `chatbot-hy0` | Document indexing into SQLite+ChromaDB | 5 | P1 |
| US3: Chat | `chatbot-17y` | RAG-based legal Q&A with Groq LLM | 6 | P1 |
| US4: Generator | `chatbot-3z4` | PDF contract generation | 6 | P1 |
| Polish | `chatbot-day` | Integration, logging, optimization | 5 | P2 |

**Total Tasks**: 36

## Convention Summary

| Label | Purpose |
|-------|---------|
| `spec:001-planning` | All tasks in this feature |
| `phase:setup` | Setup phase tasks |
| `phase:foundational` | Foundational data layer |
| `phase:us1` | User Story 1: Crawler |
| `phase:us2` | User Story 2: Indexer |
| `phase:us3` | User Story 3: Chat Agent |
| `phase:us4` | User Story 4: Document Generator |
| `phase:polish` | Polish and integration |
| `story:US1-US4` | User story traceability |
| `component:*` | Module mapping (crawler, indexer, chat, generator, cli, db, infra) |

## Phase Dependencies

```
┌─────────────────┐
│  Phase 1: Setup │ (chatbot-rvm)
│  - pyproject.toml
│  - Package structure
│  - CLI skeleton
│  - Config management
│  - Pytest setup
└────────┬────────┘
         │ blocks
         ▼
┌─────────────────┐
│ Phase 2:        │ (chatbot-t2s)
│ Foundational    │
│  - Pydantic models
│  - SQLite operations
│  - ChromaDB operations
│  - Vietnamese utils
│  - Init command
└────────┬────────┘
         │ blocks
         ▼
┌─────────────────────────────────────────────────────────┐
│                    User Stories                          │
│  (Can run in parallel after Foundational completes)     │
├─────────────────┬─────────────────┬─────────────────────┤
│ US1: Crawler    │ US2: Indexer    │ US4: Generator      │
│ (chatbot-8ir)   │ (chatbot-hy0)   │ (chatbot-3z4)       │
│                 │       │         │                     │
│                 │ blocks│         │                     │
│                 │       ▼         │                     │
│                 │ US3: Chat       │                     │
│                 │ (chatbot-17y)   │                     │
└─────────────────┴─────────────────┴─────────────────────┘
         │
         ▼
┌─────────────────┐
│ Phase 7: Polish │ (chatbot-day)
│  - Logging
│  - Integration tests
│  - Performance
│  - Documentation
└─────────────────┘
```

## User Story Details

### US1: Data Crawler (Phase 3)

**Goal**: Fetch legal documents from thuvienphapluat.vn

**Independent Test**:
```bash
python -m legal_chatbot crawl --limit 5
# Should download 5 documents to data/raw/
```

**Tasks** (4):
- `chatbot-bf8`: Implement Playwright-based web crawler
- `chatbot-8ac`: Implement HTML parser for legal documents
- `chatbot-d59`: Add crawl CLI command
- `chatbot-kup`: Implement retry logic and error handling

### US2: Knowledge Indexer (Phase 4)

**Goal**: Index documents into searchable knowledge base

**Independent Test**:
```bash
python -m legal_chatbot index --input ./data/raw
# Should index all documents, show count
```

**Tasks** (5):
- `chatbot-c2s`: Implement article extraction from HTML
- `chatbot-9ac`: Implement embedding generation
- `chatbot-eqm`: Implement document indexing pipeline
- `chatbot-71w`: Add index CLI command
- `chatbot-3r9`: Implement semantic search function

### US3: Legal Chat Agent (Phase 5)

**Goal**: Answer legal questions with citations using RAG

**Depends on**: US2 (needs indexed documents for search)

**Independent Test**:
```bash
python -m legal_chatbot chat "Điều kiện cho thuê nhà là gì?"
# Should return answer with citations
```

**Tasks** (6):
- `chatbot-9yf`: Implement Groq API client
- `chatbot-tmz`: Implement RAG context builder
- `chatbot-akk`: Create system prompt for legal assistant
- `chatbot-xb8`: Implement chat service with citation extraction
- `chatbot-tzw`: Add chat CLI command
- `chatbot-js4`: Implement chat session persistence

### US4: Document Generator (Phase 6)

**Goal**: Generate PDF contracts from templates

**Independent Test**:
```bash
python -m legal_chatbot generate --template rental --interactive
# Should create contract.pdf
```

**Tasks** (6):
- `chatbot-g5f`: Create contract template JSON files
- `chatbot-bxd`: Implement template loader and validator
- `chatbot-6jw`: Implement ReportLab PDF generator
- `chatbot-gkd`: Add templates CLI command
- `chatbot-1bv`: Add generate CLI command
- `chatbot-dwi`: Integrate document generation with chat context

## Agent Execution Flow

MCP agents and AI workflows should:

1. **Query ready tasks**: `bd ready --label spec:001-planning --limit 5`
2. **Claim task**: `bd update <task-id> --status in_progress`
3. **Implement**: Follow design in task description
4. **Complete**: `bd close <task-id> --reason "Implemented as specified"`

## MVP Scope

**Suggested MVP**: Complete through US3 (Chat Agent)

This delivers:
- Working CLI with all commands
- Crawled legal documents
- Indexed knowledge base
- RAG-based legal Q&A with citations

**MVP Validation**:
```bash
# Initialize
python -m legal_chatbot init

# Crawl sample documents
python -m legal_chatbot crawl --limit 10

# Index documents
python -m legal_chatbot index --input ./data/raw

# Test chat
python -m legal_chatbot chat "Điều kiện cho thuê nhà là gì?"
```

## Incremental Delivery

| Increment | Phases | Value Delivered |
|-----------|--------|-----------------|
| v0.1 | Setup + Foundational | Project skeleton, data layer |
| v0.2 | + US1 Crawler | Can fetch legal documents |
| v0.3 | + US2 Indexer | Searchable knowledge base |
| v0.4 (MVP) | + US3 Chat | Legal Q&A with citations |
| v1.0 | + US4 Generator + Polish | Full feature with PDF generation |

---

> This file is an index. Implementation data lives in Beads.
> Run `bd list --label spec:001-planning` for current task status.

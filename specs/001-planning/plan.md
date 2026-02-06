# Implementation Plan: Legal Chatbot

**Branch**: `001-planning` | **Date**: 2026-02-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-planning/spec.md`

## Summary

Build a Python CLI chatbot for a law firm that:
1. Crawls Vietnamese legal documents from thuvienphapluat.vn
2. Indexes documents into SQLite + ChromaDB for semantic search
3. Answers legal questions using RAG with Groq LLM (LLaMA 3.3)
4. Generates PDF contracts from templates

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Groq SDK, ChromaDB, Typer, ReportLab, Playwright
**Storage**: SQLite (structured data) + ChromaDB (vectors)
**Testing**: pytest
**Target Platform**: CLI (Windows/Linux/Mac)
**Project Type**: Single Python package
**Performance Goals**: Response time <5s for chat queries
**Constraints**: Offline-capable knowledge base, Vietnamese language support
**Scale/Scope**: Initial dataset ~100 legal documents, ~2000 articles

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Specification-First**: Spec.md complete with use cases
- [x] **Test-First**: Test strategy defined (contract + integration tests planned)
- [x] **Code Quality**: Black + isort + mypy identified
- [x] **UX Consistency**: CLI commands documented in quickstart.md
- [x] **Performance**: Response time <5s defined
- [x] **Observability**: Logging with Python logging module
- [x] **Issue Tracking**: Beads epic created (`chatbot-bzv`)

**Complexity Violations**: None identified

## Project Structure

### Documentation (this feature)

```text
specs/001-planning/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 research findings
├── data-model.md        # Database schema and models
├── quickstart.md        # Getting started guide
├── contracts/           # Module interface contracts
│   ├── crawler.md
│   ├── indexer.md
│   ├── chat.md
│   └── document-generator.md
└── tasks.md             # Phase 2 output (to be generated)
```

### Source Code (repository root)

```text
legal_chatbot/
├── __init__.py
├── __main__.py          # CLI entry point
├── cli/
│   ├── __init__.py
│   ├── main.py          # Typer CLI app
│   ├── crawl.py         # Crawl commands
│   ├── index.py         # Index commands
│   ├── chat.py          # Chat commands
│   └── generate.py      # Generate commands
├── services/
│   ├── __init__.py
│   ├── crawler.py       # Web crawler service
│   ├── indexer.py       # Document indexer service
│   ├── chat.py          # Chat agent service
│   └── generator.py     # PDF generator service
├── models/
│   ├── __init__.py
│   ├── document.py      # Legal document models
│   ├── chat.py          # Chat session models
│   └── template.py      # Contract template models
├── db/
│   ├── __init__.py
│   ├── sqlite.py        # SQLite operations
│   └── chroma.py        # ChromaDB operations
├── templates/
│   ├── rental.json      # Hợp đồng thuê nhà
│   ├── sale.json        # Hợp đồng mua bán
│   └── service.json     # Hợp đồng dịch vụ
└── utils/
    ├── __init__.py
    ├── vietnamese.py    # Vietnamese text processing
    └── config.py        # Configuration management

data/
├── raw/                 # Crawled HTML/PDF files
├── legal.db            # SQLite database
└── chroma/             # ChromaDB vector store

tests/
├── conftest.py         # Pytest fixtures
├── contract/           # Contract tests
│   ├── test_crawler_contract.py
│   ├── test_indexer_contract.py
│   ├── test_chat_contract.py
│   └── test_generator_contract.py
├── integration/        # Integration tests
│   └── test_rag_pipeline.py
└── unit/               # Unit tests
    ├── test_crawler.py
    ├── test_indexer.py
    ├── test_chat.py
    └── test_generator.py
```

**Structure Decision**: Single Python package structure chosen for simplicity. All modules in one package with clear separation of concerns.

## Implementation Phases

### Phase 1: Foundation (Project Setup)
- Initialize Python project with pyproject.toml
- Setup development environment (venv, dependencies)
- Create package structure
- Configure pytest, black, isort, mypy
- Implement configuration management

### Phase 2: Data Layer (Storage)
- Implement SQLite database schema
- Create migration system
- Setup ChromaDB collection
- Implement database operations (CRUD)
- Unit tests for data layer

### Phase 3: Crawler Module
- Implement Playwright-based crawler
- HTML parsing with BeautifulSoup
- Rate limiting and retry logic
- CLI commands for crawling
- Contract tests for crawler

### Phase 4: Indexer Module
- Vietnamese text normalization
- Article extraction from HTML
- Embedding generation with sentence-transformers
- Index into SQLite + ChromaDB
- Contract tests for indexer

### Phase 5: Chat Agent
- Groq API integration
- RAG context builder
- System prompt engineering
- Citation extraction
- Streaming response support
- Contract tests for chat

### Phase 6: Document Generator
- Contract template system (JSON-based)
- PDF generation with ReportLab
- Data validation
- CLI commands for generation
- Contract tests for generator

### Phase 7: Integration & Testing
- End-to-end tests
- Integration tests for RAG pipeline
- Performance testing
- Documentation finalization

## Dependencies

```
# Core
groq>=0.4.0
chromadb>=0.4.0
sentence-transformers>=2.2.0

# CLI
typer>=0.9.0
rich>=13.0.0

# PDF
reportlab>=4.0.0

# Crawler
playwright>=1.40.0
beautifulsoup4>=4.12.0
aiohttp>=3.9.0

# Data
pydantic>=2.0.0
python-dotenv>=1.0.0

# Dev
pytest>=7.0.0
pytest-asyncio>=0.21.0
pytest-cov>=4.0.0
black>=23.0.0
isort>=5.0.0
mypy>=1.0.0
```

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| thuvienphapluat.vn blocks crawler | Implement respectful rate limiting, use cached data |
| Groq API rate limits | Implement retry with backoff, cache frequent queries |
| LLM hallucination | Strict RAG grounding, explicit citation requirement |
| Vietnamese embedding quality | Test with legal-specific queries, consider fine-tuning |

## Success Criteria

1. **Crawler**: Successfully fetch and parse 10+ legal documents
2. **Indexer**: Index all articles with searchable vectors
3. **Chat**: Answer legal questions with accurate citations
4. **Generator**: Produce valid PDF contracts from templates

## Next Steps

1. Run `/specledger.tasks` to generate detailed task breakdown
2. Create Beads epic for issue tracking
3. Begin Phase 1 implementation

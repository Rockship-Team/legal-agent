# Legal Chatbot Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-02-05

## Active Technologies
- Python 3.11+ (All modules)
- SQLite + ChromaDB (Database + Vector store)
- Groq API with LLaMA 3.3 70B (LLM)
- Typer + Rich (CLI framework)
- ReportLab (PDF generation)
- Playwright + BeautifulSoup (Web crawling)
- sentence-transformers (Embeddings)
- pytest (Testing)
- Python 3.11+ + supabase-py, sentence-transformers, Playwright + stealth, APScheduler (002-connect-db-and-design-data-pipeline)
- Supabase PostgreSQL + pgvector (production) / SQLite (local fallback) (002-connect-db-and-design-data-pipeline)

## Project Structure

```text
legal_chatbot/
  __init__.py
  __main__.py           # CLI entry point
  cli/                  # Typer CLI commands
    main.py
    crawl.py
    index.py
    chat.py
    generate.py
  services/             # Business logic
    crawler.py
    indexer.py
    chat.py
    generator.py
  models/               # Pydantic models
    document.py
    chat.py
    template.py
  db/                   # Database operations
    sqlite.py
    chroma.py
  templates/            # Contract templates (JSON)
  utils/                # Shared utilities

data/
  raw/                  # Crawled documents
  legal.db             # SQLite database
  chroma/              # ChromaDB vectors

tests/
  contract/            # Contract tests
  integration/         # Integration tests
  unit/                # Unit tests

specs/
  001-planning/        # Feature specs
    spec.md
    plan.md
    research.md
    data-model.md
    quickstart.md
    contracts/
```

## Commands

```bash
# Setup
python -m venv venv
source venv/bin/activate  # or .\venv\Scripts\activate on Windows
pip install -r requirements.txt

# CLI Commands
python -m legal_chatbot crawl --source thuvienphapluat --limit 10
python -m legal_chatbot index --input ./data/raw
python -m legal_chatbot chat "Điều kiện cho thuê nhà là gì?"
python -m legal_chatbot generate --template rental --output contract.pdf

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
GROQ_API_KEY=gsk_...
DATABASE_PATH=./data/legal.db
CHROMA_PATH=./data/chroma
LOG_LEVEL=INFO
```

## Recent Changes
- 002-connect-db-and-design-data-pipeline: Added Python 3.11+ + supabase-py, sentence-transformers, Playwright + stealth, APScheduler
- 001-planning: Simplified to Python-only CLI with Groq API (2026-02-05)

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->

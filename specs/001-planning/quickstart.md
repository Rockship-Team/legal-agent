# Quickstart: Legal Chatbot

**Date**: 2026-02-05 | **Spec**: [spec.md](./spec.md)

## Prerequisites

- Python 3.11+
- pip (Python package manager)
- Git

## Setup

### 1. Clone and Create Virtual Environment

```bash
cd c:/Users/ADMIN/chatbot
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Create `.env` file:

```bash
GROQ_API_KEY=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
DATABASE_PATH=./data/legal.db
CHROMA_PATH=./data/chroma
LOG_LEVEL=INFO
```

### 4. Initialize Database

```bash
python -m legal_chatbot init
```

## Usage

### Crawl Legal Documents

```bash
# Crawl 10 documents from thuvienphapluat.vn
python -m legal_chatbot crawl --source thuvienphapluat --limit 10

# Crawl specific category
python -m legal_chatbot crawl --category luat --limit 5
```

### Index Documents

```bash
# Index all crawled documents
python -m legal_chatbot index --input ./data/raw

# Verify index
python -m legal_chatbot index --status
```

### Chat with Legal Assistant

```bash
# Single question
python -m legal_chatbot chat "Điều kiện cho thuê nhà là gì?"

# Interactive mode
python -m legal_chatbot chat --interactive

# JSON output
python -m legal_chatbot chat "Điều kiện thuê nhà?" --json
```

### Generate Contracts

```bash
# List available templates
python -m legal_chatbot templates

# Show template fields
python -m legal_chatbot template rental --fields

# Generate with data
python -m legal_chatbot generate --template rental \
  --output contract.pdf \
  --data '{"landlord_name": "Nguyễn Văn A", "tenant_name": "Trần Văn B", ...}'

# Interactive generation
python -m legal_chatbot generate --template rental --interactive
```

## Project Structure

```
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
│   ├── crawler.py       # Crawler service
│   ├── indexer.py       # Indexer service
│   ├── chat.py          # Chat agent service
│   └── generator.py     # Document generator
├── models/
│   ├── __init__.py
│   ├── document.py      # Domain models
│   ├── chat.py          # Chat models
│   └── template.py      # Template models
├── db/
│   ├── __init__.py
│   ├── sqlite.py        # SQLite operations
│   └── chroma.py        # ChromaDB operations
├── templates/
│   ├── rental.json
│   ├── sale.json
│   └── ...
└── utils/
    ├── __init__.py
    ├── vietnamese.py    # Vietnamese text processing
    └── config.py        # Configuration

data/
├── raw/                 # Crawled HTML files
├── legal.db            # SQLite database
└── chroma/             # ChromaDB vector store

tests/
├── contract/           # Contract tests
├── integration/        # Integration tests
└── unit/               # Unit tests
```

## Development

### Run Tests

```bash
# All tests
pytest

# Specific module
pytest tests/unit/test_crawler.py

# With coverage
pytest --cov=legal_chatbot
```

### Code Formatting

```bash
# Format code
black legal_chatbot tests

# Sort imports
isort legal_chatbot tests

# Type check
mypy legal_chatbot
```

## Troubleshooting

### Groq API Error

```
Error: Authentication failed
```

Solution: Verify `GROQ_API_KEY` in `.env` file.

### ChromaDB Error

```
Error: Collection not found
```

Solution: Run `python -m legal_chatbot index --input ./data/raw` first.

### Vietnamese Encoding Issues

```
Error: UnicodeDecodeError
```

Solution: Ensure files are saved with UTF-8 encoding.

## Next Steps

1. Crawl initial legal documents
2. Index into knowledge base
3. Test chat functionality
4. Create custom contract templates

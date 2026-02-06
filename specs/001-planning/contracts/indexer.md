# Indexer Module Contract

## Overview
The Indexer module processes crawled documents and stores them in SQLite + ChromaDB.

## Interface

### IndexerService

```python
from abc import ABC, abstractmethod
from typing import List
from pydantic import BaseModel

class IndexConfig(BaseModel):
    input_dir: str
    chunk_size: int = 1000
    chunk_overlap: int = 100
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"

class IndexResult(BaseModel):
    documents_processed: int
    articles_indexed: int
    vectors_created: int
    errors: List[str]

class ParsedArticle(BaseModel):
    document_id: str
    article_number: int
    title: Optional[str]
    content: str
    chapter: Optional[str]

class IndexerService(ABC):
    @abstractmethod
    def parse_document(self, html_content: str, document_id: str) -> List[ParsedArticle]:
        """
        Parse HTML content into individual articles.

        Extracts Điều (articles), Khoản (clauses), Điểm (points).
        """
        pass

    @abstractmethod
    def index_articles(self, articles: List[ParsedArticle]) -> IndexResult:
        """
        Index articles into SQLite and ChromaDB.

        1. Store full content in SQLite
        2. Generate embeddings
        3. Store vectors in ChromaDB
        """
        pass

    @abstractmethod
    def index_from_directory(self, config: IndexConfig) -> IndexResult:
        """
        Process all documents in input directory.
        """
        pass
```

## CLI Contract

```bash
# Index crawled documents
legal-chatbot index --input ./data/raw --chunk-size 1000

# Output: JSON to stdout
{"status": "started", "input": "./data/raw"}
{"type": "progress", "documents": 5, "articles": 120}
{"status": "completed", "documents_processed": 10, "articles_indexed": 245, "vectors_created": 245}

# Verbose mode
legal-chatbot index --input ./data/raw --verbose
{"type": "document", "id": "...", "articles_count": 25}
```

## Data Processing Pipeline

```
HTML Document
    │
    ▼ (Parse)
┌─────────────────┐
│ Extract         │
│ - Document meta │
│ - Articles      │
│ - Chapters      │
└─────────────────┘
    │
    ▼ (Normalize)
┌─────────────────┐
│ Vietnamese NFD  │
│ normalization   │
└─────────────────┘
    │
    ▼ (Store)
┌─────────────────┐     ┌─────────────────┐
│    SQLite       │     │   ChromaDB      │
│ (full content)  │     │   (vectors)     │
└─────────────────┘     └─────────────────┘
```

## Vietnamese Text Processing

```python
import unicodedata

def normalize_vietnamese(text: str) -> str:
    """
    Normalize Vietnamese text for consistent processing.
    - NFD normalization
    - Lowercase for comparison
    - Preserve original for storage
    """
    return unicodedata.normalize('NFD', text)
```

## Dependencies
- chromadb: Vector database
- sentence-transformers: Embeddings
- sqlite3: Structured storage

## Testing Contract

```python
def test_parse_extracts_articles():
    """Parser should extract all articles from document"""
    html = "<div class='article'>Điều 1. ...</div>"
    articles = indexer.parse_document(html, "doc_1")
    assert len(articles) >= 1
    assert articles[0].article_number == 1

def test_index_creates_vectors():
    """Indexer should create searchable vectors"""
    result = indexer.index_articles([...])
    assert result.vectors_created > 0
```

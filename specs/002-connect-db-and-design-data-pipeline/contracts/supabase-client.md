# Supabase Client Module Contract

## Overview
The Supabase client module provides a unified interface for database operations, implementing the abstract `DatabaseInterface` alongside the existing SQLite module.

## Interface

### DatabaseInterface (Abstract Base)

```python
# db/base.py
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

class DatabaseInterface(ABC):
    """Abstract interface for database operations.
    Implemented by both SQLite and Supabase backends."""

    @abstractmethod
    def init_db(self) -> None:
        """Initialize database schema (create tables, indexes)."""
        pass

    @abstractmethod
    def insert_document(self, document: dict) -> str:
        """Insert a legal document. Returns document ID."""
        pass

    @abstractmethod
    def insert_articles(self, articles: List[dict]) -> int:
        """Batch insert articles. Returns count inserted."""
        pass

    @abstractmethod
    def get_document(self, document_id: str) -> Optional[dict]:
        """Get document by ID."""
        pass

    @abstractmethod
    def get_documents_by_category(self, category_name: str) -> List[dict]:
        """Get all documents in a category."""
        pass

    @abstractmethod
    def search_articles(self, query_embedding: List[float],
                        top_k: int = 5, status: str = "active") -> List[dict]:
        """Semantic search via embeddings. Returns articles with similarity."""
        pass

    @abstractmethod
    def get_document_by_hash(self, content_hash: str) -> Optional[dict]:
        """Find document by content hash (for change detection)."""
        pass

    @abstractmethod
    def upsert_document(self, document: dict) -> str:
        """Insert or update document. Returns document ID."""
        pass
```

### SupabaseClient

```python
# db/supabase.py
from functools import lru_cache
from supabase import create_client, Client, ClientOptions

class SupabaseClient(DatabaseInterface):
    """Supabase implementation of DatabaseInterface."""

    def __init__(self, url: str, key: str, service_key: Optional[str] = None):
        self._client = create_client(url, key, options=ClientOptions(
            postgrest_client_timeout=10,
            storage_client_timeout=30,
        ))
        # Service role client for write operations (bypasses RLS)
        self._service_client = create_client(url, service_key) if service_key else self._client

    def search_articles(self, query_embedding, top_k=5, status="active"):
        """Call match_articles RPC function."""
        result = self._client.rpc("match_articles", {
            "query_embedding": query_embedding,
            "match_threshold": 0.5,
            "match_count": top_k,
            "filter_status": status,
        }).execute()
        return result.data

    # Storage operations
    def upload_raw_document(self, path: str, content: bytes, mime_type: str) -> str:
        """Upload raw document to Supabase Storage."""
        pass

    def download_raw_document(self, path: str) -> bytes:
        """Download raw document from Supabase Storage."""
        pass
```

### Factory Function

```python
# db/__init__.py
def get_database(mode: str = None) -> DatabaseInterface:
    """Factory: returns appropriate database implementation.

    mode: 'supabase' or 'sqlite'. Defaults to DB_MODE env var.
    """
    if mode == "supabase":
        return SupabaseClient(url=..., key=..., service_key=...)
    else:
        return SQLiteClient(path=...)
```

## CLI Contract

```bash
# Migrate schema to Supabase
python -m legal_chatbot db migrate
# Output: ✓ Tables created: 9 | Indexes: 15 | RPC functions: 2

# Check connection status
python -m legal_chatbot db status
# Output:
# Mode: supabase
# URL: https://xxx.supabase.co
# Documents: 6 | Articles: 523 | Embeddings: 523
# Storage: legal-raw-documents (6 files, 2.3 MB)

# Sync local SQLite ↔ Supabase
python -m legal_chatbot db sync
# Output: ✓ Synced 6 documents, 523 articles
```

## Error Handling

| Error | Code | Handling |
|-------|------|----------|
| Connection failed | CONN_ERROR | Retry 3x, then fallback to SQLite |
| Unique violation | 23505 | Skip (document already exists) |
| FK violation | 23503 | Log warning, skip relation |
| Wrong vector dim | 22000 | Fatal: model mismatch |
| Rate limited | 429 | Exponential backoff |

## Testing Contract

```python
def test_supabase_insert_and_query():
    """Should insert document and retrieve by ID"""
    db = SupabaseClient(url, key)
    doc_id = db.insert_document({...})
    doc = db.get_document(doc_id)
    assert doc["title"] == "Luật Đất đai 2024"

def test_supabase_vector_search():
    """Should return similar articles via RPC"""
    results = db.search_articles(query_embedding, top_k=5)
    assert len(results) > 0
    assert all(r["similarity"] > 0.5 for r in results)

def test_factory_returns_correct_implementation():
    """Factory should return correct backend based on mode"""
    db = get_database("supabase")
    assert isinstance(db, SupabaseClient)
    db = get_database("sqlite")
    assert isinstance(db, SQLiteClient)
```

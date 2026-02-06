# Data Model: Legal Chatbot

**Date**: 2026-02-05 | **Spec**: [spec.md](./spec.md)

## Overview

This document defines the data structures for the Legal Chatbot system:
1. SQLite tables for structured legal data
2. ChromaDB collections for vector search
3. Pydantic models for application layer

## 1. SQLite Schema

### 1.1 Legal Documents Table

```sql
CREATE TABLE legal_documents (
    id TEXT PRIMARY KEY,
    document_type TEXT NOT NULL,      -- 'bo_luat', 'luat', 'nghi_dinh', 'thong_tu'
    document_number TEXT NOT NULL,     -- e.g., '91/2015/QH13'
    title TEXT NOT NULL,
    effective_date DATE,
    issuing_authority TEXT,
    source_url TEXT,
    crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_content TEXT,
    status TEXT DEFAULT 'active'       -- 'active', 'amended', 'repealed'
);

CREATE INDEX idx_documents_type ON legal_documents(document_type);
CREATE INDEX idx_documents_status ON legal_documents(status);
```

### 1.2 Articles Table (Điều)

```sql
CREATE TABLE articles (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES legal_documents(id),
    article_number INTEGER NOT NULL,
    title TEXT,
    content TEXT NOT NULL,
    chapter TEXT,                      -- Chapter/Section reference
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, article_number)
);

CREATE INDEX idx_articles_document ON articles(document_id);
```

### 1.3 Contract Templates Table

```sql
CREATE TABLE contract_templates (
    id TEXT PRIMARY KEY,
    template_type TEXT NOT NULL,       -- 'rental', 'sale', 'service', 'employment'
    name TEXT NOT NULL,
    description TEXT,
    template_content TEXT NOT NULL,    -- JSON with placeholders
    required_fields TEXT,              -- JSON array of required field names
    legal_references TEXT,             -- JSON array of related article IDs
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_templates_type ON contract_templates(template_type);
```

### 1.4 Chat Sessions Table

```sql
CREATE TABLE chat_sessions (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_message_at TIMESTAMP,
    context TEXT                       -- JSON with collected user data
);

CREATE TABLE chat_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES chat_sessions(id),
    role TEXT NOT NULL,                -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    citations TEXT,                    -- JSON array of article references
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_messages_session ON chat_messages(session_id);
```

## 2. ChromaDB Collections

### 2.1 Legal Articles Collection

```python
# Collection: legal_articles
{
    "name": "legal_articles",
    "metadata": {
        "description": "Vietnamese legal articles for semantic search"
    },
    "embedding_function": "paraphrase-multilingual-MiniLM-L12-v2"
}

# Document schema
{
    "id": "article_{document_id}_{article_number}",
    "document": "Article content text...",
    "metadata": {
        "document_id": "string",
        "document_title": "string",
        "article_number": "int",
        "article_title": "string",
        "document_type": "string",
        "effective_date": "string (ISO format)",
        "chapter": "string (optional)"
    }
}
```

### 2.2 Contract Templates Collection

```python
# Collection: contract_templates
{
    "name": "contract_templates",
    "metadata": {
        "description": "Contract template descriptions for matching"
    }
}

# Document schema
{
    "id": "template_{type}_{version}",
    "document": "Template description and use cases...",
    "metadata": {
        "template_type": "string",
        "name": "string",
        "required_fields": "string (JSON array)"
    }
}
```

## 3. Pydantic Models

### 3.1 Domain Models

```python
from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, List
from enum import Enum

class DocumentType(str, Enum):
    BO_LUAT = "bo_luat"
    LUAT = "luat"
    NGHI_DINH = "nghi_dinh"
    THONG_TU = "thong_tu"

class DocumentStatus(str, Enum):
    ACTIVE = "active"
    AMENDED = "amended"
    REPEALED = "repealed"

class LegalDocument(BaseModel):
    id: str
    document_type: DocumentType
    document_number: str
    title: str
    effective_date: Optional[date]
    issuing_authority: Optional[str]
    source_url: Optional[str]
    status: DocumentStatus = DocumentStatus.ACTIVE

class Article(BaseModel):
    id: str
    document_id: str
    article_number: int
    title: Optional[str]
    content: str
    chapter: Optional[str]

class ArticleWithContext(Article):
    """Article with document context for display"""
    document_title: str
    document_type: DocumentType
    effective_date: Optional[date]
```

### 3.2 Chat Models

```python
class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class Citation(BaseModel):
    article_id: str
    article_number: int
    document_title: str
    relevance_score: float

class ChatMessage(BaseModel):
    id: str
    session_id: str
    role: MessageRole
    content: str
    citations: List[Citation] = []
    created_at: datetime

class ChatSession(BaseModel):
    id: str
    created_at: datetime
    last_message_at: Optional[datetime]
    context: dict = {}  # Collected user data
```

### 3.3 Contract Models

```python
class TemplateType(str, Enum):
    RENTAL = "rental"           # Hợp đồng thuê nhà
    SALE = "sale"               # Hợp đồng mua bán
    SERVICE = "service"         # Hợp đồng dịch vụ
    EMPLOYMENT = "employment"   # Hợp đồng lao động

class ContractField(BaseModel):
    name: str
    label: str
    field_type: str  # 'text', 'date', 'number', 'address'
    required: bool = True
    default_value: Optional[str] = None

class ContractTemplate(BaseModel):
    id: str
    template_type: TemplateType
    name: str
    description: str
    required_fields: List[ContractField]
    legal_references: List[str]  # Article IDs
    version: int = 1

class GeneratedContract(BaseModel):
    template_id: str
    filled_fields: dict
    output_path: str
    generated_at: datetime
    disclaimer: str = "Văn bản này chỉ mang tính chất tham khảo"
```

### 3.4 RAG Models

```python
class SearchResult(BaseModel):
    article: ArticleWithContext
    score: float
    highlights: List[str] = []

class RAGContext(BaseModel):
    query: str
    retrieved_articles: List[SearchResult]
    max_context_tokens: int = 4000

class LLMResponse(BaseModel):
    answer: str
    citations: List[Citation]
    suggested_templates: List[str] = []
    follow_up_questions: List[str] = []
```

## 4. Data Flow Diagram

```
User Query
    │
    ▼
┌─────────────────┐
│  Query Parser   │ → Extract intent, entities
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ ChromaDB Search │ → Semantic retrieval (top-k)
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ SQLite Lookup   │ → Fetch full article content
└─────────────────┘
    │
    ▼
┌─────────────────┐
│   RAG Context   │ → Build context for LLM
└─────────────────┘
    │
    ▼
┌─────────────────┐
│   Groq LLM      │ → Generate response
└─────────────────┘
    │
    ▼
Response with Citations
```

## 5. Migration Scripts

Initial migration to create all tables:

```python
# migrations/001_initial.py
MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS legal_documents (...);
    """,
    """
    CREATE TABLE IF NOT EXISTS articles (...);
    """,
    """
    CREATE TABLE IF NOT EXISTS contract_templates (...);
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_sessions (...);
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_messages (...);
    """
]
```

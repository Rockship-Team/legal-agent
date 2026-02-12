# Data Model: Kết nối Database & Thiết kế Data Pipeline

**Date**: 2026-02-10 | **Spec**: [spec.md](./spec.md)

## Overview

This document defines the data structures for the Supabase integration and data pipeline:
1. Supabase PostgreSQL schema (with pgvector)
2. Supabase RPC functions for vector search
3. Supabase Storage buckets
4. Pydantic models for application layer
5. Migration from existing SQLite schema

## 1. Supabase PostgreSQL Schema

### 1.1 Enable Extensions

```sql
CREATE EXTENSION IF NOT EXISTS vector;       -- pgvector for embeddings
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- UUID generation (fallback)
```

### 1.2 Legal Categories Table

```sql
CREATE TABLE legal_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,              -- 'dat_dai', 'nha_o', 'dan_su'
    display_name TEXT NOT NULL,              -- 'Đất đai', 'Nhà ở', 'Dân sự'
    description TEXT,
    crawl_url TEXT,                          -- Base URL on thuvienphapluat.vn
    last_crawled_at TIMESTAMPTZ,
    crawl_interval_hours INT DEFAULT 168,    -- 7 days
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_categories_name ON legal_categories(name);
CREATE INDEX idx_categories_active ON legal_categories(is_active);
```

### 1.3 Legal Documents Table (Extended from 001)

```sql
CREATE TABLE legal_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id UUID REFERENCES legal_categories(id),
    document_type TEXT NOT NULL,             -- 'LUAT', 'NGHI_DINH', 'THONG_TU', 'BO_LUAT'
    document_number TEXT NOT NULL,           -- '31/2024/QH15'
    title TEXT NOT NULL,
    effective_date DATE,
    expiry_date DATE,                        -- NULL = no expiry
    issuing_authority TEXT,                   -- 'Quốc hội', 'Chính phủ'
    source_url TEXT,
    raw_storage_path TEXT,                   -- Path in Supabase Storage
    status TEXT DEFAULT 'active',            -- 'active', 'amended', 'repealed', 'expired'
    replaces_document_id UUID REFERENCES legal_documents(id),
    amended_by_document_id UUID REFERENCES legal_documents(id),
    metadata JSONB DEFAULT '{}',             -- Flexible: nguoi_ky, so_cong_bao, etc.
    content_hash TEXT,                       -- SHA-256 of raw content
    crawled_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(document_number, document_type)
);

CREATE INDEX idx_documents_category ON legal_documents(category_id);
CREATE INDEX idx_documents_type ON legal_documents(document_type);
CREATE INDEX idx_documents_status ON legal_documents(status);
CREATE INDEX idx_documents_effective ON legal_documents(effective_date);
CREATE INDEX idx_documents_hash ON legal_documents(content_hash);
```

### 1.4 Articles Table (Extended with pgvector)

```sql
CREATE TABLE articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES legal_documents(id) ON DELETE CASCADE,
    article_number INT NOT NULL,
    title TEXT,
    content TEXT NOT NULL,
    chapter TEXT,                             -- Chương
    section TEXT,                             -- Mục
    part TEXT,                                -- Phần
    embedding VECTOR(768),                   -- vietnamese-bi-encoder (768d)
    content_hash TEXT,                       -- SHA-256 of content
    chunk_index INT DEFAULT 0,               -- 0 = full article, >0 = split chunk
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(document_id, article_number, chunk_index)
);

-- HNSW index for semantic search (self-updating, no rebuild needed)
CREATE INDEX articles_embedding_idx
ON articles USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_articles_document ON articles(document_id);
CREATE INDEX idx_articles_number ON articles(article_number);
CREATE INDEX idx_articles_hash ON articles(content_hash);
```

### 1.5 Document Relations Table

```sql
CREATE TABLE document_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_document_id UUID NOT NULL REFERENCES legal_documents(id) ON DELETE CASCADE,
    target_document_id UUID NOT NULL REFERENCES legal_documents(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,              -- 'replaces', 'amends', 'guides', 'references'
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(source_document_id, target_document_id, relation_type)
);

CREATE INDEX idx_relations_source ON document_relations(source_document_id);
CREATE INDEX idx_relations_target ON document_relations(target_document_id);
CREATE INDEX idx_relations_type ON document_relations(relation_type);
```

### 1.6 Pipeline Runs Table

```sql
CREATE TABLE pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id UUID REFERENCES legal_categories(id),
    status TEXT NOT NULL DEFAULT 'running',   -- 'running', 'completed', 'failed'
    documents_found INT DEFAULT 0,
    documents_new INT DEFAULT 0,
    documents_updated INT DEFAULT 0,
    articles_indexed INT DEFAULT 0,
    embeddings_generated INT DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_pipeline_category ON pipeline_runs(category_id);
CREATE INDEX idx_pipeline_status ON pipeline_runs(status);
CREATE INDEX idx_pipeline_started ON pipeline_runs(started_at);
```

### 1.7 Research Audits Table

```sql
CREATE TABLE research_audits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT,
    query TEXT NOT NULL,
    sources JSONB DEFAULT '[]',              -- [{article_id, article_number, doc_title, similarity}]
    response TEXT,
    law_versions JSONB DEFAULT '[]',         -- [{doc_id, doc_number, effective_date, status}]
    confidence_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_research_session ON research_audits(session_id);
CREATE INDEX idx_research_created ON research_audits(created_at);
```

### 1.8 Contract Audits Table

```sql
CREATE TABLE contract_audits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT,
    contract_type TEXT NOT NULL,
    input_data JSONB DEFAULT '{}',
    generated_content TEXT,
    legal_references JSONB DEFAULT '[]',
    law_versions JSONB DEFAULT '[]',
    pdf_storage_path TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_contract_session ON contract_audits(session_id);
CREATE INDEX idx_contract_type ON contract_audits(contract_type);
CREATE INDEX idx_contract_created ON contract_audits(created_at);
```

### 1.9 Existing Tables (Preserved)

The following tables from 001 are kept unchanged in Supabase:

```sql
-- Chat sessions (migrated from SQLite)
CREATE TABLE chat_sessions (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_message_at TIMESTAMPTZ,
    context JSONB DEFAULT '{}'
);

-- Chat messages (migrated from SQLite)
CREATE TABLE chat_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES chat_sessions(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    citations JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_messages_session ON chat_messages(session_id);

-- Contract templates (migrated from SQLite)
CREATE TABLE contract_templates (
    id TEXT PRIMARY KEY,
    template_type TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    template_content JSONB NOT NULL,
    required_fields JSONB DEFAULT '[]',
    legal_references JSONB DEFAULT '[]',
    version INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_templates_type ON contract_templates(template_type);
```

## 2. RPC Functions

### 2.1 Semantic Search — `match_articles`

```sql
CREATE OR REPLACE FUNCTION match_articles(
    query_embedding VECTOR(768),
    match_threshold FLOAT DEFAULT 0.5,
    match_count INT DEFAULT 5,
    filter_status TEXT DEFAULT 'active'
)
RETURNS TABLE (
    id UUID,
    document_id UUID,
    article_number INT,
    title TEXT,
    content TEXT,
    chapter TEXT,
    section TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id, a.document_id, a.article_number, a.title, a.content,
        a.chapter, a.section,
        1 - (a.embedding <=> query_embedding) AS similarity
    FROM articles a
    JOIN legal_documents d ON a.document_id = d.id
    WHERE d.status = filter_status
      AND a.embedding IS NOT NULL
      AND 1 - (a.embedding <=> query_embedding) > match_threshold
    ORDER BY a.embedding <=> query_embedding
    LIMIT match_count;
END; $$;
```

### 2.2 Extended Search — `search_legal_articles`

```sql
CREATE OR REPLACE FUNCTION search_legal_articles(
    query_embedding VECTOR(768),
    match_threshold FLOAT DEFAULT 0.5,
    match_count INT DEFAULT 10,
    filter_status TEXT DEFAULT 'active',
    filter_category TEXT DEFAULT NULL
)
RETURNS TABLE (
    article_id UUID,
    article_number INT,
    article_title TEXT,
    article_content TEXT,
    chapter TEXT,
    document_id UUID,
    document_number TEXT,
    document_title TEXT,
    document_type TEXT,
    effective_date DATE,
    category_name TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.id AS article_id,
        a.article_number,
        a.title AS article_title,
        a.content AS article_content,
        a.chapter,
        d.id AS document_id,
        d.document_number,
        d.title AS document_title,
        d.document_type,
        d.effective_date,
        c.name AS category_name,
        1 - (a.embedding <=> query_embedding) AS similarity
    FROM articles a
    JOIN legal_documents d ON a.document_id = d.id
    LEFT JOIN legal_categories c ON d.category_id = c.id
    WHERE d.status = filter_status
      AND a.embedding IS NOT NULL
      AND 1 - (a.embedding <=> query_embedding) > match_threshold
      AND (filter_category IS NULL OR c.name = filter_category)
    ORDER BY a.embedding <=> query_embedding
    LIMIT match_count;
END; $$;
```

## 3. Supabase Storage Buckets

```
legal-raw-documents/          # Raw crawled content
├── luat/                     # Luật
├── nghi-dinh/                # Nghị định
├── thong-tu/                 # Thông tư
└── bo-luat/                  # Bộ luật

generated-contracts/          # Generated PDF contracts
├── YYYY-MM/
│   └── {uuid}-{type}.pdf
```

**Bucket policies**:
- `legal-raw-documents`: Private, max 10MB per file, mime types: text/html, application/pdf
- `generated-contracts`: Private, max 5MB per file, mime types: application/pdf

## 4. Pydantic Models

### 4.1 Extended Domain Models

```python
# models/document.py — EXTENSIONS

from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel
from enum import Enum
import uuid


class DocumentStatus(str, Enum):
    ACTIVE = "active"
    AMENDED = "amended"
    REPEALED = "repealed"
    EXPIRED = "expired"


class DocumentType(str, Enum):
    BO_LUAT = "BO_LUAT"
    LUAT = "LUAT"
    NGHI_DINH = "NGHI_DINH"
    THONG_TU = "THONG_TU"
    QUYET_DINH = "QUYET_DINH"
    NGHI_QUYET = "NGHI_QUYET"


class RelationType(str, Enum):
    REPLACES = "replaces"
    AMENDS = "amends"
    GUIDES = "guides"
    REFERENCES = "references"


class LegalCategory(BaseModel):
    id: str = ""
    name: str                              # 'dat_dai'
    display_name: str                      # 'Đất đai'
    description: Optional[str] = None
    crawl_url: Optional[str] = None
    last_crawled_at: Optional[datetime] = None
    crawl_interval_hours: int = 168
    is_active: bool = True


class LegalDocument(BaseModel):
    """Extended from 001 with category, expiry, relations, hash"""
    id: str = ""
    category_id: Optional[str] = None
    document_type: DocumentType
    document_number: str
    title: str
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    issuing_authority: Optional[str] = None
    source_url: Optional[str] = None
    raw_storage_path: Optional[str] = None
    status: DocumentStatus = DocumentStatus.ACTIVE
    replaces_document_id: Optional[str] = None
    amended_by_document_id: Optional[str] = None
    metadata: dict = {}
    content_hash: Optional[str] = None
    crawled_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Article(BaseModel):
    """Extended with section, part, embedding, hash, chunk"""
    id: str = ""
    document_id: str
    article_number: int
    title: Optional[str] = None
    content: str
    chapter: Optional[str] = None
    section: Optional[str] = None
    part: Optional[str] = None
    embedding: Optional[List[float]] = None
    content_hash: Optional[str] = None
    chunk_index: int = 0


class ArticleWithContext(Article):
    """Article with document metadata for display"""
    document_title: str = ""
    document_type: DocumentType = DocumentType.LUAT
    document_number: str = ""
    effective_date: Optional[date] = None
    category_name: Optional[str] = None
    similarity: Optional[float] = None


class DocumentRelation(BaseModel):
    id: str = ""
    source_document_id: str
    target_document_id: str
    relation_type: RelationType
    description: Optional[str] = None
```

### 4.2 Pipeline Models

```python
# models/pipeline.py — NEW

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from enum import Enum


class PipelineStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CategoryConfig(BaseModel):
    """Configuration for crawling a legal category"""
    name: str                              # 'dat_dai'
    display_name: str                      # 'Đất đai'
    crawl_url: str                         # Base URL
    document_urls: List[str] = []          # Known document URLs
    max_pages: int = 20
    rate_limit_seconds: float = 4.0        # 3-5s range


class CrawlResult(BaseModel):
    """Result of crawling a single document"""
    url: str
    document_number: str
    title: str
    document_type: str
    effective_date: Optional[str] = None
    issuing_authority: Optional[str] = None
    status: str = "active"
    html_content: str = ""
    content_hash: str = ""
    is_new: bool = True                    # False if already in DB
    articles_count: int = 0


class PipelineRun(BaseModel):
    """Record of a pipeline execution"""
    id: str = ""
    category_id: Optional[str] = None
    status: PipelineStatus = PipelineStatus.RUNNING
    documents_found: int = 0
    documents_new: int = 0
    documents_updated: int = 0
    articles_indexed: int = 0
    embeddings_generated: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
```

### 4.3 Audit Models

```python
# models/audit.py — NEW

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class LawVersion(BaseModel):
    """Version of a law used in a response"""
    document_id: str
    document_number: str
    title: str
    effective_date: Optional[str] = None
    status: str = "active"


class ArticleSource(BaseModel):
    """Article used as source in a response"""
    article_id: str
    article_number: int
    document_title: str
    similarity: float


class ResearchAudit(BaseModel):
    """Audit trail for a research/chat response"""
    id: str = ""
    session_id: Optional[str] = None
    query: str
    sources: List[ArticleSource] = []
    response: str = ""
    law_versions: List[LawVersion] = []
    confidence_score: Optional[float] = None
    created_at: Optional[datetime] = None


class ContractAudit(BaseModel):
    """Audit trail for a generated contract"""
    id: str = ""
    session_id: Optional[str] = None
    contract_type: str
    input_data: dict = {}
    generated_content: str = ""
    legal_references: List[ArticleSource] = []
    law_versions: List[LawVersion] = []
    pdf_storage_path: Optional[str] = None
    created_at: Optional[datetime] = None
```

## 5. Schema Migration: SQLite → Supabase

### 5.1 Mapping

| SQLite (001) | Supabase (002) | Changes |
|-------------|----------------|---------|
| `legal_documents.id` TEXT | UUID | Auto-generated |
| `legal_documents.raw_content` | Removed (use Storage) | Raw content in bucket |
| — | `legal_documents.category_id` | NEW: FK to categories |
| — | `legal_documents.expiry_date` | NEW: Nullable |
| — | `legal_documents.replaces_document_id` | NEW: FK self-ref |
| — | `legal_documents.metadata` JSONB | NEW: Flexible |
| — | `legal_documents.content_hash` | NEW: SHA-256 |
| `articles` | Same + `embedding`, `section`, `part`, `content_hash`, `chunk_index` | Extended |
| — | `legal_categories` | NEW table |
| — | `document_relations` | NEW table |
| — | `pipeline_runs` | NEW table |
| — | `research_audits` | NEW table |
| — | `contract_audits` | NEW table |
| `contract_templates` TEXT fields | JSONB fields | Type change |
| `chat_sessions.context` TEXT | JSONB | Type change |
| `chat_messages.citations` TEXT | JSONB | Type change |

### 5.2 Data Flow Diagram

```
Pipeline Crawl
    │
    ▼
┌─────────────────┐     ┌─────────────────┐
│ Supabase Storage │     │  Parse HTML     │
│ (raw documents)  │     │  (BeautifulSoup)│
└─────────────────┘     └────────┬────────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
          ┌─────────────────┐      ┌─────────────────┐
          │ legal_documents │      │    articles      │
          │ (PostgreSQL)    │      │ (PostgreSQL +    │
          │                 │      │  pgvector)       │
          └─────────────────┘      └────────┬────────┘
                                            │
                                            ▼
                                 ┌─────────────────┐
                                 │  Embedding       │
                                 │  (vietnamese-    │
                                 │   bi-encoder)    │
                                 └────────┬────────┘
                                          │
                                          ▼
User Query ──→ match_articles() RPC ──→ Top-K Results
                                          │
                                          ▼
                              ┌─────────────────────┐
                              │  Groq LLM (RAG)     │
                              └──────────┬──────────┘
                                         │
                              ┌──────────┴──────────┐
                              ▼                     ▼
                   ┌─────────────────┐   ┌─────────────────┐
                   │ research_audits │   │ contract_audits  │
                   └─────────────────┘   └─────────────────┘
```

## 6. Row Level Security (RLS)

```sql
-- Enable RLS on all tables
ALTER TABLE legal_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE legal_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_relations ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_audits ENABLE ROW LEVEL SECURITY;
ALTER TABLE contract_audits ENABLE ROW LEVEL SECURITY;

-- Public read for legal data (anon key)
CREATE POLICY "Public read categories" ON legal_categories FOR SELECT USING (true);
CREATE POLICY "Public read documents" ON legal_documents FOR SELECT USING (true);
CREATE POLICY "Public read articles" ON articles FOR SELECT USING (true);
CREATE POLICY "Public read relations" ON document_relations FOR SELECT USING (true);

-- Service role write for pipeline operations
CREATE POLICY "Service write categories" ON legal_categories FOR ALL
    USING (auth.role() = 'service_role');
CREATE POLICY "Service write documents" ON legal_documents FOR ALL
    USING (auth.role() = 'service_role');
CREATE POLICY "Service write articles" ON articles FOR ALL
    USING (auth.role() = 'service_role');
CREATE POLICY "Service write relations" ON document_relations FOR ALL
    USING (auth.role() = 'service_role');

-- Service role for pipeline and audits
CREATE POLICY "Service write pipeline" ON pipeline_runs FOR ALL
    USING (auth.role() = 'service_role');
CREATE POLICY "Service write research_audits" ON research_audits FOR ALL
    USING (auth.role() = 'service_role');
CREATE POLICY "Service write contract_audits" ON contract_audits FOR ALL
    USING (auth.role() = 'service_role');
```

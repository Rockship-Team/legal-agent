-- Migration 002: Supabase schema for Legal Chatbot
-- Run this in Supabase SQL Editor

-- 1. Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Legal categories
CREATE TABLE IF NOT EXISTS legal_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    description TEXT,
    crawl_url TEXT,
    last_crawled_at TIMESTAMPTZ,
    crawl_interval_hours INT DEFAULT 168,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_categories_name ON legal_categories(name);
CREATE INDEX IF NOT EXISTS idx_categories_active ON legal_categories(is_active);

-- 3. Legal documents (extended from 001)
CREATE TABLE IF NOT EXISTS legal_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id UUID REFERENCES legal_categories(id),
    document_type TEXT NOT NULL,
    document_number TEXT NOT NULL,
    title TEXT NOT NULL,
    effective_date DATE,
    expiry_date DATE,
    issuing_authority TEXT,
    source_url TEXT,
    raw_storage_path TEXT,
    status TEXT DEFAULT 'active',
    replaces_document_id UUID REFERENCES legal_documents(id),
    amended_by_document_id UUID REFERENCES legal_documents(id),
    metadata JSONB DEFAULT '{}',
    content_hash TEXT,
    crawled_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(document_number, document_type)
);

CREATE INDEX IF NOT EXISTS idx_documents_category ON legal_documents(category_id);
CREATE INDEX IF NOT EXISTS idx_documents_type ON legal_documents(document_type);
CREATE INDEX IF NOT EXISTS idx_documents_status ON legal_documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_effective ON legal_documents(effective_date);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON legal_documents(content_hash);

-- 4. Articles (extended with pgvector)
CREATE TABLE IF NOT EXISTS articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES legal_documents(id) ON DELETE CASCADE,
    article_number INT NOT NULL,
    title TEXT,
    content TEXT NOT NULL,
    chapter TEXT,
    section TEXT,
    part TEXT,
    embedding VECTOR(768),
    content_hash TEXT,
    chunk_index INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(document_id, article_number, chunk_index)
);

CREATE INDEX IF NOT EXISTS articles_embedding_idx
ON articles USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_articles_document ON articles(document_id);
CREATE INDEX IF NOT EXISTS idx_articles_number ON articles(article_number);
CREATE INDEX IF NOT EXISTS idx_articles_hash ON articles(content_hash);

-- 5. Document relations
CREATE TABLE IF NOT EXISTS document_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_document_id UUID NOT NULL REFERENCES legal_documents(id) ON DELETE CASCADE,
    target_document_id UUID NOT NULL REFERENCES legal_documents(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(source_document_id, target_document_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_relations_source ON document_relations(source_document_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON document_relations(target_document_id);
CREATE INDEX IF NOT EXISTS idx_relations_type ON document_relations(relation_type);

-- 6. Pipeline runs
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id UUID REFERENCES legal_categories(id),
    status TEXT NOT NULL DEFAULT 'running',
    documents_found INT DEFAULT 0,
    documents_new INT DEFAULT 0,
    documents_updated INT DEFAULT 0,
    articles_indexed INT DEFAULT 0,
    embeddings_generated INT DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_pipeline_category ON pipeline_runs(category_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_status ON pipeline_runs(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_started ON pipeline_runs(started_at);

-- 7. Research audits
CREATE TABLE IF NOT EXISTS research_audits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT,
    query TEXT NOT NULL,
    sources JSONB DEFAULT '[]',
    response TEXT,
    law_versions JSONB DEFAULT '[]',
    confidence_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_research_session ON research_audits(session_id);
CREATE INDEX IF NOT EXISTS idx_research_created ON research_audits(created_at);

-- 8. Contract audits
CREATE TABLE IF NOT EXISTS contract_audits (
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

CREATE INDEX IF NOT EXISTS idx_contract_session ON contract_audits(session_id);
CREATE INDEX IF NOT EXISTS idx_contract_type ON contract_audits(contract_type);
CREATE INDEX IF NOT EXISTS idx_contract_created ON contract_audits(created_at);

-- 9. Existing tables (from 001, migrated)
CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_message_at TIMESTAMPTZ,
    context JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES chat_sessions(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    citations JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id);

CREATE TABLE IF NOT EXISTS contract_templates (
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

CREATE INDEX IF NOT EXISTS idx_templates_type ON contract_templates(template_type);

-- 10. RPC functions for vector search

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

-- 11. Row Level Security

ALTER TABLE legal_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE legal_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_relations ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_audits ENABLE ROW LEVEL SECURITY;
ALTER TABLE contract_audits ENABLE ROW LEVEL SECURITY;

-- Public read for legal data
CREATE POLICY "Public read categories" ON legal_categories FOR SELECT USING (true);
CREATE POLICY "Public read documents" ON legal_documents FOR SELECT USING (true);
CREATE POLICY "Public read articles" ON articles FOR SELECT USING (true);
CREATE POLICY "Public read relations" ON document_relations FOR SELECT USING (true);

-- Service role write access
CREATE POLICY "Service write categories" ON legal_categories FOR ALL
    USING (auth.role() = 'service_role');
CREATE POLICY "Service write documents" ON legal_documents FOR ALL
    USING (auth.role() = 'service_role');
CREATE POLICY "Service write articles" ON articles FOR ALL
    USING (auth.role() = 'service_role');
CREATE POLICY "Service write relations" ON document_relations FOR ALL
    USING (auth.role() = 'service_role');
CREATE POLICY "Service write pipeline" ON pipeline_runs FOR ALL
    USING (auth.role() = 'service_role');
CREATE POLICY "Service write research_audits" ON research_audits FOR ALL
    USING (auth.role() = 'service_role');
CREATE POLICY "Service write contract_audits" ON contract_audits FOR ALL
    USING (auth.role() = 'service_role');

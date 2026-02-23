-- Migration 003: Worker + Document Registry + Contract Templates
-- Run this in Supabase SQL Editor AFTER 002_supabase.sql

-- =============================================================
-- 1. ALTER legal_categories — Add worker schedule fields
-- =============================================================

ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS worker_schedule TEXT DEFAULT 'weekly';
ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS worker_time TEXT DEFAULT '02:00';
ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS worker_status TEXT DEFAULT 'active';
ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS document_count INT DEFAULT 0;
ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS article_count INT DEFAULT 0;
ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS last_worker_run_at TIMESTAMPTZ;
ALTER TABLE legal_categories ADD COLUMN IF NOT EXISTS last_worker_status TEXT;

-- =============================================================
-- 2. ALTER pipeline_runs — Add worker metadata
-- =============================================================

ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS trigger_type TEXT DEFAULT 'manual';
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS documents_skipped INT DEFAULT 0;
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS duration_seconds FLOAT;

-- =============================================================
-- 3. CREATE document_registry — URL list per category
-- =============================================================

CREATE TABLE IF NOT EXISTS document_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id UUID REFERENCES legal_categories(id),
    url TEXT NOT NULL UNIQUE,
    document_number TEXT,
    title TEXT,
    role TEXT DEFAULT 'primary',        -- 'primary', 'related', 'base'
    priority INT DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    last_checked_at TIMESTAMPTZ,
    last_content_hash TEXT,
    last_etag TEXT,
    last_modified TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_registry_category ON document_registry(category_id);
CREATE INDEX IF NOT EXISTS idx_registry_active ON document_registry(is_active);

-- =============================================================
-- 4. DROP + CREATE contract_templates — New schema
-- =============================================================
-- The old contract_templates (from 002) has a different schema.
-- Drop it and recreate with the new structure.

DROP TABLE IF EXISTS contract_templates;

CREATE TABLE contract_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id UUID REFERENCES legal_categories(id),
    contract_type TEXT NOT NULL,
    display_name TEXT NOT NULL,
    description TEXT,
    search_queries JSONB NOT NULL,
    required_laws JSONB,
    min_articles INT DEFAULT 5,
    required_fields JSONB,
    article_outline JSONB,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(category_id, contract_type)
);

CREATE INDEX IF NOT EXISTS idx_ct_category ON contract_templates(category_id);
CREATE INDEX IF NOT EXISTS idx_ct_type ON contract_templates(contract_type);

-- =============================================================
-- 5. Row Level Security for new tables
-- =============================================================

ALTER TABLE document_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE contract_templates ENABLE ROW LEVEL SECURITY;

-- Public read access
CREATE POLICY "Public read document_registry" ON document_registry FOR SELECT USING (true);
CREATE POLICY "Public read contract_templates" ON contract_templates FOR SELECT USING (true);

-- Service role write access
CREATE POLICY "Service write document_registry" ON document_registry FOR ALL
    USING (auth.role() = 'service_role');
CREATE POLICY "Service write contract_templates" ON contract_templates FOR ALL
    USING (auth.role() = 'service_role');

-- =============================================================
-- 6. RPC Functions
-- =============================================================

-- Get category stats (article/document counts)
CREATE OR REPLACE FUNCTION get_category_stats(cat_name TEXT)
RETURNS TABLE (
    id UUID,
    name TEXT,
    display_name TEXT,
    document_count INT,
    article_count INT,
    worker_status TEXT,
    last_worker_run_at TIMESTAMPTZ
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id, c.name, c.display_name,
        c.document_count, c.article_count,
        c.worker_status, c.last_worker_run_at
    FROM legal_categories c
    WHERE c.name = cat_name;
END;
$$;

-- Update category counts (called after pipeline run)
CREATE OR REPLACE FUNCTION update_category_counts(cat_id UUID)
RETURNS VOID
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE legal_categories SET
        document_count = (
            SELECT COUNT(*)::INT FROM legal_documents WHERE category_id = cat_id
        ),
        article_count = (
            SELECT COUNT(*)::INT FROM articles a
            JOIN legal_documents d ON a.document_id = d.id
            WHERE d.category_id = cat_id
        )
    WHERE id = cat_id;
END;
$$;

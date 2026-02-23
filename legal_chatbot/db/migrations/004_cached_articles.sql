-- Migration 004: Add cached_articles to contract_templates
-- Run this in Supabase SQL Editor AFTER 003_worker.sql

-- Store pre-computed search results so contract creation doesn't need embeddings
ALTER TABLE contract_templates ADD COLUMN IF NOT EXISTS cached_articles JSONB DEFAULT '[]'::jsonb;
ALTER TABLE contract_templates ADD COLUMN IF NOT EXISTS cached_at TIMESTAMPTZ;

-- 008_default_articles.sql
-- Add default_articles column to contract_templates for storing pre-generated article templates
-- Run this in Supabase SQL Editor

-- Store article templates with placeholders (e.g. {ben_a_ten}, {gia_tri})
-- so contract creation doesn't need LLM calls every time
ALTER TABLE contract_templates
ADD COLUMN IF NOT EXISTS default_articles JSONB DEFAULT NULL;

COMMENT ON COLUMN contract_templates.default_articles IS
  'Pre-generated article templates with field placeholders. Structure: [{"title": "ĐIỀU 1: ...", "content": ["1.1. {ben_a_ten} ...", ...]}]';

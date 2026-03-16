-- 007_sample_data.sql
-- Add sample_data column to contract_templates for storing LLM-generated field examples
-- Run this in Supabase SQL Editor

ALTER TABLE contract_templates
ADD COLUMN IF NOT EXISTS sample_data JSONB DEFAULT NULL;

COMMENT ON COLUMN contract_templates.sample_data IS
  'LLM-generated example data for each field. Structure: {field_name: {examples: [...], format_hint: "..."}}';

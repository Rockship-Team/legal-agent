-- Migration 005: Add title column to chat_sessions
-- Run this in Supabase SQL Editor

ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS title TEXT DEFAULT 'Cuộc hội thoại mới';

-- Index for ordering by last_message_at (used by session list)
CREATE INDEX IF NOT EXISTS idx_chat_sessions_last_msg ON chat_sessions(last_message_at DESC);

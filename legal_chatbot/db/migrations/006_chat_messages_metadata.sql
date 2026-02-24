-- 006: Add metadata JSONB column to chat_messages
-- Stores pdf_url and other message-level metadata for persistence across reloads

ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT NULL;

COMMENT ON COLUMN chat_messages.metadata IS 'Optional message metadata (pdf_url, etc.)';

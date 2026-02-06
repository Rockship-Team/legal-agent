-- Enable pgvector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify extension is installed
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE EXCEPTION 'pgvector extension failed to install';
    END IF;
END $$;

-- Create a simple test to verify vector operations work
CREATE TABLE IF NOT EXISTS _vector_test (
    id SERIAL PRIMARY KEY,
    embedding vector(3)
);

INSERT INTO _vector_test (embedding) VALUES ('[1,2,3]');

-- Test vector operations
DO $$
DECLARE
    result FLOAT;
BEGIN
    SELECT embedding <=> '[3,2,1]' INTO result FROM _vector_test WHERE id = 1;
    IF result IS NULL THEN
        RAISE EXCEPTION 'Vector operations not working';
    END IF;
END $$;

-- Clean up test table
DROP TABLE _vector_test;

-- Log success
DO $$ BEGIN RAISE NOTICE 'pgvector extension enabled and tested successfully'; END $$;

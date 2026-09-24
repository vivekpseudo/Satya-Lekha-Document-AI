CREATE TABLE IF NOT EXISTS regulation_chunks (
    id BIGSERIAL PRIMARY KEY,
    regulation_id VARCHAR(200) NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    source_uri TEXT NOT NULL,
    effective_from DATE,
    effective_to DATE,
    embedding vector(768)
);

CREATE INDEX IF NOT EXISTS regulation_chunks_regulation_id_idx
    ON regulation_chunks (regulation_id);

-- Install/enable pgvector before running this table:
-- CREATE EXTENSION IF NOT EXISTS vector;

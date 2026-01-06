-- Create embeddings table for code embeddings storage
CREATE TABLE IF NOT EXISTS embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    chunk_type VARCHAR(50) NOT NULL, -- function, class, module, directory
    embedding vector(384), -- Dimension depends on embedding model (384 for all-MiniLM-L6-v2)
    metadata JSONB DEFAULT '{}'::jsonb, -- Additional metadata (line numbers, imports, etc.)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_embeddings_repository_id ON embeddings(repository_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_file_path ON embeddings(file_path);
CREATE INDEX IF NOT EXISTS idx_embeddings_chunk_type ON embeddings(chunk_type);
-- Vector similarity index using HNSW (for fast approximate nearest neighbor search)
CREATE INDEX IF NOT EXISTS idx_embeddings_embedding_hnsw ON embeddings 
    USING hnsw (embedding vector_cosine_ops);



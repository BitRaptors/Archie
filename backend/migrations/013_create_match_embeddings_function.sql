-- Create vector similarity search function for RAG
CREATE OR REPLACE FUNCTION match_embeddings(
    query_embedding vector(384),
    match_count INT DEFAULT 10,
    filter_repository_id UUID DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    repository_id UUID,
    file_path TEXT,
    chunk_type VARCHAR(50),
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.id,
        e.repository_id,
        e.file_path,
        e.chunk_type,
        e.metadata,
        1 - (e.embedding <=> query_embedding) AS similarity
    FROM embeddings e
    WHERE (filter_repository_id IS NULL OR e.repository_id = filter_repository_id)
    ORDER BY e.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION match_embeddings TO authenticated;
GRANT EXECUTE ON FUNCTION match_embeddings TO anon;


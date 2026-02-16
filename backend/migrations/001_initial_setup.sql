-- Architecture Blueprints — Initial Database Setup
-- Consolidated migration: creates all tables, indexes, functions, and grants.
-- Run against a Supabase PostgreSQL instance with pgvector support.

-- ============================================================
-- Extensions
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- Tables (in dependency order)
-- ============================================================

-- 1. users
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    github_token_encrypted TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

-- 2. repositories
CREATE TABLE IF NOT EXISTS repositories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    owner VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    full_name VARCHAR(512) NOT NULL,
    url TEXT NOT NULL,
    description TEXT,
    language VARCHAR(100),
    default_branch VARCHAR(255) NOT NULL DEFAULT 'main',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    UNIQUE(user_id, owner, name)
);

CREATE INDEX IF NOT EXISTS idx_repositories_user_id ON repositories(user_id);
CREATE INDEX IF NOT EXISTS idx_repositories_full_name ON repositories(full_name);
CREATE INDEX IF NOT EXISTS idx_repositories_created_at ON repositories(created_at);

-- 3. analyses
CREATE TABLE IF NOT EXISTS analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    progress_percentage INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_analyses_repository_id ON analyses(repository_id);
CREATE INDEX IF NOT EXISTS idx_analyses_status ON analyses(status);
CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(created_at);

-- 4. blueprints
CREATE TABLE IF NOT EXISTS blueprints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    blueprint_path TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(repository_id, analysis_id)
);

CREATE INDEX IF NOT EXISTS idx_blueprints_repository_id ON blueprints(repository_id);
CREATE INDEX IF NOT EXISTS idx_blueprints_analysis_id ON blueprints(analysis_id);

-- 5. unified_blueprints + join table
CREATE TABLE IF NOT EXISTS unified_blueprints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    blueprint_path TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS unified_blueprint_repositories (
    unified_blueprint_id UUID NOT NULL REFERENCES unified_blueprints(id) ON DELETE CASCADE,
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    PRIMARY KEY (unified_blueprint_id, repository_id)
);

CREATE INDEX IF NOT EXISTS idx_unified_blueprints_user_id ON unified_blueprints(user_id);
CREATE INDEX IF NOT EXISTS idx_unified_blueprint_repos_blueprint_id ON unified_blueprint_repositories(unified_blueprint_id);
CREATE INDEX IF NOT EXISTS idx_unified_blueprint_repos_repo_id ON unified_blueprint_repositories(repository_id);

-- 6. analysis_prompts
CREATE TABLE IF NOT EXISTS analysis_prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100) NOT NULL,
    prompt_template TEXT NOT NULL,
    variables JSONB DEFAULT '[]'::jsonb,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_analysis_prompts_user_id ON analysis_prompts(user_id);
CREATE INDEX IF NOT EXISTS idx_analysis_prompts_category ON analysis_prompts(category);
CREATE INDEX IF NOT EXISTS idx_analysis_prompts_is_default ON analysis_prompts(is_default);

-- 7. analysis_configurations
CREATE TABLE IF NOT EXISTS analysis_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    prompt_id UUID NOT NULL REFERENCES analysis_prompts(id) ON DELETE CASCADE,
    category VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(analysis_id, category)
);

CREATE INDEX IF NOT EXISTS idx_analysis_configs_analysis_id ON analysis_configurations(analysis_id);
CREATE INDEX IF NOT EXISTS idx_analysis_configs_prompt_id ON analysis_configurations(prompt_id);

-- 8. analysis_data
CREATE TABLE IF NOT EXISTS analysis_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    data_type VARCHAR(100) NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(analysis_id, data_type)
);

CREATE INDEX IF NOT EXISTS idx_analysis_data_analysis_id ON analysis_data(analysis_id);
CREATE INDEX IF NOT EXISTS idx_analysis_data_data_type ON analysis_data(data_type);
CREATE INDEX IF NOT EXISTS idx_analysis_data_data_gin ON analysis_data USING GIN(data);

-- 9. embeddings
CREATE TABLE IF NOT EXISTS embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    chunk_type VARCHAR(50) NOT NULL,
    embedding vector(384),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_embeddings_repository_id ON embeddings(repository_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_file_path ON embeddings(file_path);
CREATE INDEX IF NOT EXISTS idx_embeddings_chunk_type ON embeddings(chunk_type);
CREATE INDEX IF NOT EXISTS idx_embeddings_embedding_hnsw ON embeddings
    USING hnsw (embedding vector_cosine_ops);

-- 10. analysis_events
CREATE TABLE IF NOT EXISTS analysis_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analysis_events_analysis_id ON analysis_events(analysis_id);
CREATE INDEX IF NOT EXISTS idx_analysis_events_created_at ON analysis_events(created_at);

-- 11. architecture_rules
CREATE TABLE IF NOT EXISTS architecture_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    blueprint_id VARCHAR(100) NOT NULL,
    rule_type VARCHAR(50) NOT NULL,
    rule_id VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    rule_data JSONB NOT NULL,
    examples JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    UNIQUE(blueprint_id, rule_type, rule_id)
);

CREATE INDEX IF NOT EXISTS idx_architecture_rules_blueprint_id ON architecture_rules(blueprint_id);
CREATE INDEX IF NOT EXISTS idx_architecture_rules_rule_type ON architecture_rules(rule_type);

COMMENT ON TABLE architecture_rules IS 'Stores structured architecture rules from reference blueprints';
COMMENT ON COLUMN architecture_rules.blueprint_id IS 'Identifier for the reference blueprint (e.g., python-backend, nextjs-frontend)';
COMMENT ON COLUMN architecture_rules.rule_type IS 'Type of rule: layer, pattern, principle, anti_pattern, location';
COMMENT ON COLUMN architecture_rules.rule_id IS 'Unique identifier for the rule within its type';
COMMENT ON COLUMN architecture_rules.rule_data IS 'JSONB containing the structured rule content';
COMMENT ON COLUMN architecture_rules.examples IS 'JSONB containing code examples for this rule';

-- 12. repository_architecture
CREATE TABLE IF NOT EXISTS repository_architecture (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    analysis_id UUID REFERENCES analyses(id),
    rule_type VARCHAR(50) NOT NULL,
    rule_id VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    rule_data JSONB NOT NULL,
    confidence FLOAT DEFAULT 1.0,
    source_files JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    UNIQUE(repository_id, rule_type, rule_id)
);

CREATE INDEX IF NOT EXISTS idx_repository_architecture_repository_id ON repository_architecture(repository_id);
CREATE INDEX IF NOT EXISTS idx_repository_architecture_analysis_id ON repository_architecture(analysis_id);
CREATE INDEX IF NOT EXISTS idx_repository_architecture_rule_type ON repository_architecture(rule_type);
CREATE INDEX IF NOT EXISTS idx_repository_architecture_confidence ON repository_architecture(confidence);

COMMENT ON TABLE repository_architecture IS 'Stores learned architecture rules observed from specific repositories';
COMMENT ON COLUMN repository_architecture.rule_type IS 'Type of observed rule: purpose (what a file does), dependency (imports), convention (naming patterns), boundary (component separation)';
COMMENT ON COLUMN repository_architecture.rule_data IS 'JSONB containing the factual observation data';
COMMENT ON COLUMN repository_architecture.confidence IS 'AI confidence score for this observation (0.0 to 1.0)';
COMMENT ON COLUMN repository_architecture.source_files IS 'JSONB array of file paths that evidence this observation';

-- 13. repository_architecture_config
CREATE TABLE IF NOT EXISTS repository_architecture_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    reference_blueprint_id VARCHAR(100),
    use_learned_architecture BOOLEAN NOT NULL DEFAULT true,
    merge_strategy VARCHAR(50) NOT NULL DEFAULT 'learned_primary',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    UNIQUE(repository_id)
);

CREATE INDEX IF NOT EXISTS idx_repository_architecture_config_repository_id ON repository_architecture_config(repository_id);
CREATE INDEX IF NOT EXISTS idx_repository_architecture_config_blueprint_id ON repository_architecture_config(reference_blueprint_id);

COMMENT ON TABLE repository_architecture_config IS 'Configuration for how architecture rules are resolved for each repository';
COMMENT ON COLUMN repository_architecture_config.reference_blueprint_id IS 'ID of the reference blueprint to use as fallback (NULL for no reference)';
COMMENT ON COLUMN repository_architecture_config.use_learned_architecture IS 'Whether to use rules learned from repository analysis';
COMMENT ON COLUMN repository_architecture_config.merge_strategy IS 'How to merge reference and learned rules: learned_primary (default), reference_primary, learned_only, reference_only';

ALTER TABLE repository_architecture_config
ADD CONSTRAINT chk_merge_strategy
CHECK (merge_strategy IN ('learned_primary', 'reference_primary', 'learned_only', 'reference_only'));

-- ============================================================
-- Additional performance indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_analyses_repo_status ON analyses(repository_id, status);
CREATE INDEX IF NOT EXISTS idx_repositories_user_created ON repositories(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_prompts_user_category ON analysis_prompts(user_id, category)
    WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_analysis_prompts_default_category ON analysis_prompts(category)
    WHERE is_default = TRUE;

-- ============================================================
-- Functions
-- ============================================================

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

-- ============================================================
-- Grants
-- ============================================================

GRANT EXECUTE ON FUNCTION match_embeddings TO authenticated;
GRANT EXECUTE ON FUNCTION match_embeddings TO anon;

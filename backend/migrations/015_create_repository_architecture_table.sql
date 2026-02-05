-- Create repository_architecture table for learned architecture
-- This stores architecture rules observed from specific repositories through pure observation

CREATE TABLE IF NOT EXISTS repository_architecture (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    analysis_id UUID REFERENCES analyses(id),
    rule_type VARCHAR(50) NOT NULL,      -- 'purpose', 'dependency', 'convention', 'boundary'
    rule_id VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    rule_data JSONB NOT NULL,            -- Structured observation data
    confidence FLOAT DEFAULT 1.0,        -- AI confidence in this observation (0.0 to 1.0)
    source_files JSONB,                  -- Files that evidence this observation
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    UNIQUE(repository_id, rule_type, rule_id)
);

-- Index for efficient queries by repository
CREATE INDEX IF NOT EXISTS idx_repository_architecture_repository_id ON repository_architecture(repository_id);

-- Index for efficient queries by analysis
CREATE INDEX IF NOT EXISTS idx_repository_architecture_analysis_id ON repository_architecture(analysis_id);

-- Index for efficient queries by rule type
CREATE INDEX IF NOT EXISTS idx_repository_architecture_rule_type ON repository_architecture(rule_type);

-- Index for filtering by confidence
CREATE INDEX IF NOT EXISTS idx_repository_architecture_confidence ON repository_architecture(confidence);

-- Comments for documentation
COMMENT ON TABLE repository_architecture IS 'Stores learned architecture rules observed from specific repositories';
COMMENT ON COLUMN repository_architecture.rule_type IS 'Type of observed rule: purpose (what a file does), dependency (imports), convention (naming patterns), boundary (component separation)';
COMMENT ON COLUMN repository_architecture.rule_data IS 'JSONB containing the factual observation data';
COMMENT ON COLUMN repository_architecture.confidence IS 'AI confidence score for this observation (0.0 to 1.0)';
COMMENT ON COLUMN repository_architecture.source_files IS 'JSONB array of file paths that evidence this observation';

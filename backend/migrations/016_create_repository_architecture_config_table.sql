-- Create repository_architecture_config table
-- Links repositories to their architecture sources and configures merge strategy

CREATE TABLE IF NOT EXISTS repository_architecture_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    reference_blueprint_id VARCHAR(100), -- NULL means no reference architecture (fallback only)
    use_learned_architecture BOOLEAN NOT NULL DEFAULT true,
    merge_strategy VARCHAR(50) NOT NULL DEFAULT 'learned_primary',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    UNIQUE(repository_id)
);

-- Index for efficient lookups by repository
CREATE INDEX IF NOT EXISTS idx_repository_architecture_config_repository_id ON repository_architecture_config(repository_id);

-- Index for finding repos using specific reference blueprints
CREATE INDEX IF NOT EXISTS idx_repository_architecture_config_blueprint_id ON repository_architecture_config(reference_blueprint_id);

-- Comments for documentation
COMMENT ON TABLE repository_architecture_config IS 'Configuration for how architecture rules are resolved for each repository';
COMMENT ON COLUMN repository_architecture_config.reference_blueprint_id IS 'ID of the reference blueprint to use as fallback (NULL for no reference)';
COMMENT ON COLUMN repository_architecture_config.use_learned_architecture IS 'Whether to use rules learned from repository analysis';
COMMENT ON COLUMN repository_architecture_config.merge_strategy IS 'How to merge reference and learned rules: learned_primary (default), reference_primary, learned_only, reference_only';

-- Add check constraint for valid merge strategies
ALTER TABLE repository_architecture_config 
ADD CONSTRAINT chk_merge_strategy 
CHECK (merge_strategy IN ('learned_primary', 'reference_primary', 'learned_only', 'reference_only'));

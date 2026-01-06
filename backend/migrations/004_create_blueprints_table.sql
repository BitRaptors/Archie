-- Create blueprints table
CREATE TABLE IF NOT EXISTS blueprints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    blueprint_path TEXT NOT NULL, -- Cloud storage path
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(repository_id, analysis_id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_blueprints_repository_id ON blueprints(repository_id);
CREATE INDEX IF NOT EXISTS idx_blueprints_analysis_id ON blueprints(analysis_id);



-- Create unified_blueprints table
CREATE TABLE IF NOT EXISTS unified_blueprints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    blueprint_path TEXT NOT NULL, -- Cloud storage path
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

-- Create unified_blueprint_repositories join table
CREATE TABLE IF NOT EXISTS unified_blueprint_repositories (
    unified_blueprint_id UUID NOT NULL REFERENCES unified_blueprints(id) ON DELETE CASCADE,
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    PRIMARY KEY (unified_blueprint_id, repository_id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_unified_blueprints_user_id ON unified_blueprints(user_id);
CREATE INDEX IF NOT EXISTS idx_unified_blueprint_repos_blueprint_id ON unified_blueprint_repositories(unified_blueprint_id);
CREATE INDEX IF NOT EXISTS idx_unified_blueprint_repos_repo_id ON unified_blueprint_repositories(repository_id);



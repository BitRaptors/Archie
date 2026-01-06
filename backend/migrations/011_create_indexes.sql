-- Additional performance indexes

-- Composite index for common query patterns
CREATE INDEX IF NOT EXISTS idx_analyses_repo_status ON analyses(repository_id, status);
CREATE INDEX IF NOT EXISTS idx_repositories_user_created ON repositories(user_id, created_at DESC);

-- Index for prompt lookups
CREATE INDEX IF NOT EXISTS idx_analysis_prompts_user_category ON analysis_prompts(user_id, category) 
    WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_analysis_prompts_default_category ON analysis_prompts(category) 
    WHERE is_default = TRUE;



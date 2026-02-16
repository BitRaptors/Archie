-- Migration 002: Prompt Management
-- Adds key/type columns to analysis_prompts and creates revision history table.

-- Add key column for lookup (e.g., "discovery", "layers")
ALTER TABLE analysis_prompts ADD COLUMN IF NOT EXISTS key VARCHAR(100);
CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_prompts_key
  ON analysis_prompts(key) WHERE key IS NOT NULL;

-- Add type column for future extensibility (prompts vs other config)
ALTER TABLE analysis_prompts ADD COLUMN IF NOT EXISTS type VARCHAR(50)
  NOT NULL DEFAULT 'prompt';

-- Revision history table
CREATE TABLE IF NOT EXISTS prompt_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_id UUID NOT NULL REFERENCES analysis_prompts(id) ON DELETE CASCADE,
    revision_number INTEGER NOT NULL,
    prompt_template TEXT NOT NULL,
    variables JSONB DEFAULT '[]'::jsonb,
    name VARCHAR(255),
    description TEXT,
    change_summary TEXT,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(prompt_id, revision_number)
);
CREATE INDEX IF NOT EXISTS idx_prompt_revisions_prompt_id
  ON prompt_revisions(prompt_id);

-- Create analysis_configurations table
CREATE TABLE IF NOT EXISTS analysis_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    prompt_id UUID NOT NULL REFERENCES analysis_prompts(id) ON DELETE CASCADE,
    category VARCHAR(100) NOT NULL, -- structure, patterns, principles, etc.
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(analysis_id, category)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_analysis_configs_analysis_id ON analysis_configurations(analysis_id);
CREATE INDEX IF NOT EXISTS idx_analysis_configs_prompt_id ON analysis_configurations(prompt_id);



-- Create analysis_prompts table
CREATE TABLE IF NOT EXISTS analysis_prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE, -- NULL for default prompts
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100) NOT NULL, -- structure, patterns, principles, blueprint_synthesis, etc.
    prompt_template TEXT NOT NULL,
    variables JSONB DEFAULT '[]'::jsonb, -- Array of variable names
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_analysis_prompts_user_id ON analysis_prompts(user_id);
CREATE INDEX IF NOT EXISTS idx_analysis_prompts_category ON analysis_prompts(category);
CREATE INDEX IF NOT EXISTS idx_analysis_prompts_is_default ON analysis_prompts(is_default);



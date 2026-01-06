-- Create analysis_data table
CREATE TABLE IF NOT EXISTS analysis_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    data_type VARCHAR(100) NOT NULL, -- structure, patterns, principles, etc.
    data JSONB NOT NULL, -- Structured analysis results
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(analysis_id, data_type)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_analysis_data_analysis_id ON analysis_data(analysis_id);
CREATE INDEX IF NOT EXISTS idx_analysis_data_data_type ON analysis_data(data_type);
-- GIN index for JSONB queries
CREATE INDEX IF NOT EXISTS idx_analysis_data_data_gin ON analysis_data USING GIN(data);



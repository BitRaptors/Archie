-- Create analysis_events table
CREATE TABLE IF NOT EXISTS analysis_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL, -- 'INFO', 'WARNING', 'ERROR', 'PHASE_START', 'PHASE_END'
    message TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_analysis_events_analysis_id ON analysis_events(analysis_id);
CREATE INDEX IF NOT EXISTS idx_analysis_events_created_at ON analysis_events(created_at);



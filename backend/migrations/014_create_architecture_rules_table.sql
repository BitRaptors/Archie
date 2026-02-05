-- Create architecture_rules table for reference architecture
-- This stores structured rules extracted from reference blueprints (e.g., DOCS/PYTHON_ARCHITECTURE_BLUEPRINT.md)

CREATE TABLE IF NOT EXISTS architecture_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    blueprint_id VARCHAR(100) NOT NULL,  -- e.g., 'python-backend', 'nextjs-frontend'
    rule_type VARCHAR(50) NOT NULL,      -- 'layer', 'pattern', 'principle', 'anti_pattern', 'location'
    rule_id VARCHAR(100) NOT NULL,       -- e.g., 'presentation-layer', 'service-registry'
    name VARCHAR(255) NOT NULL,
    description TEXT,
    rule_data JSONB NOT NULL,            -- Structured rule content
    examples JSONB,                       -- Code examples
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    UNIQUE(blueprint_id, rule_type, rule_id)
);

-- Index for efficient queries by blueprint
CREATE INDEX IF NOT EXISTS idx_architecture_rules_blueprint_id ON architecture_rules(blueprint_id);

-- Index for efficient queries by rule type
CREATE INDEX IF NOT EXISTS idx_architecture_rules_rule_type ON architecture_rules(rule_type);

-- Comments for documentation
COMMENT ON TABLE architecture_rules IS 'Stores structured architecture rules from reference blueprints';
COMMENT ON COLUMN architecture_rules.blueprint_id IS 'Identifier for the reference blueprint (e.g., python-backend, nextjs-frontend)';
COMMENT ON COLUMN architecture_rules.rule_type IS 'Type of rule: layer, pattern, principle, anti_pattern, location';
COMMENT ON COLUMN architecture_rules.rule_id IS 'Unique identifier for the rule within its type';
COMMENT ON COLUMN architecture_rules.rule_data IS 'JSONB containing the structured rule content';
COMMENT ON COLUMN architecture_rules.examples IS 'JSONB containing code examples for this rule';

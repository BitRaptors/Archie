-- Drop unused tables (0 rows, no code references)
-- Run via Supabase SQL Editor: https://supabase.com/dashboard/project/jxkfqiotreydrlgglsrt/sql

-- unified_blueprint_repositories references unified_blueprints, so drop it first
DROP TABLE IF EXISTS unified_blueprint_repositories CASCADE;
DROP TABLE IF EXISTS unified_blueprints CASCADE;
DROP TABLE IF EXISTS blueprints CASCADE;
DROP TABLE IF EXISTS analysis_configurations CASCADE;

-- Reload PostgREST schema cache so the tables disappear from the REST API
NOTIFY pgrst, 'reload schema';

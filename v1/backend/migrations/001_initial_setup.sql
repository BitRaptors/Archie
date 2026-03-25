-- Architecture Blueprints — Initial Database Setup
-- Consolidated migration: creates all tables, indexes, functions, seeds, and grants.
-- Run against a Supabase PostgreSQL instance with pgvector support.

-- ============================================================
-- Extensions
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- Tables (in dependency order)
-- ============================================================

-- 1. users
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    github_token_encrypted TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

-- 2. user_profiles
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    active_repository_id UUID,
    preferences JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    UNIQUE(user_id)
);

CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id);

-- 3. repositories
CREATE TABLE IF NOT EXISTS repositories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    owner VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    full_name VARCHAR(512) NOT NULL,
    url TEXT NOT NULL,
    description TEXT,
    language VARCHAR(100),
    default_branch VARCHAR(255) NOT NULL DEFAULT 'main',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    UNIQUE(user_id, owner, name)
);

CREATE INDEX IF NOT EXISTS idx_repositories_user_id ON repositories(user_id);
CREATE INDEX IF NOT EXISTS idx_repositories_full_name ON repositories(full_name);
CREATE INDEX IF NOT EXISTS idx_repositories_created_at ON repositories(created_at);

-- 4. analyses
CREATE TABLE IF NOT EXISTS analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    progress_percentage INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    commit_sha VARCHAR(40)
);

ALTER TABLE analyses ADD COLUMN IF NOT EXISTS commit_sha VARCHAR(40);

CREATE INDEX IF NOT EXISTS idx_analyses_repository_id ON analyses(repository_id);
CREATE INDEX IF NOT EXISTS idx_analyses_status ON analyses(status);
CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(created_at);

-- 5. analysis_prompts
CREATE TABLE IF NOT EXISTS analysis_prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100) NOT NULL,
    prompt_template TEXT NOT NULL,
    variables JSONB DEFAULT '[]'::jsonb,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    key VARCHAR(100),
    type VARCHAR(50) NOT NULL DEFAULT 'prompt'
);

CREATE INDEX IF NOT EXISTS idx_analysis_prompts_user_id ON analysis_prompts(user_id);
CREATE INDEX IF NOT EXISTS idx_analysis_prompts_category ON analysis_prompts(category);
CREATE INDEX IF NOT EXISTS idx_analysis_prompts_is_default ON analysis_prompts(is_default);
CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_prompts_key
  ON analysis_prompts(key) WHERE key IS NOT NULL;

-- 6. prompt_revisions
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

-- 7. analysis_data
CREATE TABLE IF NOT EXISTS analysis_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    data_type VARCHAR(100) NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(analysis_id, data_type)
);

CREATE INDEX IF NOT EXISTS idx_analysis_data_analysis_id ON analysis_data(analysis_id);
CREATE INDEX IF NOT EXISTS idx_analysis_data_data_type ON analysis_data(data_type);
CREATE INDEX IF NOT EXISTS idx_analysis_data_data_gin ON analysis_data USING GIN(data);

-- 8. embeddings
CREATE TABLE IF NOT EXISTS embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    chunk_type VARCHAR(50) NOT NULL,
    embedding vector(384),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_embeddings_repository_id ON embeddings(repository_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_file_path ON embeddings(file_path);
CREATE INDEX IF NOT EXISTS idx_embeddings_chunk_type ON embeddings(chunk_type);
CREATE INDEX IF NOT EXISTS idx_embeddings_embedding_hnsw ON embeddings
    USING hnsw (embedding vector_cosine_ops);

-- 9. analysis_events
CREATE TABLE IF NOT EXISTS analysis_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    analysis_id UUID NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analysis_events_analysis_id ON analysis_events(analysis_id);
CREATE INDEX IF NOT EXISTS idx_analysis_events_created_at ON analysis_events(created_at);

-- 10. discovery_ignored_dirs
CREATE TABLE IF NOT EXISTS discovery_ignored_dirs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    directory_name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 11. library_capabilities
CREATE TABLE IF NOT EXISTS library_capabilities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    library_name VARCHAR(255) NOT NULL UNIQUE,
    ecosystem VARCHAR(255) NOT NULL DEFAULT '',
    capabilities TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_library_capabilities_library_name ON library_capabilities(library_name);

-- ============================================================
-- Additional performance indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_analyses_repo_status ON analyses(repository_id, status);
CREATE INDEX IF NOT EXISTS idx_repositories_user_created ON repositories(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_prompts_user_category ON analysis_prompts(user_id, category)
    WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_analysis_prompts_default_category ON analysis_prompts(category)
    WHERE is_default = TRUE;

-- ============================================================
-- Functions
-- ============================================================

CREATE OR REPLACE FUNCTION match_embeddings(
    query_embedding vector(384),
    match_count INT DEFAULT 10,
    filter_repository_id UUID DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    repository_id UUID,
    file_path TEXT,
    chunk_type VARCHAR(50),
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.id,
        e.repository_id,
        e.file_path,
        e.chunk_type,
        e.metadata,
        1 - (e.embedding <=> query_embedding) AS similarity
    FROM embeddings e
    WHERE (filter_repository_id IS NULL OR e.repository_id = filter_repository_id)
    ORDER BY e.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ============================================================
-- Seed: Discovery ignored directories
-- ============================================================

INSERT INTO discovery_ignored_dirs (directory_name) VALUES
    ('node_modules'), ('Pods'), ('Carthage'), ('.build'), ('DerivedData'),
    ('vendor'), ('.bundle'), ('bower_components'), ('flutter_build'), ('.dart_tool'),
    ('.gradle'), ('build'), ('dist'), ('target'), ('.next'), ('.nuxt'), ('.output'),
    ('venv'), ('.venv'), ('env'), ('__pycache__'), ('.git'), ('.idea'),
    ('coverage'), ('.nyc_output')
ON CONFLICT (directory_name) DO NOTHING;

-- ============================================================
-- Seed: Library capabilities
-- ============================================================

INSERT INTO library_capabilities (library_name, ecosystem, capabilities) VALUES
    ('firebase',    'Google Firebase',  ARRAY['persistence','authentication','analytics','push_notifications','cloud_functions','hosting','storage']),
    ('supabase',    'Supabase',         ARRAY['persistence','authentication','storage','realtime','edge_functions']),
    ('aws-amplify', 'AWS',              ARRAY['persistence','authentication','storage','api','analytics']),
    ('realm',       'MongoDB Realm',    ARRAY['persistence','sync','offline_first']),
    ('coredata',    'Apple',            ARRAY['persistence','offline_storage']),
    ('room',        'Android Jetpack',  ARRAY['persistence','offline_storage']),
    ('alamofire',   'iOS',              ARRAY['networking']),
    ('retrofit',    'Android',          ARRAY['networking']),
    ('axios',       'JavaScript',       ARRAY['networking']),
    ('redux',       'React',            ARRAY['state_management']),
    ('zustand',     'React',            ARRAY['state_management']),
    ('mobx',        'JavaScript',       ARRAY['state_management']),
    ('stripe',      'Stripe',           ARRAY['payments']),
    ('auth0',       'Auth0',            ARRAY['authentication']),
    ('clerk',       'Clerk',            ARRAY['authentication']),
    ('prisma',      'Node.js',          ARRAY['persistence','orm']),
    ('sequelize',   'Node.js',          ARRAY['persistence','orm']),
    ('sqlalchemy',  'Python',           ARRAY['persistence','orm']),
    ('mongoose',    'Node.js/MongoDB',  ARRAY['persistence','odm']),
    ('apollo',      'JavaScript',       ARRAY['networking','state_management','graphql']),
    ('sentry',      'Sentry',           ARRAY['error_tracking','monitoring']),
    ('mixpanel',    'Mixpanel',         ARRAY['analytics']),
    ('onesignal',   'OneSignal',        ARRAY['push_notifications']),
    ('cloudinary',  'Cloudinary',       ARRAY['storage','image_processing']),
    ('socket.io',   'JavaScript',       ARRAY['realtime','websocket']),
    ('combine',     'Apple',            ARRAY['reactive_programming']),
    ('rxswift',     'iOS',              ARRAY['reactive_programming']),
    ('rxjava',      'Android',          ARRAY['reactive_programming']),
    ('dagger',      'Android',          ARRAY['dependency_injection']),
    ('hilt',        'Android',          ARRAY['dependency_injection']),
    ('swinject',    'iOS',              ARRAY['dependency_injection']),
    ('riverpod',    'Flutter',          ARRAY['state_management','dependency_injection']),
    ('bloc',        'Flutter',          ARRAY['state_management']),
    ('provider',    'Flutter',          ARRAY['state_management']),
    -- Mobile: Android
    ('compose',             'Android Jetpack',      ARRAY['ui_framework']),
    ('navigation-compose',  'Android Jetpack',      ARRAY['navigation']),
    ('glide',               'Android',              ARRAY['image_loading']),
    ('gson',                'Android',              ARRAY['serialization']),
    ('timber',              'Android',              ARRAY['logging']),
    ('leakcanary',          'Android',              ARRAY['monitoring']),
    ('coroutines',          'Android',              ARRAY['concurrency']),
    ('livedata',            'Android Jetpack',      ARRAY['state_management']),
    ('datastore',           'Android Jetpack',      ARRAY['persistence']),
    -- Mobile: iOS
    ('swiftui',             'Apple',                ARRAY['ui_framework']),
    ('uikit',               'Apple',                ARRAY['ui_framework']),
    ('kingfisher',          'iOS',                  ARRAY['image_loading']),
    ('snapkit',             'iOS',                  ARRAY['ui_framework']),
    ('sdwebimage',          'iOS',                  ARRAY['image_loading']),
    -- Mobile: Cross-platform
    ('lottie',              'Cross-platform',       ARRAY['ui_framework']),
    ('ktor',                'Kotlin Multiplatform', ARRAY['networking']),
    ('koin',                'Kotlin Multiplatform', ARRAY['dependency_injection']),
    ('coil',                'Android',              ARRAY['image_loading']),
    ('okhttp',              'Cross-platform',       ARRAY['networking']),
    ('moshi',               'Cross-platform',       ARRAY['serialization']),
    ('moya',                'iOS',                  ARRAY['networking'])
ON CONFLICT (library_name) DO NOTHING;

-- ============================================================
-- Grants (safe for both Supabase and local PostgreSQL)
-- ============================================================

DO $$
BEGIN
  EXECUTE 'GRANT EXECUTE ON FUNCTION match_embeddings TO authenticated';
  EXECUTE 'GRANT EXECUTE ON FUNCTION match_embeddings TO anon';
EXCEPTION WHEN undefined_object THEN
  NULL;  -- Roles don't exist on local PostgreSQL, skip
END $$;

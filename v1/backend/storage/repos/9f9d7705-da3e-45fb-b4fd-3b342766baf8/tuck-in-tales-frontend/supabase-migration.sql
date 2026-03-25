-- ============================================================
-- TuckInTales - Supabase Migration Script
-- Full schema recreation for new Supabase project
-- Generated: 2026-02-18
-- ============================================================

-- NOTE: The backup SQL files in _restore/ (prompts_rows.sql,
-- prompt_versions_rows.sql, projects_rows.sql) are from a DIFFERENT
-- project and are NOT related to TuckInTales. This migration creates
-- the TuckInTales schema from scratch based on the backend source code.

-- ============================================================
-- 0. EXTENSIONS
-- ============================================================

-- Required for vector similarity search (memories RAG)
CREATE EXTENSION IF NOT EXISTS vector;

-- Required for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- 1. TABLES
-- ============================================================

-- ---- families ----
CREATE TABLE public.families (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT,
    join_code VARCHAR(20) UNIQUE,
    default_language VARCHAR(10),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---- users ----
-- users.id is the Firebase UID (string), NOT a UUID
CREATE TABLE public.users (
    id VARCHAR(255) PRIMARY KEY,  -- Firebase UID
    email VARCHAR(255),
    display_name VARCHAR(255),
    avatar_url TEXT,
    family_id UUID REFERENCES public.families(id) ON DELETE SET NULL
);

-- ---- characters ----
CREATE TABLE public.characters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    family_id UUID NOT NULL REFERENCES public.families(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    bio TEXT,
    photo_paths JSONB DEFAULT '[]'::jsonb,       -- array of storage paths in "photos" bucket
    avatar_url TEXT,                               -- storage path in "avatars" bucket
    birthdate DATE,
    visual_description TEXT,                       -- AI-generated description from photos
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ
);

-- ---- family_main_characters (junction table) ----
CREATE TABLE public.family_main_characters (
    family_id UUID NOT NULL REFERENCES public.families(id) ON DELETE CASCADE,
    character_id UUID NOT NULL REFERENCES public.characters(id) ON DELETE CASCADE,
    PRIMARY KEY (family_id, character_id)
);

-- ---- stories ----
CREATE TABLE public.stories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    family_id UUID NOT NULL REFERENCES public.families(id) ON DELETE CASCADE,
    title TEXT,
    input_prompt TEXT,
    pages JSONB NOT NULL DEFAULT '[]'::jsonb,     -- array of StoryPageProgress objects
    language VARCHAR(10) NOT NULL DEFAULT 'en',
    target_age INTEGER,
    character_ids JSONB DEFAULT '[]'::jsonb,       -- array of UUID strings
    status VARCHAR(50) NOT NULL DEFAULT 'INITIALIZING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Story pages JSON structure reference:
-- [
--   {
--     "page": 1,
--     "description": "...",        -- from outline
--     "text": "...",               -- AI-generated story text
--     "image_prompt": "...",       -- AI-generated image prompt
--     "image_url": "...",          -- public URL in "story-images" bucket
--     "characters_on_page": ["..."] -- character names on this page
--   }
-- ]

-- ---- memories ----
CREATE TABLE public.memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    family_id UUID NOT NULL REFERENCES public.families(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    date DATE NOT NULL,
    embedding vector(1536),                        -- OpenAI text-embedding for RAG search
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 2. INDEXES
-- ============================================================

CREATE INDEX idx_users_family_id ON public.users(family_id);
CREATE INDEX idx_characters_family_id ON public.characters(family_id);
CREATE INDEX idx_stories_family_id ON public.stories(family_id);
CREATE INDEX idx_stories_created_at ON public.stories(created_at DESC);
CREATE INDEX idx_memories_family_id ON public.memories(family_id);
CREATE INDEX idx_memories_date ON public.memories(date DESC);
CREATE INDEX idx_families_join_code ON public.families(join_code);

-- ============================================================
-- 3. RPC FUNCTIONS
-- ============================================================

-- Vector similarity search for memories (used by RAG)
CREATE OR REPLACE FUNCTION match_memories(
    query_embedding vector(1536),
    match_threshold float,
    match_count int,
    filter_family_id text
)
RETURNS TABLE (
    id UUID,
    family_id UUID,
    text TEXT,
    date DATE,
    created_at TIMESTAMPTZ,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id,
        m.family_id,
        m.text,
        m.date,
        m.created_at,
        1 - (m.embedding <=> query_embedding) AS similarity
    FROM public.memories m
    WHERE m.family_id = filter_family_id::uuid
      AND 1 - (m.embedding <=> query_embedding) > match_threshold
    ORDER BY m.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ============================================================
-- 4. ROW LEVEL SECURITY (RLS)
-- ============================================================

-- Enable RLS on all tables
ALTER TABLE public.families ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.characters ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.family_main_characters ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memories ENABLE ROW LEVEL SECURITY;

-- The backend uses the SERVICE_KEY which bypasses RLS.
-- These policies are for direct client access (e.g., frontend storage).
-- For now, allow service_role full access (backend pattern).

-- Service role bypass policies (service_role already bypasses RLS by default)
-- If you want anon/authenticated access for specific operations, add policies here.

-- Example: Allow authenticated users to read their family's data via anon key
-- (Not needed currently since all queries go through the backend with service key)

-- ============================================================
-- 5. STORAGE BUCKETS
-- ============================================================

-- Run these via Supabase Dashboard or SQL Editor:
-- (Storage bucket creation via SQL requires the storage schema)

-- INSERT INTO storage.buckets (id, name, public) VALUES ('photos', 'photos', false);
-- INSERT INTO storage.buckets (id, name, public) VALUES ('avatars', 'avatars', true);
-- INSERT INTO storage.buckets (id, name, public) VALUES ('story-images', 'story-images', true);

-- Storage policies for the "avatars" bucket (public read):
-- CREATE POLICY "Public read access for avatars"
--   ON storage.objects FOR SELECT
--   USING (bucket_id = 'avatars');

-- Storage policies for the "story-images" bucket (public read):
-- CREATE POLICY "Public read access for story-images"
--   ON storage.objects FOR SELECT
--   USING (bucket_id = 'story-images');

-- Storage policies for service key uploads (service_role bypasses by default):
-- No additional policies needed for backend uploads via service key.

-- ============================================================
-- 6. NOTES
-- ============================================================

-- Auth: Firebase (NOT Supabase Auth). Users table stores Firebase UIDs as VARCHAR primary keys.
-- All backend queries use the Supabase SERVICE_KEY (bypasses RLS).
-- Frontend only accesses Supabase Storage directly (public avatar/story-image URLs).
-- The "photos" bucket is PRIVATE (signed URLs used for AI vision API calls).
-- The "avatars" and "story-images" buckets are PUBLIC.

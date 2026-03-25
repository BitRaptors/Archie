# TuckInTales - Supabase Restore Guide

The old Supabase project (`tgiuehwyimavzxxyhutb`) was paused 90+ days and cannot be restored. This guide walks through setting up a new Supabase project from scratch.

## What was lost

- **Database tables**: users, families, characters, stories, memories, family_main_characters (all user data)
- **Storage buckets**: `photos` (private character photos), `avatars` (public generated avatars), `story-images` (public story illustrations)
- **RPC functions**: `match_memories` (vector similarity search)

> **Note**: The backup SQL files in `_restore/` (prompts_rows.sql, prompt_versions_rows.sql, projects_rows.sql) are from a **different project** and are NOT related to TuckInTales. There is no TuckInTales user data to restore.

## Step 1: Create a new Supabase project

1. Go to [supabase.com/dashboard](https://supabase.com/dashboard)
2. Create a new project (any region, note the project ref)
3. Wait for the project to finish provisioning
4. Note down:
pw: VrGTrL3bCXYYLjy9
   - **Project URL**:https://supabase.com/dashboard/project/nxuprpxggpymnhuebbqq  `https://<project-ref>.supabase.co`
   - **Anon Key**: ""
   - **Service Role Key**: ""

## Step 2: Run the migration SQL

1. Open the Supabase **SQL Editor** (left sidebar)
2. Paste the contents of `./supabase-migration.sql`
3. Click **Run** — this creates all tables, indexes, the `match_memories` RPC function, and enables RLS

## Step 3: Create storage buckets

In the Supabase **Storage** section (left sidebar):

1. Create bucket: **photos**
   - Public: **OFF** (private — backend uses signed URLs)
2. Create bucket: **avatars**
   - Public: **ON**
3. Create bucket: **story-images**
   - Public: **ON**

### Storage policies

For the **avatars** bucket:
- Add policy: "Allow public read" → SELECT for all users (`true` condition)
- Add policy: "Allow service role uploads" → INSERT/UPDATE/DELETE for `service_role`

For the **story-images** bucket:
- Same as avatars (public read, service role write)

For the **photos** bucket:
- Add policy: "Allow service role full access" → ALL for `service_role`
- No public read (backend generates signed URLs for AI API calls)

Alternatively, run this in the SQL Editor:

```sql
-- Create buckets
INSERT INTO storage.buckets (id, name, public) VALUES ('photos', 'photos', false);
INSERT INTO storage.buckets (id, name, public) VALUES ('avatars', 'avatars', true);
INSERT INTO storage.buckets (id, name, public) VALUES ('story-images', 'story-images', true);

-- Public read for avatars
CREATE POLICY "Public read avatars" ON storage.objects FOR SELECT USING (bucket_id = 'avatars');

-- Public read for story-images
CREATE POLICY "Public read story-images" ON storage.objects FOR SELECT USING (bucket_id = 'story-images');
```

## Step 4: Update environment variables

### Backend (`tuck-in-tales-backend/.env`)

```env
SUPABASE_URL=https://<NEW-PROJECT-REF>.supabase.co
SUPABASE_ANON_KEY=<new-anon-key>
SUPABASE_SERVICE_KEY=<new-service-role-key>
```

### Frontend (`.env`)

```env
VITE_SUPABASE_URL=https://<NEW-PROJECT-REF>.supabase.co
VITE_SUPABASE_ANON_KEY=<new-anon-key>
```

### Also update if deployed

- Any CI/CD secrets (GitHub Actions, Vercel, Railway, etc.)
- Any production `.env` files on hosting

## Step 5: Update the frontend Supabase config

The file `src/utils/supabaseUtils.ts` has a hardcoded project ref for avatar URL construction. Update the `SUPABASE_PROJECT_REF` constant (or the URL pattern) to match the new project ref:

```typescript
// Old: tgiuehwyimavzxxyhutb
// New: <your-new-project-ref>
```

## Step 6: Verify

1. **Start the backend** and confirm it connects to Supabase without errors
2. **Start the frontend** and:
   - Create a new account (Firebase auth)
   - Create a family
   - Add a character
   - Upload a photo and generate an avatar
   - Generate a story
   - Create a memory
3. **Check storage** — confirm files appear in the correct buckets
4. **Check the database** — confirm rows appear in all tables

## Architecture reference

```
Frontend (React/Vite)
  ├── Firebase Auth (login/signup)
  ├── Backend API (all data operations)
  └── Supabase Storage (public avatar/story URLs only)

Backend (FastAPI/Python)
  ├── Firebase Admin SDK (token verification)
  ├── Supabase DB (all table operations via service key)
  ├── Supabase Storage (upload/download/delete)
  ├── OpenAI (embeddings, story generation, image generation)
  └── LangGraph (story & avatar generation workflows)
```

### Database tables

| Table | Purpose |
|-------|---------|
| `users` | Firebase UID → family mapping, display info |
| `families` | Family groups with join codes |
| `characters` | Story characters with photos/avatars |
| `family_main_characters` | Junction: which characters are "main" (for age targeting) |
| `stories` | Generated bedtime stories with pages |
| `memories` | Family memories with vector embeddings for RAG |

### Storage buckets

| Bucket | Public | Purpose |
|--------|--------|---------|
| `photos` | No | Original character photos (AI reference) |
| `avatars` | Yes | AI-generated character avatars |
| `story-images` | Yes | AI-generated story page illustrations |

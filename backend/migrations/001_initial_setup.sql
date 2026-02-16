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
    updated_at TIMESTAMPTZ
);

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
-- Seed default prompts
-- ============================================================

INSERT INTO analysis_prompts (name, category, prompt_template, variables, is_default, key, type)
VALUES
(
    'Discovery Analysis',
    'discovery',
    E'You are analyzing a codebase to produce a unified architecture blueprint covering ALL platforms (backend, frontend, mobile, etc.).\n\n## Discovery Analysis\n\nRepository: {repository_name}\n\n### Project Structure:\n{file_tree}\n\n### Dependencies:\n{dependencies}\n\n### Configuration Files:\n{config_files}\n\nAnalyze and document:\n\n1. **Project Type**: Identify if this is a monorepo, single app, microservice, serverless, full-stack, etc.\n2. **Platforms Detected**: List ALL platforms found (backend, web-frontend, mobile-ios, mobile-android, desktop, CLI, etc.)\n3. **Entry Points**: List main application entry files for EACH platform (main.py, index.ts, App.tsx, etc.)\n4. **Module Organization**: Describe how modules/packages are organized\n5. **Environment Configuration**: Document environment variable patterns and config management\n6. **Key Observations**: Any notable architectural decisions visible at this level\n\nProvide your analysis in structured JSON format:\n```json\n{\n  "project_type": "...",\n  "platforms": ["backend", "web-frontend"],\n  "entry_points": [{"file": "...", "purpose": "...", "platform": "..."}],\n  "module_organization": "...",\n  "config_approach": "...",\n  "key_observations": ["..."]\n}\n```',
    '["repository_name", "file_tree", "dependencies", "config_files"]'::jsonb,
    TRUE,
    'discovery',
    'prompt'
),
(
    'Layer Identification',
    'layers',
    E'## Layer Identification\n\nRepository: {repository_name}\n\n### Discovery Summary:\n{discovery_summary}\n\n### File Structure:\n{file_tree}\n\n### Sample Code Files:\n{code_samples}\n\n**CRITICAL**: Analyze the ACTUAL codebase structure. Do NOT assume layers exist. Only document layers that you can clearly identify from:\n1. Import patterns between directories\n2. Directory structure and naming\n3. Actual code organization\n\nAnalyze ALL platforms (backend AND frontend) found in the codebase.\n\n**If no clear layers exist**, set "has_layers" to false and document the actual structure (flat, modular, feature-based, etc.).\n\nFor each layer found, document:\n\n1. **Location**: Directory path(s) - must be actual paths from the codebase\n2. **Platform**: Which platform this layer belongs to (backend, frontend, shared)\n3. **Responsibility**: Single sentence describing what this layer does based on actual code\n4. **Contains**: Types of components found (controllers, services, entities, hooks, components, etc.)\n5. **Depends On**: Which other layers it imports from (based on actual import statements)\n6. **Exposes To**: What other layers consume from it (based on actual usage)\n7. **Key Files**: Most important files with brief descriptions (actual file paths)\n\nProvide your analysis in structured JSON format:\n```json\n{\n  "has_layers": true,\n  "structure_type": "layered | flat | modular | feature-based | monolithic | other",\n  "layers": [\n    {\n      "name": "...",\n      "platform": "backend | frontend | shared",\n      "location": "...",\n      "responsibility": "...",\n      "contains": ["..."],\n      "depends_on": ["..."],\n      "exposes_to": ["..."],\n      "key_files": [{"file": "...", "description": "..."}]\n    }\n  ],\n  "dependency_rules": {\n    "allowed": ["..."],\n    "forbidden": ["..."]\n  },\n  "actual_structure": "..."\n}\n```',
    '["repository_name", "discovery_summary", "file_tree", "code_samples"]'::jsonb,
    TRUE,
    'layers',
    'prompt'
),
(
    'Pattern Extraction',
    'patterns',
    E'## Pattern Extraction\n\nRepository: {repository_name}\n\n### Discovery Summary:\n{discovery_summary}\n\n### Layer Analysis:\n{layer_analysis}\n\n### Code Samples:\n{code_samples}\n\nIdentify and document architectural patterns with concrete examples from the codebase. Cover BOTH backend and frontend patterns.\n\n### Backend Structural Patterns to identify:\n- **Dependency Injection**: How are dependencies wired? Container? Manual? Framework?\n- **Repository**: How is data access abstracted? Interface + implementation?\n- **Factory**: How are complex objects created?\n- **Registry/Plugin**: How are multiple implementations managed?\n\n### Frontend Structural Patterns to identify:\n- **Component Composition**: How are UI components composed? HOC? Render props? Hooks?\n- **Data Fetching**: How is server state managed? React Query? SWR? Apollo?\n- **State Management**: Global state approach? Context? Redux? Zustand?\n- **Routing**: File-based? Config-based? How are routes organized?\n\n### Behavioral Patterns to identify:\n- **Service Orchestration**: How are multi-step workflows coordinated?\n- **Streaming**: How are long-running responses handled? SSE? WebSockets?\n- **Event-Driven**: Are there publish/subscribe patterns?\n- **Optimistic Updates**: How are UI updates handled before server confirmation?\n\n### Cross-Cutting Patterns to identify:\n- **Error Handling**: Custom exceptions? Error boundaries? Global handler? Error mapping?\n- **Validation**: Where? How? What library? Client-side vs server-side?\n- **Authentication**: JWT? Session? OAuth? Where validated? How propagated to frontend?\n- **Logging**: Structured? What logger? What''s logged?\n- **Caching**: What''s cached? TTL strategy? Browser cache? Server cache?\n\nProvide your analysis in structured JSON format:\n```json\n{\n  "structural_patterns": [{"pattern": "...", "platform": "backend|frontend|shared", "implementation": "...", "examples": ["..."]}],\n  "behavioral_patterns": [{"pattern": "...", "platform": "backend|frontend|shared", "implementation": "...", "examples": ["..."]}],\n  "cross_cutting_patterns": [{"concern": "...", "approach": "...", "location": "..."}]\n}\n```',
    '["repository_name", "discovery_summary", "layer_analysis", "code_samples"]'::jsonb,
    TRUE,
    'patterns',
    'prompt'
),
(
    'Communication Analysis',
    'communication',
    E'## Communication Analysis\n\nRepository: {repository_name}\n\n### Previous Analysis:\n{previous_analyses}\n\n### Code Samples:\n{code_samples}\n\nDocument how components communicate across ALL platforms (backend AND frontend):\n\n### Internal Communication:\n1. **Backend**: Direct method calls between layers, in-process events, message buses\n2. **Frontend**: Props, Context, event emitters, pub/sub, state management\n3. **Cross-Platform**: API calls from frontend to backend, shared types/contracts\n\n### External Communication:\n1. **HTTP/REST**: External API calls (both backend-to-external and frontend-to-backend)\n2. **Message Queue**: Async job processing (Redis, RabbitMQ, etc.)\n3. **Streaming**: SSE, WebSockets, gRPC streams\n4. **Database**: Query patterns, transactions\n5. **Real-time**: Push notifications, live updates\n\n### Third-Party Integrations:\nList all external services:\n- AI/LLM providers\n- Payment processors\n- Auth providers (including frontend SDKs)\n- Storage services\n- Analytics/monitoring\n- CDN/asset hosting\n\n### Frontend-Backend Contract:\n- How do frontend and backend communicate? (REST, GraphQL, tRPC, etc.)\n- Are types shared between frontend and backend?\n- How are API errors propagated to the UI?\n\nProvide your analysis in structured JSON format:\n```json\n{\n  "internal_communication": [{"type": "...", "platform": "backend|frontend|cross-platform", "mechanism": "...", "examples": ["..."]}],\n  "external_communication": [{"type": "...", "protocol": "...", "examples": ["..."]}],\n  "third_party_integrations": [{"service": "...", "purpose": "...", "integration_point": "..."}],\n  "frontend_backend_contract": {"protocol": "...", "shared_types": true, "error_propagation": "..."},\n  "pattern_guidelines": [{"scenario": "...", "pattern": "...", "rationale": "..."}]\n}\n```',
    '["repository_name", "previous_analyses", "code_samples"]'::jsonb,
    TRUE,
    'communication',
    'prompt'
),
(
    'Technology Inventory',
    'technology',
    E'## Technology Inventory\n\nRepository: {repository_name}\n\n### All Previous Analysis:\n{all_analyses}\n\n### Dependencies:\n{dependencies}\n\nCreate a complete technology inventory organized by category. Include technologies for ALL platforms (backend AND frontend).\n\n1. **Runtime**: Language, version, runtime environment (for each platform)\n2. **Backend Framework**: Web framework, version, key features used\n3. **Frontend Framework**: UI framework/library, version, rendering strategy\n4. **Database**: Type, ORM/query builder, version\n5. **Cache**: Redis, Memcached, in-memory, browser cache, etc.\n6. **Queue**: Celery, RabbitMQ, ARQ, Redis Queue, etc.\n7. **AI/ML**: Providers (OpenAI, Anthropic, etc.), SDKs, models\n8. **Auth**: Library, provider, JWT/session handling (both backend and frontend)\n9. **State Management**: Frontend state (Redux, Zustand, React Query, etc.)\n10. **Styling**: CSS framework, component library (Tailwind, MUI, etc.)\n11. **Validation**: Library, approach (both client and server)\n12. **Testing**: Framework, tools, coverage approach (for each platform)\n13. **Linting/Formatting**: Tools, configuration\n14. **Deployment**: Container, CI/CD, cloud platform\n15. **Monitoring**: Logging, metrics, error tracking\n\nFor each technology, include:\n- Component name\n- Technology/library name\n- Version\n- Purpose/why chosen\n- Platform (backend, frontend, shared)\n\nProvide your analysis in structured JSON format:\n```json\n{\n  "runtime": [{"language": "...", "version": "...", "environment": "...", "platform": "..."}],\n  "backend_framework": {"name": "...", "version": "...", "features": ["..."]},\n  "frontend_framework": {"name": "...", "version": "...", "rendering_strategy": "SSR|SSG|CSR|hybrid"},\n  "database": [{"type": "...", "orm": "...", "version": "..."}],\n  "cache": [{"technology": "...", "purpose": "..."}],\n  "queue": [{"technology": "...", "purpose": "..."}],\n  "ai_ml": [{"provider": "...", "sdk": "...", "models": ["..."]}],\n  "auth": {"library": "...", "approach": "..."},\n  "state_management": [{"library": "...", "purpose": "..."}],\n  "styling": {"framework": "...", "approach": "..."},\n  "validation": {"library": "...", "approach": "..."},\n  "testing": [{"framework": "...", "type": "...", "platform": "..."}],\n  "linting": [{"tool": "...", "purpose": "..."}],\n  "deployment": {"container": "...", "cicd": "...", "platform": "..."},\n  "monitoring": [{"tool": "...", "purpose": "..."}]\n}\n```',
    '["repository_name", "all_analyses", "dependencies"]'::jsonb,
    TRUE,
    'technology',
    'prompt'
),
(
    'Frontend Architecture Analysis',
    'frontend_analysis',
    E'## Frontend Architecture Analysis\n\nRepository: {repository_name}\n\n### Previous Analysis (Discovery, Layers, Patterns):\n{previous_analyses}\n\n### Frontend Code Samples:\n{code_samples}\n\nAnalyze the frontend architecture in detail. This analysis covers web frontends, mobile apps, and any client-side code.\n\n### 1. Framework & Rendering\n- What UI framework is used? (React, Vue, Angular, SwiftUI, Jetpack Compose, etc.)\n- What rendering strategy? (SSR, SSG, CSR, ISR, hybrid)\n- What meta-framework? (Next.js, Nuxt, Remix, Expo, etc.)\n\n### 2. Component Architecture\nFor each major UI component/page identified:\n- Name and location\n- Type: page | layout | feature | shared | primitive\n- Key props/inputs\n- Child components it renders\n\n### 3. State Management\n- Global state approach (Context, Redux, Zustand, Recoil, etc.)\n- Server state management (React Query, SWR, Apollo, etc.)\n- Local component state patterns\n- Form state management\n\n### 4. Routing\n- Routing approach (file-based, config-based)\n- List of routes with their components\n- Auth-protected routes\n- Dynamic routes\n\n### 5. Data Fetching\n- How does the frontend fetch data from the backend?\n- Custom hooks for data fetching?\n- Loading/error state handling patterns\n- Caching strategy\n\n### 6. Styling\n- Styling approach (Tailwind, CSS Modules, Styled Components, etc.)\n- Component library used?\n- Design system / tokens?\n\n### 7. Key Conventions\n- File naming conventions for components\n- Component organization (co-located, feature-based, atomic)\n- Custom hooks naming/organization\n- Test file placement\n\nProvide your analysis in structured JSON format:\n```json\n{\n  "framework": "...",\n  "rendering_strategy": "SSR | SSG | CSR | ISR | hybrid",\n  "ui_components": [\n    {"name": "...", "location": "...", "component_type": "page|layout|feature|shared|primitive", "description": "...", "props": ["..."], "children": ["..."]}\n  ],\n  "state_management": {\n    "approach": "...",\n    "global_state": [{"store": "...", "purpose": "..."}],\n    "server_state": "...",\n    "local_state": "...",\n    "rationale": "..."\n  },\n  "routing": [\n    {"path": "...", "component": "...", "description": "...", "auth_required": false}\n  ],\n  "data_fetching": [\n    {"name": "...", "mechanism": "...", "when_to_use": "...", "examples": ["..."]}\n  ],\n  "styling": "...",\n  "key_conventions": ["..."]\n}\n```',
    '["repository_name", "previous_analyses", "code_samples"]'::jsonb,
    TRUE,
    'frontend_analysis',
    'prompt'
),
(
    'Blueprint Synthesis (Structured JSON)',
    'blueprint_synthesis',
    E'## Architecture Blueprint \u2014 {repository_name}\n\nSynthesize ALL analysis into a single JSON architecture blueprint. This is the **source of truth** for CLAUDE.md, Cursor rules, and MCP validation.\n\n### Analysis Results\n\n**Discovery:** {discovery}\n\n**Layers:** {layers}\n\n**Patterns:** {patterns}\n\n**Communication:** {communication}\n\n**Technology:** {technology}\n\n**Frontend / UI:** {frontend_analysis}\n\n**Code Samples:** {code_samples}\n\n{platform_hint}\n\n---\n\n### OUTPUT RULES\n\n1. Output ONLY a JSON object. No markdown fences, no commentary before or after.\n2. BE CONCISE. Use short descriptions (1 sentence max). Prefer brevity over elaboration.\n3. Every rule must be grounded in the analysis above. Do NOT invent rules.\n4. Use glob patterns for source_pattern, allowed_imports, forbidden_imports.\n5. Limit arrays: max 5 dependency_constraints, 8 file_placement_rules, 5 naming_conventions, 6 components, 5 key_decisions, 3 trade_offs, 5 communication patterns, 10 stack items, 3 templates.\n6. Confidence: 0.9+ = clearly observed, 0.7-0.9 = inferred, <0.7 = omit.\n7. COMPLETE the entire JSON structure. A complete but concise blueprint is far better than a detailed but truncated one.\n\n### JSON Structure (fill all sections):\n\n{"meta":{"repository":"","repository_id":"","analyzed_at":"ISO-8601","schema_version":"2.0.0","architecture_style":"plain language","platforms":[],"confidence":{"architecture_rules":0,"decisions":0,"components":0,"communication":0,"technology":0,"frontend":0}},"architecture_rules":{"dependency_constraints":[{"source_pattern":"","source_description":"","allowed_imports":[],"forbidden_imports":[],"severity":"error|warn","rationale":""}],"file_placement_rules":[{"component_type":"","naming_pattern":"","location":"","example":"","description":""}],"naming_conventions":[{"scope":"","pattern":"","examples":[],"description":""}]},"decisions":{"architectural_style":{"title":"","chosen":"","rationale":"","alternatives_rejected":[]},"key_decisions":[{"title":"","chosen":"","rationale":"","alternatives_rejected":[]}],"trade_offs":[{"accept":"","benefit":""}],"out_of_scope":[]},"components":{"structure_type":"","components":[{"name":"","location":"","platform":"backend|frontend|shared","responsibility":"","depends_on":[],"exposes_to":[],"key_interfaces":[{"name":"","methods":[],"description":""}],"key_files":[{"file":"","description":""}]}],"contracts":[]},"communication":{"patterns":[{"name":"","when_to_use":"","how_it_works":"","examples":[]}],"integrations":[{"service":"","purpose":"","integration_point":""}],"pattern_selection_guide":[{"scenario":"","pattern":"","rationale":""}]},"quick_reference":{"where_to_put_code":{},"pattern_selection":{},"error_mapping":[{"error":"","status_code":0,"description":""}]},"technology":{"stack":[{"category":"","name":"","version":"","purpose":""}],"templates":[{"component_type":"","description":"","file_path_template":"","code":""}],"project_structure":"","run_commands":{}},"frontend":{"framework":"","rendering_strategy":"","ui_components":[{"name":"","location":"","component_type":"","description":"","props":[],"children":[]}],"state_management":{"approach":"","global_state":[],"server_state":"","local_state":"","rationale":""},"routing":[{"path":"","component":"","description":"","auth_required":false}],"data_fetching":[{"name":"","mechanism":"","when_to_use":"","examples":[]}],"styling":"","key_conventions":[]}}\n\nGenerate the complete JSON for {repository_name}.',
    '["repository_name", "discovery", "layers", "patterns", "communication", "technology", "frontend_analysis", "code_samples", "platform_hint"]'::jsonb,
    TRUE,
    'blueprint_synthesis',
    'prompt'
)
ON CONFLICT (key) WHERE key IS NOT NULL DO NOTHING;

-- ============================================================
-- Grants
-- ============================================================

GRANT EXECUTE ON FUNCTION match_embeddings TO authenticated;
GRANT EXECUTE ON FUNCTION match_embeddings TO anon;

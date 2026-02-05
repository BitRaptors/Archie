# Repository Analysis & Architecture Enforcement System

A comprehensive system for analyzing GitHub repositories, generating architecture blueprints, and enforcing architectural consistency for AI coding agents via MCP.

## Overview

This system provides:
1. **Repository Analysis**: Analyzes codebases using AI-powered phased analysis
2. **Architecture Blueprint Generation**: Creates comprehensive architecture documentation
3. **Architecture Enforcement**: Validates code against learned and reference architectures
4. **AI Agent Integration**: Provides MCP tools for AI agents to query and validate architecture

## Tech Stack

- **Backend**: FastAPI (Python) with layered architecture
- **Frontend**: Next.js (React/TypeScript)
- **Database**: Supabase (PostgreSQL with pgvector for embeddings)
- **AI**: Anthropic Claude API for analysis
- **Storage**: Local or Cloud Storage (GCS/S3)
- **MCP Server**: Provides architecture tools and resources for AI agents

---

## Complete Data Flow: From Codebase to Outputs

This section explains exactly how data flows through the system - from raw codebase to final blueprint, CLAUDE.md, and Cursor rules.

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              COMPLETE DATA FLOW DIAGRAM                                  │
└─────────────────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐
  │  CODEBASE    │
  │  (Any Size)  │
  └──────┬───────┘
         │
         │ git clone
         ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: DATA EXTRACTION (analysis_service.py)                                          │
│ ─────────────────────────────────────────────────────────────────────────────────────── │
│                                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │ File Tree       │  │ Dependencies    │  │ Config Files    │  │ Code Samples    │    │
│  │ (structure_     │  │ (requirements.  │  │ (tsconfig.json, │  │ (10 represent-  │    │
│  │  analyzer.py)   │  │  txt, package.  │  │  docker-compose │  │  ative files)   │    │
│  │                 │  │  json, etc.)    │  │  .yml, etc.)    │  │                 │    │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘    │
│           │                    │                    │                    │              │
│           └────────────────────┴────────────────────┴────────────────────┘              │
│                                        │                                                │
│                                        ▼                                                │
│                         ┌──────────────────────────────┐                               │
│                         │ capture_gathered_data()       │ ──▶ Supabase: analysis_data  │
│                         │ (analysis_data_collector.py)  │     data_type: "gathered"    │
│                         └──────────────────────────────┘                               │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: RAG INDEXING (rag_retriever.py) - Optional but Recommended                     │
│ ─────────────────────────────────────────────────────────────────────────────────────── │
│                                                                                         │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐ │
│  │ For EACH code file in repository:                                                  │ │
│  │                                                                                    │ │
│  │   1. Read file content                                                             │ │
│  │   2. Chunk by function/class boundaries                                            │ │
│  │   3. Generate 384-dim embedding (sentence-transformers/all-MiniLM-L6-v2)           │ │
│  │   4. Store in Supabase pgvector: embeddings table                                  │ │
│  │      - repository_id, file_path, chunk_type, embedding, metadata                   │ │
│  │                                                                                    │ │
│  │ Stats captured: {files: 150, chunks: 890, total_lines: 25000}                      │ │
│  └───────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                         │
│  WHY RAG?: Allows analyzing codebases of ANY size by retrieving only relevant code     │
│            for each phase, instead of trying to fit everything in context window.      │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ PHASE 3: AI PHASED ANALYSIS (phased_blueprint_generator.py)                             │
│ ─────────────────────────────────────────────────────────────────────────────────────── │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │ OBSERVATION PHASE (NEW - Architecture Agnostic)                                   │   │
│  │ ─────────────────────────────────────────────────────────────────────────────────│   │
│  │ Input:                                                                            │   │
│  │   • File signatures from ALL code files (up to 300 files)                         │   │
│  │   • ~200 tokens per file: path + imports + class/function signatures              │   │
│  │                                                                                   │   │
│  │ AI Prompt: "Observe what you see. Do NOT assume standard patterns."               │   │
│  │                                                                                   │   │
│  │ Output: JSON {architecture_style, detected_components, key_search_terms}          │   │
│  │         ──▶ Generates CUSTOM RAG queries for this specific codebase               │   │
│  │                                                                                   │   │
│  │ Examples:                                                                         │   │
│  │   • Actor-based → queries: "actor message receive mailbox"                        │   │
│  │   • Event-sourced → queries: "event store aggregate projection"                   │   │
│  │   • Custom pattern → queries based on observed naming conventions                 │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                         │                                               │
│                                         ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │ DISCOVERY PHASE (Enhanced with observations)                                      │   │
│  │ ─────────────────────────────────────────────────────────────────────────────────│   │
│  │ Input:                                                                            │   │
│  │   • file_tree[:3000]        (compressed structure)                                │   │
│  │   • dependencies[:1500]     (package files)                                       │   │
│  │   • config_files[:4000]     (OR RAG-retrieved if enabled)                         │   │
│  │   • observation_result      (architecture insights from Phase 0)                  │   │
│  │                                                                                   │   │
│  │ RAG Query: CUSTOM queries based on observations (not hardcoded!)                  │   │
│  │                                                                                   │   │
│  │ Prompt: prompts.json → "discovery" → AI                                           │   │
│  │                                                                                   │   │
│  │ Output: JSON {project_type, entry_points, module_organization, config_approach}   │   │
│  │         ──▶ Stored in Supabase: data_type: "phase_discovery"                      │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                         │                                               │
│                                         ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │ LAYERS PHASE                                                                      │   │
│  │ ─────────────────────────────────────────────────────────────────────────────────│   │
│  │ Input:                                                                            │   │
│  │   • discovery_summary[:1500]  (from previous phase)                               │   │
│  │   • file_tree[:2500]                                                              │   │
│  │   • code_samples[:5000]       (RAG-retrieved OR fallback samples)                 │   │
│  │                                                                                   │   │
│  │ RAG Query: "service layer business logic", "repository data access", etc.         │   │
│  │                                                                                   │   │
│  │ Output: JSON {has_layers, structure_type, layers[], dependency_rules}             │   │
│  │         ──▶ Stored in Supabase: data_type: "phase_layers"                         │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                         │                                               │
│                                         ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │ PATTERNS PHASE                                                                    │   │
│  │ ─────────────────────────────────────────────────────────────────────────────────│   │
│  │ Input: discovery + layers + RAG-retrieved code showing patterns                   │   │
│  │                                                                                   │   │
│  │ RAG Query: "dependency injection container factory", "error handling exception"   │   │
│  │                                                                                   │   │
│  │ Output: JSON {structural_patterns[], behavioral_patterns[], cross_cutting[]}      │   │
│  │         ──▶ Stored in Supabase: data_type: "phase_patterns"                       │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                         │                                               │
│                                         ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │ COMMUNICATION PHASE                                                               │   │
│  │ ─────────────────────────────────────────────────────────────────────────────────│   │
│  │ Input: All previous phases + RAG-retrieved API/event code                         │   │
│  │                                                                                   │   │
│  │ RAG Query: "API endpoint route handler", "event publisher subscriber"             │   │
│  │                                                                                   │   │
│  │ Output: JSON {internal_comm[], external_comm[], third_party[], guidelines[]}      │   │
│  │         ──▶ Stored in Supabase: data_type: "phase_communication"                  │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                         │                                               │
│                                         ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │ TECHNOLOGY PHASE                                                                  │   │
│  │ ─────────────────────────────────────────────────────────────────────────────────│   │
│  │ Input: All analyses + dependencies + RAG-retrieved import statements              │   │
│  │                                                                                   │   │
│  │ Output: JSON {runtime, framework, database, cache, queue, ai_ml, auth, ...}       │   │
│  │         ──▶ Stored in Supabase: data_type: "phase_technology"                     │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                         │                                               │
│                                         ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │ SYNTHESIS PHASE (The "Cartographer" Step)                                         │   │
│  │ ─────────────────────────────────────────────────────────────────────────────────│   │
│  │                                                                                   │   │
│  │ Input: ALL PREVIOUS PHASE OUTPUTS COMBINED                                        │   │
│  │   • discovery[:2500]                                                              │   │
│  │   • layers[:2500]                                                                 │   │
│  │   • patterns[:2500]                                                               │   │
│  │   • communication[:2500]                                                          │   │
│  │   • technology[:2500]                                                             │   │
│  │   • code_samples[:4000]                                                           │   │
│  │                                                                                   │   │
│  │ Prompt: "backend_synthesis" - Generate comprehensive architecture document        │   │
│  │                                                                                   │   │
│  │ Output: COMPLETE MARKDOWN BLUEPRINT (15-20K chars)                                │   │
│  │   - Architectural Decision Rationale                                              │   │
│  │   - Core Principles (SOLID, etc.)                                                 │   │
│  │   - Layer Architecture (or actual structure if no layers)                         │   │
│  │   - Communication Patterns                                                        │   │
│  │   - Component Contracts                                                           │   │
│  │   - Error Handling Strategy                                                       │   │
│  │   - Implementation Guide with templates                                           │   │
│  │                                                                                   │   │
│  │         ──▶ Stored in Supabase: data_type: "phase_backend_synthesis"              │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ PHASE 4: SAVE BLUEPRINT (analysis_service.py)                                           │
│ ─────────────────────────────────────────────────────────────────────────────────────── │
│                                                                                         │
│  Blueprint saved to: storage/blueprints/{repository_id}/backend_blueprint.md            │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ PHASE 5: GENERATE AGENT FILES (analyses.py → get_agent_files endpoint)                  │
│ ─────────────────────────────────────────────────────────────────────────────────────── │
│                                                                                         │
│  Input: The saved blueprint markdown content                                            │
│                                                                                         │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐                │
│  │ CLAUDE.md          │  │ Cursor Rules       │  │ AGENTS.md          │                │
│  │ ──────────────────│  │ ──────────────────│  │ ──────────────────│                │
│  │ Extracts:          │  │ Extracts:          │  │ Lists:             │                │
│  │ • All ## sections  │  │ • Layer sections   │  │ • Blueprint sections│               │
│  │ • Prioritizes:     │  │ • Pattern sections │  │ • Agent roles       │                │
│  │   - Principles     │  │ • Contract sections│  │ • Integration guide │                │
│  │   - Layers         │  │ • Auto-detect globs│  │                    │                │
│  │   - Patterns       │  │   from extensions  │  │                    │                │
│  │   - Dependencies   │  │   in blueprint     │  │                    │                │
│  │ • Language-agnostic│  │ • Language-agnostic│  │ • Language-agnostic│                │
│  └────────────────────┘  └────────────────────┘  └────────────────────┘                │
│                                                                                         │
│  KEY: These files are generated FROM the blueprint, not independently.                  │
│       They reflect whatever was discovered - iOS, Android, Python, anything.            │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ FINAL OUTPUTS (Frontend: blueprint/[id].tsx)                                            │
│ ─────────────────────────────────────────────────────────────────────────────────────── │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │ TAB: Backend Architecture                                                         │   │
│  │ Source: GET /api/v1/analyses/{id}/blueprint?type=backend                          │   │
│  │ Content: Full markdown blueprint rendered                                         │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │ TAB: CLAUDE.md                                                                    │   │
│  │ Source: GET /api/v1/analyses/{id}/agent-files → claude_md                         │   │
│  │ Content: Condensed architecture guidance for AI assistants                        │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │ TAB: Cursor Rules                                                                 │   │
│  │ Source: GET /api/v1/analyses/{id}/agent-files → cursor_rules                      │   │
│  │ Content: .cursor/rules/architecture.md format                                     │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐   │
│  │ TAB: Analysis Data & Prompts                                                      │   │
│  │ Source: GET /api/v1/analyses/{id}/analysis-data                                   │   │
│  │ Content: Full transparency - what was gathered, what was sent to AI, RAG stats    │   │
│  └─────────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Observation-First Architecture (NEW)

**The Problem**: Traditional RAG queries assume patterns like "service layer", "repository pattern" - but what about:
- Actor-based architectures?
- Event-sourced systems?
- CQRS patterns?
- Custom/unique patterns?

**The Solution**: Observation-First approach that detects architecture style BEFORE running targeted queries.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 0: FULL FILE SIGNATURE SCAN (Architecture-Agnostic)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ For EVERY code file (up to 300 files):                                      │
│   1. Extract file path                                                      │
│   2. Extract imports (first 15 lines)                                       │
│   3. Extract class/function SIGNATURES (not full implementation)            │
│                                                                             │
│ Token budget: 300 files × ~200 tokens = 60,000 tokens ✓ Fits!               │
│                                                                             │
│ AI Prompt: "Observe and describe what you see. Do NOT assume patterns."     │
│                                                                             │
│ Output: Architecture style detection + custom RAG queries                   │
│                                                                             │
│ Example detected styles:                                                    │
│   • "Actor-based with message passing" → queries: "actor receive mailbox"   │
│   • "Event-sourced with CQRS" → queries: "event store aggregate projection" │
│   • "Feature-sliced design" → queries: "feature module slice"               │
│   • "Traditional layered" → queries: "service repository controller"        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### How RAG and Phased Analysis Work Together

**The Problem**: Large codebases (100K+ files) can't fit in an AI's context window (~100-200K tokens).

**The Solution**: Three complementary strategies working together:

| Strategy | What It Does | When It Helps |
|----------|--------------|---------------|
| **Observation Phase** | Scans ALL file signatures, detects architecture style | Non-standard architectures, unique patterns |
| **RAG (Vector Search)** | Indexes entire codebase, retrieves only relevant chunks per phase | Finding specific code patterns across huge codebases |
| **Phased Analysis** | Builds understanding incrementally, each phase adds ~500-2500 chars | Compressing understanding into manageable context |

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ WITHOUT RAG (Small Codebases < 50 files)                                    │
│ ─────────────────────────────────────────────────────────────────────────── │
│                                                                             │
│   File Tree + Dependencies + 10 Code Samples                                │
│                     │                                                       │
│                     ▼                                                       │
│              [Each Phase Gets Same Samples]                                 │
│                     │                                                       │
│                     ▼                                                       │
│                 Blueprint                                                   │
│                                                                             │
│   Works fine for small projects where samples cover most patterns.          │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ WITH RAG (Large Codebases 50+ files)                                        │
│ ─────────────────────────────────────────────────────────────────────────── │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │ Index Phase (One Time)                                                │  │
│   │   Every file → Chunks → Embeddings → Supabase pgvector               │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │ Discovery Phase                                                       │  │
│   │   Query: "entry point", "configuration" → Get relevant chunks         │  │
│   │   Result: entry.py, config.py, main.swift, AppDelegate.m, etc.       │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │ Layers Phase                                                          │  │
│   │   Query: "service layer", "repository", "controller" → Get chunks     │  │
│   │   Result: UserService.kt, Repository.swift, Controller.py, etc.      │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │ Patterns Phase                                                        │  │
│   │   Query: "dependency injection", "factory" → Get chunks               │  │
│   │   Result: Container.py, Factory.swift, Module.kt, etc.               │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   Each phase gets DIFFERENT, RELEVANT code from the entire codebase!        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Files in the Pipeline

| File | Role |
|------|------|
| `analysis_service.py` | Orchestrates entire pipeline, extracts raw data |
| `structure_analyzer.py` | Scans file tree, identifies code files |
| `rag_retriever.py` | Indexes code, performs semantic search |
| `phased_blueprint_generator.py` | Runs 6 AI phases, generates blueprint |
| `analysis_data_collector.py` | Captures all data for transparency UI |
| `prompts.json` | All AI prompts for each phase |
| `analyses.py` (routes) | API endpoints including agent-files generation |

---

## Analysis Pipeline: How Blueprints Are Generated

The system uses a **phased AI analysis pipeline** with RAG (Retrieval-Augmented Generation) to analyze codebases of any size and generate comprehensive architecture blueprints.

### Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         REPOSITORY CLONE                                │
│                              │                                          │
│                              ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    DATA EXTRACTION                                 │  │
│  │  • File tree structure                                             │  │
│  │  • Dependencies (package.json, requirements.txt, etc.)             │  │
│  │  • Configuration files                                             │  │
│  │  • Code samples                                                    │  │
│  └───────────────────────────┬───────────────────────────────────────┘  │
│                              │                                          │
│                              ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    RAG INDEXING                                    │  │
│  │  • Chunk code files by functions/classes                           │  │
│  │  • Generate embeddings (sentence-transformers)                     │  │
│  │  • Store in pgvector for semantic search                           │  │
│  └───────────────────────────┬───────────────────────────────────────┘  │
│                              │                                          │
│                              ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                 PHASED AI ANALYSIS                                 │  │
│  │                                                                    │  │
│  │   Phase 1: Discovery ──► Phase 2: Layers ──► Phase 3: Patterns    │  │
│  │         │                      │                    │              │  │
│  │         └──────────────────────┴────────────────────┘              │  │
│  │                              │                                      │  │
│  │         ┌────────────────────┴────────────────────┐                │  │
│  │         │                                         │                │  │
│  │   Phase 4: Communication              Phase 5: Technology          │  │
│  │         │                                         │                │  │
│  │         └────────────────────┬────────────────────┘                │  │
│  │                              │                                      │  │
│  │                              ▼                                      │  │
│  │                   Phase 6: Backend Synthesis                       │  │
│  └───────────────────────────┬───────────────────────────────────────┘  │
│                              │                                          │
│                              ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                  FINAL BLUEPRINT                                   │  │
│  │           (Comprehensive Markdown Document)                        │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Analysis Phases (AI Agents)

Each phase is powered by Claude AI with specific prompts designed to extract different aspects of the architecture:

| Phase | Agent | Input | Output | Purpose |
|-------|-------|-------|--------|---------|
| **1. Discovery** | Discovery Agent | File tree, dependencies, config files | Project type, entry points, module organization | Understand what the project is and how it's organized |
| **2. Layers** | Layer Agent | Discovery output + file tree + RAG code samples | Layer definitions, dependency rules, structure type | Identify architectural layers (if any) |
| **3. Patterns** | Pattern Agent | Discovery + Layers + RAG code samples | Structural patterns, behavioral patterns, cross-cutting concerns | Extract design patterns used |
| **4. Communication** | Communication Agent | All previous + RAG code samples | Internal/external communication, integrations | Map how components communicate |
| **5. Technology** | Technology Agent | All previous + dependencies | Complete tech stack inventory | Document all technologies used |
| **6. Synthesis** | Synthesis Agent | All phase outputs + code samples | Final Blueprint Markdown | Generate comprehensive architecture document |

### Handling Large Codebases (The Context Window Problem)

**The Challenge**: AI models have limited context windows (e.g., ~100K-200K tokens for Claude), but codebases can be millions of lines. How do we analyze the entire architecture?

**The Solution**: A combination of **smart data extraction**, **RAG-based retrieval**, and **progressive context building**.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    LARGE CODEBASE (e.g., 500+ files)                   │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│ COMPRESSION   │      │  RAG INDEX    │      │  SELECTIVE    │
│ (Structure)   │      │ (Embeddings)  │      │  SAMPLING     │
├───────────────┤      ├───────────────┤      ├───────────────┤
│ Full file tree│      │ Chunk by      │      │ Config files  │
│ compressed to │      │ function/class│      │ Entry points  │
│ ~3000 chars   │      │ 384-dim vectors│     │ Key samples   │
└───────────────┘      └───────────────┘      └───────────────┘
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              PHASE-SPECIFIC CONTEXT ASSEMBLY                            │
│                                                                         │
│  For each phase, we assemble a focused context:                         │
│  • Compressed structure (~3000 chars)                                   │
│  • Previous phase outputs (~2500 chars each)                            │
│  • RAG-retrieved code relevant to THIS phase (~5000 chars)              │
│  • Phase-specific prompt                                                │
│  ─────────────────────────────────────────────────────────────          │
│  Total per phase: ~15-20K tokens (fits in context window)               │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Strategy 1: Compressed Structure (File Tree)

Instead of sending every file path, we send a compressed tree:

```
Original (100KB+):                    Compressed (~3KB):
/src/api/routes/users.py              📁 src/api/routes/
/src/api/routes/auth.py                 📄 users.py
/src/api/routes/products.py             📄 auth.py
/src/api/routes/__init__.py             📄 products.py
/src/api/middleware/auth.py           📁 src/api/middleware/
/src/api/middleware/logging.py          📄 auth.py
... (thousands more)                  ... and 847 more items
```

The AI sees the **shape** of the codebase without needing every file.

#### Strategy 2: RAG-Based Semantic Retrieval

For each analysis phase, we retrieve **only the most relevant code**:

```python
# Phase-specific semantic queries
phase_queries = {
    "discovery": [
        "main entry point application startup initialization",
        "configuration settings environment variables",
        "project structure module organization",
    ],
    "layers": [
        "service layer business logic orchestration",
        "repository data access database operations",
        "controller route handler API endpoint",
    ],
    "patterns": [
        "dependency injection container factory provider",
        "repository pattern interface implementation",
        "error handling exception try catch",
    ],
    "communication": [
        "API endpoint route handler request response",
        "event publisher subscriber message queue",
        "websocket realtime connection handler",
    ],
    "technology": [
        "import from require module dependency",
        "database connection ORM query",
    ],
}
```

**How it works:**
1. **Indexing**: All code files are chunked by function/class boundaries
2. **Embedding**: Each chunk is embedded using `sentence-transformers/all-MiniLM-L6-v2`
3. **Storage**: 384-dimensional vectors stored in Supabase pgvector
4. **Retrieval**: For each phase, we query with relevant terms and get top-15 most similar chunks
5. **Context**: Only ~5000 chars of the most relevant code is sent to AI

```sql
-- Example: pgvector similarity search
SELECT file_path, metadata, 
       1 - (embedding <=> query_embedding) as similarity
FROM embeddings
WHERE repository_id = 'uuid'
ORDER BY embedding <=> query_embedding
LIMIT 15;
```

#### Strategy 3: Progressive Context Building

Each phase builds on previous phases, creating a compressed "memory":

```
Phase 1 (Discovery):
  Input:  file_tree + dependencies + configs
  Output: project_type, entry_points, organization  ← ~500 chars JSON

Phase 2 (Layers):
  Input:  discovery_output (500 chars) + file_tree + RAG code
  Output: layers, dependency_rules  ← ~800 chars JSON

Phase 3 (Patterns):
  Input:  discovery (500) + layers (800) + RAG code
  Output: structural_patterns, behavioral_patterns  ← ~1000 chars JSON

... and so on

Phase 6 (Synthesis):
  Input:  ALL previous outputs (~4000 chars total) + RAG code
  Output: FINAL BLUEPRINT (~15-20K chars)
```

The AI never sees the entire codebase at once, but it **progressively builds understanding** through structured outputs from each phase.

#### Strategy 4: Smart Truncation with Visibility

When data must be truncated, we:
1. **Track what was cut**: Store both full and truncated versions
2. **Prioritize important content**: Keep headers, signatures, key code
3. **Show truncation in UI**: The "Analysis Data & Prompts" tab shows exactly what was sent vs. gathered

```
┌─────────────────────────────────────────┐
│ Gathered: 45,000 chars                  │
│ Sent to AI: 5,000 chars (11%)           │
│ ─────────────────────────────────────── │
│ [████░░░░░░░░░░░░░░░░] 11% sent         │
└─────────────────────────────────────────┘
```

#### Character Limits by Phase

| Phase | File Tree | Dependencies | Code Samples | Previous Context |
|-------|-----------|--------------|--------------|------------------|
| Discovery | 3,000 | 1,500 | 4,000 | - |
| Layers | 2,500 | - | 5,000 | 1,500 |
| Patterns | - | - | 6,000 | 2,500 |
| Communication | - | - | 5,000 | 3,000 |
| Technology | - | 2,000 | 3,000 | 3,500 |
| Synthesis | - | - | 4,000 | 12,500 (all phases) |

**Total per phase**: ~15-20K characters, well within Claude's context window while covering the entire codebase through intelligent selection.

### Analysis Data Collection

All intermediate data is captured and persisted to Supabase for transparency:

| Data Type | Description |
|-----------|-------------|
| `gathered` | Raw data extracted from codebase (file tree, dependencies, configs) |
| `phase_discovery` | Discovery phase input/output and exact prompt |
| `phase_layers` | Layers phase input/output and exact prompt |
| `phase_patterns` | Patterns phase input/output and exact prompt |
| `phase_communication` | Communication phase input/output and exact prompt |
| `phase_technology` | Technology phase input/output and exact prompt |
| `phase_backend_synthesis` | Synthesis phase input/output and exact prompt |
| `summary` | Overall metrics (chars sent, phase count, timestamps) |

This data is viewable in the **"Analysis Data & Prompts"** tab in the frontend, allowing you to:
- See exactly what data was gathered from the codebase
- Compare what was gathered vs. what was sent to AI (truncation visibility)
- View the exact prompts sent to Claude
- See RAG retrieval results for each phase

### Final Blueprint Structure

The synthesis phase generates a comprehensive Markdown document with:

```markdown
# [Repository Name] Backend Architecture Blueprint

## Purpose
[What this document covers and who it's for]

## Table of Contents
### Part 1: Architecture (Sections 1-7)
### Part 2: Implementation (Section 8)

## 1. Architectural Decision Rationale
- Why this architecture was chosen
- Trade-offs accepted
- What this architecture does NOT solve

## 2. Core Principles
- SOLID principles with codebase examples

## 3. Layer Architecture
- Layer diagram (or actual structure if no layers)
- Dependency rules (allowed/forbidden imports)

## 4. Communication Patterns
- Internal communication mechanisms
- External API patterns
- Pattern selection guide

## 5. Component Contracts
- Key interfaces and their purposes

## 6. Error Handling Strategy
- Error categories and flow
- HTTP status mapping

## 7. Cross-Cutting Concerns
- Logging, auth, validation, caching

## 8. Implementation Guide
- Complete tech stack table
- Project structure
- Code templates for all components
- Running instructions
```

---

## Architecture Enforcement System

The system helps AI coding agents maintain architecture through two complementary approaches:

### Architecture Sources

| Mode | Description | Use Case |
|------|-------------|----------|
| `learned_primary` (default) | Learned rules take precedence, reference fills gaps | Most projects after initial analysis |
| `reference_primary` | Reference rules take precedence, learned adds extras | Enforcing org-wide standards |
| `learned_only` | Only use learned architecture | Fully autonomous project |
| `reference_only` | Only use reference architecture | New project, no analysis yet |

### How It Works

```
┌─────────────────┐     ┌─────────────────┐
│ Learned         │     │ Reference       │
│ Architecture    │     │ Architecture    │
│ (from analysis) │     │ (from templates)│
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
              ┌──────▼──────┐
              │ Architecture │
              │   Resolver   │
              └──────┬──────┘
                     │
         ┌───────────┼───────────┐
         │           │           │
    ┌────▼────┐ ┌────▼────┐ ┌────▼────┐
    │  MCP    │ │CLAUDE.md│ │ Cursor  │
    │  Tools  │ │Generator│ │ Rules   │
    └─────────┘ └─────────┘ └─────────┘
```

### MCP Tools for AI Agents

- `get_architecture_for_repo` - Get resolved architecture rules for a repository
- `validate_code` - Validate code against architecture before committing
- `check_file_location` - Verify file placement follows conventions
- `get_implementation_guide` - Get step-by-step implementation guidance
- `configure_architecture` - Set architecture sources and merge strategy
- `list_reference_blueprints` - List available reference architectures

### Generated Files

The system can generate instruction files for AI agents:
- **CLAUDE.md** - General AI agent instructions
- **.cursor/rules/architecture.md** - Cursor-specific rules
- **AGENTS.md** - Multi-agent system instructions

## Quick Start

### Start Both Servers

Use the startup script to run both backend and frontend:

**Linux/Mac:**
```bash
./start-dev.sh
```

**Windows:**
```batch
start-dev.bat
```

**Python (Cross-platform):**
```bash
python start-dev.py
```

This will automatically:
- Check for required environment files
- Create virtual environment if needed
- Install dependencies if needed
- Start backend on http://localhost:8000
- Start frontend on http://localhost:3000

Press `Ctrl+C` to stop both servers.

## Setup

### Prerequisites

1. **Configure environment variables:**
   - Copy `backend/.env.example` to `backend/.env.local`
   - Add your `SUPABASE_JWT_SECRET` and `ANTHROPIC_API_KEY`
   - Copy `frontend/.env.example` to `frontend/.env.local` (if needed)

2. **Database setup:**
   - All migrations have been applied to Supabase
   - See `SETUP_COMPLETE.md` for details

### Manual Setup (if not using startup script)

**Backend:**

1. Install dependencies:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. Start server:
```bash
python src/main.py
# Or: uvicorn src.main:app --reload
```

**Frontend:**

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Start dev server:
```bash
npm run dev
```

## Key Features

- GitHub repository analysis
- Embedding-based semantic search
- Custom prompt system
- Unified blueprints from multiple repos
- MCP integration for Cursor

## Getting Started

### 1. Get a GitHub Token

You'll need a GitHub Personal Access Token to authenticate. See **[GITHUB_TOKEN_GUIDE.md](./GITHUB_TOKEN_GUIDE.md)** for detailed instructions.

**Quick steps:**
1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes: `repo` and `read:user`
4. Copy the token (starts with `ghp_`)

### 2. Start the Application

```bash
./start-dev.sh
```

### 3. Authenticate

1. Open the frontend (usually http://localhost:3000)
2. Navigate to the Authentication page
3. Paste your GitHub token
4. Click "Authenticate"

## Running Tests

The system includes a comprehensive test suite for validating business logic:

```bash
# Run all tests
cd backend
pytest tests/ -v

# Run unit tests only
pytest tests/unit/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/agents/test_orchestrator.py -v

# Run tests matching pattern
pytest tests/ -k "resolver" -v
```

## API Endpoints

### Analysis API

- `POST /api/v1/repositories/{id}/analyze` - Start analysis for a repository
- `GET /api/v1/analyses/{id}` - Get analysis status
- `GET /api/v1/analyses/{id}/stream` - Stream analysis progress (SSE)
- `GET /api/v1/analyses/{id}/blueprint?type=backend` - Get generated blueprint
- `GET /api/v1/analyses/{id}/analysis-data` - Get all analysis data (phases, prompts, metrics)
- `GET /api/v1/analyses/{id}/agent-files` - Get CLAUDE.md, Cursor rules, and AGENTS.md

### Architecture API

- `GET /api/v1/architecture/repositories/{id}` - Get resolved architecture
- `PUT /api/v1/architecture/repositories/{id}/config` - Configure architecture sources
- `POST /api/v1/architecture/repositories/{id}/validate` - Validate code
- `POST /api/v1/architecture/repositories/{id}/check-location` - Check file location
- `GET /api/v1/architecture/repositories/{id}/guide/{type}` - Get implementation guide
- `GET /api/v1/architecture/repositories/{id}/agent-files` - Get CLAUDE.md, etc.
- `GET /api/v1/architecture/reference-blueprints` - List reference blueprints

## Frontend Features

### Blueprint View (`/blueprint/{analysis_id}`)

After analysis completes, view the results:

| Tab | Description |
|-----|-------------|
| **Backend Architecture** | The generated architecture blueprint (Markdown rendered) |
| **Frontend Architecture** | Frontend-specific blueprint (coming soon) |
| **CLAUDE.md** | AI agent instructions - place in project root for AI assistants |
| **Cursor Rules** | Cursor IDE rules - place at `.cursor/rules/architecture.md` |
| **MCP Server Setup** | Instructions to connect this blueprint to Cursor via MCP |
| **Analysis Data & Prompts** | Full transparency into the analysis process |

### Analysis Data & Prompts Tab

This tab provides complete visibility into how the blueprint was generated:

1. **Summary Dashboard**: Total chars sent, phases completed, RAG coverage
2. **Data Gathered**: Raw file tree, dependencies, config files extracted from repo
3. **Phase Details**: For each phase (Discovery, Layers, Patterns, etc.):
   - What data was gathered
   - What was actually sent to AI (with truncation indicators)
   - RAG retrieval results
   - Exact prompt sent to Claude

This transparency helps you:
- Understand why certain architectural decisions were documented
- Debug analysis issues
- Customize prompts for better results

## Syncing Reference Blueprints

To sync reference blueprints from `DOCS/` to the database:

```bash
cd backend
python -m application.services.reference_blueprint_sync
```

This extracts structured rules from markdown blueprints like `DOCS/PYTHON_ARCHITECTURE_BLUEPRINT.md` and stores them in the `architecture_rules` table.

## Development

### Project Structure

```
backend/
├── src/
│   ├── api/routes/          # API endpoints
│   ├── application/
│   │   ├── agents/          # Orchestrator and workers
│   │   └── services/        # Business logic
│   ├── domain/entities/     # Domain models
│   └── infrastructure/
│       ├── mcp/             # MCP server and tools
│       └── persistence/     # Database repositories
├── tests/                   # Test suite
└── migrations/              # Database migrations

DOCS/                        # Reference architecture blueprints
frontend/                    # Next.js frontend
```

### Key Components

#### Analysis Pipeline
- **StructureAnalyzer**: Scans repository file structure and extracts metadata
- **PhasedBlueprintGenerator**: Orchestrates the 6-phase AI analysis pipeline
- **RAGRetriever**: Indexes code and retrieves semantically relevant chunks
- **AnalysisDataCollector**: Captures and persists all analysis data to Supabase
- **PromptLoader**: Loads analysis prompts from `prompts.json`

#### Architecture Enforcement
- **ArchitectureOrchestrator**: Plans and coordinates analysis workers
- **ArchitectureResolver**: Merges reference and learned architectures
- **ArchitectureExtractor**: Parses blueprints into structured rules
- **ValidationWorker**: Validates code against architecture rules
- **AgentFileGenerator**: Creates CLAUDE.md and Cursor rules

#### Key Files
- `backend/prompts.json` - All AI prompts for each analysis phase
- `backend/src/application/services/phased_blueprint_generator.py` - Main analysis orchestration
- `backend/src/infrastructure/analysis/rag_retriever.py` - RAG indexing and retrieval
- `backend/src/application/services/analysis_data_collector.py` - Analysis data persistence

### Customizing Analysis Prompts

The AI prompts for each phase are defined in `backend/prompts.json`. You can customize:
- What each phase analyzes
- The output format (JSON structure)
- The final blueprint structure

Example prompt structure:
```json
{
  "prompts": {
    "discovery": {
      "name": "Discovery Analysis",
      "category": "discovery",
      "prompt_template": "You are analyzing a codebase...\n{repository_name}\n{file_tree}...",
      "variables": ["repository_name", "file_tree", "dependencies", "config_files"]
    }
  }
}
```

See `backend/prompts.json` for all available prompts and their variables.

# Archie Deep Scan — Comprehensive Architecture Baseline

Run a comprehensive architecture analysis. Produces full blueprint, per-folder CLAUDE.md, rules, and health metrics.

**Modes:**
- `/archie-deep-scan` — full baseline from step 1 (default, proven workflow)
- `/archie-deep-scan --incremental` — only process files changed since last deep scan (fast, 3-6 min)
- `/archie-deep-scan --from N` — resume from step N (runs N through 9)
- `/archie-deep-scan --continue` — resume from where the last run stopped

**Prerequisites:** Run `npx @bitraptors/archie` first to install the scripts. If `.archie/scanner.py` doesn't exist, tell the user to run `npx @bitraptors/archie` and try again.

**CRITICAL CONSTRAINT: Never write inline Python.**
Do NOT use `python3 -c "..."` or any ad-hoc scripting to inspect, parse, or transform JSON. Every operation has a dedicated command:
- Normalize blueprint: `python3 .archie/finalize.py "$PROJECT_ROOT" --normalize-only`
- Append health history: `python3 .archie/measure_health.py "$PROJECT_ROOT" --append-history --scan-type deep`
- Inspect any JSON file: `python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" <filename>`
- Query a specific field: `python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" scan.json --query .frontend_ratio`

If you need data not covered by these commands, proceed without it or ask the user. NEVER improvise Python.

## Preamble: Determine starting step

Check the user's message (ARGUMENTS) for flags:

**If `--from N` is present** (e.g., `/archie-deep-scan --from 5`):
1. Set START_STEP = N (the number after --from)
2. Validate prerequisites exist:
```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" check-prereqs N
```
3. If check fails, tell the user which files are missing and which earlier step to run.
4. If check passes, proceed. Set state:
```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" init
```

**If `--continue` is present:**
1. Read state:
```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" read
```
2. If status is "none" or "completed": print "No interrupted run found. Starting fresh from step 1." Set START_STEP = 1.
3. If status is "in_progress": Set START_STEP = last_completed + 1. Print "Resuming deep scan from step {START_STEP}."

**If `--incremental` is present:**
1. Check if `.archie/blueprint.json` exists. If not: print "No existing blueprint — running full baseline instead." Set SCAN_MODE = "full", START_STEP = 1, and proceed as default.
2. If blueprint exists, detect changes:
```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" detect-changes
```
3. Read the JSON output:
   - If `mode` is "full" (threshold exceeded or no previous scan): print the `reason` and say "Running full baseline." Set SCAN_MODE = "full", START_STEP = 1.
   - If `mode` is "incremental" and `changed_count` is 0: print "No files changed since last deep scan. Nothing to do." Exit.
   - If `mode` is "incremental": Set SCAN_MODE = "incremental". Save `changed_files` and `affected_folders` from the output. Print "Incremental deep scan: N files changed. Analyzing changes only." Set START_STEP = 1.
4. Initialize state:
```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" init
```

**If no flags (default — full baseline):**
1. Set SCAN_MODE = "full"
2. Set START_STEP = 1
3. Initialize fresh state:
```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" init
```

**For every step below:**
- If the step number < START_STEP, skip it entirely.
- If SCAN_MODE is not set, it defaults to "full" (all existing behavior unchanged).
- **Do NOT ask the user any questions during execution. Do NOT offer to skip, reduce scope, or present alternatives for any step. Execute every step fully as documented.**

## Phase 0: Resolve scope

Every run needs to know whether to scan the root, a specific workspace, or a set of workspaces. The choice is persisted in `.archie/archie_config.json` so we ask at most once per project.

### Step A: Read existing config

```bash
python3 .archie/intent_layer.py scan-config "$PWD" read
```

- **Exit 0** → config exists. Parse `scope`, `workspaces`, `monorepo_type` from the JSON. Skip to Step D.
- **Exit 1** → config missing. Go to Step B.

If the user invoked the command with `--reconfigure`, skip Step A entirely and go to Step B.

### Step B: Detect monorepo type + subprojects

```bash
python3 .archie/scanner.py "$PWD" --detect-subprojects
```

Parse `monorepo_type` and count subprojects where `is_root_wrapper` is false.

- **0 or 1 non-wrapper subprojects** → Not a monorepo. Write config as `single`:

  ```bash
  echo '{"scope":"single","monorepo_type":"<detected-type>","workspaces":[]}' \
    | python3 .archie/intent_layer.py scan-config "$PWD" write
  ```

  Skip to Step D.

- **2+ non-wrapper subprojects** → Go to Step C.

### Step C: Interactive scope prompt

Present the user with:

> Found **N workspaces** in this **{monorepo_type}** monorepo:
> 1. {name} ({type}) — {path}
> 2. {name} ({type}) — {path}
> ...
>
> **How do you want to analyze it?**
>
> - **whole** — One unified blueprint treating the monorepo as one product. Workspaces become components; cross-workspace imports become the primary architecture view. Fastest.
> - **per-package** — One blueprint per workspace you pick. Deep detail per package, no product-level view.
> - **hybrid** — Whole blueprint at root + per-workspace blueprints for specific workspaces. Most comprehensive, slowest.
> - **single** — Ignore the workspaces and scan the whole tree as if it were one project. Only use this for small monorepos.

Wait for the user's answer.

- If `whole` or `single` → `WORKSPACES=[]`
- If `per-package` or `hybrid` → ask which workspaces to include. Accept comma-separated numbers (`1,3,5`) or `all`. Resolve to paths relative to `$PWD`.

If `per-package` or `hybrid`, also ask:

> Run the selected workspaces in **parallel** (faster, more agents) or **sequential** (one at a time)?

Persist the chosen config (parallel/sequential lives only in the run itself, not in the config file):

```bash
echo '{"scope":"<chosen>","monorepo_type":"<detected-type>","workspaces":[<array>]}' \
  | python3 .archie/intent_layer.py scan-config "$PWD" write
```

### Step D: Validate

```bash
python3 .archie/intent_layer.py scan-config "$PWD" validate
```

- **Exit 0** → proceed.
- **Exit 1** → workspace drift. Instruct the user to re-run with `--reconfigure`. Stop.

Expose `SCOPE`, `WORKSPACES`, `MONOREPO_TYPE`.

### Execution plan based on SCOPE

- **SCOPE=single** — Set `PROJECT_ROOT="$PWD"` and run Steps 1-9 once. No monorepo awareness.
- **SCOPE=whole** — Set `PROJECT_ROOT="$PWD"` and run Steps 1-9 once, applying the workspace-aware addendum in the Structure agent (Step 3) so each workspace is a top-level component, and the Wave 2 reasoning agent populates `blueprint.workspace_topology`.
- **SCOPE=per-package** — For each path in `WORKSPACES`, set `PROJECT_ROOT="$PWD/<path>"` and run Steps 1-9. Parallel mode spawns one background Agent per workspace (temp files namespaced as `/tmp/archie_sub1_<name>.json`). Sequential mode runs them one after another. After all finish, go to Step 8 / 9 each within its own `PROJECT_ROOT`.
- **SCOPE=hybrid** — Pass 1: run Steps 1-9 at `PROJECT_ROOT="$PWD"` with whole-mode semantics. Pass 2: iterate `WORKSPACES` per-package. Each pass writes its own blueprint under `PROJECT_ROOT/.archie/`.

**IMPORTANT:** The `.archie/*.py` scripts are installed at the REPO ROOT. Always reference them as `.archie/scanner.py` etc. from the repo root. Pass `PROJECT_ROOT` as the first argument when it is not `$PWD`.

---

Run the following steps once per project. In single-project mode, `PROJECT_ROOT` is the repo root. In monorepo mode, `PROJECT_ROOT` is the sub-project directory.

Use `PROJECT_NAME` as the basename of `PROJECT_ROOT` for namespacing temp files (e.g., "gasztroterkepek-android").

## Step 1: Run the scanner

**If START_STEP > 1, skip this step.**

```bash
python3 .archie/scanner.py "$PROJECT_ROOT"
python3 .archie/detect_cycles.py "$PROJECT_ROOT" --full 2>/dev/null
```

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 1
```

## Step 2: Read scan results

**If START_STEP > 2, skip this step.**

Read `$PROJECT_ROOT/.archie/scan.json`. Note total files, detected frameworks, top-level directories, and `frontend_ratio`.

Also read `$PROJECT_ROOT/.archie/dependency_graph.json` if it exists — it provides the resolved directory-level dependency graph with node metrics (in-degree, out-degree, file count) and cycle data. Wave 1 agents can reference this for quantitative dependency analysis.

**UI layer detection:** Only spawn the dedicated UI Layer agent if `frontend_ratio` >= 0.20 (20%+ of source files are UI/frontend). A small SwiftUI menubar or a minor React admin panel in an otherwise backend/CLI/library project does NOT warrant a dedicated UI agent — the Structure agent will cover it.

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 2
```

## Step 3: Spawn analytical agents

**If START_STEP > 3, skip this step.**

### If SCAN_MODE = "incremental":

Spawn a **single Sonnet subagent** (`model: "sonnet"`) with:
- The `changed_files` list (from detect-changes output in preamble)
- The existing `.archie/blueprint_raw.json`
- Skeletons for changed files only (read `.archie/skeletons.json`, filter to only keys matching changed file paths)
- The scan.json import graph

Agent prompt:
> You have the existing architectural blueprint and a list of files that changed since the last analysis. Read the changed files and their context. Report what changed architecturally:
> - New or modified components (name, location, responsibility, depends_on)
> - Changed communication patterns or integrations
> - New technology or dependencies
> - Modified file placement patterns
>
> Return the same JSON structure as the full analysis but ONLY for sections affected by the changes. Omit unchanged sections — they'll be preserved from the existing blueprint.
>
> GROUNDING RULES apply (see below).

Save the agent's complete output to `/tmp/archie_incremental_$PROJECT_NAME.json`.

Then skip to Step 4.

### If SCAN_MODE = "full" (default):

Spawn 3–4 Sonnet subagents in parallel (Agent tool, `model: "sonnet"`), each focused on a different analytical concern. ALL agents read ALL source files under `$PROJECT_ROOT` — they are not split by directory. Each agent gets: the scan.json file_tree, dependencies, config files, and the GROUNDING RULES at the end of this step.

**If `frontend_ratio` >= 0.20, spawn all 4 agents. Otherwise spawn only the first 3 (skip UI Layer).**

---

### Structure agent

> **CRITICAL INSTRUCTIONS:**
> You are analyzing a codebase to understand its architecture. Your goal is to OBSERVE and DESCRIBE what exists, NOT to categorize it into known patterns.
>
> **Workspace-aware addendum (only when `SCOPE === "whole"`):**
> This is a workspace monorepo (`MONOREPO_TYPE={type}`, N workspaces under paths `<workspaces>`). Treat each workspace member as a top-level component in `components.components`:
> - `name` = workspace `name` from its `package.json` (or equivalent for Cargo/Gradle)
> - `location` = workspace directory path relative to `$PROJECT_ROOT`
> - `platform` = inferred from workspace contents (frontend/backend/shared/etc.)
> - `responsibility` = inferred from package `description` + entry points
> - `depends_on` = other workspace members it imports (read its `package.json` dependencies, filter to workspace names)
>
> Additionally produce a top-level `workspace_topology` field:
> ```json
> "workspace_topology": {
>   "type": "{MONOREPO_TYPE}",
>   "members": [{"name": "...", "path": "...", "role": "app|lib|tool"}],
>   "edges": [{"from": "name-a", "to": "name-b", "count": 3}],
>   "cycles": [["a", "b", "a"]],
>   "dependency_magnets": [{"name": "shared", "in_degree": 8}]
> }
> ```
>
> Surface cross-workspace import cycles as `pitfalls` with severity `error`. Surface workspaces with very high fan-in (top quartile of in_degree) as `dependency_magnets`. Reference workspace members by **name** (not path) in all cross-references.

>
> **DO NOT:**
> - Assume this is a "layered architecture", "MVC", "Clean Architecture", or any specific pattern
> - Look for patterns that match your training data
> - Force observations into predefined categories
>
> **DO:**
> - Describe the ACTUAL file organization you see
> - Identify how files relate to each other based on naming and imports
> - Note any conventions unique to this codebase
>
> Read all source files. Analyze the actual structure of this codebase:
>
> ### 1. Project Type & Platforms
> - Identify if this is a monorepo, single app, microservice, serverless, full-stack, library, etc.
> - List ALL platforms found: backend, web-frontend, mobile-ios, mobile-android, desktop, CLI, shared/common
> - List main entry point files for EACH platform (main.py, index.ts, App.tsx, AppDelegate.swift, MainActivity.kt, main.dart, etc.)
> - Document module/package organization approach
>
> ### 2. Components
> Identify main components from actual code — class names, imports, file organization. For each component:
> - **name**: Component name
> - **location**: Directory path (MUST exist in file_tree)
> - **platform**: backend | frontend | shared | ios | android
> - **responsibility**: Describe what the code DOES, not what names suggest. BAD: "Handles business logic". GOOD: "Orchestrates weather data fetching via WeatherProvider, manages profile state, coordinates push notification scheduling". Reference actual class names and services.
> - **depends_on**: From actual import statements
> - **exposes_to**: What other components consume from it
> - **key_interfaces**: Actual method/function names with brief description. For API routes, list ONLY methods actually implemented — do NOT assume CRUD.
> - **key_files**: With descriptions of what each file does (paths MUST exist in file_tree)
>
> ### 3. Layers
> Analyze ALL platforms (backend AND frontend). Only document layers you can clearly identify from:
> 1. Import patterns between directories
> 2. Directory structure and naming
> 3. Actual code organization
>
> **If no clear layers exist**, set structure_type to flat, modular, or feature-based and document the actual structure.
>
> For each layer found, document: name, platform (backend|frontend|shared), location, responsibility (SPECIFIC — reference actual classes), contains (component types), depends_on (from imports), exposes_to, key_files.
>
> Common backend patterns (only if they ACTUALLY exist): Presentation/API (routes, controllers, DTOs), Application/Service (orchestration, use cases), Domain (entities, interfaces), Infrastructure (database, external APIs, caching).
> Common frontend patterns (only if they ACTUALLY exist): Pages/Views, Features/Containers, Components/UI, Hooks/Services, State/Store.
>
> ### 4. Architecture Style
> Describe in plain language. Examples: "Actor-based with message passing", "Event-sourced with CQRS separation", "Feature-sliced with co-located concerns", "Traditional layered with services and repositories", "Functional core with imperative shell" — or describe something completely unique.
>
> ### 5. File Placement & Naming
> - Where do tests, configs, components, services actually live? With naming patterns observed.
> - Search the file_tree for where test files, config files, build output, and generated code actually live. Do NOT assume conventional locations.
> - Document actual naming conventions: PascalCase components, snake_case utils, kebab-case files, etc. With 2-4 examples each.
>
> ### 6. Framework Usage
> Catalog external frameworks/libraries from import statements. For each, note the framework name and usage scope.
>
> Return JSON:
> ```json
> {
>   "meta": {
>     "architecture_style": "plain language description",
>     "platforms": ["backend", "web-frontend"],
>     "executive_summary": "3-5 factual sentences: what this does, primary tech, architecture style. No filler."
>   },
>   "components": {
>     "structure_type": "layered | flat | modular | feature-based",
>     "components": [
>       {"name": "", "location": "", "platform": "", "responsibility": "", "depends_on": [], "exposes_to": [], "key_interfaces": [{"name": "", "methods": [], "description": ""}], "key_files": [{"file": "", "description": ""}]}
>     ]
>   },
>   "architecture_rules": {
>     "file_placement_rules": [
>       {"component_type": "", "naming_pattern": "", "location": "", "example": "", "description": ""}
>     ],
>     "naming_conventions": [
>       {"scope": "", "pattern": "", "examples": [], "description": ""}
>     ]
>   }
> }
> ```

### Patterns agent

> Read all source files. Analyze design patterns and communication across ALL platforms (backend AND frontend).
>
> ### 1. Structural Patterns (identify with concrete examples)
> **Backend:**
> - **Dependency Injection**: How are dependencies wired? Container? Manual? Framework? (@inject, providers, etc.)
> - **Repository**: How is data access abstracted? Interface + implementation? Active Record?
> - **Factory**: How are complex objects created?
> - **Registry/Plugin**: How are multiple implementations managed?
>
> **Frontend:**
> - **Component Composition**: How are UI components composed? HOC? Render props? Hooks? Slots?
> - **Data Fetching**: How is server state managed? React Query? SWR? Apollo? Combine? Coroutines?
> - **State Management**: Global state approach? Context? Redux? Zustand? @Observable? ViewModel+StateFlow? Bloc?
> - **Routing**: File-based? Config-based? NavigationStack? NavGraph?
>
> For each pattern found: pattern name, platform (backend|frontend|shared), implementation description, example file paths.
>
> ### 2. Behavioral Patterns
> - **Service Orchestration**: How are multi-step workflows coordinated?
> - **Streaming**: How are long-running responses handled? SSE? WebSockets? gRPC streams?
> - **Event-Driven**: Are there publish/subscribe patterns? Event buses?
> - **Optimistic Updates**: How are UI updates handled before server confirmation?
> - **State Machines**: Any explicit state machine patterns?
>
> ### 3. Cross-Cutting Patterns
> - **Error Handling**: Custom exceptions? Error boundaries? Global handler? Error mapping? What errors map to what status codes?
> - **Validation**: Where? How? What library? Client-side vs server-side?
> - **Authentication**: JWT? Session? OAuth? Where validated? How propagated to frontend?
> - **Logging**: Structured? What logger? What's logged?
> - **Caching**: What's cached? TTL strategy? Browser cache? Server cache?
>
> For each: concern, approach, location (actual file paths).
>
> ### 4. Internal Communication
> - **Backend**: Direct method calls between layers, in-process events, message buses
> - **Frontend**: Props, Context, event emitters, pub/sub, state management stores
> - **Cross-Platform**: API calls from frontend to backend, shared types/contracts
>
> ### 5. External Communication
> - **HTTP/REST**: External API calls (both backend-to-external and frontend-to-backend)
> - **Message Queue**: Async job processing (Redis, RabbitMQ, etc.)
> - **Streaming**: SSE, WebSockets, gRPC streams
> - **Database**: Query patterns, transactions, ORM usage
> - **Real-time**: Push notifications, live updates
>
> ### 6. Third-Party Integrations
> List ALL external services with: service name, purpose, integration point (file path).
> Categories: AI/LLM providers, payment processors, auth providers, storage services, analytics/monitoring, CDN/asset hosting.
>
> ### 7. Frontend-Backend Contract
> - How do frontend and backend communicate? (REST, GraphQL, tRPC, WebSocket, etc.)
> - Are types shared between frontend and backend?
> - How are API errors propagated to the UI?
>
> ### 8. Pattern Selection Guide
> For common scenarios in this codebase, which pattern should be used and why?
>
> Return JSON:
> ```json
> {
>   "communication": {
>     "patterns": [
>       {"name": "", "when_to_use": "", "how_it_works": "", "examples": []}
>     ],
>     "integrations": [
>       {"service": "", "purpose": "", "integration_point": ""}
>     ],
>     "pattern_selection_guide": [
>       {"scenario": "", "pattern": "", "rationale": ""}
>     ]
>   },
>   "quick_reference": {
>     "pattern_selection": {"scenario": "pattern"},
>     "error_mapping": [{"error": "", "status_code": 0, "description": ""}]
>   }
> }
> ```

### Technology agent

> Read config files, package.json/requirements.txt/Gemfile/build.gradle/pubspec.yaml/Package.swift, CI/CD configs, Dockerfiles, cloud platform files. Create a complete technology inventory.
>
> ### 1. Full Stack Inventory (by category)
> For each technology include: category, name, version, purpose, platform (backend|frontend|shared).
>
> Categories to check:
> 1. **Runtime**: Language, version, runtime environment (for each platform)
> 2. **Backend Framework**: Web framework, version, key features used
> 3. **Frontend Framework**: UI framework/library, version, rendering strategy
> 4. **Database**: Type, ORM/query builder, version
> 5. **Cache**: Redis, Memcached, in-memory, browser cache, etc.
> 6. **Queue**: Celery, RabbitMQ, ARQ, Redis Queue, etc.
> 7. **AI/ML**: Providers (OpenAI, Anthropic, etc.), SDKs, models
> 8. **Auth**: Library, provider, JWT/session handling
> 9. **State Management**: Frontend state (Redux, Zustand, React Query, etc.)
> 10. **Styling**: CSS framework, component library
> 11. **Validation**: Library, approach
> 12. **Testing**: Framework, tools, coverage approach (for each platform)
> 13. **Linting/Formatting**: Tools, configuration
> 14. **Monitoring**: Logging, metrics, error tracking
>
> ### 2. Run Commands
> From package.json scripts, Makefile, Rakefile, etc. Map command name to command string.
>
> ### 3. Project Structure
> ASCII directory tree from scan.json showing top-level organization.
>
> ### 4. Templates
> Common file patterns — how to create a new component/route/service/test in this codebase. Include file_path_template, component_type, description, and a brief code skeleton (max 3 lines).
>
> ### 5. Deployment Detection (CRITICAL — check for ALL of these)
> - **Cloud provider**: GCP (app.yaml, cloudbuild.yaml, google-cloud-* deps, firebase.json), AWS (boto3, aws-cdk, serverless.yml, buildspec.yml, template.yaml), Azure (azure-* SDKs, azure-pipelines.yml, host.json), Vercel (vercel.json), Netlify (netlify.toml), Fly.io (fly.toml), Railway (railway.json), Render (render.yaml)
> - **Compute**: Cloud Run, App Engine, Lambda, EC2, Fargate, Azure Functions, Vercel Edge, Heroku dynos
> - **Container**: Docker (Dockerfile, .dockerignore), Podman; orchestration (Kubernetes, Docker Compose, ECS, Helm, skaffold)
> - **Serverless**: Cloud Functions, Lambda, Edge Functions, Vercel Serverless
> - **CI/CD**: GitHub Actions (.github/workflows/), Cloud Build (cloudbuild.yaml), GitLab CI (.gitlab-ci.yml), CircleCI, Jenkins, Fastlane (Fastfile), Bitrise
> - **Distribution**: App Store, Google Play, npm registry, PyPI, Docker Hub, Maven Central, CocoaPods, pub.dev, Homebrew, APK sideload
> - **IaC**: Terraform (*.tf), CloudFormation/SAM (template.yaml), Pulumi, Helm charts
> - **Supporting services**: Firebase, Supabase, Redis Cloud, managed databases, CDNs, object storage (GCS, S3)
> - **Environment config**: .env files, Secret Manager, SSM Parameter Store, Vault, config maps
> - **Mobile-specific**: Backend services (BaaS), push notification providers, analytics, OTA updates, app signing
> - **Library-specific**: Package registry, build/publish pipeline, versioning strategy
> - List all deployment-related KEY FILES found in the repository
>
> ### 6. Development Rules
> Imperative rules inferred from tooling config. Each MUST cite a source file.
>
> Sources to check:
> - Package manager lockfiles (poetry.lock, yarn.lock, pnpm-lock.yaml)
> - Pre-commit/quality checks (.pre-commit-config.yaml, husky, lint-staged)
> - CI enforcement (.github/workflows/, Makefile, tox.ini)
> - Linting/formatting mandates (ruff.toml, .eslintrc, prettier, editorconfig)
> - Environment setup (setup.sh, Makefile, docker-compose.yml, .env.example)
> - Testing requirements (CI configs, pytest.ini, jest.config)
> - Git conventions (.gitignore, commit hooks, branch protection)
>
> State each as: "Always X" or "Never Y", cite the source file.
>
> **CRITICAL**: Every rule MUST be specific to THIS project. Generic rules are WORTHLESS.
> GOOD: "Always register new routes in api/app.py — uses explicit include_router()" (source: api/app.py)
> GOOD: "Never import from infrastructure/ in domain/ — dependency rule enforced by layer structure" (source: directory layout)
> BAD: "Use descriptive variable names", "Follow SOLID principles", "Write unit tests"
>
> Return JSON:
> ```json
> {
>   "technology": {
>     "stack": [{"category": "", "name": "", "version": "", "purpose": ""}],
>     "run_commands": {"command_name": "command_string"},
>     "project_structure": "ASCII tree",
>     "templates": [{"component_type": "", "description": "", "file_path_template": "", "code": ""}]
>   },
>   "deployment": {
>     "runtime_environment": "GCP|AWS|Azure|Vercel|on-device|browser|self-hosted",
>     "compute_services": [],
>     "container_runtime": "Docker|Podman|none",
>     "orchestration": "Kubernetes|Docker Compose|ECS|none",
>     "serverless_functions": "Cloud Functions|Lambda|Edge Functions|none",
>     "ci_cd": [],
>     "distribution": [],
>     "infrastructure_as_code": "Terraform|CloudFormation|Pulumi|none",
>     "supporting_services": [],
>     "environment_config": "",
>     "key_files": []
>   },
>   "development_rules": [
>     {"category": "dependency_management|testing|code_style|ci_cd|environment|git", "rule": "Always/Never ...", "source": "file_that_proves_it"}
>   ]
> }
> ```

### UI Layer agent (only if `frontend_ratio` >= 0.20)

> Read all UI/frontend source files. This codebase contains a significant UI layer. Analyze it as ONE ASPECT of the project — do NOT label the entire project as a "frontend app" or "iOS app" if the UI is only part of a larger system. Adapt each section to the platform detected.
>
> ### 1. Framework & Rendering
> - **Web**: What UI framework? (React, Vue, Angular, Svelte, etc.) Rendering strategy? (SSR, SSG, CSR, ISR, hybrid) Meta-framework? (Next.js, Nuxt, Remix, etc.)
> - **iOS**: Declarative (SwiftUI) vs imperative (UIKit)? App architecture? (MVVM, VIPER, Clean Swift, etc.)
> - **Android**: Jetpack Compose vs XML layouts? Architecture? (MVVM, MVI, Clean Architecture?)
> - **Cross-platform**: Framework? (Flutter, React Native, KMP, etc.) Platform-specific bridging?
>
> ### 2. UI Components
> For each major component/screen/view:
> - **name** and **location** (must exist in file_tree)
> - **component_type**: screen | page | layout | feature | shared | primitive | widget
> - **description**: What it renders and its purpose
> - **props**/inputs/parameters
> - **children**: Child components it renders or embeds
>
> ### 3. State Management
> - **Web**: Global state (Context, Redux, Zustand, Recoil), server state (React Query, SWR, Apollo), local state, form state
> - **iOS**: @State, @Observable, @EnvironmentObject, Combine, MVVM with ObservableObject, @Published
> - **Android**: ViewModel + StateFlow/LiveData, Compose state (remember/mutableStateOf), MVI pattern, SavedStateHandle
> - **Cross-platform**: Platform-specific (Bloc, Riverpod, Provider for Flutter; Redux/MobX for RN)
>
> Document: approach, global_state stores with purposes, server_state mechanism, local_state approach, and rationale for the choices.
>
> ### 4. Routing / Navigation
> - **Web**: File-based or config-based? List routes with paths, components, descriptions, auth requirements, dynamic segments.
> - **iOS**: NavigationStack, UINavigationController, Coordinator pattern, TabBar, deep links
> - **Android**: Navigation Component (NavHost/NavGraph), bottom navigation, deep links, Intent-based
> - **Cross-platform**: Navigator/Router, tab/stack/drawer navigation
>
> ### 5. Data Fetching / Networking
> - **Web**: Data fetching hooks/patterns, loading/error states, caching strategy
> - **iOS**: URLSession, Alamofire, Moya; Combine/async-await patterns; offline support
> - **Android**: Retrofit, Ktor, OkHttp; Coroutine/Flow patterns; offline support (Room + network)
> - **Cross-platform**: Dio/http for Flutter; fetch/axios for RN; Ktor for KMP
>
> ### 6. Styling / Theming
> - **Web**: Tailwind, CSS Modules, Styled Components, component library, design tokens
> - **iOS**: SwiftUI modifiers, UIKit programmatic styling, Interface Builder, custom themes
> - **Android**: Compose theming/Material3, XML themes, Material Components, custom design system
> - **Cross-platform**: Flutter ThemeData, RN StyleSheet, shared design tokens
>
> ### 7. Key Conventions
> - File naming conventions for components/screens/views
> - Component organization (co-located, feature-based, atomic, module-based)
> - Custom hooks/extensions/utilities naming and organization
> - Test file placement
>
> Return JSON:
> ```json
> {
>   "frontend": {
>     "framework": "",
>     "rendering_strategy": "SSR | SSG | CSR | ISR | hybrid | declarative | imperative",
>     "ui_components": [
>       {"name": "", "location": "", "component_type": "", "description": "", "props": [], "children": []}
>     ],
>     "state_management": {
>       "approach": "",
>       "global_state": [{"store": "", "purpose": ""}],
>       "server_state": "",
>       "local_state": "",
>       "rationale": ""
>     },
>     "routing": [
>       {"path": "", "component": "", "description": "", "auth_required": false}
>     ],
>     "data_fetching": [
>       {"name": "", "mechanism": "", "when_to_use": "", "examples": []}
>     ],
>     "styling": "",
>     "key_conventions": []
>   }
> }
> ```

---

**Every agent also gets these GROUNDING RULES:**

> **GROUNDING RULES — every claim must come from code you READ, never from names or conventions.**
> This applies to ANY codebase — web, mobile, desktop, backend, CLI, library, any language.
>
> 1. **Paths**: Only reference file/directory paths that appear in scan.json file_tree. Do NOT infer conventional paths — every framework has different conventions (Rails uses `spec/`, Go uses `_test.go` files, Swift uses `Tests/`, etc.). Find the ACTUAL paths by reading the code.
> 2. **Component responsibility**: Read the actual source file. Describe what the code DOES, not what the filename or class name suggests. A file named `Publisher.swift` might only subscribe to events. A class named `UserManager` might only read, never write. Only the code tells you which.
> 3. **API/route/endpoint methods**: Read the actual handler code. List ONLY the methods/verbs/actions that are actually implemented. Do NOT assume CRUD from the resource name — a "presets" endpoint might support GET+PUT but not POST. This applies to HTTP routes, gRPC services, GraphQL resolvers, CLI commands, or any interface.
> 4. **File placement rules**: Search the file_tree for where test files, config files, build output, and generated code actually live. Do NOT assume conventional locations — the project might put tests alongside source, in a top-level `test/` dir, or anywhere else.
> 5. **Pitfalls**: Only describe problems grounded in actual code patterns you observed. Describe what the code DOES and the risks of THAT pattern. Do NOT recommend alternatives the code doesn't use as if it does.
> 6. **Build/output paths**: Read the build config, generation logic, or Makefile to find where output is actually written. Do NOT assume any framework's default output directory.
>
> **The rule is simple: if you didn't read it in a file, don't claim it.** Focus on cross-file relationships, architecture decisions, conventions, and integration patterns. Return ONLY valid JSON.

**Spawn ALL agents in parallel.**

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 3
```

## Step 4: Save Wave 1 output and merge

**If START_STEP > 4, skip this step.**

### If SCAN_MODE = "incremental":

The single incremental agent's output was saved to `/tmp/archie_incremental_$PROJECT_NAME.json` in Step 3. Patch the existing blueprint:

```bash
python3 .archie/merge.py "$PROJECT_ROOT" --patch /tmp/archie_incremental_$PROJECT_NAME.json
```

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 3
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 4
```

### If SCAN_MODE = "full" (default):

**If resuming via --from or --continue:** Step 4 depends on Wave 1 agent outputs in /tmp/. These may not survive a system reboot. If merge fails with missing files, re-run from step 3: `/archie-deep-scan --from 3`

After each subagent completes, use the Write tool to save its COMPLETE output text to a temporary file. The merge script handles JSON extraction automatically — it can parse plain JSON, code-fenced JSON, and conversation envelopes.

**IMPORTANT: Save the COMPLETE raw text from each agent. Do NOT try to extract JSON yourself — the script handles all extraction including conversation envelopes, code fences, and escape issues.**

```
Write /tmp/archie_sub1_$PROJECT_NAME.json with Structure agent's COMPLETE output text
Write /tmp/archie_sub2_$PROJECT_NAME.json with Patterns agent's COMPLETE output text
Write /tmp/archie_sub3_$PROJECT_NAME.json with Technology agent's COMPLETE output text
Write /tmp/archie_sub4_$PROJECT_NAME.json with UI Layer agent's COMPLETE output text (if spawned)
```

Then merge:

```bash
python3 .archie/merge.py "$PROJECT_ROOT" /tmp/archie_sub1_$PROJECT_NAME.json /tmp/archie_sub2_$PROJECT_NAME.json /tmp/archie_sub3_$PROJECT_NAME.json /tmp/archie_sub4_$PROJECT_NAME.json
```

This saves `$PROJECT_ROOT/.archie/blueprint_raw.json` (raw merged data). Verify the output shows non-zero component/section counts. If it says "0 sections, 0 components", the merge failed — check the agent output files.

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 4
```

## Step 5: Wave 2 — Reasoning agent

**If START_STEP > 5, skip this step.**

### If SCAN_MODE = "incremental":

Spawn an **Opus subagent** (`model: "opus"`) with scoped context:
- The existing `$PROJECT_ROOT/.archie/blueprint.json` (full current architecture)
- The patched `$PROJECT_ROOT/.archie/blueprint_raw.json` (with incremental changes from Step 4)
- The changed file contents (from `changed_files` list)

Tell the scoped Reasoning agent:

> The architecture was previously analyzed (blueprint.json attached). The blueprint_raw.json was updated with incremental structural changes. These specific files changed: [list changed_files]. Review the changes and update ONLY the affected sections:
> - If changes affect a key decision, update it
> - If changes introduce a new trade-off or invalidate one, update trade_offs
> - If changes trigger or resolve a pitfall, update pitfalls
> - Update the decision_chain only for affected branches
> Return ONLY the sections that need updating — unchanged sections will be preserved.

Save output and finalize with patch mode:
```
Write /tmp/archie_sub_x_$PROJECT_NAME.json with the Reasoning agent's COMPLETE output text
```
```bash
python3 .archie/finalize.py "$PROJECT_ROOT" --patch /tmp/archie_sub_x_$PROJECT_NAME.json
```
```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 5
```

Then skip to Step 6.

### If SCAN_MODE = "full" (default):

Wave 1 gathered facts: components, patterns, technology, deployment, UI layer. Now spawn a single Opus subagent (`model: "opus"`) that reads ALL Wave 1 output and produces deep architectural reasoning.

Tell the Reasoning agent:

> Read `$PROJECT_ROOT/.archie/blueprint_raw.json` — it contains the full analysis from Wave 1 agents: components, communication patterns, technology stack, deployment, frontend. Also read key source files: entry points, main configs, core abstractions.
>
> With the COMPLETE picture of what was built and how, produce deep architectural reasoning:
>
> ### 1. Decision Chain
> Trace the root constraint(s) that shaped this architecture. Build a dependency tree:
> - What is the ROOT constraint? (e.g., "local-first tool requiring filesystem access")
> - What does it FORCE? (each forced decision)
> - What does EACH forced decision FORCE in turn?
> - Continue until you reach leaf decisions
> - For EACH node, include `violation_keywords`: specific code patterns or package names that would violate this decision (e.g., for "SQLite only" → `["pg", "mongoose", "prisma", "typeorm", "postgres"]`)
>
> Every decision in the chain must be grounded in code you can see in the blueprint or source files. Do NOT invent theoretical constraints.
>
> ### 2. Architectural Style Decision
> THE top-level architecture choice. You can see the full component list, pattern list, and tech stack — explain WHY this architecture, not just WHAT. Reference specific components and patterns from the blueprint.
> - **title**: e.g., "Full-stack monolith with subprocess orchestration"
> - **chosen**: What was chosen and how it manifests
> - **rationale**: WHY — reference specific components, patterns, and tech stack items from the blueprint
> - **alternatives_rejected**: What alternatives were NOT chosen and WHY they were ruled out by the constraints
>
> ### 3. Key Decisions (3-7)
> Each with: title, chosen, rationale, alternatives_rejected.
> - **rationale** must reference specific components, patterns, or tech from the blueprint
> - **forced_by**: What constraint or other decision made this one necessary
> - **enables**: What this decision makes possible downstream
>
> ### 4. Trade-offs (3-5)
> Each with: accept, benefit, caused_by (which decision created this trade-off), violation_signals (code patterns that would indicate someone is undoing this trade-off, e.g., removing Puppeteer → `["uninstall puppeteer", "remove puppeteer", "playwright"]`)
>
> ### 5. Out-of-Scope
> What this codebase does NOT do. For each item, optionally note which decision makes it out of scope.
>
> ### 6. Pitfalls (3-5)
> Each with:
> - **area**, **description**, **recommendation**
> - **stems_from**: NOT just a label — the FULL causal chain as an array. Example: `["local-first constraint", "chose SQLite for zero-config", "singleton pattern in db.ts", "no connection recovery on corruption"]`. Each element is a step in the chain from root decision to pitfall.
> - **applies_to**: file paths where this pitfall is relevant
>
> Only describe problems grounded in actual code. Do NOT recommend alternatives the code doesn't use.
>
> ### 7. Architecture Diagram
> Mermaid `graph TD` with 8-12 nodes. You have the full component list and communication patterns from the blueprint — use actual component names and real data flows.
>
> ### 8. Implementation Guidelines (5-8)
> Capabilities using third-party libraries. Cross-reference the tech stack and pattern list from the blueprint. For each:
> - **capability**: Human-readable name
> - **category**: auth | notifications | media | storage | networking | analytics | persistence | ui | payments | location | state_management | navigation | testing
> - **libraries**: Libraries used with versions (from tech stack)
> - **pattern_description**: Architecture pattern, main service/class, data flow
> - **key_files**: Actual file paths (MUST exist in file_tree)
> - **usage_example**: Realistic code snippet. A single line is fine when the pattern genuinely is one-line (`logger.track(Event.X)`). Multi-line (typically 3-10 lines) when clarity demands it — use real newlines, not `;` chains. Show the full pattern a developer would actually write.
> - **tips**: Gotchas specific to this implementation
>
> Return JSON:
> ```json
> {
>   "decisions": {
>     "architectural_style": {"title": "", "chosen": "", "rationale": "", "alternatives_rejected": []},
>     "key_decisions": [{"title": "", "chosen": "", "rationale": "", "alternatives_rejected": [], "forced_by": "", "enables": ""}],
>     "trade_offs": [{"accept": "", "benefit": "", "caused_by": "", "violation_signals": []}],
>     "out_of_scope": [],
>     "decision_chain": {"root": "", "forces": [{"decision": "", "rationale": "", "violation_keywords": [], "forces": []}]}
>   },
>   "pitfalls": [{"area": "", "description": "", "recommendation": "", "stems_from": ["causal", "chain", "steps"], "applies_to": []}],
>   "architecture_diagram": "graph TD\n  A[...] --> B[...]",
>   "implementation_guidelines": [
>     {"capability": "", "category": "", "libraries": [], "pattern_description": "", "key_files": [], "usage_example": "", "tips": []}
>   ]
> }
> ```

The Reasoning agent also gets the GROUNDING RULES from Step 3.

After the Reasoning agent completes, save its output and finalize:

```
Write /tmp/archie_sub_x_$PROJECT_NAME.json with the Reasoning agent's output
```

```bash
python3 .archie/finalize.py "$PROJECT_ROOT" /tmp/archie_sub_x_$PROJECT_NAME.json
```

This single command: merges the Reasoning agent's output into the blueprint, normalizes the schema, renders CLAUDE.md + AGENTS.md + rule files, installs hooks, and validates. Review the validation output — warnings are informational, not blocking.

After finalize completes, regenerate the dependency graph (the blueprint now has component definitions, which enables cross-component edge detection):

```bash
python3 .archie/detect_cycles.py "$PROJECT_ROOT" --full 2>/dev/null
```

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 5
```

## Step 6: AI Rule Synthesis

**If START_STEP > 6, skip this step.**

### If SCAN_MODE = "incremental":

The blueprint was patched in Step 5. Spawn a **Sonnet subagent** (`model: "sonnet"`) with this additional instruction prepended to the standard prompt below:

> The existing rules are in `.archie/rules.json`. Only propose rules for patterns discovered in the changed files. Do not regenerate existing rules. If a change invalidates an existing rule, flag it with `"status": "invalidated"` in the output.

### All modes (full and incremental):

The blueprint contains architectural facts. This step synthesizes them into **architectural rules** — insights that the AI reviewer uses to evaluate plans and code changes.

Spawn a **Sonnet subagent** (`model: "sonnet"`) with this prompt:

> Read `$PROJECT_ROOT/.archie/blueprint.json` ONCE (do not re-read it). It contains the full architecture: components, decisions (with decision chains and violation keywords), patterns, trade-offs (with violation signals), pitfalls (with causal chains), technology stack, and development rules.
>
> Produce 20-40 architectural rules. Each rule captures an architectural insight that a coding agent must respect when planning or making changes.
>
> **Primary enforcement is AI-powered:** the AI reviewer reads each rule's `rationale` on every plan approval and pre-commit, and evaluates whether changes violate the rule's *intent*.
>
> **Secondary enforcement is mechanical (optional):** if a rule can also be expressed as a regex, add `check` + `forbidden_patterns`/`required_in_content` fields so the pre-edit hook catches obvious violations instantly. Most rules won't have this — that's fine. Don't force regex where it doesn't fit.
>
> Return ONLY valid JSON: `{"rules": [...]}`.
>
> ## Rule schema
>
> **Required fields** (every rule):
> ```json
> {"id": "dep-001", "description": "What is forbidden/required", "rationale": "Why — the architectural reasoning chain", "severity": "error|warn"}
> ```
>
> **Optional mechanical fields** (add ONLY when a meaningful regex exists):
> - `"check"`: one of `forbidden_import`, `required_pattern`, `forbidden_content`, `architectural_constraint`
> - `"applies_to"`: directory prefix scope
> - `"file_pattern"`: glob matched against filename
> - `"forbidden_patterns"`: regex patterns that violate the rule
> - `"required_in_content"`: strings that must appear in matching files
>
> When `check` is present:
> - `forbidden_import`: requires `applies_to` + `forbidden_patterns`
> - `required_pattern`: requires `file_pattern` + `required_in_content`
> - `forbidden_content`: requires `forbidden_patterns`, optional `applies_to`
> - `architectural_constraint`: requires `file_pattern` + `forbidden_patterns`
>
> ## The `rationale` field (REQUIRED — this is the most important field)
>
> This tells the AI reviewer WHY this rule exists — the architectural reasoning chain. Write 1-3 sentences tracing the constraint back to a root decision, trade-off, or pitfall from the blueprint. Examples:
> - "We chose SQLite for the local-first constraint. Introducing any ORM or remote database would undermine the zero-config deployment model and force connection management the architecture doesn't support."
> - "ViewModels must stay framework-agnostic because the decision chain roots in testability — if a ViewModel references Android Context, it can't be unit-tested without instrumentation, which breaks the fast-feedback development loop."
> - "Feature modules are isolated to enable independent deployment. Cross-feature imports create hidden coupling that prevents releasing features independently."
>
> ## Examples
>
> Rationale-only rule (most rules will look like this):
> ```json
> {"id": "arch-001", "description": "Business logic must not depend on UI framework classes", "rationale": "The decision chain roots in testability. Business logic that references framework classes can't be unit-tested without instrumentation, which breaks the fast-feedback loop and makes refactoring risky.", "severity": "error"}
> ```
>
> Rule with optional mechanical enforcement:
> ```json
> {"id": "dep-001", "description": "Domain layer must not import from presentation layer", "rationale": "The domain is the stable core. UI depends on domain, never the reverse. Inverting this makes every UI refactor a domain change.", "severity": "error", "check": "forbidden_import", "applies_to": "domain/", "forbidden_patterns": ["from presentation", "import.*\\.ui\\."]}
> ```
>
> ## What to produce:
>
> **Deep architectural rules** — invariants an AI coding agent might accidentally violate. These are the most valuable. Derive them from decision chains, trade-offs, pitfalls, and pattern descriptions. Examples: "ViewModel must never reference View/Context", "Repository must use IO dispatcher", "Fragments must use DI delegation not direct construction".
>
> **Structural rules** — dependency direction between layers/components, forbidden technologies (from decisions/trade-offs).
>
> ## Critical:
> - Every rule must be specific to THIS project — never generic programming advice
> - Focus on what an AI coding agent would get wrong without knowing this codebase
> - If you include `forbidden_patterns`, every entry must be a valid regex
> - Include an `"id"` field for each rule (e.g., "dep-001", "arch-001", "ban-001")
> - The `description` must explain WHAT is forbidden in one sentence
> - The `rationale` must explain WHY — trace it back to a decision, trade-off, or pitfall from the blueprint
> - Do NOT force mechanical fields — if the insight is "don't put orchestration logic in repositories", that's a rationale-only rule

**IMPORTANT: If `.archie/rules.json` already exists (from previous scans), read it first. The new rules must be MERGED with existing rules — do not overwrite user-adopted rules.**

After the agent responds, save its COMPLETE output text to a temp file and extract:

```
Write /tmp/archie_rules_$PROJECT_NAME.json with the agent's COMPLETE output text
```

```bash
python3 .archie/extract_output.py rules /tmp/archie_rules_$PROJECT_NAME.json "$PROJECT_ROOT/.archie/rules.json"
```

**IMPORTANT: Do NOT try to extract or parse JSON yourself. Always use the pre-installed scripts.**

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 6
```

## Step 7: Intent Layer — per-folder CLAUDE.md

**If START_STEP > 7, skip this step.**

This step generates per-folder CLAUDE.md files with AI-generated architectural descriptions using bottom-up DAG scheduling. State is tracked automatically in `.archie/enrich_state.json`.

**Execute this step fully. Do NOT ask the user whether to run, skip, or reduce scope. Do NOT offer alternatives. Run all batches as instructed below.**

### If SCAN_MODE = "incremental":

Only re-enrich folders containing changed files + their parent chain. Unchanged folders keep their existing CLAUDE.md.

1. Prepare with `--only-folders` using the `affected_folders` from the preamble:
```bash
python3 .archie/intent_layer.py prepare "$PROJECT_ROOT" --only-folders AFFECTED_FOLDER1,AFFECTED_FOLDER2,...
python3 .archie/intent_layer.py reset-state "$PROJECT_ROOT"
mkdir -p "$PROJECT_ROOT/.archie/enrichments"
```

Replace `AFFECTED_FOLDER1,AFFECTED_FOLDER2,...` with the comma-separated `affected_folders` list from the detect-changes output. This marks only those folders + their ancestors as dirty. The `next-ready` command will only return dirty folders.

Then proceed with the same wave processing as full mode (step 2 below). The waves will be much smaller since only dirty folders are included.

### If SCAN_MODE = "full" (default):

1. Prepare the folder DAG and reset state:
```bash
python3 .archie/intent_layer.py prepare "$PROJECT_ROOT"
python3 .archie/intent_layer.py reset-state "$PROJECT_ROOT"
mkdir -p "$PROJECT_ROOT/.archie/enrichments"
```

2. Process in readiness waves. The script tracks done folders automatically.

   **Repeat until done:**

   a. Get ready folders:
   ```bash
   python3 .archie/intent_layer.py next-ready "$PROJECT_ROOT"
   ```
   The script reads done state from `.archie/enrich_state.json` automatically. First call returns all leaf folders.

   b. If the ready list is empty (`[]`), all folders are done. Proceed to step 3.

   c. Get batches for the ready folders:
   ```bash
   python3 .archie/intent_layer.py suggest-batches "$PROJECT_ROOT" <ready1> <ready2> ...
   ```
   Output is JSON array: `[{"id": "w0", "folders": [...]}, ...]`. Use `id` (NOT `batch_id`) to reference batches. Do NOT write ad-hoc Python to inspect this — use the output directly.

   d. For each batch, generate the prompt and spawn a subagent:
   ```bash
   python3 .archie/intent_layer.py prompt "$PROJECT_ROOT" --folders <comma-separated> --child-summaries "$PROJECT_ROOT/.archie/enrichments/" > /tmp/archie_intent_prompt_$PROJECT_NAME.txt
   ```
   Read the prompt file. Spawn a Sonnet subagent (`model: "sonnet"`) with the prompt content. The subagent must return ONLY valid JSON with folder paths as keys.
   **Spawn ALL batches in a wave in parallel.**

   e. After each subagent completes, save its COMPLETE output text to a temp file, then use the save-enrichment command to extract JSON and mark folders as done:
   ```
   Write /tmp/archie_enrichment_<batch_id>.json with the subagent's COMPLETE output text
   ```
   ```bash
   python3 .archie/intent_layer.py save-enrichment "$PROJECT_ROOT" <batch_id> /tmp/archie_enrichment_<batch_id>.json
   ```
   This extracts the JSON, saves it to `.archie/enrichments/<batch_id>.json`, and automatically marks the folders as done.

   **IMPORTANT: Do NOT try to extract or parse JSON yourself. Do NOT write inline Python to process agent output. The save-enrichment command handles everything including conversation envelopes, code fences, multi-block merging, and escape issues.**

   f. Go to (a) for the next wave.

3. Merge enrichments into CLAUDE.md files:
```bash
python3 .archie/intent_layer.py merge "$PROJECT_ROOT"
```

---

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 7
```

## Step 8: Clean up

**If START_STEP > 8, skip this step.**

```bash
rm -f /tmp/archie_sub*_$PROJECT_NAME.json /tmp/archie_rules_$PROJECT_NAME.json /tmp/archie_intent_prompt_$PROJECT_NAME.txt /tmp/archie_enrichment_*.json
```

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 8
```

## Step 9: Drift Detection & Architectural Assessment

**If START_STEP > 9, skip this step.**

### Phase 0: Health measurement

```bash
python3 .archie/measure_health.py "$PROJECT_ROOT" > "$PROJECT_ROOT/.archie/health.json" 2>/dev/null
```

Save health scores to history for trending:

```bash
python3 .archie/measure_health.py "$PROJECT_ROOT" --append-history --scan-type deep
```

### Phase 1: Mechanical drift scan

```bash
python3 .archie/drift.py "$PROJECT_ROOT"
```

### Phase 2: Deep architectural drift (AI)

Identify files to analyze:
```bash
git -C "$PROJECT_ROOT" log --name-only --pretty=format: --since="30 days ago" -- '*.kt' '*.java' '*.swift' '*.ts' '*.tsx' '*.py' '*.go' '*.rs' | sort -u | head -100
```
If that returns nothing (new repo or no recent changes), use all source files from the scan:
```bash
python3 .archie/extract_output.py recent-files "$PROJECT_ROOT/.archie/scan.json"
```

For each file (batch into groups of ~15), collect:
- The file's content
- Its folder's CLAUDE.md **if it exists** (per-folder patterns, anti-patterns — these were generated in Step 7, but may be missing if Step 7 was skipped or partially completed)
- Its parent folder's CLAUDE.md **if it exists**

Read `$PROJECT_ROOT/.archie/blueprint.json` — specifically `decisions.key_decisions`, `decisions.decision_chain`, `decisions.trade_offs` (with `violation_signals`), `pitfalls` (with `stems_from`), `communication.patterns`, `development_rules`.

Read `$PROJECT_ROOT/.archie/drift_report.json` (mechanical findings from Phase 1).

Spawn a **Sonnet subagent** (`model: "sonnet"`) with the file contents, their folder CLAUDE.md files, and the blueprint context. Tell it:

> You are an architecture reviewer. You have the project's architectural blueprint (decisions, trade-offs, pitfalls, patterns), per-folder CLAUDE.md files describing expected patterns, mechanical drift findings (already detected), and source files to review.
>
> Find **deep architectural violations** — problems that pattern matching cannot catch. For each finding, return:
> - `folder`: the folder path
> - `file`: the specific file
> - `type`: one of `decision_violation`, `pattern_erosion`, `trade_off_undermined`, `pitfall_triggered`, `responsibility_leak`, `abstraction_bypass`, `semantic_duplication`
> - `severity`: `error` or `warn`
> - `decision_or_pattern`: which architectural decision, pattern, or pitfall this violates (reference by name from the blueprint)
> - `evidence`: the specific code (function name, class, line pattern) that demonstrates the violation
> - `message`: one sentence explaining what's wrong and why it matters
>
> Focus on:
> 1. **Decision violations** — code that contradicts a key architectural decision
> 2. **Pattern erosion** — code that doesn't follow the patterns described in its folder's CLAUDE.md
> 3. **Trade-off undermining** — code that works against an accepted trade-off (check `violation_signals`)
> 4. **Pitfall triggers** — code that falls into a documented pitfall (check `stems_from` chains)
> 5. **Responsibility leaks** — a component doing work that belongs to another component
> 6. **Abstraction bypass** — code reaching through a layer instead of using the intended interface
> 7. **Semantic duplication** — functions/methods with different signatures but essentially the same logic. AI agents frequently copy-paste a function, tweak the name/parameters, and leave the body identical or near-identical. Look for: functions with similar names (e.g., `getText`/`getTexts`, `loadUser`/`fetchUser`), functions in different files that do the same thing with slightly different types, helper functions reimplemented instead of shared. For each, use type `semantic_duplication` and explain what's duplicated and which function should be the canonical one.
>
> Do NOT report: style/formatting/naming (the script handles those), generic best-practice violations not grounded in THIS project's blueprint, or issues already in the mechanical drift report.
>
> Return JSON: `{"deep_findings": [...]}`

Save the deep findings:
```
Write /tmp/archie_deep_drift.json with the agent's COMPLETE output text
```
```bash
python3 .archie/extract_output.py deep-drift /tmp/archie_deep_drift.json "$PROJECT_ROOT/.archie/drift_report.json"
rm -f /tmp/archie_deep_drift.json
```

### Phase 3: Present the combined assessment

Read `$PROJECT_ROOT/.archie/blueprint.json` and `$PROJECT_ROOT/.archie/drift_report.json` (now contains both mechanical and deep findings). This is the final output — make it valuable.

#### Part 1: What was generated

List the generated artefacts with counts:
- Blueprint sections populated (out of total)
- Components discovered
- Enforcement rules generated
- Per-folder CLAUDE.md files created
- Rule files in `.claude/rules/`

#### Part 2: Architecture Summary

From the blueprint, summarize in 5-10 lines:
- **Architecture style** (from `meta.architecture_style`)
- **Key components** (top 5-7 from `components.components` — name + one-line responsibility)
- **Technology stack highlights** (from `technology.stack` — framework, language, key libs)
- **Key decisions** (from `decisions.key_decisions` — the 2-3 most impactful, one line each)

#### Part 3: Architecture Health Assessment

Rate and explain each dimension (use these exact labels: Strong / Adequate / Weak / Not assessed):

1. **Separation of concerns** — Are layers/modules clearly bounded? Do components have single responsibilities? Any god classes or circular dependencies?
2. **Dependency direction** — Do dependencies flow in one direction? Are domain/core layers independent of infrastructure? Any inverted or tangled dependencies?
3. **Pattern consistency** — Is the same pattern used consistently across similar components? Are there one-off deviations that break the uniformity?
4. **Testability** — Is the architecture conducive to testing? Can components be tested in isolation? Are external dependencies injectable?
5. **Change impact radius** — When a component changes, how many others are affected? Are changes localised or do they ripple?

Base every rating on actual evidence from the blueprint and drift findings — reference specific components, patterns, or findings. If the blueprint lacks data for a dimension, say "Not assessed" rather than guessing.

#### Part 4: Architectural Drift

Present ALL findings — mechanical and deep together, organized by severity (errors first).

**Deep architectural findings** (from AI analysis):
- For each: the file, which decision/pattern it violates, the evidence, and why it matters
- Group related findings (e.g., multiple files violating the same decision)

**Mechanical findings** (from script):
- Pattern divergences, dependency violations, naming violations, structural outliers, anti-pattern clusters
- For each: what diverged, why it matters, suggested action

If 0 findings, say so — that's a positive signal.

#### Part 5: Top Risks & Recommendations

Synthesize from pitfalls, trade-offs, drift findings (both mechanical and deep), and your observations. List the **3-5 most important architectural risks**, ordered by impact:
- What the risk is (one sentence)
- Where it manifests (specific components/files/drift findings)
- What to watch for going forward

#### Part 6: Semantic Duplication

**This is a critical section.** The mechanical verbosity score (0-1) only catches exact line-for-line clones. AI agents frequently create near-identical functions with slightly different names, signatures, or types — the verbosity metric completely misses these.

Present the `semantic_duplication` findings from the deep drift analysis. If the drift agent found none, **do your own quick check now**: scan the skeletons for functions with similar names (e.g., `getText`/`getTexts`, `loadUser`/`fetchUser`, `formatDate` in multiple files, `handleError` reimplemented per-module). Read suspicious pairs and confirm whether the logic is duplicated.

For each confirmed duplicate group:
- The canonical function (the one that should be the shared version)
- The duplicates: which files, what differs (just the signature? types? minor logic?)
- Whether they could be consolidated

Present in the health table as:
```
| Semantic duplication | N groups found | See Part 6 for details |
```

If genuinely none found after checking, say "No semantic duplication detected after AI analysis."

**Health scores** from Phase 0 have been saved to `.archie/health_history.json` for trending. Note: the verbosity metric is mechanical (exact line clones only) — the semantic duplication analysis in Part 6 above is the AI-powered complement. Run `/archie-scan` regularly to track how these metrics change over time.

### Phase 4: Persist findings to `.archie/scan_report.md`

The Phase 3 synthesis above is valuable but ephemeral — it only exists in the chat output. `/archie-share` (and future trending runs of `/archie-scan`) need the findings on disk. Write the same content to `.archie/scan_report.md` in the format `/archie-scan` produces.

Check whether a prior scan report exists (for resolved/new/recurring classification):
```bash
test -f "$PROJECT_ROOT/.archie/scan_report.md" && echo "PRIOR_REPORT_EXISTS" || echo "FIRST_BASELINE"
```

If `FIRST_BASELINE` (no prior scan_report.md): all findings are tagged **NEW (baseline)**. If `PRIOR_REPORT_EXISTS`: compare against the prior file's Findings section and classify each as **NEW**, **RECURRING**, or **RESOLVED**.

Read `$PROJECT_ROOT/.archie/health.json` for precise numeric values and `$PROJECT_ROOT/.archie/health_history.json` to compute trends (previous run values vs. current).

Write `$PROJECT_ROOT/.archie/scan_report.md` with this exact structure (use the Write tool, do NOT shell-heredoc):

```markdown
# Archie Scan Report
> Deep scan baseline | <today's date in YYYY-MM-DD HH:MM UTC> | <total_functions> functions / <total_loc> LOC analyzed | baseline run

## Architecture Overview

<2-3 paragraphs from Part 2: architecture style, key components, most important decisions. Prose, not bullets.>

## Health Scores

| Metric | Current | Previous | Trend | What it means |
|--------|--------:|---------:|------:|---------------|
| Erosion    | <erosion>    | <prev or "—"> | <up/down/flat> | <one-liner interpretation> |
| Gini       | <gini>       | <prev or "—"> | <trend> | <one-liner> |
| Top-20%    | <top20>      | <prev or "—"> | <trend> | <one-liner> |
| Verbosity  | <verbosity>  | <prev or "—"> | <trend> | <one-liner> |
| LOC        | <total_loc>  | <prev or "—"> | <trend> | <one-liner> |

<one paragraph summarizing what the numbers say together>

### Complexity Trajectory
<short list of the top 5-8 high-CC functions from health.json with file:line and CC values, and what they suggest about risk concentration>

## Findings

Ranked by severity, grouped by novelty.

### NEW (first observed this scan)
<numbered list of findings — each: **[severity] Title.** Description. Confidence N.>

### RECURRING (previously documented, still present)
<only if prior report exists; otherwise omit this subsection>

### RESOLVED
<only if prior report exists; otherwise omit. "None" if nothing resolved.>

## Proposed Rules

<Any new rules proposed by Step 6 synthesis that are not yet in rules.json. Reference proposed_rules.json.>
```

Sources for Findings:
- `drift_report.json` — mechanical and deep drift findings from Phase 1 and 2
- `blueprint.json` — `pitfalls` (each causal chain becomes a finding), `decisions.trade_offs` with violated `violation_signals` (if any appear in drift_report)
- Top complexity offenders from `health.json` (only if CC ≥ 15 or a cluster — don't list every high-CC function as a finding)

Severity mapping:
- `error` — decision violations, inverted dependencies, cycles across architectural boundaries
- `warn` — pattern erosion, god-objects, pitfalls currently manifesting, trade-offs actively undermined
- `info` — structural observations (dependency magnets, high fan-in nodes) that aren't currently broken

Confidence: carry forward from drift findings when available; otherwise use 0.8-0.95 for findings grounded in direct code reading, lower for inferred ones.

Verify the write:
```bash
test -s "$PROJECT_ROOT/.archie/scan_report.md" && wc -l "$PROJECT_ROOT/.archie/scan_report.md"
```

Expected: non-empty file with at least 30 lines.

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 9
```

Save baseline marker for future incremental runs (use "full" or "incremental" based on SCAN_MODE):
```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" save-baseline SCAN_MODE
```
(Replace SCAN_MODE with the actual mode — "full" or "incremental")

End with: **"Archie is now active. Architecture rules will be enforced on every code change. Run `/archie-scan` for fast health checks. Run `/archie-deep-scan --incremental` after code changes to update the architecture analysis."**

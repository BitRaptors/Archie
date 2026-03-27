# Archie Init — Full Architecture Analysis

Analyze this repository's architecture. Zero dependencies — works with any language.

**Prerequisites:** Run `npx archie` first to install the scripts. If `.archie/scanner.py` doesn't exist, tell the user to run `npx archie` and try again.

**IMPORTANT: Do NOT write inline Python scripts or bash one-liners. Every step uses a pre-installed script from `.archie/`. Just run the bash commands shown. Do NOT generate code to parse JSON, extract data, or create files. The scripts handle everything. If a step produces an error, follow the instructions for that step exactly — do not improvise workarounds.**

## Step 1: Detect sub-projects

```bash
python3 .archie/scanner.py "$PWD" --detect-subprojects
```

Read the JSON output. Count non-wrapper sub-projects (where `is_root_wrapper` is false).

- **If 0-1 non-wrapper sub-projects:** This is a single-project repo. Set `PROJECT_ROOT="$PWD"` and go to Step 3 (single-project pipeline).
- **If 2+ non-wrapper sub-projects:** This is a monorepo. Go to Step 2.

## Step 2: Project selection (monorepo only)

Present the detected sub-projects to the user as a numbered list:

> Found N sub-projects:
> 1. name (type) — path
> 2. name (type) — path
> ...
>
> Options:
> - **all** — Analyze all sub-projects
> - **1,3** — Analyze specific projects (comma-separated numbers)

Wait for the user's response. Build a list of selected sub-project paths.

Then ask:

> Run selected projects in **parallel** (faster, more agents) or **sequential** (one at a time)?

**Parallel mode:** For each selected sub-project, spawn a separate background Agent (Agent tool, `run_in_background: true`) that runs the full pipeline (Steps 3-8) with `PROJECT_ROOT="$PWD/<subproject_path>"`. Use the project name in the agent name (e.g., "Archie: gasztroterkepek-android"). Namespace temp files with the project name: `/tmp/archie_sub1_<name>.json`. Wait for all agents to complete, then go to Step 9.

**Sequential mode:** For each selected sub-project, set `PROJECT_ROOT="$PWD/<subproject_path>"` and run Steps 3-8 in order. Repeat for the next project. Then go to Step 9.

**IMPORTANT:** The `.archie/*.py` scripts are installed at the REPO ROOT. Always reference them as `.archie/scanner.py` etc. from the repo root. But pass `PROJECT_ROOT` (the sub-project path) as the first argument to each script. This is how the scripts know which directory to analyze.

---

## Steps 3-8: Per-Project Pipeline

Run these steps once per project. In single-project mode, `PROJECT_ROOT` is the repo root. In monorepo mode, `PROJECT_ROOT` is the sub-project directory.

Use `PROJECT_NAME` as the basename of `PROJECT_ROOT` for namespacing temp files (e.g., "gasztroterkepek-android").

## Step 3: Run the scanner

```bash
python3 .archie/scanner.py "$PROJECT_ROOT"
```

## Step 4: Read scan results

Read `$PROJECT_ROOT/.archie/scan.json`. Note total files, detected frameworks, and top-level directories. Check if frontend code is detected (look for React, Vue, Angular, Svelte, Next.js, Nuxt, Flutter, SwiftUI, Jetpack Compose, React Native, etc. in frameworks or file extensions like .tsx, .jsx, .vue, .svelte, .dart, .swift, .kt).

## Step 5: Spawn parallel analytical agents

Spawn 3–4 Sonnet subagents in parallel (Agent tool, `model: "sonnet"`), each focused on a different analytical concern. ALL agents read ALL source files under `$PROJECT_ROOT` — they are not split by directory. Each agent gets: the scan.json file_tree, dependencies, config files, and the GROUNDING RULES at the end of this step.

**If frontend code was detected in Step 4, spawn all 4 agents (A–D). Otherwise spawn only agents A–C.**

---

### Agent A: "Structure & Components"

> **CRITICAL INSTRUCTIONS:**
> You are analyzing a codebase to understand its architecture. Your goal is to OBSERVE and DESCRIBE what exists, NOT to categorize it into known patterns.
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

### Agent B: "Patterns & Communication"

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

### Agent C: "Technology, Deployment & Rules"

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

### Agent D: "Frontend Architecture" (only if frontend detected)

> Read all frontend/UI source files. This analysis covers web frontends, iOS apps, Android apps, cross-platform mobile, and any client-side code. Adapt each section to the platform detected.
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

## Step 6: Save Wave 1 output and merge

After each subagent completes, use the Write tool to save its COMPLETE output text to a temporary file. The merge script handles JSON extraction automatically — it can parse plain JSON, code-fenced JSON, and conversation envelopes.

**IMPORTANT: Save the COMPLETE raw text from each agent. Do NOT try to extract JSON yourself — the script handles all extraction including conversation envelopes, code fences, and escape issues.**

```
Write /tmp/archie_sub1_$PROJECT_NAME.json with Agent A's COMPLETE output text
Write /tmp/archie_sub2_$PROJECT_NAME.json with Agent B's COMPLETE output text
Write /tmp/archie_sub3_$PROJECT_NAME.json with Agent C's COMPLETE output text
Write /tmp/archie_sub4_$PROJECT_NAME.json with Agent D's COMPLETE output text (if spawned)
```

Then merge:

```bash
python3 .archie/merge.py "$PROJECT_ROOT" /tmp/archie_sub1_$PROJECT_NAME.json /tmp/archie_sub2_$PROJECT_NAME.json /tmp/archie_sub3_$PROJECT_NAME.json /tmp/archie_sub4_$PROJECT_NAME.json
```

This saves `$PROJECT_ROOT/.archie/blueprint_raw.json` (raw merged data). Verify the output shows non-zero component/section counts. If it says "0 sections, 0 components", the merge failed — check the agent output files.

## Step 7: Wave 2 — Agent X ("Architectural Reasoning")

Wave 1 gathered facts: components, patterns, technology, deployment, frontend. Now spawn a single Opus subagent (`model: "opus"`) that reads ALL Wave 1 output and produces deep architectural reasoning.

Tell Agent X:

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
> - **usage_example**: Brief code snippet (max 1 line)
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

Agent X also gets the GROUNDING RULES from Step 5.

After Agent X completes, save its output and finalize:

```
Write /tmp/archie_sub_x_$PROJECT_NAME.json with Agent X's output
```

```bash
python3 .archie/finalize.py "$PROJECT_ROOT" /tmp/archie_sub_x_$PROJECT_NAME.json
```

This single command: merges Agent X into the blueprint, normalizes the schema, renders CLAUDE.md + AGENTS.md + rule files, installs hooks, and validates. Review the validation output — warnings are informational, not blocking.

## Step 7.5: AI Rule Synthesis

The blueprint contains architectural facts. This step synthesizes them into **mechanically enforceable rules** that hooks can validate on every code edit.

Spawn a **Sonnet subagent** (`model: "sonnet"`) with this prompt:

> Read `$PROJECT_ROOT/.archie/blueprint.json`. It contains the full architecture: components, decisions (with decision chains and violation keywords), patterns, trade-offs (with violation signals), pitfalls (with causal chains), technology stack, and development rules.
>
> Produce 20-40 enforcement rules that a hook can mechanically validate. Each rule checks a file path + code content and gives a clear pass/fail. Return ONLY valid JSON: `{"rules": [...]}`.
>
> ## Rule types (use these exact `check` values):
>
> ### `forbidden_import` — File in directory X must not import from Y
> ```json
> {"check": "forbidden_import", "description": "...", "applies_to": "path/prefix/", "forbidden_patterns": ["regex1", "regex2"], "severity": "error"}
> ```
> `applies_to`: directory prefix. `forbidden_patterns`: regex patterns matched against file content.
>
> ### `required_pattern` — File matching a name pattern must contain certain code
> ```json
> {"check": "required_pattern", "description": "...", "file_pattern": "glob pattern", "required_in_content": ["string1", "string2"], "severity": "warn"}
> ```
> `file_pattern`: glob matched against filename (e.g., `*ViewModel.kt`). `required_in_content`: at least ONE must appear in the file content.
>
> ### `forbidden_content` — Code must never contain certain patterns
> ```json
> {"check": "forbidden_content", "description": "...", "forbidden_patterns": ["regex1", "regex2"], "applies_to": "", "severity": "error"}
> ```
> `applies_to`: optional directory prefix (empty = all files). `forbidden_patterns`: regex patterns.
>
> ### `architectural_constraint` — Deep invariants scoped to specific file types
> ```json
> {"check": "architectural_constraint", "description": "...", "file_pattern": "glob", "forbidden_patterns": ["regex1"], "rationale": "why this matters", "severity": "error"}
> ```
> `file_pattern`: glob matched against filename. `forbidden_patterns`: regex patterns that violate the constraint.
>
> ## What to produce:
>
> **Structural rules** — dependency direction between layers/components, forbidden technologies (from decisions/trade-offs), file naming where violations would break the build or architecture.
>
> **Deep architectural rules** — invariants an AI coding agent might accidentally violate. These are the most valuable. Examples: "ViewModel must never reference View/Context", "Repository must use IO dispatcher", "Fragments must use DI delegation not direct construction". Derive these from decision chains, trade-offs, pitfalls, and pattern descriptions.
>
> ## Critical:
> - Every rule must be specific to THIS project — never generic programming advice
> - Focus on what an AI coding agent would get wrong without knowing this codebase
> - Every `forbidden_patterns` entry must be a valid regex
> - Include an `"id"` field for each rule (e.g., "dep-001", "arch-001", "ban-001")
> - The `description` must explain WHAT is forbidden and WHY in one sentence

After the agent responds, save its COMPLETE output text to a temp file and use the merge script to extract the JSON:

```
Write /tmp/archie_rules_$PROJECT_NAME.json with the agent's COMPLETE output text
```

```bash
python3 -c "
import json, sys; sys.path.insert(0, '$PROJECT_ROOT/.archie')
from merge import extract_json_from_text
text = open('/tmp/archie_rules_$PROJECT_NAME.json').read()
data = extract_json_from_text(text)
if data:
    open('$PROJECT_ROOT/.archie/rules.json', 'w').write(json.dumps(data, indent=2))
    print(f'Saved {len(data.get(\"rules\", []))} rules')
else:
    print('ERROR: could not extract rules JSON', file=sys.stderr); sys.exit(1)
"
```

**IMPORTANT: Do NOT try to extract or parse JSON yourself. The script handles conversation envelopes, code fences, and escape issues.**

## Step 8: Intent Layer — per-folder CLAUDE.md

This step generates per-folder CLAUDE.md files with AI-generated architectural descriptions using bottom-up DAG scheduling. State is tracked automatically in `.archie/enrich_state.json`.

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

## Step 9: Clean up

```bash
rm -f /tmp/archie_sub*_$PROJECT_NAME.json /tmp/archie_rules_$PROJECT_NAME.json /tmp/archie_intent_prompt_$PROJECT_NAME.txt /tmp/archie_enrichment_*.json
```

## Step 10: Drift Detection & Architectural Assessment

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
python3 -c "import json; [print(f['path']) for f in json.load(open('$PROJECT_ROOT/.archie/scan.json')).get('file_tree',[]) if f.get('extension','') in ('.kt','.java','.swift','.ts','.tsx','.py','.go','.rs')]" | head -100
```

For each file (batch into groups of ~15), collect:
- The file's content
- Its folder's CLAUDE.md (per-folder patterns, anti-patterns)
- Its parent folder's CLAUDE.md if it exists

Read `$PROJECT_ROOT/.archie/blueprint.json` — specifically `decisions.key_decisions`, `decisions.decision_chain`, `decisions.trade_offs` (with `violation_signals`), `pitfalls` (with `stems_from`), `communication.patterns`, `development_rules`.

Read `$PROJECT_ROOT/.archie/drift_report.json` (mechanical findings from Phase 1).

Spawn a **Sonnet subagent** (`model: "sonnet"`) with the file contents, their folder CLAUDE.md files, and the blueprint context. Tell it:

> You are an architecture reviewer. You have the project's architectural blueprint (decisions, trade-offs, pitfalls, patterns), per-folder CLAUDE.md files describing expected patterns, mechanical drift findings (already detected), and source files to review.
>
> Find **deep architectural violations** — problems that pattern matching cannot catch. For each finding, return:
> - `folder`: the folder path
> - `file`: the specific file
> - `type`: one of `decision_violation`, `pattern_erosion`, `trade_off_undermined`, `pitfall_triggered`, `responsibility_leak`, `abstraction_bypass`
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
>
> Do NOT report: style/formatting/naming (the script handles those), generic best-practice violations not grounded in THIS project's blueprint, or issues already in the mechanical drift report.
>
> Return JSON: `{"deep_findings": [...]}`

Save the deep findings:
```
Write /tmp/archie_deep_drift.json with the agent's COMPLETE output text
```
```bash
python3 -c "
import json, sys; sys.path.insert(0, '$PROJECT_ROOT/.archie')
from merge import extract_json_from_text
text = open('/tmp/archie_deep_drift.json').read()
data = extract_json_from_text(text)
if data:
    report = json.load(open('$PROJECT_ROOT/.archie/drift_report.json'))
    report['deep_findings'] = data.get('deep_findings', [])
    s = report['summary']
    deep_count = len(report['deep_findings'])
    s['deep_findings'] = deep_count
    s['total_findings'] += deep_count
    s['warnings'] += sum(1 for f in report['deep_findings'] if f.get('severity') == 'warn')
    open('$PROJECT_ROOT/.archie/drift_report.json', 'w').write(json.dumps(report, indent=2))
    print(f'Added {deep_count} deep findings')
else:
    print('Warning: could not extract deep findings', file=sys.stderr)
"
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
- Rule files in `.claude/rules/` and `.cursor/rules/`

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

End with: **"Archie is now active. Architecture rules will be enforced on every code change. Run `/archie-drift` to track drift over time."**

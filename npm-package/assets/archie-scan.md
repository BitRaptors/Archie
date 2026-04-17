# Archie Scan — Architecture Health Check with Compound Learning

Analyze this project's architectural health using 4 parallel agents. Each scan evolves the blueprint — knowledge compounds over time.

**Usage:** `/archie-scan` or `/archie-scan --reconfigure`

**Prerequisites:** If `.archie/scanner.py` doesn't exist, tell the user to run `npx @bitraptors/archie` first.

**CRITICAL CONSTRAINTS:**

1. **Never write inline Python.** Do NOT use `python3 -c "..."` or any ad-hoc scripting to inspect, parse, or transform JSON. Every operation has a dedicated command:
   - Normalize blueprint: `python3 .archie/finalize.py "$PROJECT_ROOT" --normalize-only`
   - Append health history: `python3 .archie/measure_health.py "$PROJECT_ROOT" --append-history --scan-type fast`
   - Inspect any JSON file: `python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" <filename>`
   - Query a specific field: `python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" scan.json --query .frontend_ratio`
   If you need data not covered by these commands, proceed without it or ask the user. NEVER improvise Python.

2. **Timestamps use shell-native date.** For telemetry, record timestamps with:
   ```bash
   date -u +"%Y-%m-%dT%H:%M:%SZ"
   ```
   Never use `python3 -c` for timestamps.

3. **Agent outputs go to `/tmp/` temp files.** Findings extracts go to `$PROJECT_ROOT/.archie/sf_*.json`. Never mix these locations.

---

## Phase 0: Resolve scope

Every run needs to know whether to scan the root, a specific workspace, or a set of workspaces. The choice is persisted in `.archie/archie_config.json` so we ask at most once per project.

### Step A: Read existing config

```bash
python3 .archie/intent_layer.py scan-config "$PROJECT_ROOT" read
```

- **Exit 0** → config exists. Parse `scope`, `workspaces`, `monorepo_type` from the JSON. Skip to Step D.
- **Exit 1** → config missing. Go to Step B.

If the user invoked the command with `--reconfigure`, skip Step A entirely and go to Step B (forcing a fresh prompt).

### Step B: Detect monorepo type + subprojects

```bash
python3 .archie/scanner.py "$PROJECT_ROOT" --detect-subprojects
```

Parse `monorepo_type` and count subprojects where `is_root_wrapper` is false.

- **0 or 1 non-wrapper subprojects** → Not a monorepo (or a monorepo with only one real package). Write config as `single`:

  ```bash
  echo '{"scope":"single","monorepo_type":"<detected-type>","workspaces":[]}' \
    | python3 .archie/intent_layer.py scan-config "$PROJECT_ROOT" write
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
- If `per-package` or `hybrid` → ask the user which workspaces to include. Accept comma-separated numbers (`1,3,5`) or `all`. Resolve to paths relative to `$PROJECT_ROOT`.

Persist the choice:

```bash
echo '{"scope":"<chosen>","monorepo_type":"<detected-type>","workspaces":[<array>]}' \
  | python3 .archie/intent_layer.py scan-config "$PROJECT_ROOT" write
```

### Step D: Validate and announce

```bash
python3 .archie/intent_layer.py scan-config "$PROJECT_ROOT" validate
```

- **Exit 0** → proceed with the rest of the pipeline.
- **Exit 1** → a workspace was removed or renamed since last run. Print the drift message and instruct the user to re-run with `--reconfigure`. Stop execution.

After validation, expose these variables for downstream steps:

- `SCOPE` = `single` | `whole` | `per-package` | `hybrid`
- `WORKSPACES` = array of workspace paths (empty for `single` and `whole`)
- `MONOREPO_TYPE` = `bun-workspaces` | `npm-workspaces` | `pnpm` | `turborepo` | `nx` | `lerna` | `cargo` | `gradle` | `none`

---

## Execution-plan guidance by scope

Downstream pipeline steps branch on `SCOPE`:

- **`single` or `whole`** — Run the rest of the pipeline once with `PROJECT_ROOT="$PWD"`. For `whole`, the Structure/analysis agent gets the workspace-aware prompt addendum so components are workspaces.
- **`per-package`** — Iterate `WORKSPACES`. For each path, set `PROJECT_ROOT="$PWD/<path>"` and run the full pipeline. Produces one blueprint per workspace.
- **`hybrid`** — Two passes:
  1. Root pass with `SCOPE=whole` semantics (single blueprint at `$PWD`)
  2. Per-workspace pass over `WORKSPACES`

The existing parallel/sequential agent scheduling inside `/archie-deep-scan` applies to per-package iterations.

---

## Step 1: Scan (deterministic)

Record telemetry start:
```bash
TELEMETRY_STEP1_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

Run all three scripts simultaneously:

```bash
python3 .archie/scanner.py "$PROJECT_ROOT"
```
```bash
python3 .archie/measure_health.py "$PROJECT_ROOT" > "$PROJECT_ROOT/.archie/health.json" 2>/dev/null
```
```bash
python3 .archie/detect_cycles.py "$PROJECT_ROOT" --full 2>/dev/null
```

Record telemetry end:
```bash
TELEMETRY_STEP1_END=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

---

## Step 2: Gather (4 parallel agents)

<!-- MAINTAINER NOTE: The 4 agent prompts below are inlined from the shared fragments in
     .claude/commands/_shared/agent_{structure,patterns,health,technology}.md
     Those fragments are the source of truth. When updating an agent prompt, edit the
     _shared/ fragment first, then re-inline into both archie-scan.md and archie-deep-scan.md,
     then sync to npm-package/assets/. -->

Record telemetry start:
```bash
TELEMETRY_STEP2_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

Spawn 4 Sonnet subagents in parallel (Agent tool, `model: "sonnet"`). Each agent receives the data from Step 1 and can read source files when needed.

**EFFICIENCY RULE:** Agents read `skeletons.json` which contains every file's path, class/function signatures, imports, and first lines. This is sufficient for pattern detection, outlier finding, and most analysis. Agents should ONLY use the Read tool on source files when the skeleton genuinely lacks the information needed to make a judgment.

**Read existing knowledge before spawning agents** (skip any that don't exist — normal for first scan):
- `$PROJECT_ROOT/.archie/skeletons.json` — every file's header, function/class signatures, line counts
- `$PROJECT_ROOT/.archie/scan.json` — file tree, import graph, detected frameworks
- `$PROJECT_ROOT/.archie/health.json` — erosion, gini, verbosity, complexity per function
- `$PROJECT_ROOT/.archie/dependency_graph.json` — resolved directory-level dependency graph
- `$PROJECT_ROOT/.archie/blueprint.json` — the evolving architectural knowledge base
- `$PROJECT_ROOT/.archie/scan_report.md` — previous scan's report (for trending)
- `$PROJECT_ROOT/.archie/health_history.json` — historical health scores
- `$PROJECT_ROOT/.archie/rules.json` — adopted enforcement rules
- `$PROJECT_ROOT/.archie/proposed_rules.json` — rules discovered but not yet adopted

**This is the compound learning input.** The agents below receive everything Archie has ever learned about this codebase.

### Agent: Structure

> You are analyzing the ARCHITECTURE and DEPENDENCIES of a codebase. You have access to scan data and the existing blueprint (if any).
>
> **Your inputs:**
> - `.archie/skeletons.json` — every file's header, class/function signatures, imports, line counts. This is your primary data source.
> - `.archie/dependency_graph.json` — resolved directory-level graph. Node schema: `{id, label, component, inDegree, outDegree, inCycle, fileCount}` — use `id` for directory path, NOT `path`. Edge schema: `{source, target, weight, crossComponent}`. Do NOT write ad-hoc Python to analyze this data — use it directly in your analysis.
> - `.archie/scan.json` — file tree, import graph, detected frameworks, `frontend_ratio`
> - `.archie/blueprint.json` — existing architectural knowledge (if any)
>
> **Your job:**
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
> **DO NOT assume this is a "layered architecture", "MVC", "Clean Architecture", or any specific pattern.** DO NOT look for patterns that match your training data or force observations into predefined categories. Describe the ACTUAL file organization, identify how files relate based on naming and imports, and note conventions unique to this codebase.
>
> ### 5. File Placement & Naming
> - Where do tests, configs, components, services actually live? With naming patterns observed.
> - Search the file_tree for where test files, config files, build output, and generated code actually live. Do NOT assume conventional locations.
> - Document actual naming conventions: PascalCase components, snake_case utils, kebab-case files, etc. With 2-4 examples each.
>
> ### 6. Framework Usage
> Catalog external frameworks/libraries from import statements. For each, note the framework name and usage scope.
>
> **Efficiency rule:** Read skeletons.json + dependency_graph.json first — they contain every file's path, class/function signatures, imports, and first lines. This is sufficient for pattern detection, outlier finding, and most analysis. Only use the Read tool on source files when the skeleton genuinely lacks the information needed to make a judgment.
>
> **GROUNDING RULES — every claim must come from code you READ, never from names or conventions.**
> 1. **Paths**: Only reference file/directory paths that appear in scan.json file_tree. Do NOT infer conventional paths.
> 2. **Component responsibility**: Read the actual source file. Describe what the code DOES, not what the filename or class name suggests.
> 3. **API/route/endpoint methods**: Read the actual handler code. List ONLY the methods/verbs/actions actually implemented. Do NOT assume CRUD.
> 4. **File placement rules**: Search the file_tree for where files actually live. Do NOT assume conventional locations.
>
> **Pattern observations (for synthesis to consume):**
> Raw cross-file anomalies in your domain — NOT finished findings, just signals for the synthesis step to contextualize. Each observation: `{type, evidence_locations, note}`.
>
> Types in your domain:
> - `dep_magnet` — directory/module with unusually high fan-in across unrelated domains
> - `layer_cycle` — import cycle crossing a layer boundary
> - `inverted_dependency` — lower-level module importing from higher-level
> - `workspace_boundary_crossed` — import crossing workspace boundary unexpectedly (monorepo only)
> - `high_fan_in_rising` — a node's in-degree is high AND growing vs prior scan
>
> Example:
> ```json
> {"type": "dep_magnet", "evidence_locations": ["packages/shared"], "note": "fan-in 22 across auth/storage/UI/logging — unrelated domains"}
> ```
>
> **Findings:**
> Emit findings per `.claude/commands/_shared/semantic_findings_spec.md`. Your domain is **architecture and dependencies**.
> Before emitting, Read the spec file and follow S1 (schema), S2 (quality gate), S3 (severity rubric), S4 (taxonomy).
>
> Produce two categories:
> - **Systemic** (category: systemic): `god_component`, `boundary_violation`. Each with >=3 evidence locations, pattern_description, root_cause, fix_direction, blast_radius.
> - **Localized** (category: localized): `dependency_violation`, `cycle`. Each with a single location, root_cause, fix_direction.
>
> All findings MUST carry `synthesis_depth: "draft"` and `source: "agent_structure"`.
>
> Do NOT emit count caps. Emit every finding you can substantiate with concrete evidence. Before emitting, verify each finding against the quality gate in S2 of the spec — dropped candidates are better than padded ones.
>
> **Workspace-aware addendum (only when `SCOPE === "whole"`):**
>
> This is a workspace monorepo (`MONOREPO_TYPE={type}`, N workspaces under paths `<workspaces>`). Treat each workspace member as a top-level component in `components`:
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
> Surface cross-workspace import cycles as findings with severity `error`. Surface workspaces with very high fan-in (top quartile of in_degree) as `dep_magnet` pattern observations. Reference workspace members by **name** (not path) in all cross-references.
>
> **Output:** Write to `/tmp/archie_agent_structure.json`:
> ```json
> {
>   "meta": {
>     "architecture_style": "plain language description",
>     "platforms": ["backend", "web-frontend"],
>     "executive_summary": "3-5 factual sentences: what this does, primary tech, architecture style. No filler."
>   },
>   "components": [
>     {
>       "name": "", "location": "", "platform": "",
>       "responsibility": "", "depends_on": [], "exposes_to": [],
>       "key_interfaces": [{"name": "", "methods": [], "description": ""}],
>       "key_files": [{"file": "", "description": ""}]
>     }
>   ],
>   "layers": [
>     {
>       "name": "", "platform": "", "location": "",
>       "responsibility": "", "contains": [], "depends_on": [], "exposes_to": []
>     }
>   ],
>   "architecture_rules": {
>     "file_placement_rules": [
>       {"component_type": "", "naming_pattern": "", "location": "", "example": ""}
>     ],
>     "naming_conventions": [
>       {"scope": "", "pattern": "", "examples": []}
>     ]
>   },
>   "workspace_topology": {},
>   "pattern_observations": [
>     {"type": "dep_magnet", "evidence_locations": ["packages/shared"], "note": "fan-in 22 across unrelated domains"}
>   ],
>   "findings": [
>     {
>       "category": "systemic",
>       "type": "god_component",
>       "severity": "error",
>       "scope": {"kind": "system_wide", "components_affected": ["packages/shared"], "locations": ["apps/webui/src/auth.ts:14", "apps/electron/src/storage.ts:3", "apps/webui/src/ui/Button.tsx:1"]},
>       "pattern_description": "shared/ accumulates responsibilities from 7 unrelated domains",
>       "evidence": "22 consumers import from packages/shared across auth, storage, UI, logging",
>       "root_cause": "every cross-cutting util was added to shared without domain boundary; decision D.3 treated shared as primitives but actual usage crosses domains",
>       "fix_direction": "split into packages/{auth, storage, ui-primitives, logging}; migrate per-domain starting with auth",
>       "blueprint_anchor": "decision:D.3",
>       "blast_radius": 22,
>       "synthesis_depth": "draft",
>       "source": "agent_structure"
>     }
>   ]
> }
> ```

Save output: `/tmp/archie_agent_structure.json`

### Agent: Patterns

> You are analyzing PATTERNS, COMMUNICATION, and RULES in a codebase. You look for how components talk to each other, how patterns are applied, and where architectural invariants hold or break.
>
> **Your inputs:**
> - `.archie/skeletons.json` — every file's header, class/function signatures, imports, line counts. This is your primary data source.
> - `.archie/scan.json` — file tree, import graph, detected frameworks
> - `.archie/rules.json` — currently adopted rules
> - `.archie/proposed_rules.json` — previously proposed rules (adopted or pending)
> - `.archie/blueprint.json` — existing architectural knowledge (if any)
>
> **Your job:**
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
> ### 9. Rule Discovery
> Look for architectural invariants — things that should always be true in this codebase. Check existing rules in `.archie/rules.json` for violations; discover new patterns that could become rules.
>
> For each proposed rule: `{id, description, rationale, severity, confidence}`.
> - **id**: `scan-NNN` (pick next available number)
> - **description**: "Always X" or "Never Y" — specific to THIS project
> - **rationale**: Why this invariant matters, with evidence
> - **severity**: `error` (violation causes bugs/breakage) or `warn` (violation causes inconsistency)
> - **confidence**: 0.0-1.0. Start at 0.6-0.7 for newly observed patterns. Raise to 0.8+ only when the pattern is nearly universal across the codebase.
>
> **Confidence calibration:**
> - 0.5-0.6: Emerging pattern, seen in ~50% of eligible locations
> - 0.7-0.8: Strong pattern, seen in ~70-80% of eligible locations
> - 0.9+: Near-universal, exceptions are clearly deliberate
>
> **Efficiency rule:** Read skeletons.json first — it contains every file's path, class/function signatures, imports, and first lines. This is sufficient for pattern detection, outlier finding, and most analysis. Only use the Read tool on source files when the skeleton genuinely lacks the information needed to make a judgment.
>
> **Pattern observations (for synthesis to consume):**
> Raw cross-file anomalies in your domain — NOT finished findings, just signals for the synthesis step. Each observation: `{type, evidence_locations, note}`.
>
> Types in your domain:
> - `fragmentation_signal` — same job done N different ways
> - `missing_abstraction_signal` — copy-paste or repeated protocol without a shared helper
> - `pattern_outlier` — 1-2 files deviating from an otherwise-consistent pattern
> - `inconsistency_signal` — feature built one way in component X, another way in component Y
>
> Example:
> ```json
> {"type": "fragmentation_signal", "evidence_locations": ["handlers/orders.ts", "handlers/users.ts", "handlers/admin.ts"], "note": "auth enforcement inline in each handler with 3 different approaches"}
> ```
>
> **Findings:**
> Emit findings per `.claude/commands/_shared/semantic_findings_spec.md`. Your domain is **rules, patterns, and duplication**.
> Before emitting, Read the spec file and follow S1 (schema), S2 (quality gate), S3 (severity rubric), S4 (taxonomy).
>
> Produce two categories:
> - **Systemic** (category: systemic): `fragmentation` (same job done N different ways), `missing_abstraction` (copy-paste without helper), `inconsistency` (equivalent operations expressed differently). Each with >=3 evidence locations, pattern_description, root_cause, fix_direction, blast_radius.
> - **Localized** (category: localized): `pattern_divergence` (outlier breaking a 0.7+ confident pattern), `semantic_duplication` (near-twin functions), `rule_violation` (code breaking an adopted rule from `.archie/rules.json`). Each with a single location, root_cause, fix_direction.
>
> All findings MUST carry `synthesis_depth: "draft"` and `source: "agent_patterns"`.
>
> Be honest about systemic vs localized: if >=3 locations exhibit the same problem, it's systemic; a single outlier is localized.
>
> Do NOT emit count caps. Emit every finding you can substantiate with concrete evidence. Before emitting, verify each finding against the quality gate in S2 of the spec — dropped candidates are better than padded ones.
>
> **Workspace-aware addendum (only when `SCOPE === "whole"`):**
>
> If the current scope is `whole`, `PROJECT_ROOT` is a workspace monorepo (`MONOREPO_TYPE={type}`). The blueprint's `components` section treats each workspace as a top-level component, and `blueprint.workspace_topology` (if present) captures the inter-workspace dependency graph. When analyzing drift and findings, pay special attention to:
>
> - Cross-workspace imports that create cycles in the workspace dependency graph -> always severity `error`
> - Shared/library packages (e.g., `packages/*`) that import from application packages (e.g., `apps/*`) -> inverted dependency flow, severity `error`
> - Workspaces with very high fan-in (top 20% of `in_degree`) that keep growing — flag as "dependency magnet at risk"
> - Reference components by **workspace name** (from `package.json`), not by path, in findings
>
> **Output:** Write to `/tmp/archie_agent_patterns.json`:
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
>   },
>   "pattern_observations": [
>     {"type": "fragmentation_signal", "evidence_locations": ["handlers/orders.ts", "handlers/users.ts"], "note": "auth enforcement inline with divergent policies"}
>   ],
>   "findings": [
>     {
>       "category": "systemic",
>       "type": "fragmentation",
>       "severity": "error",
>       "scope": {"kind": "cross_component", "components_affected": ["handlers"], "locations": ["handlers/orders.ts:23", "handlers/users.ts:15", "handlers/reports.ts:41", "handlers/admin.ts:12"]},
>       "pattern_description": "auth enforcement is done inline in each handler with divergent policies",
>       "evidence": "4 handlers each validate session differently; no shared middleware",
>       "root_cause": "first handler copy-pasted as pattern; subsequent handlers added domain checks inline rather than extending a shared guard",
>       "fix_direction": "extract authGuard({scope?, role?, allowServiceToken?}) middleware; migrate admin -> reports -> users -> orders",
>       "blast_radius": 4,
>       "synthesis_depth": "draft",
>       "source": "agent_patterns"
>     }
>   ],
>   "proposed_rules": [
>     {"id": "scan-NNN", "description": "Always/Never ...", "rationale": "...", "severity": "error", "confidence": 0.85}
>   ],
>   "rule_confidence_updates": [
>     {"rule_id": "scan-NNN", "old_confidence": 0.7, "new_confidence": 0.85, "reason": "..."}
>   ]
> }
> ```

Save output: `/tmp/archie_agent_patterns.json`

### Agent: Health

> You are analyzing the HEALTH and COMPLEXITY of a codebase. You have access to health metrics, complexity data, and historical trends.
>
> **Your inputs:**
> - `.archie/health.json` — current erosion, gini, verbosity, waste, function-level complexity (cyclomatic complexity per function)
> - `.archie/health_history.json` — historical health scores (for trend analysis across scans)
> - `.archie/skeletons.json` — every file's header, class/function signatures, imports, line counts
> - `.archie/blueprint.json` — existing architectural knowledge (if any)
>
> **Your job:**
>
> ### 1. Health Scores
> Compute a summary of the current health state from `health.json`: erosion, gini, top20_share, verbosity, total_loc. These populate the viewer's Health Tab and feed into the scan report.
>
> ### 2. Trend Analysis
> Compare current health scores against `health_history.json` (if it exists) to determine the trajectory:
> - **direction**: `improving`, `stable`, or `degrading`
> - **details**: Describe what changed and by how much (e.g., "top-20 share grew 0.64 -> 0.72 over 3 scans", "erosion stable at 0.28 for 5 scans")
>
> If no history exists, set direction to `stable` and note "first scan — no trend data".
>
> ### 3. Complexity Hotspots
> Identify functions with cyclomatic complexity (CC) >= 10 from `health.json`. Severity per the spec's CC rubric:
> - CC >= 50: `error`
> - CC 25-49: `warn`
> - CC 10-24: `info`
>
> For each hotspot, the `root_cause` must be **mechanistic** — NOT "high CC" but a specific explanation of why the function is complex. Examples:
> - "conflates auth validation with request parsing and response formatting in a single method"
> - "switch statement handles 14 message types with inline processing for each"
> - "nested conditionals for 6 platform variants with platform-specific retry logic interleaved"
>
> Use skeletons first to understand the function's signature and context. Read the actual source file only when the skeleton is genuinely insufficient to determine why the function is complex.
>
> ### 4. Trajectory Degradation
> Only when substantiated by history: if >=3 complexity hotspots are ALL worsening over `health_history.json` entries, emit a systemic `trajectory_degradation` finding.
>
> ### 5. Abstraction Bypass
> Identify cases where a single-method class, tiny wrapper function, or trivial indirection layer exists that obscures rather than clarifies the underlying structure. These are localized findings.
>
> **Important boundary:** If you spot copy-paste or a repeated helper shape, leave it for the Patterns agent's `missing_abstraction` / `fragmentation` findings — do not emit those here.
>
> **Efficiency rule:** Read skeletons.json + health.json first. Only use the Read tool on source files when the CC signature in the skeleton is genuinely insufficient to determine the mechanistic root cause.
>
> **Findings:**
> Emit findings per `.claude/commands/_shared/semantic_findings_spec.md`. Your domain is **health and complexity**.
> Before emitting, Read the spec file and follow S1 (schema), S2 (quality gate), S3 (severity rubric), S4 (taxonomy).
>
> Produce:
> - **Localized**: `complexity_hotspot` (functions with CC >= 10, severity per CC rubric above), `abstraction_bypass` (trivial indirection obscuring structure). Each with a single location, root_cause, fix_direction.
> - **Systemic** (only when substantiated): `trajectory_degradation` (>=3 hotspots all worsening over history). With >=3 evidence locations, pattern_description, root_cause, fix_direction, blast_radius.
>
> All findings MUST carry `synthesis_depth: "draft"` and `source: "agent_health"`.
>
> Do NOT emit count caps. Emit every finding you can substantiate with concrete evidence. Before emitting, verify each finding against the quality gate in S2 of the spec — dropped candidates are better than padded ones.
>
> **Output:** Write to `/tmp/archie_agent_health.json`:
> ```json
> {
>   "health_scores": {
>     "erosion": 0.31,
>     "gini": 0.58,
>     "top20_share": 0.72,
>     "verbosity": 0.003,
>     "total_loc": 9400
>   },
>   "trend": {
>     "direction": "degrading",
>     "details": "top-20 share grew 0.64 -> 0.72 over 3 scans"
>   },
>   "findings": [
>     {
>       "category": "localized",
>       "type": "complexity_hotspot",
>       "severity": "error",
>       "scope": {"kind": "single_file", "components_affected": ["apps/electron"], "locations": ["apps/electron/src/AppShell.tsx:45:render"]},
>       "evidence": "AppShell.render has CC=669; combines layout + routing + state wiring + providers",
>       "root_cause": "organic accretion: render grew to serve as god-function for startup; no extraction ever happened",
>       "fix_direction": "split into AppLayout + AppRouter + AppProviders (three components, each <CC 50)",
>       "synthesis_depth": "draft",
>       "source": "agent_health"
>     }
>   ]
> }
> ```

Save output: `/tmp/archie_agent_health.json`

### Agent: Technology

> You are analyzing the TECHNOLOGY STACK, DEPLOYMENT, and DEVELOPMENT RULES of a codebase. You read CONFIG FILES ONLY — you never read `.ts`, `.py`, `.kt`, `.swift`, `.java`, `.go`, `.rs`, `.rb`, `.dart`, or any other source code files.
>
> **Your inputs (config files only):**
> - `package.json`, `requirements.txt`, `Gemfile`, `build.gradle`, `build.gradle.kts`, `pubspec.yaml`, `Package.swift`, `Cargo.toml`, `go.mod`, `pom.xml` — dependency manifests
> - `Dockerfile`, `docker-compose.yml`, `.dockerignore` — container config
> - `.github/workflows/*.yml`, `cloudbuild.yaml`, `.gitlab-ci.yml`, `Fastfile`, `bitrise.yml` — CI/CD configs
> - `vercel.json`, `netlify.toml`, `fly.toml`, `railway.json`, `render.yaml`, `app.yaml`, `firebase.json`, `serverless.yml` — deployment platform configs
> - `*.tf`, `template.yaml`, `helm/` — infrastructure as code
> - `Makefile`, `Rakefile`, `justfile`, `taskfile.yml` — build/task configs
> - `.env.example`, `.env.template` — environment variable templates
> - `tsconfig.json`, `ruff.toml`, `.eslintrc*`, `.prettierrc*`, `.editorconfig`, `pyproject.toml`, `setup.cfg` — tooling configs
> - `pytest.ini`, `jest.config.*`, `vitest.config.*` — test configs
> - `.pre-commit-config.yaml`, `.husky/`, `.lintstagedrc*` — quality gate configs
> - `.gitignore`, `.gitattributes` — git configs
> - `.archie/scan.json` — file tree and detected frameworks (for project structure)
>
> **Your job:**
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
> ### 5. Deployment Detection (check for ALL of these)
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
> **Efficiency rule:** Read config files only. You never need to read source code files — your entire analysis domain is configuration, dependency manifests, CI/CD, and deployment. If a question requires reading source code to answer, skip it — another agent covers that domain.
>
> **Output:** Write to `/tmp/archie_agent_technology.json`:
> ```json
> {
>   "technology": {
>     "stack": [
>       {"category": "runtime", "name": "Python", "version": "3.11", "purpose": "Backend language"}
>     ],
>     "run_commands": {
>       "dev": "npm run dev",
>       "test": "pytest tests/ -v",
>       "build": "docker build -t app ."
>     },
>     "project_structure": "ASCII tree showing top-level directories",
>     "templates": [
>       {"component_type": "api_route", "description": "New REST endpoint", "file_path_template": "api/routes/{name}.py", "code": "router = APIRouter(prefix='/{name}')"}
>     ]
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
>     {"category": "dependency_management", "rule": "Always use poetry for dependency management — lockfile enforced", "source": "pyproject.toml"}
>   ]
> }
> ```

Save output: `/tmp/archie_agent_technology.json`

**Wait for all 4 agents to complete before proceeding to Step 3.**

Record telemetry end:
```bash
TELEMETRY_STEP2_END=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

---

## Step 3: Aggregate (deterministic)

Record telemetry start:
```bash
TELEMETRY_STEP3_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

Extract findings from each agent's output into per-source files, then invoke the aggregator. Technology agent has no findings — skip extraction for it.

```bash
python3 .archie/extract_output.py findings /tmp/archie_agent_structure.json "$PROJECT_ROOT/.archie/sf_structure.json"
python3 .archie/extract_output.py findings /tmp/archie_agent_patterns.json "$PROJECT_ROOT/.archie/sf_patterns.json"
python3 .archie/extract_output.py findings /tmp/archie_agent_health.json "$PROJECT_ROOT/.archie/sf_health.json"
```

Run mechanical drift detection:
```bash
python3 .archie/drift.py "$PROJECT_ROOT"
```

Run the aggregator — it reads every `sf_*.json` and `semantic_findings_*.json` source in `.archie/`, merges by signature, applies the quality gate, computes `lifecycle_status` against the prior `semantic_findings.json`, and writes the canonical result to `.archie/semantic_findings.json`:
```bash
python3 .archie/aggregate_findings.py "$PROJECT_ROOT"
```

Record telemetry end:
```bash
TELEMETRY_STEP3_END=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

---

## Step 4: Light Synthesis (Sonnet)

Record telemetry start:
```bash
TELEMETRY_STEP4_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

Spawn a single Sonnet subagent (Agent tool, `model: "sonnet"`). It reads all 4 agent outputs plus the existing blueprint and produces the narrative glue that ties the architectural overview together.

Prompt for the synthesis agent:

> Read these files:
> - `/tmp/archie_agent_structure.json` — components, layers, architecture style
> - `/tmp/archie_agent_patterns.json` — communication patterns, integrations
> - `/tmp/archie_agent_health.json` — health scores, trends
> - `/tmp/archie_agent_technology.json` — tech stack, deployment, dev rules
> - `$PROJECT_ROOT/.archie/blueprint.json` — existing blueprint (if any; skip if missing)
>
> Produce:
> 1. **Executive summary** (3-5 sentences): what this codebase does, primary tech, architecture style, current health state. Reference specific components and patterns — no generic filler.
> 2. **Architecture style characterization** (1 paragraph): what pattern, how it manifests across the codebase, what holds it together. If the existing blueprint has a style, evolve it — don't restart from scratch.
>
> Do NOT produce decisions, pitfalls, trade-offs, architecture diagram, or implementation guidelines — those are deep-scan territory.
>
> Return JSON:
> ```json
> {
>   "meta": {
>     "executive_summary": "...",
>     "architecture_style": "..."
>   }
> }
> ```

Save output: `/tmp/archie_synthesis.json`

Record telemetry end:
```bash
TELEMETRY_STEP4_END=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

---

## Step 5: Merge + Render (deterministic)

Record telemetry start:
```bash
TELEMETRY_STEP5_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

### 5a: Merge agent outputs into blueprint

Read the existing blueprint (or start with `{}` if none exists). Deep-merge each agent's output plus the synthesis into the appropriate blueprint sections:

- **Structure agent** → `components`, `layers`, `architecture_rules.file_placement_rules`, `architecture_rules.naming_conventions`, `workspace_topology`
- **Patterns agent** → `communication`, `quick_reference`
- **Health agent** → `meta.health` (health_scores + trend)
- **Technology agent** → `technology`, `deployment`, `development_rules`
- **Synthesis** → `meta.executive_summary`, `meta.architecture_style`

**Blueprint evolution rules:**
- If the blueprint already has sections from a deep-scan (decisions, pitfalls, trade-offs, diagram, guidelines), **preserve them**. Scan does not produce or overwrite these.
- For components: if a component in the blueprint no longer appears in the Structure agent's output, keep it but add `"status": "not_found_in_latest_scan"`. Never delete.
- For architecture style: if the blueprint has a style and the synthesis disagrees, keep the blueprint's but add `"alternative_assessment"` from this scan.
- Increment `meta.scan_count`. Update `meta.last_scan` timestamp. Set `meta.schema_version: "2.0.0"`.
- **Never decrease confidence** on data from a deep scan unless there is strong contrary evidence.
- **Resolved findings stay** with `"status": "resolved"` — they are part of the project's architectural history.

Write the evolved blueprint to `.archie/blueprint.json`.

Then normalize to ensure canonical schema:
```bash
python3 .archie/finalize.py "$PROJECT_ROOT" --normalize-only
```

### 5b: Render CLAUDE.md, AGENTS.md, rule files

```bash
python3 .archie/renderer.py "$PROJECT_ROOT"
```

### 5c: Write scan_report.md

Get the current date/time and scan number from the blueprint (`meta.scan_count`):
```bash
date -u +"%Y-%m-%dT%H%M"
```

Create the scan history directory:
```bash
mkdir -p "$PROJECT_ROOT/.archie/scan_history"
```

Read `$PROJECT_ROOT/.archie/semantic_findings.json`, `$PROJECT_ROOT/.archie/blueprint.json`, `$PROJECT_ROOT/.archie/health.json`, and `$PROJECT_ROOT/.archie/health_history.json` for health trend.

Write the report to `.archie/scan_history/scan_NNN_YYYY-MM-DDTHHMM.md` (where NNN is the zero-padded scan number) and copy to `.archie/scan_report.md` (latest pointer).

Use this **exact** structure — this layout is shared with `/archie-deep-scan`; both produce structurally identical reports:

```markdown
# Scan Report — <repo name>

## Executive Summary
- Health score: X.XX (trend: up / down / stable vs previous scan from `health_history.json`)
- Systemic findings: N total (new: X, recurring: Y, worsening: Z, resolved: W)
- Top 3 systemic findings by severity x blast_radius:
  1. [severity] type — component name (blast: N)
  2. [severity] type — component name (blast: N)
  3. [severity] type — component name (blast: N)

## Systemic Findings (N)

<For each finding where `category == "systemic"` AND `lifecycle_status != "resolved"`, render with the full expanded treatment below. Order by severity (error > warn > info) then `blast_radius` descending.>

### [severity . lifecycle] type — component name
**Pattern:** <pattern_description — one sentence>
**Evidence:**
- location1 — short why
- location2 — short why
- (more...)
**Root cause:** <root_cause>
**Fix direction:** <fix_direction>
**Severity:** <severity> — blast_radius: N (delta: +K / -K / 0)
**Blueprint anchor:** <blueprint_anchor if present, else omit line>

## Localized Findings (M)

<Compact tables grouped by `type`. Only emit a subsection if at least one finding of that type exists. Use these exact table schemas.>

### Dependency violations (k)
| Sev | Location | Evidence | Fix |
|---|---|---|---|
| error | path/file:line | short detail | short fix |

### Cycles (k)
| Sev | Modules | Evidence | Fix |
|---|---|---|---|

### Complexity hotspots (k)
| Sev | Function | CC | Location | Why | Fix |
|---|---|---:|---|---|---|

### Pattern divergences (k)
| Sev | Location | Evidence | Fix |
|---|---|---|---|

### Rule violations (k)
| Sev | Rule | Location | Evidence | Fix |
|---|---|---|---|---|

### Semantic duplications (k)
| Sev | Canonical | Duplicates | Fix |
|---|---|---|---|

### Pattern erosion (k)
| Sev | File | Violated pattern | Fix |
|---|---|---|---|

### Decision violations (k)
| Sev | Decision | Location | Evidence | Fix |
|---|---|---|---|---|

### Trade-offs undermined (k)
| Sev | Trade-off | Location | Evidence | Fix |
|---|---|---|---|---|

### Pitfalls triggered (k)
| Sev | Pitfall | Location | Evidence | Fix |
|---|---|---|---|---|

### Responsibility leaks (k)
| Sev | Location | Evidence | Fix |
|---|---|---|---|

### Abstraction bypasses (k)
| Sev | Location | Evidence | Fix |
|---|---|---|---|

## Resolved Findings (W)

<Compressed list of findings where `lifecycle_status == "resolved"`. Group by `type`. Omit the section entirely if W == 0.>

## Mechanical Findings (p)

<Findings where `source == "mechanical"` — output of `drift.py` that AI analysis didn't subsume. Keep compact (1 line per item: severity, type, location, one-line detail). Omit the section if p == 0.>
```

**Rendering rules:**

- Order within Systemic Findings: severity (error > warn > info), then `blast_radius` descending.
- Within each Localized table, order by severity then by location string for stable diffs.
- "component name" in the Top-3 summary and Systemic headings comes from `scope.components_affected[0]` if present, else derived from the first location.
- `blast_radius_delta` renders as `+K` (worsening), `-K` (improving), or `0` (unchanged). Omit parentheses if the finding is new and delta is 0.
- When the aggregator produces zero findings in a section, include the heading only if the section has a count in parentheses (so `## Systemic Findings (0)` stays; empty Localized subsections are omitted).
- `blueprint_anchor` lines: include only when the field is non-null.

### 5d: Update satellite files

Append health scores to history:
```bash
python3 .archie/measure_health.py "$PROJECT_ROOT" --append-history --scan-type fast
```

Save ALL proposed rules (from Patterns agent) to `.archie/proposed_rules.json`:
1. Read existing `proposed_rules.json` (create as `{"rules": []}` if missing)
2. Append new proposed rules with `"source": "scan-proposed"` (keep AI-assigned confidence)
3. Skip if a rule with the same id already exists
4. Update confidence on existing proposed rules if the Patterns agent recommended changes
5. Write back

Derive the legacy `.archie/semantic_duplications.json` snapshot from the aggregated findings (for `/archie-share` + viewer backward compat):
1. Read `.archie/semantic_findings.json` (the aggregator's canonical output from Step 3)
2. Filter `findings` where `type == "semantic_duplication"`
3. For each matching finding, map to the legacy entry shape: `{function, locations, recommendation}`
   - `function`: derive from the finding's first location or from `pattern_description`
   - `locations`: `scope.locations` (list of "file:line" strings)
   - `recommendation`: `fix_direction`
4. Write to `.archie/semantic_duplications.json` as `{"duplications": [...], "scanned_at": "<ISO UTC>"}`
5. Overwrite on every scan — this is a snapshot, not append-only

### 5e: Clean up temp files

```bash
rm -f /tmp/archie_agent_structure.json /tmp/archie_agent_patterns.json /tmp/archie_agent_health.json /tmp/archie_agent_technology.json /tmp/archie_synthesis.json
```

Note: keep `.archie/health.json` — `/archie-share` needs it.

### 5f: Write telemetry

Record telemetry end:
```bash
TELEMETRY_STEP5_END=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

Create the telemetry directory and write the timing data:
```bash
mkdir -p "$PROJECT_ROOT/.archie/telemetry"
```

Assemble the telemetry JSON from the timestamps collected throughout the run and write it to `$PROJECT_ROOT/.archie/telemetry/scan_YYYY-MM-DDTHH-MM-SSZ.json` using the `TELEMETRY_STEP1_START` timestamp for the filename.

The telemetry file must follow this schema:
```json
{
  "command": "archie-scan",
  "started_at": "<TELEMETRY_STEP1_START>",
  "completed_at": "<TELEMETRY_STEP5_END>",
  "steps": [
    {"name": "scan", "started_at": "<TELEMETRY_STEP1_START>", "completed_at": "<TELEMETRY_STEP1_END>"},
    {"name": "gather", "started_at": "<TELEMETRY_STEP2_START>", "completed_at": "<TELEMETRY_STEP2_END>"},
    {"name": "aggregate", "started_at": "<TELEMETRY_STEP3_START>", "completed_at": "<TELEMETRY_STEP3_END>"},
    {"name": "synthesis", "started_at": "<TELEMETRY_STEP4_START>", "completed_at": "<TELEMETRY_STEP4_END>", "model": "sonnet"},
    {"name": "render", "started_at": "<TELEMETRY_STEP5_START>", "completed_at": "<TELEMETRY_STEP5_END>"}
  ]
}
```

Write this JSON to the telemetry file. Use a bash heredoc to write the file — this is writing a text file, not running inline Python.

---

## Present Results

Show the user a summary of the scan results:

1. **Health score + trend** (one line):
   > Health: 0.XX erosion, 0.XX gini, 0.XX top-20% share (trend: improving/stable/degrading)

2. **Findings summary**:
   > Findings: N systemic (X new, Y worsening), M localized, W resolved

3. **Top 3 systemic findings** by severity x blast_radius (one line each):
   > 1. [error] god_component — shared (blast: 22)
   > 2. [warn] fragmentation — handlers (blast: 4)
   > 3. [info] trajectory_degradation — core (blast: 3)

4. **Rules proposed**: N new rules proposed by the Patterns agent. Present as a numbered checklist:
   > **Proposed rules:**
   > 1. [warn] "Always use the API client for HTTP calls" (confidence: 0.85)
   > 2. [error] "Never import from apps/ in packages/" (confidence: 0.92)
   >
   > **Reply with the numbers to adopt** (e.g., `1, 2` or `all` or `none`).
   > Adopted rules take effect immediately. Skipped rules remain in `/archie-viewer` -> Rules tab.

5. **Blueprint status**: "Blueprint evolved (scan #N)" or "Blueprint created (first scan)"

6. **Path to full report**: `.archie/scan_report.md`

**Wait for the user's response on rule adoption.** Then process:

- Numbers → adopt those rules into `.archie/rules.json` with `"source": "scan-adopted"` (keep AI confidence)
- `all` → adopt every proposed rule
- `none` → skip (rules stay in `proposed_rules.json`)

Print confirmation:
> Adopted N rules, skipped M (available in /archie-viewer -> Rules tab). Scan #N complete — blueprint evolved.

# Shared fragment — Agent: Structure (architecture, components, dependencies)

> **This is the source of truth for the Structure agent prompt used by both `/archie-scan` and `/archie-deep-scan`.**
> Slash commands can't include other files, so the block below is physically inlined into both.
> When updating this fragment, update BOTH archie-scan.md AND archie-deep-scan.md, then re-sync to npm-package/assets/.

---

You are analyzing the ARCHITECTURE and DEPENDENCIES of a codebase. You have access to scan data and the existing blueprint (if any).

**Your inputs:**
- `.archie/skeletons.json` — every file's header, class/function signatures, imports, line counts. This is your primary data source.
- `.archie/dependency_graph.json` — resolved directory-level graph. Node schema: `{id, label, component, inDegree, outDegree, inCycle, fileCount}` — use `id` for directory path, NOT `path`. Edge schema: `{source, target, weight, crossComponent}`. Do NOT write ad-hoc Python to analyze this data — use it directly in your analysis.
- `.archie/scan.json` — file tree, import graph, detected frameworks, `frontend_ratio`
- `.archie/blueprint.json` — existing architectural knowledge (if any)

**Your job:**

### 1. Project Type & Platforms
- Identify if this is a monorepo, single app, microservice, serverless, full-stack, library, etc.
- List ALL platforms found: backend, web-frontend, mobile-ios, mobile-android, desktop, CLI, shared/common
- List main entry point files for EACH platform (main.py, index.ts, App.tsx, AppDelegate.swift, MainActivity.kt, main.dart, etc.)
- Document module/package organization approach

### 2. Components
Identify main components from actual code — class names, imports, file organization. For each component:
- **name**: Component name
- **location**: Directory path (MUST exist in file_tree)
- **platform**: backend | frontend | shared | ios | android
- **responsibility**: Describe what the code DOES, not what names suggest. BAD: "Handles business logic". GOOD: "Orchestrates weather data fetching via WeatherProvider, manages profile state, coordinates push notification scheduling". Reference actual class names and services.
- **depends_on**: From actual import statements
- **exposes_to**: What other components consume from it
- **key_interfaces**: Actual method/function names with brief description. For API routes, list ONLY methods actually implemented — do NOT assume CRUD.
- **key_files**: With descriptions of what each file does (paths MUST exist in file_tree)

### 3. Layers
Analyze ALL platforms (backend AND frontend). Only document layers you can clearly identify from:
1. Import patterns between directories
2. Directory structure and naming
3. Actual code organization

**If no clear layers exist**, set structure_type to flat, modular, or feature-based and document the actual structure.

For each layer found, document: name, platform (backend|frontend|shared), location, responsibility (SPECIFIC — reference actual classes), contains (component types), depends_on (from imports), exposes_to, key_files.

Common backend patterns (only if they ACTUALLY exist): Presentation/API (routes, controllers, DTOs), Application/Service (orchestration, use cases), Domain (entities, interfaces), Infrastructure (database, external APIs, caching).
Common frontend patterns (only if they ACTUALLY exist): Pages/Views, Features/Containers, Components/UI, Hooks/Services, State/Store.

### 4. Architecture Style
Describe in plain language. Examples: "Actor-based with message passing", "Event-sourced with CQRS separation", "Feature-sliced with co-located concerns", "Traditional layered with services and repositories", "Functional core with imperative shell" — or describe something completely unique.

**DO NOT assume this is a "layered architecture", "MVC", "Clean Architecture", or any specific pattern.** DO NOT look for patterns that match your training data or force observations into predefined categories. Describe the ACTUAL file organization, identify how files relate based on naming and imports, and note conventions unique to this codebase.

### 5. File Placement & Naming
- Where do tests, configs, components, services actually live? With naming patterns observed.
- Search the file_tree for where test files, config files, build output, and generated code actually live. Do NOT assume conventional locations.
- Document actual naming conventions: PascalCase components, snake_case utils, kebab-case files, etc. With 2-4 examples each.

### 6. Framework Usage
Catalog external frameworks/libraries from import statements. For each, note the framework name and usage scope.

**Efficiency rule:** Read skeletons.json + dependency_graph.json first — they contain every file's path, class/function signatures, imports, and first lines. This is sufficient for pattern detection, outlier finding, and most analysis. Only use the Read tool on source files when the skeleton genuinely lacks the information needed to make a judgment.

**GROUNDING RULES — every claim must come from code you READ, never from names or conventions.**
1. **Paths**: Only reference file/directory paths that appear in scan.json file_tree. Do NOT infer conventional paths.
2. **Component responsibility**: Read the actual source file. Describe what the code DOES, not what the filename or class name suggests.
3. **API/route/endpoint methods**: Read the actual handler code. List ONLY the methods/verbs/actions actually implemented. Do NOT assume CRUD.
4. **File placement rules**: Search the file_tree for where files actually live. Do NOT assume conventional locations.

**Pattern observations (for synthesis to consume):**
Raw cross-file anomalies in your domain — NOT finished findings, just signals for the synthesis step to contextualize. Each observation: `{type, evidence_locations, note}`.

Types in your domain:
- `dep_magnet` — directory/module with unusually high fan-in across unrelated domains
- `layer_cycle` — import cycle crossing a layer boundary
- `inverted_dependency` — lower-level module importing from higher-level
- `workspace_boundary_crossed` — import crossing workspace boundary unexpectedly (monorepo only)
- `high_fan_in_rising` — a node's in-degree is high AND growing vs prior scan

Example:
```json
{"type": "dep_magnet", "evidence_locations": ["packages/shared"], "note": "fan-in 22 across auth/storage/UI/logging — unrelated domains"}
```

**Findings:**
Emit findings per `.claude/commands/_shared/semantic_findings_spec.md`. Your domain is **architecture and dependencies**.
Before emitting, Read the spec file and follow S1 (schema), S2 (quality gate), S3 (severity rubric), S4 (taxonomy).

Produce two categories:
- **Systemic** (category: systemic): `god_component`, `boundary_violation`. Each with >=3 evidence locations, pattern_description, root_cause, fix_direction, blast_radius.
- **Localized** (category: localized): `dependency_violation`, `cycle`. Each with a single location, root_cause, fix_direction.

All findings MUST carry `synthesis_depth: "draft"` and `source: "agent_structure"`.

Do NOT emit count caps. Emit every finding you can substantiate with concrete evidence. Before emitting, verify each finding against the quality gate in S2 of the spec — dropped candidates are better than padded ones.

**Workspace-aware addendum (only when `SCOPE === "whole"`):**

This is a workspace monorepo (`MONOREPO_TYPE={type}`, N workspaces under paths `<workspaces>`). Treat each workspace member as a top-level component in `components`:
- `name` = workspace `name` from its `package.json` (or equivalent for Cargo/Gradle)
- `location` = workspace directory path relative to `$PROJECT_ROOT`
- `platform` = inferred from workspace contents (frontend/backend/shared/etc.)
- `responsibility` = inferred from package `description` + entry points
- `depends_on` = other workspace members it imports (read its `package.json` dependencies, filter to workspace names)

Additionally produce a top-level `workspace_topology` field:
```json
"workspace_topology": {
  "type": "{MONOREPO_TYPE}",
  "members": [{"name": "...", "path": "...", "role": "app|lib|tool"}],
  "edges": [{"from": "name-a", "to": "name-b", "count": 3}],
  "cycles": [["a", "b", "a"]],
  "dependency_magnets": [{"name": "shared", "in_degree": 8}]
}
```

Surface cross-workspace import cycles as findings with severity `error`. Surface workspaces with very high fan-in (top quartile of in_degree) as `dep_magnet` pattern observations. Reference workspace members by **name** (not path) in all cross-references.

**Output:** Write to `/tmp/archie_agent_structure.json`:
```json
{
  "meta": {
    "architecture_style": "plain language description",
    "platforms": ["backend", "web-frontend"],
    "executive_summary": "3-5 factual sentences: what this does, primary tech, architecture style. No filler."
  },
  "components": [
    {
      "name": "", "location": "", "platform": "",
      "responsibility": "", "depends_on": [], "exposes_to": [],
      "key_interfaces": [{"name": "", "methods": [], "description": ""}],
      "key_files": [{"file": "", "description": ""}]
    }
  ],
  "layers": [
    {
      "name": "", "platform": "", "location": "",
      "responsibility": "", "contains": [], "depends_on": [], "exposes_to": []
    }
  ],
  "architecture_rules": {
    "file_placement_rules": [
      {"component_type": "", "naming_pattern": "", "location": "", "example": ""}
    ],
    "naming_conventions": [
      {"scope": "", "pattern": "", "examples": []}
    ]
  },
  "workspace_topology": {},
  "pattern_observations": [
    {"type": "dep_magnet", "evidence_locations": ["packages/shared"], "note": "fan-in 22 across unrelated domains"}
  ],
  "findings": [
    {
      "category": "systemic",
      "type": "god_component",
      "severity": "error",
      "scope": {"kind": "system_wide", "components_affected": ["packages/shared"], "locations": ["apps/webui/src/auth.ts:14", "apps/electron/src/storage.ts:3", "apps/webui/src/ui/Button.tsx:1"]},
      "pattern_description": "shared/ accumulates responsibilities from 7 unrelated domains",
      "evidence": "22 consumers import from packages/shared across auth, storage, UI, logging",
      "root_cause": "every cross-cutting util was added to shared without domain boundary; decision D.3 treated shared as primitives but actual usage crosses domains",
      "fix_direction": "split into packages/{auth, storage, ui-primitives, logging}; migrate per-domain starting with auth",
      "blueprint_anchor": "decision:D.3",
      "blast_radius": 22,
      "synthesis_depth": "draft",
      "source": "agent_structure"
    },
    {
      "category": "localized",
      "type": "dependency_violation",
      "severity": "error",
      "scope": {"kind": "single_file", "components_affected": ["apps/webui"], "locations": ["apps/webui/src/app.ts:42"]},
      "evidence": "apps/webui imports from apps/electron/src/shared (inverted)",
      "root_cause": "shared helper never extracted to packages/; apps reach sideways instead",
      "fix_direction": "extract to packages/shared-ui or duplicate the helper in webui",
      "blueprint_anchor": null,
      "synthesis_depth": "draft",
      "source": "agent_structure"
    }
  ]
}
```

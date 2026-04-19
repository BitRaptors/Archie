# Archie LLM Wiki — Design Spec

- **Date:** 2026-04-17
- **Author:** Csaba (brainstorm with Claude Opus 4.7)
- **Status:** Draft, pending user review
- **References:**
  - [Karpathy's LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
  - [llmwiki.app](https://llmwiki.app) — hosted Next.js implementation of Karpathy's pattern
  - [safishamsi/graphify](https://github.com/safishamsi/graphify) — closest code-oriented precedent

## 1. Problem

Archie's deep-scan pipeline produces a richly relational `blueprint.json` — decisions link to each other via `forced_by`/`enables`, components via `depends_on`/`exposes_to`, pitfalls link to their causal decisions via `stems_from`, patterns to scenarios via `when_to_use`. The `renderer.py` output today flattens this graph into five separate markdown files (`CLAUDE.md`, `AGENTS.md`, `.claude/rules/*.md`) as **prose**. The cross-references exist as English sentences, not as navigable links. Consequences for agent work in the consumer repo:

1. An agent implementing a new feature cannot browse existing capabilities — it often reimplements something that already exists.
2. When changing a component, the agent cannot discover which capabilities depend on it without grep-spelunking.
3. When making a decision, the agent cannot see which pitfalls stem from similar past decisions.
4. There is no single entry point the agent opens "before any task" to orient itself.

The user wants the generated documentation to function like a **wiki for the app**: a linked, browsable, cross-referenced artifact where every concept has its own page and the relationships are first-class.

## 2. Goals and non-goals

**Goals:**

- Generate a markdown wiki under `.archie/wiki/` as a new deterministic output of `/archie-deep-scan`, refreshed incrementally by `/archie-scan`.
- Surface the relational graph already present in `blueprint.json` as navigable markdown links plus auto-generated "Referenced by" sections.
- Add a new **Capabilities** page type — user-facing features (e.g. "Auth flow", "Payment pipeline") discovered by a new Wave 1 capabilities agent — linking to the components, decisions, patterns, and pitfalls that realize them.
- Preserve **provenance** on every claim: whether it came from the deterministic scanner, Wave 1 extraction, or Wave 2 reasoning.
- Keep the existing outputs (`CLAUDE.md`, `AGENTS.md`, `.claude/rules/*.md`) unchanged in v1. Purely additive.

**Non-goals (explicit, for v1):**

- Replace `CLAUDE.md` / `AGENTS.md` / `.claude/rules/` — stays for v2.
- Run community-detection / graph clustering (graphify uses NetworkX + Leiden) — the AI capabilities agent does this conceptually, without adding a heavy Python dependency.
- Serve the wiki through an MCP server — the agent reads markdown natively with `Read`.
- Automatic PreToolUse hook that warns "did you check the wiki?" — considered for v1.2 after we see real usage.
- Compounding Karpathy-style `log.md` + per-query ingest — considered for v2 once the base wiki proves itself.

## 3. User-facing surface

### 3.1 CLAUDE.md patch (added by renderer)

~8 lines appended after the existing summary:

```markdown
## Before you implement anything

Open `.archie/wiki/index.md` and scan the "Capabilities" list. If your task
matches an existing capability, open that page and follow links to decisions
and pitfalls before coding. Extending beats reimplementing.
```

### 3.2 AGENTS.md patch (added by renderer)

New "Using the Archie Wiki" section (~20 lines) with the three-step consumption protocol: read index → check capability match → follow links to components/decisions/pitfalls. When touching an existing component, read its "Referenced by" section to see what ripples.

### 3.3 `.archie/wiki/` directory layout

```
.archie/wiki/
  index.md                       # agent entry point
  capabilities/<slug>.md         # new, from Wave 1 capabilities agent
  decisions/<slug>.md            # from blueprint.decisions[]
  components/<slug>.md           # from blueprint.components[]
  patterns/<slug>.md             # from blueprint.communication / patterns
  pitfalls/<slug>.md             # from blueprint.pitfalls[]
  _meta/
    backlinks.json               # precomputed reverse edges
    provenance.json              # per-page source + evidence + SHA256 hash
```

### 3.4 Link format

Standard markdown relative paths only: `[Auth Flow](../capabilities/auth-flow.md)`. No special syntax, no build step, no resolver. An agent's `Read` tool follows them natively.

Backlinks are rendered **inline** at the bottom of every page under a `## Referenced by` section — the agent does not need to open `_meta/backlinks.json`. The JSON exists for the viewer UI and lint, not for agent consumption.

### 3.5 Viewer integration

`archie/standalone/viewer.py` already serves the blueprint dashboard over zero-dep HTTP. It gains a `/wiki/*` route that:

- Renders the markdown to HTML using the same minimal renderer already in the module.
- Generates a sidebar from `_meta/backlinks.json` grouped by page type.
- The existing `/archie-viewer` command adds a "Wiki" tab to its UI.

Viewer integration is **optional polish** — the markdown wiki is self-contained and usable without it.

## 4. Page schemas

Every page carries YAML frontmatter for machine-readable metadata and structured markdown sections. Slugs are `kebab-case` derived from the entity name, unique per type.

### 4.1 Capability page

```markdown
---
type: capability
slug: auth-flow
provenance: INFERRED              # Wave 1 capabilities agent
evidence:
  - features/auth/**
  - routes matching /api/auth/*
last_refreshed: 2026-04-17
---

# Auth Flow

> **Source:** Wave 1 capabilities agent · **Evidence:** 8 files under `features/auth/`
> **Last refreshed:** 2026-04-17 (scan) · **Provenance:** INFERRED

One-line purpose.

## Entry points

- Route: `POST /api/auth/login` → `AuthController.login`
- Route: `POST /api/auth/logout`
- UI: `screens/LoginScreen.tsx`

## Components

- [AuthService](../components/auth-service.md) — token lifecycle
- [SessionStore](../components/session-store.md) — session persistence

## Decisions

- [JWT over sessions](../decisions/jwt-over-sessions.md)
- [Refresh-token rotation](../decisions/refresh-token-rotation.md)

## Patterns

- [Repository](../patterns/repository.md) for user data
- [Decorator](../patterns/decorator.md) for auth middleware

## Pitfalls

- [Token in localStorage](../pitfalls/token-in-localstorage.md)

## Key files

- `features/auth/AuthService.ts`
- `features/auth/AuthController.ts`

## Referenced by

(auto-generated from `_meta/backlinks.json`)
```

### 4.2 Decision page

Derived from `blueprint.decisions[]`. Frontmatter includes `type: decision`, `provenance: EXTRACTED|INFERRED`. Sections: `**Chosen**`, `**Rationale**`, `**Forced by**`, `**Enables**`, `**Alternatives rejected**`, `**Trade-offs**`, `**Affects capabilities**` (backlink), `**Related pitfalls**` (`stems_from` backlink), `## Referenced by`.

### 4.3 Component page

Derived from `blueprint.components[]`. Sections: `**Purpose**`, `**Depends on**` (links), `**Exposes to**` (links), `**Contracts**` (API/events/UI it provides or expects), `**Key files**`, `**Used in capabilities**` (backlink), `**Subject to pitfalls**` (backlink), `## Referenced by`.

### 4.4 Pattern page

Derived from `blueprint.communication` and any `patterns` section. Sections: `**Definition**`, `**When to use**`, `**When NOT to use**`, `**Used by components**` (backlink), `**Used in capabilities**` (backlink), `## Referenced by`.

### 4.5 Pitfall page

Derived from `blueprint.pitfalls[]`. Sections: `**Description**`, `**Stems from**` (link), `**Recommendation**`, `**Affects components**` (backlink), `**Affects capabilities**` (backlink), `**Detection rule**` (link to `.claude/rules/*.md` if one exists), `## Referenced by`.

### 4.6 index.md

```markdown
# {Project name} Wiki

## Before you implement anything

These capabilities already exist. Check whether your task belongs to one:

- [Auth Flow] — login, signup, token rotation
- [Payment Pipeline] — checkout + refund
- ...

## Browse by type

Capabilities (N) · Decisions (N) · Components (N) · Patterns (N) · Pitfalls (N)

## Constraint roots

Root-level `forced_by` constraints from which many decisions flow.

## Recent updates

- 2026-04-17: Auth Flow refreshed (3 files changed)

## Orphans

Pages with no inbound backlinks (wiki-lint flag).
```

### 4.7 Plan 5a page types

Added in Plan 5a (render-layer enrichment). All types render from existing blueprint fields — no new AI calls.

- **`guidelines/<slug>.md`** — One page per `implementation_guidelines[]` entry. Sections: Category, Pattern, Libraries, Key files, Usage example (fenced code), Tips. Slug derived from the `name` field.
- **`rules/architecture.md`** — Single page combining `architecture_rules.file_placement_rules` + `naming_conventions` as tables. Skipped entirely if both sub-lists are empty.
- **`rules/development.md`** — Single page rendering `development_rules[]` grouped by `category` (preserving insertion order), with `Uncategorized rules` section at the bottom for entries without a category. Each rule shows text, optional rationale, and optional applies_to globs as code-formatted.
- **`technology.md`** — Single page with `## Stack` (table: Category / Name / Version / Purpose), `## External integrations` (bullets from `communication.integrations`), `## Run commands` (fenced bash block from `technology.run_commands`).
- **`quick-reference.md`** — Single page with `## Which pattern should I use?` table, `## Pattern decision tree` from `communication.pattern_selection_guide`, `## Error handling` table from `quick_reference.error_mapping`.
- **`frontend.md`** — Conditional page (only if `blueprint.frontend` has at least one populated field). Renders Framework / State management / Routing / Styling / Data fetching / Rendering strategy / UI components as inline bullets, plus a `## Conventions` section.
- **`architecture.md`** — Conditional page containing `meta.executive_summary` prose + `## Architectural style` + `## System diagram` with the `architecture_diagram` (Mermaid) in a fenced `` ```mermaid `` block.
- **`decisions/index.md`** — Overview page inside the existing `decisions/` directory. Renders `architectural_style`, `trade_offs` (table), `out_of_scope` (list), and an "All decisions" list linking to each per-decision page (sorted by title).

### 4.8 Component page enrichment (Plan 5a)

`components/<slug>.md` pages gain (all conditional on field presence):

- Inline `**Platform:**` and `**Location:**` lines directly under the title.
- `## Responsibility` prose section (from `component.responsibility`).
- `## Public interface` listing each `key_interfaces[]` entry with backtick-formatted signature and description.
- `## Key files` listing file paths (backtick-formatted) with descriptions.

`depends_on`, `exposes_to`, and the auto-generated `## Referenced by` stay unchanged.

### 4.9 Pitfall page enrichment (Plan 5a)

`pitfalls/<slug>.md` pages gain a `## Applies to` section with file paths rendered inside a fenced code block (so agents can grep the paths cleanly from raw text). Emitted only when `pitfalls[*].applies_to` is a non-empty list.

### 4.10 Index overhaul (Plan 5a)

`index.md` gains a `## System overview` section at the top — before the `## Before you implement anything` capability list. It contains `meta.platforms` inline, `meta.executive_summary` prose, and a `### Architecture style` sub-section from `meta.architecture_style`. The `## Browse by type` block was extended with rows for Guidelines, Rules, Technology, Quick reference, Frontend (conditional), and Architecture (conditional). The Decisions section gained a pointer to `./decisions/index.md` at the top.

### 4.11 Data model page (Plan 5b.1)

`data-models/<slug>.md` — One page per `data_models[]` entry. Renders structs/classes/interfaces representing domain entities (e.g. `User`, `Place`, `Order`) so agents can understand the data shape without grepping source.

Page sections (all conditional on field presence):
- Inline `**Location:**` (file path, backtick-formatted) and `**Purpose:**` lines under the title.
- `## Fields` — table with `Name | Type | Nullable` columns, one row per `fields[]` entry. Field names and types are backtick-formatted; `nullable` renders as `yes`/`no`.
- `## Used by` — bullet list of components referenced via `data_models[*].used_by_components`. Each entry links to `../components/<slug>.md` when known; unknown component names degrade to plain text.

Slug derived from the `name` field via the same `slugify_unique` helper used elsewhere. Frontmatter: `type: data-model`, `slug`, `provenance` (defaults to `INFERRED`).

Component pages also gain a reverse `## Data models` section listing every entity that includes the component in its `used_by_components` list (computed in `build_wiki` via `_build_component_to_data_models`). The section is omitted when no data models reference the component.

`index.md` gains:
- A `**Data models (N)** — entities moving through the system` row in `## Browse by type`, positioned between Components and Patterns.
- A dedicated `## Data models` section listing each entry alphabetically with links to `./data-models/<slug>.md`, positioned between `## Components` and `## Patterns`.

Both index additions only appear when `data_models[]` produces at least one slug.

Synthesis: a new Wave 1 "Data models agent" (mirrors the Capabilities agent) extracts entries from source. `merge.merge_data_models()` validates each entry's `used_by_components` refs against `blueprint.components[*].name`, drops unknown refs individually (entry survives), and silently skips nameless entries.

### 4.12 Utilities catalog (Plan 5b.2)

`utilities.md` — Single page rendering reusable helper functions discovered by the scanner. Goal: agents can grep one page before reimplementing `formatDate`, `deduplicate`, or extension methods that already exist.

Source: `scan.json.symbols[]` (deterministic, no AI). Each symbol entry has `file`, `name`, `kind`, `signature`, `exported`, `language`. The scanner ships per-language extractors (Swift, TypeScript/JavaScript, Python in v1; Kotlin/Go are explicit follow-ups).

Page structure:
- `## <Category> (N function[s])` heading per group, alphabetical with `Uncategorized` always last.
- Each entry: bolded backtick-formatted `signature`, optional ` _(extension)_` marker when the symbol name contains `.`, then a second line with the file path in backticks for grep.

Categorization heuristic (first match wins):
1. Filename topic — strip `Ext`/`Utils`/`Helper` suffix, match against an allowed-topic set (`Date`, `String`, `Array`, `Number`, `URL`, `JSON`, `File`, `Path`, `Color`, `Time`).
2. Function-name prefix — `format*` → "Formatting", `is*`/`has*`/`can*`/`should*` → "Predicate", `to*`/`from*`/`parse*`/`stringify*` → "Conversion".
3. Fallback → "Uncategorized".

Filtering (in scanner): test files excluded via path patterns (`Tests/`, `__tests__/`, `tests/`, `*_test.py`, `*.test.ts`, etc.), private/non-exported functions excluded per language convention, names starting with `_` excluded.

`index.md` gains a `**Utilities (N functions)** — existing helpers; grep before implementing new ones` row in `## Browse by type` and a one-line `## Utilities` section linking to the catalog page. Both appear only when at least one symbol was extracted.

Out of scope for v1: per-function pages, AI-enhanced categorization, calling-convention normalization across languages, function-body extraction. See Plan 5b.2 "Known follow-ups" for the full list.

### 4.13 Wiki polish bundle (Plan 5c)

Three small refinements to the data-model and backlink rendering:

- **Page-type backlinks** — `wiki_index._page_type_from_dir` now recognizes `data-models/` (singular: `data-model`), `guidelines/`, `rules/`, and the root-level single-page outputs (`utilities.md` → `utility-catalog`, `technology.md`, `quick-reference.md`, `frontend.md`, `architecture.md`, `index.md`) so the auto-injected `## Referenced by` section displays a meaningful page-type label instead of `(unknown)`.
- **Data-model relations** — `render_data_model` gains a `## Related models` section listing entities referenced via field types. Detection (`_extract_data_model_refs`) is word-boundary regex against the set of known data-model names; multi-field references coalesce into a single line per related model (e.g. `[Place](./place.md) — via \`homeLocation\`, \`workLocation\` fields`). Self-references are excluded. Section sits between `## Fields` and `## Used by`.
- **Field-type normalization** — `_normalize_field_type` maps language-specific optional notations (`String?`, `Optional<String>`, `Optional[str]`, `str | None`) to a canonical lowercase + `?` form. Primitive type names (`String`/`Int`/`Bool`/`Float`/...) are lowercased; custom and acronym types are preserved verbatim. Collection wrappers (`[Foo]`, `Array<Foo>`, `List<Foo>`) pass through unchanged minus optionality. The Fields table renders `canonical (raw)` when the two differ — agents see the canonical form first, with the original kept for fidelity.

### 4.14 Blueprint freshness check (Plan 5d)

`/archie-deep-scan` previously skipped the Wave 1 agent set when the orchestrator detected no source-code changes since the last baseline. This optimization broke whenever a new Wave 1 agent was added (e.g. Plan 5b.1's `data_models`): the existing blueprint lacked the new key, but the optimization reused it anyway, so the new agent never produced output. Confirmed in production: a 2026-04-19 deep-scan of Gasztroterkepek.iOS reused the prior-day blueprint and silently regressed the data-models feature.

The fix is a small standalone helper `check_blueprint_completeness.py` that runs as **Step 0.5** in the deep-scan command (before Step 1 / scanner). It compares `blueprint.json`'s top-level keys against an `EXPECTED_KEYS` list maintained inside the helper (each entry annotated with the plan that introduced it). When any expected key is missing — or the blueprint is malformed JSON — the helper exits non-zero and the deep-scan command writes a marker file `/tmp/archie_force_full_wave1_<project>` that Step 3 must consult before applying the "no code changes → reuse blueprint" optimization. The marker is cleaned up in Step 9 alongside other `/tmp` artifacts.

Status semantics:
- `MISSING` — `.archie/blueprint.json` does not exist; exit 0 (first-run logic in deep-scan handles it).
- `OK` — all expected keys present; exit 0.
- `STALE: missing <key1> (<intro_plan>), <key2> (<intro_plan>)` — sorted by intro plan version then key name; exit 1.
- `MALFORMED` — JSON parse failure; exit 1.

Empty arrays count as PRESENT (the agent ran and returned nothing legitimately). The check operates on key presence only — does NOT validate inner structure (the per-agent merger handles that).

Maintenance contract: any plan that adds a new Wave 1 agent must add a matching entry to `EXPECTED_KEYS` in the same commit. Without it, the new agent will silently regress on the first project upgrade after the new toolchain rolls out.

## 5. Generation pipeline

### 5.1 Deep-scan (full build)

Today's pipeline: Scanner → Wave 1 (parallel) → Wave 2 Opus → Normalize → Render → Validate → Intent Layer → Scan report.

Changes:

- **Wave 1** gains one new agent: `capabilities_agent` (Sonnet, parallel with structure/patterns/technology/ui_layer). Trigger condition: `scan.json` contains ≥ 5 files under plausibly-feature directories (heuristic in builder: `features/`, `routes/`, `controllers/`, `pages/`, or framework-specific equivalents). If the heuristic misses, the agent returns an empty list and the Wave 2 Opus-reasoning pass can still populate `blueprint.capabilities[]` from other signals.
- **Wave 2 Opus** reasoning consumes the capabilities agent's output and weaves it into the final `blueprint.json` under `capabilities[]`, wiring each capability to `uses_components[]` and `constrained_by_decisions[]` using existing slug IDs.
- **New Step 8 `wiki_builder.py`** runs after Intent Layer. Input: `blueprint.json`, `scan.json`, `.archie/intents/*.md`. Output: full rewrite of `.archie/wiki/**` plus `_meta/backlinks.json` and `_meta/provenance.json`. Invariant: deletes and regenerates the wiki directory; deep-scan is authoritative.
- **Step 9 Scan report** gets a `## Wiki summary` section: page counts per type, orphans, stale-evidence warnings.

### 5.2 Scan (incremental update)

1. Run scanner → new `scan.json`.
2. Diff against previous `scan.json` → list of added / modified / deleted files.
3. `wiki_builder.py --incremental`:
   - Load `_meta/provenance.json`: every page's evidence glob(s).
   - `affected_pages = { page | page.evidence ∩ changed_files ≠ ∅ }`.
   - If any affected page is a capability → re-run `capabilities_agent` with a **scoped prompt** covering only the affected directories (token-cost ~ $0.01–$0.02).
   - Re-render affected pages from current blueprint + new capability outputs.
   - SHA256-diff each re-rendered page vs its stored hash. Pages whose content is unchanged are not written; pages whose content is changed update both file and `provenance.last_refreshed`.
   - Rebuild `_meta/backlinks.json` (cheap — pure parse).
4. `scan_report.md` appends a `## Wiki updates` section listing the actually-changed pages.

**Architectural safety valve:** if the incremental path detects that blueprint-level structure changed (decisions, components, pitfalls — anything outside capabilities), it aborts incremental update and emits a warning instructing the user to run `/archie-deep-scan`. Scan is intentionally capability-scoped; architecture-level changes require re-reasoning.

### 5.3 Lint (part of `/archie-scan`)

The scan LLM inspects the wiki alongside its existing rule-review duties and flags in `scan_report.md`:

- **Orphan**: page has zero inbound backlinks (excluded: `index.md`).
- **Broken link**: markdown link target does not exist.
- **Stale evidence**: page evidence globs match zero current files.
- **Dangling backlink**: `_meta/backlinks.json` references a nonexistent page.
- **Contradiction**: `pitfall.stems_from: decision-X` but `decision-X.md` has no corresponding backlink.

Suggestions are written to the report; automatic fixes are out of scope for v1.

## 6. Code modules

New files (in `archie/standalone/`, mirrored to `npm-package/assets/` per existing sync convention):

- `wiki_builder.py` — blueprint + scan → markdown files. CLI entrypoint `python3 wiki_builder.py <project> [--incremental]`.
- `wiki_index.py` — builds `_meta/backlinks.json` and `_meta/provenance.json`. Imported by `wiki_builder.py`; may also be called standalone for lint.
- `agents/capabilities.py` — prompt template + response parser for the new Wave 1 capabilities agent. Follows the same shape as existing agent modules.

Touched:

- `archie/standalone/renderer.py` — appends the CLAUDE.md "Before you implement anything" patch and the AGENTS.md "Using the Archie Wiki" section. No other changes.
- `archie/standalone/viewer.py` — adds `/wiki/*` route. Gated behind `--with-wiki-ui` flag for the first release so existing viewer behavior is unchanged by default.
- `.claude/commands/archie-deep-scan.md` — new bash step invoking `python3 .archie/wiki_builder.py "$PWD"` after the Intent Layer phase. Add "Wiki summary" to the scan report section.
- `.claude/commands/archie-scan.md` — new bash step invoking `python3 .archie/wiki_builder.py "$PWD" --incremental` and (for lint) `python3 .archie/wiki_index.py "$PWD" --lint`. Follows the existing "every operation has a dedicated command; never write inline Python" constraint.
- `archie/engine/scan.py` — if engine-level orchestration is used for an equivalent Python entry point, mirror the same call sequence there so the behavior is consistent between CLI-invoked and skill-invoked flows.
- `scripts/verify_sync.py` — new canonical files registered.

Not touched: `intent_layer.py`, `measure_health.py`, `install_hooks.py`, `platform_rules.json`, existing rules renderers.

## 7. Feature flag

`ARCHIE_WIKI_ENABLED` env var (default: `true`). Also readable from `.archie/archie.json`. When `false`:

- Deep-scan skips Step 8 and does not call `capabilities_agent`.
- Scan does not call incremental update.
- Renderer does not inject the CLAUDE.md / AGENTS.md patches.
- Viewer does not expose `/wiki/*`.

This lets existing consumers opt out if the wiki is unwanted, and keeps the failure mode graceful.

## 8. Testing strategy

### 8.1 Unit tests (`tests/wiki/`)

- **`test_wiki_builder.py`** — fixture `blueprint.json` + `scan.json` → asserts: every expected page exists, frontmatter schema per type is correct, every markdown link target exists, `A → B` forward link implies `A` in `B`'s `## Referenced by`.
- **`test_capabilities_agent.py`** — mocked Sonnet responses: parser validates that all referenced component/decision slugs exist in the blueprint; unknown references raise `ValidationError`.
- **`test_provenance.py`** — unchanged blueprint → zero dirty pages; rename one component → only directly-affected pages change, backlinks updated.
- **`test_lint.py`** — synthetic wiki containing orphan + broken link + stale evidence + contradiction; lint surfaces each; clean wiki produces zero findings (no false-positives).

### 8.2 Integration tests (`tests/integration/`)

Run deep-scan + scan on two existing fixture repos (small Python CLI + small React app). Snapshot expected structure under `tests/fixtures/expected_wiki/` and assert:

- Page-count per type matches snapshot.
- Key backlinks present.
- Index sections populated.

Not byte-perfect (AI outputs vary) — structural assertions only.

**Incremental scenario:** modify one known file → assert that ≤ 3 pages change (via SHA256-hash comparison).

### 8.3 Manual validation

Before declaring v1 done, run 5 fictional tasks ("implement user login", "add refresh token", "fix session leak", "add 2FA", "migrate from JWT to sessions") **with** and **without** the wiki on a fixture project. Rubric:

- Did the agent reference relevant existing capabilities / pitfalls in its plan?
- Did it propose creating something that already exists?
- Did it cite the wiki explicitly?

Manual evaluation — not a CI gate, but a go/no-go signal for release.

## 9. Cost

| Flow | Added AI calls | Estimated cost per run |
|------|----------------|------------------------|
| Deep-scan | +1 Sonnet (capabilities agent) | +$0.05 |
| Scan, no capability change | 0 | $0 |
| Scan, 1–2 capabilities affected | 1 scoped Sonnet | +$0.01 |
| Lint | 0 (runs inside existing `/archie-scan` analysis) | $0 |

## 10. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Capabilities agent hallucinates capabilities (e.g. one per folder) | Evidence threshold: min. 3 files + route/controller/entry-point signal required. Validated by synthetic fixtures. |
| Wiki drifts between scans | `provenance.last_refreshed` visible on every page; `index.md` flags pages older than N days as stale. |
| Noisy wiki from many small commits | Incremental updater is SHA256-diff'd; unchanged content does not rewrite the file or bump `last_refreshed`. |
| Agent ignores the wiki | AGENTS.md protocol is explicit; v1.2 adds a `/archie-scan` lint finding when a recent PR modified a capability but touched no linked documentation. |
| Circular backlinks cause infinite traversal | `backlinks.json` is a directed edge list; render-time does not follow transitively, so no cycles are traversed. |
| Slug collisions (two components named "User") | Slug generator appends a numeric suffix on collision; the full entity name remains in the page title and frontmatter. |

## 11. Rollout

**v1.0** ships as one release:

- `wiki_builder.py`, `agents/capabilities.py`, `wiki_index.py` (canonical in `archie/standalone/`, mirrored to `npm-package/assets/`).
- `/archie-deep-scan` gains Step 8.
- `/archie-scan` gains incremental update + wiki lint.
- `viewer.py` gains `/wiki/*` route behind `--with-wiki-ui`.
- Renderer injects CLAUDE.md + AGENTS.md patches.
- `ARCHIE_WIKI_ENABLED` feature flag, default `true`.
- Docs updated; `scripts/verify_sync.py` covers the new files.

**v1.1** — viewer UI polish: wiki tab default on, client-side search, optional D3 backlinks graph.

**v1.2** — optional PreToolUse hook suggesting the wiki when a new file is created.

**v2.0** — consolidate `.claude/rules/*.md` into wiki frontmatter (breaking, requires its own brainstorm).

## 12. See also and future integrations

### 12.1 [tobi/qmd](https://github.com/tobi/qmd)

`qmd` is Tobi Lütke's on-device hybrid-search CLI referenced in Karpathy's gist — Node.js/Bun + SQLite FTS5 + sqlite-vec + GGUF embeddings + LLM reranker, exposed as a Claude Code skill and MCP server. It is a **read-side retrieval engine**, not a wiki generator: no `build`, no `log.md`, no "answer filed back as a new page". Orthogonal to this design — the wiki we generate is exactly the kind of markdown corpus qmd is built to index.

Relationship to this design:

- **Not adopted for v1.** Our corpus is small (~50–200 pages, regenerated per scan), so an embedded SQLite + vector stack with a GGUF model dependency is overkill compared to ripgrep + `Read`. Our intent layer already propagates per-folder context, which is conceptually what qmd's path-context tree accomplishes.
- **User-level option, not a dependency.** A user who wants heavier retrieval can point qmd at `.archie/wiki/`:

  ```bash
  qmd collection add archie-wiki .archie/wiki
  qmd embed
  qmd query "how does refresh-token rotation work" --md
  ```

  Nothing in our design prevents this. We will mention it in the wiki docs as an optional enhancement.
- **Prompt conventions worth studying later.** qmd's `lex / vec / hyde + intent` query taxonomy and its `SKILL.md` shape are good templates if we ever ship a native `/archie-wiki-query` skill.

### 12.2 Future work (out of scope for v1)

- **`/archie-wiki-query` skill (v1.2 candidate).** Grep-first search over `.archie/wiki/**` with optional Haiku rerank, mirroring qmd's `--json --files --md` output modes and query-type taxonomy. Only worth building if passive Read-and-follow turns out to be insufficient.
- **MCP wiki server (v2.0 candidate).** Expose the wiki to non-Claude-Code clients via an MCP endpoint. Only useful if users actually want wiki access outside Claude Code sessions.
- **Karpathy-style `log.md` + query-as-new-page (v2.0 candidate).** Append-only record of every deep-scan / scan + filing significant agent-answered questions back as wiki pages. This is the "compounding knowledge" pattern — valuable but requires its own brainstorm.
- **Graph view in the viewer (v1.1).** Client-side D3 visualization of the backlinks graph, sourced from `_meta/backlinks.json`. Small addition once the data is there.

## 13. Open questions (to revisit before implementation)

- **Capability slug collision** with existing component slugs (e.g. a component "auth" and a capability "auth-flow"). Proposal: namespace slugs by type (`capabilities/auth-flow` vs `components/auth`), unique within type only. Accept.
- **Per-folder intent layer CLAUDE.md** — should these also be linked from the wiki? Leaning yes — add a "Location context" section on each capability page linking to the leaf-folder intent CLAUDE.md for the capability's directory. Low risk, small patch. Treat as in-scope for v1.
- **Serialized pickle / cache format for SHA256 provenance** — use plain JSON to keep zero-dep and human-inspectable. No `pickle`, no binary formats.

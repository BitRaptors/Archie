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

## 12. Open questions (to revisit before implementation)

- **Capability slug collision** with existing component slugs (e.g. a component "auth" and a capability "auth-flow"). Proposal: namespace slugs by type (`capabilities/auth-flow` vs `components/auth`), unique within type only. Accept.
- **Per-folder intent layer CLAUDE.md** — should these also be linked from the wiki? Leaning yes — add a "Location context" section on each capability page linking to the leaf-folder intent CLAUDE.md for the capability's directory. Low risk, small patch. Treat as in-scope for v1.
- **Serialized pickle / cache format for SHA256 provenance** — use plain JSON to keep zero-dep and human-inspectable. No `pickle`, no binary formats.

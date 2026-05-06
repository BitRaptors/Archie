# Design: Splitting `enforcement.md` into Topic-Indexed Topic Files

**Date:** 2026-05-06
**Branch:** `feat/enforcement-rules-topic-split`
**Status:** Approved (brainstorming complete, ready for plan)

## Problem

Archie currently renders all enforcement rules into a single
`.claude/rules/enforcement.md` topic file. On a real project (Gasztroterkepek.iOS,
117 rules) this file is **70 KB ≈ 17 k tokens**. Issues:

1. **Hard to navigate** — agents and humans must scan the entire file to find
   the rule(s) relevant to the current task.
2. **Forces all-or-nothing loading** — when an agent decides it needs
   "enforcement context," it pulls the full 17 k tokens even if only the
   reactive-programming rules apply to the file it's editing.
3. **Discourages on-demand loading** — because the file is so large, most agent
   workflows just skip it, defeating the purpose of having browseable
   enforcement docs at all.

The single file does **not** affect runtime enforcement: the pre-validate hook
reads `.archie/rules.json` directly, not `enforcement.md`. This change is purely
about how agents and humans browse and selectively load rule context.

## Goal

Replace the monolithic `enforcement.md` with a small, agent-friendly directory
structure where:

- A tiny **`index.md`** (~3–5 KB) lists every topic with rule counts and provides
  both a topic-based and a path-glob-based lookup table.
- **Per-topic files** (`by-topic/<topic>.md`) hold the actual rule content,
  each focused enough that an agent loads only what's relevant to the current
  task (typically 1–3 files, ~5–10 KB total).
- A separate **`universal.md`** holds the platform-baked anti-patterns from
  `platform_rules.json` so they're identifiable as "Archie-baked, not
  project-specific."
- The split must work for **any platform** (iOS, Android, web frontend,
  backend, mixed monorepos) — no iOS-specific or framework-specific assumptions
  in the renderer.

## Non-Goals

- No change to runtime enforcement (pre-validate hook, align_check) — those
  keep reading `.archie/rules.json` directly.
- No change to the rule-authoring schema beyond adding one new field
  (`topic`).
- No change to how `/archie-scan` proposes new rules (those still land in
  `.archie/proposed_rules.json`; renderer treats them the same as merged rules).
- Do not introduce a UI layer or browser viewer for enforcement files — the
  Archie viewer already serves `rules.json`.

## Solution

### Directory layout

```
.claude/rules/
  enforcement/
    index.md              ← navigation hub, ~3–5 KB
    universal.md          ← platform_rules.json content (Archie-baked)
    by-topic/
      data-access.md
      concurrency.md
      ui.md
      navigation.md
      layering.md
      services.md
      dependencies.md
      security.md
      testing.md
      resources.md
      <project-specific topics>.md   ← e.g. mapping.md, payments.md, auth.md
```

The legacy `.claude/rules/enforcement.md` is replaced. `AGENTS.md` is updated to
point at `enforcement/index.md` instead of `enforcement.md`.

### `topic` field on every rule

Every rule object in `.archie/rules.json` and
`archie/standalone/platform_rules.json` gains a new field:

```json
{
  "id": "rx-001",
  "topic": "concurrency",
  "severity_class": "pitfall_triggered",
  "description": "...",
  "why": "...",
  "example": "...",
  "triggers": { "path_glob": ["Sources/**/*.swift"], "code_shape": [...] }
}
```

The renderer groups by `rule["topic"]` to produce one file per distinct topic
under `by-topic/`. Within each file, rules are still ordered by severity
(decision_violation → pitfall_triggered → mechanical_violation →
tradeoff_undermined → pattern_divergence) — same severity ordering as today.

### Recommended cross-platform topic vocabulary

Archie ships a **suggested** topic registry the AI uses as a hint. The list is
not enforced — Step 6 may introduce project-specific topics when justified.

- `data-access` — fetching, persisting, caching, ORMs, network
- `concurrency` — async/reactive primitives, threads, schedulers
- `ui` — view layer, components, styling, layout
- `navigation` — routing, deep links, screen transitions
- `layering` — file placement, dependency direction, layer rules
- `services` — singletons, DI, cross-cutting service patterns
- `state-management` — global state, stores, reactive sources
- `dependencies` — package managers, build, secrets handling
- `security` — auth, secrets, GDPR/PII, crypto
- `testing` — test harness, fixtures, anti-patterns
- `resources` — assets, i18n, localized strings
- `error-handling` — error propagation, fallbacks, retries

Project-specific examples (Step 6 may emit any of these when warranted):
`mapping`, `payments`, `auth`, `realtime`, `migrations`, `accessibility`.

### `index.md` format

The index is the only enforcement file an agent loads to *plan* what else to
load. It must stay small (target <5 KB) and contain two lookup tables:

```markdown
# Enforcement Rules — Index

This project has 117 rules across 9 topics. Load only the topic file(s)
relevant to your task. Universal Archie anti-patterns live in `universal.md`
and apply to every project.

## By topic

| Topic           | File                          | Rules |
|-----------------|-------------------------------|-------|
| Concurrency     | by-topic/concurrency.md       | 11    |
| Data access     | by-topic/data-access.md       | 12    |
| Layering        | by-topic/layering.md          | 9     |
| Mapping         | by-topic/mapping.md           | 7     |  ← project-specific
| Navigation      | by-topic/navigation.md        | 4     |
| Services        | by-topic/services.md          | 8     |
| UI              | by-topic/ui.md                | 14    |
| Dependencies    | by-topic/dependencies.md      | 6     |
| Resources       | by-topic/resources.md         | 5     |
| Universal       | universal.md                  | 30    |

## By path

When editing a file matching one of these globs, load the listed topics first.

| Path glob                          | Topics to load                         |
|------------------------------------|----------------------------------------|
| Sources/Controllers/**/*.swift     | concurrency, navigation, layering, ui  |
| Sources/Views/**/*.swift           | concurrency, ui, layering              |
| Sources/Services/**/*.swift        | data-access, services, layering        |
| Sources/Models/**/*.swift          | layering                               |
```

The "By path" table is generated from `triggers.path_glob` on every rule —
each unique glob lists every topic that has at least one rule with that glob.

### Renderer changes

Two new responsibilities for `archie/standalone/renderer.py`:

1. Replace `build_enforcement_rules_topic` with `build_enforcement_directory`,
   which returns a `dict[str, str]` mapping relative paths
   (`enforcement/index.md`, `enforcement/universal.md`,
   `enforcement/by-topic/<topic>.md`) to file contents.
2. Update `generate_all` to splice those entries into the output dict.

The grouping logic is a 3-line `defaultdict(list)` keyed on
`rule.get("topic", "misc")`. Universal vs. project rules are split by source
file: anything coming from `platform_rules.json` goes to `universal.md`, the
rest go to `by-topic/<topic>.md`. (The current loader already keeps these two
sources separable — see the `for fname in ("rules.json",
"platform_rules.json")` loop in `_render_main`; we just need to thread the
"is platform rule" flag through.)

The path-glob index is built by walking all rules and inverting
`(path_glob → set[topic])`.

### Backwards compatibility

Some existing projects have `rules.json` files with no `topic` field on any
rule. The renderer falls back as follows:

1. If `topic` is missing, infer from a small **prefix-to-topic heuristic
   table** (`rx-` → concurrency, `nav-` → navigation, etc.). This table lives
   in the renderer for the ~12 most common iOS prefixes Archie has emitted to
   date.
2. If the prefix is unrecognized, the rule lands in `by-topic/misc.md` and the
   renderer logs a one-line warning suggesting the project re-run
   `/archie-deep-scan` to refresh tagging.

This keeps existing projects working without forcing an immediate re-scan.
Once they re-scan, Step 6 emits proper `topic` fields and `misc.md`
disappears.

### Step 6 prompt update

`/archie-deep-scan` Step 6 (the senior-architect rule synthesis pass) gets a
new instruction in its prompt:

> Each rule object MUST include a `topic` field — a short slug naming the
> conceptual area the rule governs (e.g. `concurrency`, `data-access`,
> `navigation`, `ui`, `layering`, `security`, `mapping`, `auth`). Prefer
> topics from the recommended list below, but you MAY introduce a
> project-specific topic when a coherent group of 3+ rules clearly belongs
> together under a name not in the list.

The recommended list is the cross-platform vocabulary above. The Sonnet pass
on each project will produce 5–12 topics depending on stack.

### `platform_rules.json` migration

We hand-edit `archie/standalone/platform_rules.json` (30 rules) to add a
`topic` field to each. The existing `category` field already correlates well
(`erosion-*` → `complexity`, `decay-*` → `quality`, layer rules → `layering`),
so this is a one-shot mechanical edit, not an AI pass.

After editing, copy to `npm-package/assets/platform_rules.json` per the
`File Sync` rule in CLAUDE.md.

### `AGENTS.md` template change

The renderer's main file template needs one line update — replacing:

```markdown
[`.claude/rules/enforcement.md`](.claude/rules/enforcement.md) lists every rule …
```

with:

```markdown
[`.claude/rules/enforcement/index.md`](.claude/rules/enforcement/index.md)
indexes every rule, grouped by topic and by path glob. Load only the
topic file(s) relevant to the file you're editing.
```

In the "Architectural Rules" bullet list, the line for `enforcement.md` is
replaced with a link to `enforcement/index.md`. The other 8 topic-file
bullets (`architecture.md`, `patterns.md`, `technology.md`,
`guidelines.md`, `pitfalls.md`, `dev-rules.md`, `infrastructure.md`,
`frontend.md`) stay unchanged — only the enforcement entry moves.

## Components

| Component | Responsibility | Touch points |
|---|---|---|
| Renderer (`archie/standalone/renderer.py`) | Group rules by topic + emit directory | New: `build_enforcement_directory`. Update: `generate_all`, `_render_main` template |
| Platform rules (`archie/standalone/platform_rules.json`) | Provides Archie-baked rules | Add `topic` field on every rule |
| Step 6 prompt (`.claude/commands/archie-deep-scan.md`) | Rule synthesis | Add `topic` instruction |
| Test (`tests/test_renderer.py`) | Renderer regression coverage | New: tests for split directory layout, fallback heuristic, universal.md split |
| File sync (`scripts/verify_sync.py`) | Keep `archie/standalone/` ↔ `npm-package/assets/` consistent | No code change, but every edit must be mirrored to npm-package/assets/ |

## Data flow

1. `_render_main` calls `build_enforcement_directory(rules, platform_rules)`.
2. The function partitions rules: project rules (from `rules.json`) vs.
   universal rules (from `platform_rules.json`).
3. Universal rules → render to `universal.md` (single file, current
   severity-grouped format).
4. Project rules → group by `rule["topic"]` (with fallback heuristic).
5. For each topic group, render a file at `enforcement/by-topic/<topic>.md`
   with the same per-rule format used today (description, why, example,
   triggers).
6. Build `index.md`:
   - Topic table from the topic groups + `universal.md` row.
   - Path-glob table by inverting `path_glob → topics` across all rules.
7. Return `{ "enforcement/index.md": ..., "enforcement/universal.md": ...,
   "enforcement/by-topic/data-access.md": ..., ... }`.
8. `generate_all` splices these into the output dict; the writer drops them
   on disk under `.claude/rules/enforcement/`.

## Error handling

- **Empty `topic` on every rule** (legacy project): fallback heuristic
  populates topics, log one warning, render proceeds normally.
- **Unknown prefix in fallback heuristic**: rule lands in `misc.md`, no
  failure.
- **Empty rule set**: no `enforcement/` directory is emitted (matches today's
  behavior of skipping `enforcement.md` when there are zero rules).
- **Topic slug with weird characters** (e.g. AI emits `Data Access` with a
  space): renderer slugifies (`data-access`) before using as filename.

## Testing

`tests/test_renderer.py` gets new cases:

1. Given a rule list with `topic` fields → directory contains expected files,
   each with the right rules.
2. Given rules without `topic` → fallback heuristic places known prefixes
   correctly, unknowns land in `misc.md`.
3. Given a mix of `rules.json` and `platform_rules.json` rules → universal
   rules go to `universal.md`, project rules to `by-topic/`.
4. Index file contains every topic from the topic group with correct counts.
5. Index path-glob table inverts triggers correctly.
6. Topic name with spaces gets slugified to a safe filename.
7. Empty rule list → no `enforcement/` files emitted.

Existing tests for `build_enforcement_rules_topic` get retired (the function
is removed).

## Migration / rollout

1. **Phase 1 — code change** (this branch): renderer emits the new directory
   structure. Existing projects with no `topic` fields use the fallback
   heuristic, so their first re-render after upgrading still produces a
   reasonable split (with `misc.md` for any unknown prefixes).
2. **Phase 2 — Step 6 prompt update** (same branch): new deep-scans emit
   `topic` fields cleanly. No `misc.md` for fresh scans.
3. **Phase 3 — platform_rules.json topic tagging** (same branch): hand-edit
   the 30 rules to carry `topic`. Copy to npm-package/assets/.
4. **Existing-user upgrade path**: a user who upgrades Archie sees the new
   directory after their next `/archie-deep-scan` (or even just after
   re-running the renderer). They keep working; if `misc.md` shows up, the
   inline warning tells them to re-scan.

No data migration script is needed — the heuristic + re-scan path is enough.

## Out of scope (deferred)

- Hot-loading enforcement files via a hook (e.g. inject only the relevant
  topic when the agent edits a matching file). The directory structure
  enables this future work but the spec for the hook itself is separate.
- Cross-references between topic files (e.g. `concurrency.md` linking
  related rules in `services.md`). Once we see real-world patterns we can
  add this in a follow-up.
- A "smart loader" CLI (`archie load-enforcement <path>`) that prints the
  set of topics relevant to a given source path. The path table in
  `index.md` already gives the agent what it needs to do this manually.

## Open questions

None blocking. Implementation can begin.

# C4 architecture diagram — deterministic, script-built, second tab

**Date:** 2026-06-02
**Branch:** `feature/c4-diagram`
**Status:** approved design, ready for implementation plan

## Problem

A user asked for a C4 architecture diagram in the viewer/share. Archie today
produces a single "Simplified Overview" — an AI-curated Mermaid `graph TD` spine
(8-12 nodes), built by the Overview agent (`step-5c-overview.md`) and rendered in
`ReportPage.tsx` section `id="diagram"`. We want to **add** a C4 diagram as a
**second tab** next to it, built **deterministically by script** (no AI), from
data the blueprint already carries.

## Grounded facts (verified, not assumed)

- **Viewer already renders C4.** `share/viewer` runs Mermaid `^11.4.1` and ships
  the `c4Diagram-*.js` chunk. A C4 Mermaid string renders with zero new deps.
- **No `role` field on components.** Each `components.components[]` carries
  `name, location, platform, responsibility, depends_on, exposes_to,
  key_interfaces, key_files` — nothing flags "deployable app" vs "library".
- **`integrations` mixes externals and datastores.** openmeter's list is
  `PostgreSQL, ClickHouse, Kafka, Redis, Svix, Stripe, Sandbox invoicing,
  CustomInvoicing` — the first four are also in `persistence_stores`. True
  third-party SaaS = `integrations` − `persistence_stores`.
- **Real deployables come from entrypoints, not components.** openmeter has 7
  `main.go` binaries (`cmd/server`, `cmd/billing-worker`, `cmd/balance-worker`,
  `cmd/sink-worker`, `cmd/notification-service`, `cmd/jobs`,
  `cmd/benthos-collector`), but the AI lumped 4 workers into one component at
  location `cmd`, and `tools/migrate`'s entrypoint is nested at
  `tools/migrate/cmd/viewgen/main.go`. So entrypoint detection (subtree match) is
  the honest source for the Container level.
- **One bundle assembler feeds both surfaces.** `viewer.py`'s local `/api/bundle`
  imports `build_bundle` from `upload.py`; share uploads the same `build_bundle`
  output to Supabase. One edit covers both.
- **Supabase needs no change.** `upload/index.ts` stores the bundle blob with no
  key whitelist (only: require `bundle.blueprint`, reject >5 MB); `blueprint`
  GET returns the full blob. `c4` rides along free. (Distinct from the telemetry
  schema change, which had `=1` validation gates.)

## Decisions

1. **Levels:** all three C4 levels with an inner toggle — **Context → Container →
   Component** — in one "C4 Model" tab.
2. **Classification is a 3-source hybrid**, each source used where it's strongest
   (orthogonal fields, not competing ways to compute the same thing):
   - `kind` (app/service/worker/cli/lib/datastore) ← scanner **entrypoints** +
     `persistence_stores`. Answers "is it deployable?". Drives node **type**.
   - `group` (cmd / openmeter / api / pkg / app / tools) ← first path segment /
     workspace member. Answers "what layer?". Drives `System_Boundary` grouping.
3. **Container level is driven by scanner entrypoints** (the 7 real binaries), not
   the AI's 29 components. Component level is driven by the AI components +
   `depends_on`. Context level needs neither `kind` nor `group`.
4. **Storage:** a separate `.archie/c4.json` file (not inside `blueprint.json`),
   carried into the bundle so share and viewer both get it.
5. **Determinism:** nodes/edges sorted by name, IDs slugified from `name` →
   byte-stable output across runs (a real edge over the AI spine — no diff churn).

## Architecture

### Generation pipeline (all deterministic, no agent)

1. **Scanner** (`scanner.py`, step 1) emits `entrypoints[]` into `scan.json`:
   subtree scan for `main.go`, `package.json` `bin`/`scripts.start`,
   `Dockerfile`/compose services, `__main__.py`/`pyproject [project.scripts]`.
   Each: `{path, kind}` where `kind` derives from the entrypoint's folder name
   (`*-worker`→worker, `server`/`*-service`→service, `jobs`/`*-cli`→cli, else app).
   `group` is read off the file tree (first path segment) — no new scan.

2. **Enrich pass** (render time, after Wave-1 components exist) stamps two fields
   onto each component:
   - `kind` — subtree match: deployable if any entrypoint sits at-or-under the
     component's `location`/`key_files`; datastore if it maps to a
     `persistence_store`; else `lib`.
   - `group` — first path segment of `location`.

3. **`archie/standalone/c4.py`** reads enriched blueprint + `scan.json`, writes
   `.archie/c4.json` = `{context, container, component}` (Mermaid strings):
   - **context** (`C4Context`): one `System` (repo) + `System_Ext` per external
     (`integrations` − `persistence_stores`) + `SystemDb` per persistence store.
     Edges from `integrations.integration_point` + persistence writers.
   - **container** (`C4Container`): one `Container` per scanner entrypoint (typed
     by entrypoint kind) + `ContainerDb` per persistence store + externals
     outside; grouped in `System_Boundary` by `group`. Edges: container→datastore
     (persistence writers, fallback `depends_on`), container→external
     (`integration_point` → owning binary by path).
   - **component** (`C4Component`): AI components + `depends_on`/`exposes_to`, each
     node in a `System_Boundary` by `group`.

### Bundle plumbing (one edit, both surfaces)

- `upload.py::build_bundle` — optional read of `.archie/c4.json`; if a dict,
  `bundle["c4"] = c4`. `viewer.py` reuses `build_bundle`, so local + share both
  get it.
- Supabase: **no change** (verified above).

### Viewer/share UX (`ReportPage.tsx`, `api.ts`)

- `api.ts` `interface Bundle` gains
  `c4?: { context?: string; container?: string; component?: string }`.
- Section `id="diagram"` wraps its single diagram in a tab strip:
  - **"Simplified Overview"** — existing `architecture_diagram`, default tab,
    unchanged.
  - **"C4 Model"** — shown only if `bundle.c4` present. Inner toggle
    Context / Container / Component, each rendered via the existing
    (C4-capable) `MermaidDiagram`. Per-level caption. Empty level hidden; whole
    tab hidden on old bundles.

## Sync + multi-CLI

`c4.py` is standalone and deterministic (no prompt, no agent) → CLI-agnostic.
Edit `archie/standalone/` → mirror to `archie/assets/` + `npm-package/assets/`;
`scripts/verify_sync.py` must pass. Scanner/renderer edits follow the same mirror.
No connector or workflow-prompt change.

## Testing

- `c4.py` unit: fixture blueprint+scan → valid `C4Context/C4Container/C4Component`
  syntax; byte-stable (run twice = identical); externals exclude datastores;
  container nodes == entrypoints; subtree match catches aggregate `cmd` +
  nested `tools/migrate`.
- `build_bundle`: `c4.json` present → `bundle["c4"]`; absent → key omitted.
- Viewer: renders with/without `c4` (tab appears/hidden); level toggle switches
  strings; old bundle (no `c4`) unaffected.

## Out of scope

- C4 Level 4 (Code / class-level) — Archie has no class-level structured data.
- AI-authored C4 — the whole point is deterministic/script-built.
- Replacing the Simplified Overview — it stays the default tab.

## Risks

- **Entrypoint detection coverage** across stacks (Go/Node/Python covered; exotic
  build systems may under-detect → Container level thinner, but Context +
  Component still render). Mitigate: `lib` fallback, never crash.
- **`integration_point` → owning binary mapping** for container→external edges may
  be approximate; acceptable (edges are best-effort, nodes are exact).
- **Granularity mismatch** between AI components and real binaries is the reason
  Container is entrypoint-driven; keep the two levels sourced separately.

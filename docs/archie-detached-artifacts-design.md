# Detached Artifacts — Design Spec

**Status:** shipped (POC) — implementation on branch `feature/detached-artifacts`
**Date:** 2026-06-30
**Branch:** `feature/detached-artifacts`

## Problem

Every Archie artifact is currently coupled to the repository working tree:
root `CLAUDE.md` / `AGENTS.md`, `.claude/rules/*.md`, per-folder `CLAUDE.md`
(intent layer), and `.archie/{blueprint,findings,health}.json`. This means
generated content pollutes git history/diffs/PRs (repo-cleanliness pain) and
there is no path to an Archie-owned store that could later be hosted, queried,
and shared across a team (SaaS pain).

We want to **decouple the artifacts from the working tree** so the tree stays
clean, while keeping the coding agent's experience identical — and leave a clean
seam to later back the store with a server.

## Goals

1. **Clean working tree** — the only Archie footprint tracked in git is a tiny
   committed pointer.
2. **Artifacts live outside the repo**, in an external folder that is the source
   of truth (POC); later swappable for a server-backed cache.
3. **Agent experience unchanged** — Claude Code / Cursor / Codex read context and
   hooks enforce exactly as today.
4. **Opt-in** — in-repo mode (today's behavior) remains the default and is fully
   supported alongside detached mode.
5. **A control plane** — reuse the viewer to enable/disable artifact exposure,
   gatekeeping what the coding agent can see (and what is enforced).

## Non-Goals (POC — seams left in)

- No server, no auth, no network. `detached-remote` / `publish` are stubs.
- No versioning / snapshot refs. Single current copy in the external folder
  (a `snapshot` field is reserved in the link file for later).
- No team sync. Detached-local is effectively single-developer; cross-teammate
  divergence is expected and is exactly what the future server backend solves.
- No per-project / per-developer mode layering. A single binary mode flag for now.

## Decisions (from brainstorm)

| # | Decision |
|---|----------|
| Motivation | Repo cleanliness (A) + eventual hosted store (B); POC = local external folder |
| Delivery to agent | Materialize-on-demand via symlinks (not MCP) |
| Blended files | Split: root `CLAUDE.md` keeps a hand-authored committed `@import` pointer; generated content is symlinked. No in-tree merge. |
| Keying | Explicit `project_id` in committed `.archie-link.json`; remote/path fallback deferred |
| Sync | N/A for POC — the external folder *is* the live store (read/write in place). SessionStart+TTL pull is a future-remote concern. |
| Versioning | Deferred; `snapshot` field reserved in the link file |
| POC scope | **Full** — includes scattered per-folder `CLAUDE.md` via a tree-mirror + per-file links + an `externalize` step |
| Wrapper | Viewer becomes the control plane; a symlink toggle gates **both** visibility and enforcement |
| Toggle granularity | Category switches + expandable per-file overrides; `exposure.json` manifest in the external folder |
| Modes | `repo` / `detached-local` / `detached-remote` behind a provider interface; write-through keeps the pipeline unchanged |
| Opt-in | Single binary global flag (in-repo vs detached); per-project layering deferred |

## Architecture — three zones

Files split by *who owns them*:

**Zone 1 — Committed (the only Archie footprint in git):**
- Root `CLAUDE.md` — hand-authored, carries a one-line `@import` pointer to the
  symlinked Archie content + the user's own guidance. Archie never rewrites it.
- `.archie-link.json` — tiny committed file: `project_id` (UUID minted on first
  bind), `mode`, and reserved `snapshot` field.
- `.gitignore` entries that hide Zone 2.

**Zone 2 — Surfaced in the working tree (gitignored, what the agent reads):**
- `.archie/` → directory link into the external folder.
- `.claude/rules/` → directory link into the external folder.
- Per-folder `CLAUDE.md` → per-file links into a tree-mirrored area.

**Zone 3 — External folder (source of truth, outside the repo):**
- `~/.archie/projects/<project-id>/` with `artifacts/`, `tree/`, `meta.json`,
  `exposure.json`.

**Write-through trick:** because `.archie/` and `.claude/rules/` are *directory*
links created at bind time, the existing scanner/renderer/intent-layer scripts
keep writing to `root/.archie/…` and `root/.claude/rules/…` — the writes pass
*through* the link and land in the external folder. Near-zero pipeline change.
The exception is the dynamically-created per-folder `CLAUDE.md` files, which need
a post-write `externalize` step (you cannot pre-link a not-yet-existing file).

## Pluggable storage modes

| Mode | Artifacts live | Reach the tree | When |
|---|---|---|---|
| `repo` | working tree | real files (today) | default, unchanged |
| `detached-local` | `~/.archie/projects/<id>/` | links into the tree | the POC |
| `detached-remote` | server, mirrored to local cache | links into the cache→tree | future |

**Provider interface** — four operations differ by mode; everything else is shared:
1. `init/bind` — `repo`: real dirs. `detached`: create external folder, lay
   directory links, add `.gitignore` + `@import` pointer.
2. `externalize` (detached) — post-write relocation of scattered per-folder files.
3. `expose/hide` (detached) — the symlink toggle that powers the viewer panel.
4. `publish` (future remote) — push external folder to server; no-op for local.

Consequence: **gatekeeping is inherently a detached-mode capability.** In `repo`
mode the files are real and committed, so the viewer's toggles render inert.

## Cross-platform — presentation strategy

Symlinks are not a portable primitive, so the provider abstracts a **presentation
strategy** per OS. The external folder is always the source of truth; only how it
surfaces in the tree changes:

| Artifact zone | macOS / Linux / WSL | Windows |
|---|---|---|
| Directory artifacts (`.archie/`, `.claude/rules/`) | POSIX symlink | **NTFS junction** — no admin / Developer Mode needed; transparent to tools |
| Scattered per-folder `CLAUDE.md` (files) | POSIX symlink | file symlink *if* Developer Mode, else **copy-materialize fallback** |

- macOS/Linux/WSL: native `os.symlink`, no privileges.
- Windows dirs: junctions (`_winapi.CreateJunction`) need no privileges, transparent.
- Windows files: file symlinks need Admin/Developer Mode; junctions don't work on
  files → **default to copy-materialize fallback** (loses live edit-through, works
  with zero setup; `reconcile` refreshes).
- **Universal floor:** copy-materialize is always available, so the design never
  hard-fails on missing symlink capability. `.gitignore` keeps git out of the
  symlink/junction question entirely (links are never tracked).

## Components

### `linker.py` (new standalone; mirror to `npm-package/assets/`)
- `bind` — mint `project_id`, create `~/.archie/projects/<id>/{artifacts,tree}/`,
  lay the directory links, write `.archie-link.json` (committed) + `.gitignore`
  entries, ensure the root `CLAUDE.md` `@import` pointer.
- `reconcile` — idempotent: make the working tree match `exposure.json`. Create
  missing enabled links (incl. tree-mirrored per-folder), remove links for
  disabled/deleted artifacts.
- `externalize` — after intent-layer writes `src/a/CLAUDE.md`, move it to
  `tree/src/a/CLAUDE.md` and replace with a link.
- `attach`/`detach` — switch a repo between `repo` and `detached`. Detach resolves
  every link into a real file and drops the links; attach does the reverse.
  Reversible, non-destructive.
- `status` — what's exposed vs hidden (for the viewer).
- **Safety invariant (load-bearing):** only ever remove links whose target
  resolves *inside the external folder*. Never touch a real file.

### Viewer control plane (additive to `viewer.py` + React app)
- `GET /api/exposure` — categories + per-file artifacts with on/off state.
- `POST /api/exposure` — flip a category or file → write `exposure.json` →
  `reconcile`.
- UI: category switches (rules / per-folder context / blueprint / findings) with
  expand-to-per-file overrides. In `repo` mode the panel is read-only/inert.

### Pipeline + CLI integration (small)
- Scanner / renderer / intent-layer: unchanged thanks to write-through;
  intent-layer gains an `externalize` call after each folder write.
- `archie init` / `archie-deep-scan`: accept the mode flag; in detached mode call
  `linker bind` first.
- Hooks: unchanged — they read through links transparently.

## File locations

| What | Location | Tracked? |
|---|---|---|
| Committed pointer | `<repo>/.archie-link.json` (+ `@import` line in `CLAUDE.md`) | committed |
| External store (macOS/Linux) | `~/.archie/projects/<id>/` (override `$ARCHIE_HOME`; XDG-aware) | outside repo |
| External store (Windows) | `%LOCALAPPDATA%\archie\projects\<id>\` | outside repo |
| Links / junctions / copies | working tree, at normal paths | gitignored |

External folder layout:
```
~/.archie/projects/<id>/
  meta.json          # project_id, bound repo path(s), mode, created
  exposure.json      # the viewer's toggle manifest
  artifacts/
    .archie/         # blueprint.json, findings.json, health.json, intent_layer_state.json
    .claude/rules/   # *.md
  tree/              # repo-mirrored per-folder context
    src/a/CLAUDE.md
```
Link resolution: `<repo>/.archie` → `artifacts/.archie`,
`<repo>/.claude/rules` → `artifacts/.claude/rules`,
`<repo>/src/a/CLAUDE.md` → `tree/src/a/CLAUDE.md`.

## Workflow

1. **Setup (opt in):** `npx @bitraptors/archie /path --detached` → mint id,
   create external folder, lay links, write `.archie-link.json`, gitignore,
   `@import` pointer.
2. **Baseline:** `/archie-deep-scan` runs as today; writes pass through the links;
   intent-layer + `externalize` handle per-folder files.
3. **Daily coding:** agent reads context + hooks enforce through links; `git
   status` clean.
4. **Gatekeeping:** `/archie-viewer` → toggle exposure → `reconcile`.
5. **Fresh clone:** `.archie-link.json` committed → `archie connect` creates the
   local external folder; POC re-scans (server later pulls).
6. **Opt out:** `archie detach`/`attach` — reversible.

## Open decisions (resolve during implementation)

- **Windows file fallback default** — default to copy-materialize (zero setup) vs
  require Developer Mode for fidelity. *Lean: copy fallback.*
- **`connect` trigger** — explicit command vs auto-run on first session.
  *Lean: explicit for POC, with a clear message when the external folder is absent.*

## Testing strategy

- Unit: `linker` bind/reconcile/externalize/attach/detach with a temp repo +
  temp `$ARCHIE_HOME`; assert link targets, gitignore content, safety invariant
  (never removes real files), idempotency.
- Platform: presentation-strategy resolver tested per-OS; copy-fallback path
  exercised directly (not OS-gated) so CI covers it everywhere.
- Viewer: `/api/exposure` GET/POST round-trip drives `reconcile`; `repo`-mode
  inert.
- End-to-end: scan a fixture repo in detached mode → assert clean `git status`,
  resolvable context, working hooks; detach → assert real files restored.

# Unify `/archie-viewer` and `/archie-scan` under one React codebase

**Status:** Design approved 2026-05-09. Ready for implementation plan.
**Branch:** `feature/unify-viewer-scan` (off main).
**Owner:** Gabor.

## Problem

Two render stacks exist for the same data:

- `archie/standalone/viewer.py` — 2067 LOC zero-dep Python stdlib server with an embedded HTML SPA. Powers `/archie-viewer`.
- `share/viewer/` — Vite + React + TypeScript app. Powers `archie-viewer.vercel.app` (the share flow at `/r/:token/details`).

Both consume the same `.archie/*.json` files. Maintaining two render stacks doubles the cost of every UI improvement and makes feature parity impossible.

## Goal

Delete the Python-side render stack. `/archie-viewer` spins up a small Python sidecar that serves the **same React app** the share flow uses, sourced from the **same codebase**. V1 ships render parity with the share viewer's detail page. V2 features can diverge under the same codebase via a dedicated local-only page wrapper, with no runtime mode-checks polluting shared components.

## Non-goals

- V2 feature work (file browser, dependency-graph viz, inline rule editor, folder-CLAUDE.md browser). These return later, not in this PR.
- Changes to `/archie-share` upload flow.
- Changes to `archie-viewer.vercel.app` deployment (the React app's `/r/:token` and `/r/:token/details` routes are unchanged).
- The cover page (`CoverPage.tsx`) is share-only; local mode lands directly on the detail page.

## Architecture

```
┌──────────────────── User runs /archie-viewer ────────────────────┐
│                                                                  │
│  python3 .archie/viewer.py "$PWD"     ← new ~150 LOC sidecar     │
│                                                                  │
│   ├── serves  .archie/viewer/dist/    as static                  │
│   │           (built React app from share/viewer/)               │
│   │                                                              │
│   └── exposes  GET /api/bundle                                   │
│              → calls upload.build_bundle(project_root)           │
│              → returns same Bundle shape /archie-share uploads   │
│                                                                  │
│  Auto-opens browser → http://localhost:5847/local                │
│      └── React app's new LocalPage.tsx fetches /api/bundle       │
│            and renders ReportPage with the bundle                │
└──────────────────────────────────────────────────────────────────┘
```

**Single source of truth:** `share/viewer/` is the only React codebase. The Vercel-hosted share viewer and the local `/archie-viewer` render the same components from the same package, just wired to different data sources at the edges.

## Components changing

| File | Change | Purpose |
|---|---|---|
| `share/viewer/src/main.tsx` | Add `<Route path="/local" element={<LocalPage />} />` | Route the local-mode landing page. |
| `share/viewer/src/pages/LocalPage.tsx` | **NEW**, ~40 LOC. Fetches `/api/bundle`, renders `ReportPage` via prop. Hides the share-mode "Try Archie" CTA. | Local-mode wrapper, divergence point for V2. |
| `share/viewer/src/pages/ReportPage.tsx` | Accept optional `bundle` prop; when provided, skip the token-based `fetchReport`. | Reuse the same component for share + local. |
| `archie/standalone/viewer.py` | **REWRITE** to ~150 LOC. Serves `.archie/viewer/dist/` as static, exposes `GET /api/bundle`, auto-opens browser to `/local`, port 5847 with free-port fallback. `--api-only` and `--no-open` flags. | The new sidecar. |
| `archie/standalone/upload.py` | No code change. `build_bundle()` is reused. | One bundle-building function for both share + local. |
| `npm-package/assets/viewer/` | **NEW**, mirrors build inputs from `share/viewer/`: `src/`, `public/`, `package.json`, `package-lock.json`, `vite.config.ts`, `tsconfig.json`, `tailwind.config.js`, `postcss.config.js`, `index.html`. **No `node_modules/`, no `dist/`.** | Source shipped to user's project so install-time build can produce `dist/`. |
| `npm-package/archie.mjs` | After copying scripts, copy `assets/viewer/` → `target/.archie/viewer/`, then run `npm ci --prefix .archie/viewer`, `npm run build --prefix .archie/viewer`, `rm -rf .archie/viewer/node_modules`. Skip if `.archie/viewer/dist/.archie-version` matches the package version. Stream child output with `[npm]` / `[vite]` prefixes. | Install-time build. Idempotent re-runs. Visible progress. |
| `scripts/verify_sync.py` | Sync rule: `share/viewer/{src,public,package.json,...}` → `npm-package/assets/viewer/`. Treat `node_modules/` and `dist/` as ignored. | Catch divergence between canonical React source and the asset mirror. |
| `archie/standalone/viewer.py` (asset copy) | `npm-package/assets/viewer.py` mirrors the new file. | Standard Archie sync rule. |
| `.claude/commands/archie-viewer.md` + `npm-package/assets/archie-viewer.md` | Update prerequisite text (now needs `.archie/viewer/dist/`). Launch line unchanged. | Slash-command docs follow the change. |
| `tests/test_viewer.py` | **NEW**, ~80 LOC. `/api/bundle` returns valid JSON with required keys; static assets serve; `--api-only` flag works; 404 for unknown paths. | Validation gate. |

**Net diff:** ~1700 LOC removed, ~300 LOC added, plus mirrored React source in `npm-package/assets/viewer/` (~300 KB committed).

## Data flow

```
.archie/blueprint.json         ─┐
.archie/health.json             │
.archie/rules.json              │   upload.build_bundle()
.archie/proposed_rules.json     ├──────────────────────►  Bundle JSON
.archie/scan_report.md          │                              │
.archie/findings.json           │                              ▼
.archie/semantic_duplications  ─┘                       GET /api/bundle
                                                               │
                                                               ▼
                                                        LocalPage.tsx
                                                               │
                                                               ▼
                                                       ReportPage(bundle)
```

The `Bundle` interface in `share/viewer/src/lib/api.ts` is unchanged. Local mode produces exactly the same shape the share flow already produces.

## End-user UX — `/archie-viewer`

```
$ /archie-viewer
Starting Archie viewer…
Bundle: 1 blueprint, 12 findings, 7 rules adopted
Listening on http://localhost:5847
Opening browser…
Press Ctrl+C to stop.
```

Browser opens to `http://localhost:5847/local`. Detail page renders directly. No cover, no token, no install CTA.

**Edge cases:**

- `.archie/blueprint.json` missing → exit 1 with `Run /archie-scan or /archie-deep-scan first.`
- Port 5847 taken → free-port fallback.
- `.archie/viewer/dist/` missing → exit 1 with `Run npx @bitraptors/archie to set up the viewer.`
- `--api-only` flag → JSON endpoint only, for V2 contributors who run `vite dev` separately.
- `--no-open` flag → suppress `webbrowser.open()`.

## Install-time UX — `npx @bitraptors/archie`

```
$ npx @bitraptors/archie /path/to/project

[archie] Copying scripts to .archie/                            (1s)
[archie] Local viewer setup (one-time, ~45s)
[archie]   This installs React dependencies and builds the UI.
[archie]   Future installs skip this step unless the package version changes.
[archie]
[archie]   → Installing dependencies (npm ci)
[npm]       added 245 packages in 31s
[archie]   → Building viewer bundle (vite build)
[vite]      ✓ 1428 modules transformed
[vite]      dist/index.html             0.56 kB
[vite]      dist/assets/index-*.js      617 kB │ gzip: 198 kB
[vite]      dist/assets/index-*.css      72 kB │ gzip:  12 kB
[vite]      dist/assets/<lazy chunks>  ~2.4 MB │ (loaded on-demand)
[vite]      ✓ built in 14.2s
[archie]   → Cleaning up build dependencies                     (2s)
[archie]   → Writing version marker
[archie]
[archie] Done in 48s. Run /archie-scan to begin.
```

**Messaging rules:**

1. Tell-then-show. The "one-time, ~45s" notice prints **before** the pause; every phase has a `→` line.
2. Stream child stdout/stderr with `[npm]` / `[vite]` prefixes — pass through, don't censor.
3. On re-runs with matching version marker, collapse the entire block to one line: `[archie] Local viewer up to date (vX.Y.Z) — skipping build.`
4. On failure, give next-action: `[archie] npm ci failed. Common causes: no internet, corporate proxy, node <18. Run 'node --version' and 'npm ping'. Full output above.`
5. Print total elapsed at the end.

End state on user's disk after install: `.archie/viewer/dist/` (~3.7 MB) + `.archie/viewer/{src,configs,...}` (~300 KB) ≈ 4 MB. `node_modules/` is removed after build.

## V1 features

Render the existing `share/viewer/` ReportPage. Working sections:

- Architecture summary, mermaid diagram, workspace topology
- Health scores + trend
- Components, decisions, trade-offs, pitfalls
- Rules: architecture, enforcement (adopted), development, infrastructure
- Findings (active only — same filter as the share viewer)
- Communications, integrations, technology, deployment

`ReportPage` is already defensive against missing data (every blueprint field has a `|| {}` fallback), so partial blueprints from `/archie-scan`-only runs (no deep scan) render with sparse sections rather than crashing.

**Dropped from current `viewer.py`, return in V2 if wanted:**

- Files browser (.claude/rules/* + AGENTS.md/CLAUDE.md viewer)
- Folder CLAUDE.md browser (per-folder intent layer output)
- Dependency graph (vis-network viz)
- Inline rule editor (POST /api/rules — rule adoption already happens via `/archie-scan`'s AskUserQuestion flow)

## V2 divergence

```
share/viewer/src/pages/
  ReportPage.tsx        ← shared body, used by /r/:token/details and /local
  LocalPage.tsx         ← local wrapper; can grow local-only sections
  CoverPage.tsx         ← share-only

share/viewer/src/components/local/    ← future home for local-only widgets
  RuleEditor.tsx        ← V2: POSTs to /api/rules
  FilesBrowser.tsx      ← V2: hits /api/generated-files
  DepGraph.tsx          ← V2: hits /api/dependency-graph (vis-network)
```

Local-only API endpoints get added to `viewer.py` as needed. The share viewer never sees them. Build artifacts split cleanly because `/r/:token/details` doesn't import from `components/local/`.

**No flags, no conditionals in `ReportPage`.** Divergence happens at the page-wrapper layer (`LocalPage` adds new sections), not via runtime mode-checks. This keeps the share-mode build stable.

## Build & distribution

**Pre-release** (Archie maintainers): `git push`. No prebuilt artifacts shipped. CI validates that `cd npm-package/assets/viewer && npm ci && npm run build` succeeds on every PR but doesn't commit the output.

**Install at user's project:**

```
npx @bitraptors/archie /path/to/project
1. copies .archie/scripts (Python files)
2. copies .archie/viewer/{src,public,package.json,...}  (React source, ~300 KB)
3. runs npm ci --prefix .archie/viewer  (~30s, ~298 MB transient)
4. runs npm run build --prefix .archie/viewer  (~15s, produces dist/)
5. rm -rf .archie/viewer/node_modules  (cleanup, dist/ stays)
6. writes .archie/viewer/dist/.archie-version with package version
```

**At runtime:** `python3 .archie/viewer.py "$PWD"` serves `.archie/viewer/dist/`.

## What gets deleted

- `archie/standalone/viewer.py` lines 250-2066: the inline 1800-LOC HTML SPA + helpers `_collect_folder_claude_mds`, `_collect_generated_files`.
- `npm-package/assets/viewer.py` (replaced by sync copy of new file).
- All endpoints in old viewer.py except `/api/bundle` (new): `/api/blueprint`, `/api/rules` (GET+POST), `/api/health`, `/api/scan-reports`, `/api/findings`, `/api/generated-files`, `/api/folder-claude-mds`, `/api/dependency-graph`, `/api/drift`, `/api/proposed-rules`, `/api/ignored-rules`, the inline `HTML_PAGE` constant.

These can be re-added in V2 if needed; not deleted forever.

## Validation gates

1. `python -m pytest tests/ -v` — all green, including new `test_viewer.py`.
2. `python3 scripts/verify_sync.py` — clean.
3. CI step: `cd npm-package/assets/viewer && npm ci && npm run build` — fails the PR if React build breaks.
4. Manual: `npx @bitraptors/archie /tmp/empty-project` on a clean machine — verify install builds successfully and the version marker is written.
5. Manual: in a project with a real blueprint, run `/archie-viewer` — bundle loads, ReportPage renders, mermaid diagram draws, findings list populates.
6. Verify the share flow at `archie-viewer.vercel.app/r/:token/details` is unchanged after the `ReportPage` prop refactor — deploy preview from the same Vite build is the proof.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| `ReportPage` prop refactor breaks the existing Vercel share route. | Validation step 6. Change is small (optional prop, default behavior preserved). |
| User has no node/npm at install time. | `archie.mjs` itself runs in node (since it's `npx`), so node is guaranteed. npm ships with node. Risk reduces to "npm misconfigured". Clear error message names the common causes. |
| Slow / offline at install time. | One-time cost. Subsequent runs skip via version marker. Offline users can't `npx` anyway. |
| npm registry hiccup → install fails. | Hard fail. Original plan would have shipped a pre-built bundle, this one doesn't. Trade accepted for package size. |
| Stale build from old npm cache. | `npm ci` (not `npm install`) is deterministic against the lockfile. |
| Node version too old. | `package.json` engines field pins min Node 18. `archie.mjs` checks `process.versions.node` and exits with a clear message if too old. |
| User customized `.archie/viewer/` between runs. | Version marker check is a stat on `dist/.archie-version`. To force rebuild after manual edits, delete `.archie/viewer/dist/`. Documented in the marker file's first comment. |
| Port 5847 collides with another service. | Free-port fallback (already in current viewer.py). |
| User on Linux SSH without DISPLAY. | `webbrowser.open()` no-ops there; URL still printed. `--no-open` flag for explicit suppression. |
| V2 divergence drift between local + share. | `LocalPage` and `components/local/` keep local-only code physically separated. Share viewer build doesn't import from `local/`. |

## PR description outline

Title: `feat(viewer): unify /archie-viewer with share/viewer/ React app`

- *Why* — viewer.py and share/viewer/ are two render stacks for the same data. Unifying them halves the maintenance and makes V2 features ship to both immediately.
- *What ships in V1* — the V1 features list above.
- *What gets dropped* — the four V2-eligible features above.
- *How V2 diverges* — the page-wrapper pattern.
- *Test plan* — validation gates above.

## Decisions locked

| Decision | Choice |
|---|---|
| Distribution model | Build at install time (no committed `dist/`). |
| Data path in local mode | New `/local` route + `GET /api/bundle` reusing `upload.build_bundle()`. |
| V1 feature parity | Match share viewer's detail page; drop the four V2-eligible features. |
| Browser auto-open | Yes; `--no-open` flag opt-out. |
| Default port | 5847 with free-port fallback. |
| PR slicing | Single PR on `feature/unify-viewer-scan`. |
| V2 divergence pattern | `LocalPage` page wrapper + `components/local/` directory. No runtime mode-checks in shared components. |

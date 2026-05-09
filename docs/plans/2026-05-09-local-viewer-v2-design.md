# Local Viewer V2 — restore dropped features

**Status:** Design approved 2026-05-09. Ready for implementation.
**Branch:** `feature/unify-viewer-scan` (continuation of V1, no separate branch).
**Reference:** Builds on `docs/plans/2026-05-09-unify-viewer-scan-design.md`.

## Problem

V1 dropped four features from the old `viewer.py` to ship the React unification cleanly. Three of them are useful enough to bring back as local-only features the share viewer never sees: inline rule editing, per-folder CLAUDE.md browsing, and generated-files browsing.

V1's divergence design (LocalPage wrapper + `components/local/`) was built for exactly this. V2 fills it in.

## Goal

Local `/archie-viewer` gains:

1. **Inline rule editor** — adopt / reject / disable / enable / edit rules directly from the existing rule cards, one-click for toggles, modal for edit. Reversible (no destructive delete). Available only in local mode; share viewer's bundle is byte-identical.
2. **Folder CLAUDE.md browser** — new tab. Always visible. Shows per-folder intent-layer output as a tree + markdown viewer; when intent layer hasn't run, shows an empty state explaining what it is and how to generate it.
3. **Generated files browser** — new tab. Always visible. Shows root `CLAUDE.md`, `AGENTS.md`, and `.claude/rules/**/*.md` as a tree + markdown viewer.

## Non-goals

- No bulk operations on rules. Each toggle/edit is one atomic action.
- No optimistic UI. After a write, re-fetch `/api/bundle` to reconcile.
- No long-poll / job-stream UI for the renderer/rule_index subprocesses. Fire-and-forget; failures don't block the user-facing toast.
- No changes to `/archie-share` flow. The Vercel viewer's `/r/:token/details` route is unchanged.
- No tab for the inline rule editor. It's inline by design.

## Architecture

`LocalPage` becomes a tabbed shell. The default tab renders `ReportPage` with a `LocalEditContext` provider in scope; the other tabs are local-only browsers.

```
share/viewer/src/pages/LocalPage.tsx
  ├── <Tabs default="report">
  │     ├── Tab "report"      → <LocalEditContext.Provider>
  │     │                        <ReportPage bundle={bundle} />
  │     │                       </LocalEditContext.Provider>
  │     ├── Tab "generated"   → <Suspense><GeneratedFilesBrowser /></Suspense>
  │     └── Tab "folders"     → <Suspense><FolderClaudeMdsBrowser /></Suspense>

share/viewer/src/components/local/
  RuleControls.tsx           lazy — inline buttons (✓ adopt / ✕ reject / 🔒 disable / 🔓 enable / ✎ edit)
  RuleEditModal.tsx          lazy — multi-line edit for description/why/example/severity_class
  GeneratedFilesBrowser.tsx  lazy — tree + markdown
  FolderClaudeMdsBrowser.tsx lazy — tree + markdown, with empty-state branch
  IntentLayerEmptyState.tsx  CTA card when count == 0
  MarkdownPane.tsx           shared primitive (react-markdown + rehype-highlight)
  TreeNav.tsx                shared primitive (path-grouped sidebar)
  Toast.tsx                  shared primitive — bottom-right success indicator on mutations
  context/LocalEditContext.tsx   the React Context that ReportPage checks
```

**Bundle separation invariant:** `share/viewer/src/components/local/**` must NOT be imported anywhere reachable from `share/viewer/src/pages/CoverPage.tsx` or from `ReportPage` outside the context check. ReportPage's check is a `useContext(LocalEditContext)` — `null` in share mode → render nothing extra. The context's *type* is imported at compile time, but the *components* are lazy-imported only inside `LocalPage`. Vite tree-shakes the share build → zero local-only JS in the share bundle.

## Feature 1 — Inline rule editor

### State machine

```
                 [✓ adopt]
   proposed ─────────────────► active
       │                          │ ▲
       │ [✕ reject]    [🔒 disable]│ │ [🔓 enable]
       │                          ▼ │
       └────────────────────► ignored
                                  ▲
                              ── ✎ edit ── (active or ignored)
```

Five actions, each one-click except `edit` (modal). All reversible. No destructive delete.

### File mapping

| Action | Source file | Destination file | Stamp |
|---|---|---|---|
| `adopt` | `proposed_rules.json` | `rules.json` | `source: "scan-adopted"` |
| `reject` | `proposed_rules.json` | `ignored_rules.json` | preserve fields |
| `disable` | `rules.json` | `ignored_rules.json` | preserve fields |
| `enable` | `ignored_rules.json` | `rules.json` | preserve fields |
| `edit` | (in-place) | (in-place) | patch description/why/example/severity_class |

### Backend

```
POST /api/rules
  body: { action: "adopt" | "reject" | "disable" | "enable" | "edit",
          rule_id: string,
          patch?: { description?, why?, example?, severity_class? } }
  responses:
    200 { ok: true }
    400 { error: "invalid severity_class | unknown rule_id | unknown action" }
    409 { error: "rule_id not in expected source state" }
    500 { error: "<message>" }
```

**Atomic write per action:**
1. Read source + destination files into memory.
2. Apply transition.
3. Write `<file>.tmp`, fsync, `os.replace()` to final name. POSIX atomic.
4. Return 200 immediately.
5. Fire-and-forget two subprocesses (no await): `python3 .archie/rule_index.py build` and `python3 .archie/renderer.py`. If they fail, the persisted JSON is correct anyway; the user sees stale `enforcement.md` until next scan, which is acceptable degradation.

**Schema validation for `edit`:** `severity_class ∈ {decision_violation, pitfall_triggered, tradeoff_undermined, pattern_divergence, mechanical_violation}`. Backend returns 400 with the allowed set if violated. UI surfaces as toast "Invalid severity class — must be one of: …" — no save.

### Frontend

Inline `<RuleControls rule={...} action="adopt|reject|disable|enable" />` rendered next to each rule card, only when `useContext(LocalEditContext)` is non-null. Edit is a separate `[✎]` button → opens `<RuleEditModal>` over the current page. Modal has a textarea per editable field + a severity_class dropdown.

After a successful `POST /api/rules`, LocalPage re-fetches `/api/bundle` and the rule list re-renders from disk. A small `<Toast>` confirms "Rule {id} {actioned}." for ~2s bottom-right.

### ReportPage change (the only intrusion in shared code)

In each rule rendering site (Architecture Rules, Enforcement Rules adopted, Development Rules, Infrastructure Rules, Proposed Enforcement Rules), add:

```tsx
const localCtx = useContext(LocalEditContext)
// inside rule card:
{localCtx && <Suspense fallback={null}><RuleControls rule={rule} ctx={localCtx} /></Suspense>}
```

`LocalEditContext` defaults to `null` (share mode). Share-mode behavior is identical: no controls render, nothing imports lazy components. Vite confirms with `npm run build` — the share bundle has no local/* chunks loaded by default.

## Feature 2 — Folder CLAUDE.md browser

### Two-state UI

**State A — intent layer present:** standard tree + markdown layout.

**State B — intent layer missing:** `<IntentLayerEmptyState />` card:

```
┌──────────────────────────────────────────────────────────────────┐
│ 📁  Per-folder context not yet generated                          │
│                                                                  │
│ Archie can write a CLAUDE.md into each meaningful directory of   │
│ your repo, giving AI agents directory-level architectural        │
│ context (what this layer does, what it depends on, what to       │
│ avoid here). Without this, agents only see the root CLAUDE.md.   │
│                                                                  │
│ Two ways to generate:                                            │
│                                                                  │
│   /archie-deep-scan                                              │
│     Runs the intent layer as Phase 7. Full baseline, ~15-20 min. │
│                                                                  │
│   /archie-intent-layer prepare && /archie-intent-layer next-ready│
│     Incremental, resumable across sessions. Run next-ready until │
│     the queue is empty.                                          │
│                                                                  │
│ Detected: 0 per-folder CLAUDE.md files outside the repo root.    │
└──────────────────────────────────────────────────────────────────┘
```

The "Detected: N" line uses the live count — if N>0 but `intent_layer_state.json` is absent, that means CLAUDE.mds were created some other way (manual?); the card still shows but with the live count, helping the user diagnose.

### Backend

```
GET /api/intent-layer-status
  → { exists: bool, count: number }

GET /api/folder-claude-mds
  → { "app/src/main/CLAUDE.md": "<markdown content>", ... }
```

`exists = (count > 0) OR (.archie/intent_layer_state.json exists with non-empty `processed`)`. Two signals, OR'd, so we cover both deep-scan-driven and incremental-driven generation.

`_collect_folder_claude_mds` helper recoverable verbatim from the deleted V1 viewer.py code (~15 LOC).

## Feature 3 — Generated files browser

Always visible. Same TreeNav + MarkdownPane primitives as feature 2.

```
GET /api/generated-files
  → { "CLAUDE.md": "...",
      "AGENTS.md": "...",
      ".claude/rules/enforcement.md": "...",
      ".claude/rules/<topic>.md": "...",
      ... }
```

`_collect_generated_files` helper recoverable verbatim from V1 viewer.py code (~15 LOC).

## Shared primitives

Built once in iteration 1, reused by 1, 2, and 3:

- `MarkdownPane` — wraps `ReactMarkdown` + `remarkGfm` + `rehypeHighlight` + `highlight.js/styles/atom-one-dark.min.css` (already in dependency list, used by ReportPage). ~30 LOC.
- `TreeNav` — path-prefix grouped sidebar. Takes `{paths: string[], selected, onSelect}`. ~50 LOC.
- `Toast` — bottom-right notification, auto-dismiss after 2s. Used by RuleControls. ~25 LOC.

## Decisions locked

| Decision | Choice |
|---|---|
| Rule editor placement | Inline on existing ReportPage rule cards, gated by LocalEditContext |
| Toggle UX | One-click for adopt/reject/disable/enable; modal for edit |
| Destructive delete | None — disable is the only "off" state, reversible |
| Folder browser visibility | Always visible; CTA empty state when intent layer missing |
| Empty-state CTA copy | Names both `/archie-deep-scan` (with 15-20 min cost) and `/archie-intent-layer prepare/next-ready` (with "incremental, resumable") |
| Generated files browser visibility | Always visible |
| Bulk operations | None in V2 |
| Optimistic UI | None — re-fetch bundle after each mutation |
| Subprocess output | Fire-and-forget; user-visible toast on POST success regardless |
| Save indicator | Small bottom-right toast (`<Toast>`), 2s auto-dismiss |
| Branch / PR strategy | All commits land directly on `feature/unify-viewer-scan` alongside V1; no separate branch, no V1-to-main PR until V2 also lands |

## Risks

| Risk | Mitigation |
|---|---|
| Lazy import boundaries leak — share build accidentally pulls a `local/` component into the main chunk | After iteration 1 lands, run `cd npm-package/assets/viewer && npm ci && npm run build` and grep `dist/assets/index-*.js` for class names from `local/`. Add to V2 verification gate. |
| Concurrent `/archie-viewer` instances issue mutating POSTs | Last-write-wins. Document in slash command. Single-user local tool; not worth file locking. |
| `os.replace()` on Windows not atomic for cross-volume — but `.archie/` is always one path under repo root, so same volume always | No mitigation needed. Documented assumption. |
| `rule_index.py` or `renderer.py` subprocess fails after the JSON write | The rules.json write is the source of truth; subprocesses are derivable artifacts. Next `/archie-scan` regenerates them. Toast still confirms save success. |
| Schema drift in `severity_class` — adding a sixth allowed value to the rule system breaks the editor | Editor reads the allowed set from a constant in the backend's response (could be `GET /api/rule-schema`) — but this is YAGNI; the five values have been stable since the deep-scan refactor. Hardcode for now. |
| User edits a rule that proposed_rules.json also references with the same id (because the scanner re-proposed something already adopted) | The dedup happens at scan time, not edit time. Backend's edit action only patches the file the rule currently lives in (rules.json or ignored_rules.json) — proposed_rules.json is read-only via this endpoint. |

## Test plan

- Backend: pytest exercises each `POST /api/rules` action against tmpdir fixtures, asserting file moves are atomic + correct, and that schema validation rejects bad payloads.
- Backend: pytest covers `GET /api/intent-layer-status` returning correct (exists, count) pairs across (no marker / marker only / files only / both) combinations.
- Backend: pytest covers `GET /api/folder-claude-mds` and `GET /api/generated-files` for empty repos, repos with files, repos with `_SKIP_DIRS` content (which must be excluded).
- Frontend: no unit tests (share/viewer has no test framework). Manual smoke per iteration: build dist, run viewer.py against the Archie repo itself, verify each tab renders, verify a single round-trip toggle of a real rule lands correctly in `.archie/rules.json`.

## What ships in V2

After all three iterations are committed:

- `LocalPage` is a 3-tab shell.
- Tab "Report" embeds `ReportPage` with inline rule controls.
- Tab "Generated" lists `CLAUDE.md`, `AGENTS.md`, `.claude/rules/**/*.md` with markdown viewer.
- Tab "Folders" lists per-folder CLAUDE.mds, or shows the intent-layer CTA when none exist.
- Mutations on `/api/rules` are atomic and reversible.
- Vercel share viewer at `archie-viewer.vercel.app/r/:token/details` is unchanged in behavior and bundle composition.
- Eventual main-PR will land V1 + V2 in one merge.

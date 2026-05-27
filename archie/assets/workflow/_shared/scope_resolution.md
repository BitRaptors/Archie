# Shared fragment — "Resolve scope" Phase 0

> **This file is the source of truth for Phase 0 in `{{COMMAND_PREFIX}}archie-deep-scan` (and adopted by `{{COMMAND_PREFIX}}archie-scan` as a follow-up).**
> Slash commands don't support file includes, so commands either physically inline this content or load it via Read at activation. After the modularization refactor, `{{COMMAND_PREFIX}}archie-deep-scan` loads this file at Activation; `{{COMMAND_PREFIX}}archie-scan` still inlines a near-identical copy and should be migrated next.

The fragment produces variables that downstream steps read:

- `SCOPE` — one of `single`, `whole`, `per-package`, `hybrid`
- `WORKSPACES` — array of workspace paths relative to `$PWD`. Empty for `single` and `whole`.
- `MONOREPO_TYPE` — when applicable, the detected workspace manager (npm / pnpm / yarn / cargo / gradle / etc.)

---

## Phase 0: Resolve scope

Every run needs to know whether to scan the root, a specific workspace, or a set of workspaces. The choice is persisted in `.archie/archie_config.json` so we ask at most once per project.

### Step A: Read existing config

```bash
python3 .archie/intent_layer.py scan-config "$PWD" read
```

- **Exit 0** → config exists. Parse `scope`, `workspaces`, `monorepo_type` from the JSON. Skip to Step D.
- **Exit 1** → config missing. Go to Step B.

If the user invoked the command with `--reconfigure`, skip Step A entirely and go to Step B.

### Step B: Detect monorepo type + subprojects

```bash
python3 .archie/scanner.py "$PWD" --detect-subprojects
```

Parse `monorepo_type` and count subprojects where `is_root_wrapper` is false.

- **0 or 1 non-wrapper subprojects** → Not a monorepo. Write config as `single`:

  ```bash
  echo '{"scope":"single","monorepo_type":"<detected-type>","workspaces":[]}' \
    | python3 .archie/intent_layer.py scan-config "$PWD" write
  ```

  Skip to Step D.

- **2+ non-wrapper subprojects** → Go to Step C.

### Step C: Interactive scope prompt

> **This is a required decision gate, not a clarifying question.** You MUST ask the user the scope choice interactively — even when the session is running in non-interactive or "no clarifying questions" mode. Never auto-select, never infer the answer from the project type, never skip the prompt. Scope determines which trees get analyzed and what files get written into the user's repo; only the user can authorize that.

First, print the workspace list so the user sees what's available:

> Found **N workspaces** in this **{monorepo_type}** monorepo:
> 1. {name} ({type}) — {path}
> 2. {name} ({type}) — {path}
> ...

Then ask the user the scope choice — {{>ask_user}}:

- **question:** "How do you want to analyze this monorepo?"
- **header:** "Scope"
- **multiSelect:** false
- **options** (exactly these four labels and descriptions):
  1. label `Whole` — description `One unified blueprint treating the monorepo as one product. Workspaces become components; cross-workspace imports become the primary architecture view. Fastest.`
  2. label `Per-package` — description `One blueprint per workspace you pick. Deep detail per package, no product-level view.`
  3. label `Hybrid` — description `Whole blueprint at root + per-workspace blueprints for specific workspaces. Most comprehensive, slowest.`
  4. label `Single` — description `Ignore the workspaces and scan the whole tree as if it were one project. Only for small monorepos.`

Map the answer: Whole → `whole`, Per-package → `per-package`, Hybrid → `hybrid`, Single → `single`.

- If `whole` or `single` → `WORKSPACES=[]`
- If `per-package` or `hybrid` → ask which workspaces to include.
  - Ask the user which workspaces to include — {{>ask_user}}. Allow multiple selections: one option per workspace, label `{name} ({type})`, description `Path: {path}`. If presenting a numbered list, accept comma-separated numbers (e.g., `1,3,5`) or `all`. Map the user's picks back to paths relative to `$PWD`.
  - Either way, honor `all` as a shortcut for every workspace.

If `per-package` or `hybrid`, also ask the user the run mode — {{>ask_user}}:

- **question:** "How should the selected workspaces run?"
- **header:** "Run mode"
- **multiSelect:** false
- **options:**
  1. label `Parallel` — description `Spawn one agent per workspace at the same time. Faster, more concurrent model usage.`
  2. label `Sequential` — description `Run workspaces one after another. Slower but easier to follow the output.`

Map: Parallel → `parallel`, Sequential → `sequential`.

Persist the chosen config (parallel/sequential lives only in the run itself, not in the config file):

```bash
echo '{"scope":"<chosen>","monorepo_type":"<detected-type>","workspaces":[<array>]}' \
  | python3 .archie/intent_layer.py scan-config "$PWD" write
```

### Step D: Validate

```bash
python3 .archie/intent_layer.py scan-config "$PWD" validate
```

- **Exit 0** → proceed.
- **Exit 1** → workspace drift. Instruct the user to re-run with `--reconfigure`. Stop.

Expose `SCOPE`, `WORKSPACES`, `MONOREPO_TYPE`.

### Step E: Intent Layer choice

> **This is a required decision gate, not a clarifying question.** You MUST ask the user here — even when the session is running in non-interactive or "no clarifying questions" mode. Never auto-select an option, never infer the answer from the project type ("it's a deep Android tree, so yes"), never skip the prompt. The Intent Layer writes a `CLAUDE.md` into every folder of the user's repo; only the user can authorize that. If a harness instruction tells you to avoid clarifying questions, that instruction does NOT override this gate — this is a deliberate, mandatory choice, not a clarification.

Ask the user whether to run the per-folder enrichment pass (Step 7) — {{>ask_user}}:

- **question:** "Generate per-folder CLAUDE.md files (Intent Layer)?"
- **header:** "Intent Layer"
- **multiSelect:** false
- **options:**
  1. label `Yes — enrich every folder (Recommended)` — description `Adds a short, folder-specific CLAUDE.md to every directory in your project — role, expected patterns, anti-patterns. AI coding agents then get pinpoint local context wherever they edit instead of re-deriving it from the root CLAUDE.md each time. Adds a few minutes of {{ANALYSIS_MODEL}} time (scales with folder count).`
  2. label `No — skip Intent Layer` — description `Faster deep-scan. Only the root CLAUDE.md + rule files are written. AI agents editing files in deep folders won't have folder-local architectural guidance.`

Map the answer: Yes → `INTENT_LAYER=yes`, No → `INTENT_LAYER=no`. Expose `INTENT_LAYER` for the rest of the run. Step 7 honors this flag.

### Step F: Persist run context

Write every shell variable that Steps 1–10 depend on into `.archie/deep_scan_state.json` so `/compact` + `--continue` can rehydrate them from disk without relying on orchestrator memory:

```bash
echo "$WORKSPACES" | python3 .archie/intent_layer.py deep-scan-state "$PWD" save-run-context \
    --scope "$SCOPE" \
    --intent-layer "$INTENT_LAYER" \
    --scan-mode "$SCAN_MODE" \
    --monorepo-type "$MONOREPO_TYPE" \
    --start-step "$START_STEP" \
    --workspaces-from-stdin
```

Note: `PROJECT_ROOT` is not persisted — `$PWD` at resume time is the authoritative value (slash commands are always invoked from the repo root, and the state file itself lives under `<root>/.archie/`). Persisting the absolute path would leak machine-specific info (e.g. `/Users/foo/...`) into a state file users may commit. The `save-run-context` subcommand silently accepts `--project-root` for backward compat with older installs but discards the value.

This is a no-op on `--continue` runs because the Resume Prelude already rehydrated these variables. Safe to call every time.

### Execution plan based on SCOPE

- **SCOPE=single** — Set `PROJECT_ROOT="$PWD"` and run Steps 1-9 once. No monorepo awareness.
- **SCOPE=whole** — Set `PROJECT_ROOT="$PWD"` and run Steps 1-9 once, applying the workspace-aware addendum in the Structure agent (Step 3) so each workspace is a top-level component, and the Wave 2 reasoning agent populates `blueprint.workspace_topology`.
- **SCOPE=per-package** — For each path in `WORKSPACES`, set `PROJECT_ROOT="$PWD/<path>"` and run Steps 1-9. Each per-workspace run writes its own artifacts namespaced under `PROJECT_ROOT/.archie/tmp/` so workspaces never clobber each other. After all finish, go to Step 8 / 9 each within its own `PROJECT_ROOT`.
    - **Parallel mode** — {{>dispatch_workspace_parallel}}
    - **Sequential mode** — run the workspaces one after another in a plain loop. No subagent dispatch.
- **SCOPE=hybrid** — Pass 1: run Steps 1-9 at `PROJECT_ROOT="$PWD"` with whole-mode semantics. Pass 2: iterate `WORKSPACES` per-package using the same parallel/sequential mechanism as `SCOPE=per-package` above. Each pass writes its own blueprint under `PROJECT_ROOT/.archie/`.

**IMPORTANT:** The `.archie/*.py` scripts are installed at the REPO ROOT. Always reference them as `.archie/scanner.py` etc. from the repo root. Pass `PROJECT_ROOT` as the first argument when it is not `$PWD`.

---

Run the following steps once per project. In single-project mode, `PROJECT_ROOT` is the repo root. In monorepo mode, `PROJECT_ROOT` is the sub-project directory.

Use `PROJECT_NAME` as the basename of `PROJECT_ROOT` for namespacing temp files (e.g., "gasztroterkepek-android").


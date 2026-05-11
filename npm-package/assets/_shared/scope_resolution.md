# Shared fragment — "Resolve scope" Phase 0

> **This file is the source of truth for Phase 0 in both `/archie-scan` and `/archie-deep-scan`.**
> Slash commands don't support includes, so the block below is physically inlined into both.
> When you update this fragment, update both `.claude/commands/archie-scan.md` and `.claude/commands/archie-deep-scan.md`, then re-sync to `npm-package/assets/`.

The fragment produces two variables that downstream steps read:

- `SCOPE` — one of `single`, `whole`, `per-package`, `hybrid`
- `WORKSPACES` — array of workspace paths relative to `$PROJECT_ROOT`. Empty for `single` and `whole`.

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
- If `per-package` or `hybrid` → ask the user which workspaces to include.
  - **When N ≤ 4 workspaces:** use `AskUserQuestion` with `multiSelect: true`. One option per workspace, label `{name} ({type})`, description `Path: {path}`. Map the user's checkbox picks back to paths.
  - **When N ≥ 5 workspaces:** `AskUserQuestion`'s 4-option maximum doesn't fit — fall back to a free-form prompt: *"Which workspaces? Type comma-separated numbers (e.g., `1,3,5`) or `all`."* Resolve to paths relative to `$PROJECT_ROOT`.
  - Either way, also honor `all` as a shortcut for every workspace.

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

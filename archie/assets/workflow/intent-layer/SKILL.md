# Archie Intent Layer — Per-Folder CLAUDE.md Generation

Generate AI-written `CLAUDE.md` for every folder in the project using bottom-up DAG scheduling. Each folder gets a ~80-line architectural description (purpose, patterns, anti-patterns, key files, decisions) so agents editing deep in the tree have folder-local guidance — not just the root CLAUDE.md.

Use this when the user skipped Intent Layer during `{{COMMAND_PREFIX}}archie-deep-scan` (chose "No — skip Intent Layer" at the prompt), or when `.archie/enrichments/` is empty but a blueprint already exists.

**Prerequisites:** If `.archie/intent_layer.py` doesn't exist, tell the user to run `npx @bitraptors/archie` first.

**CRITICAL CONSTRAINT: Never write inline Python.**
Do NOT use `python3 -c "..."` for inspection, parsing, or transformation. Every operation uses a dedicated `.archie/*.py` command. If you need data not covered by these commands, proceed without it or ask the user. NEVER improvise Python.

### Flags (optional)

If invoked as `{{COMMAND_PREFIX}}archie-intent-layer --continue` → set `RESUME_INTENT=continue` before anything else. Skip the Phase 0 interactive resume prompt if partial state is detected.

If invoked as `{{COMMAND_PREFIX}}archie-intent-layer --finalize-partial` → set `RESUME_INTENT=finalize`. Skip the Phase 0 interactive resume prompt if partial state is detected.

Otherwise → `RESUME_INTENT=ask`.

---

## Telemetry consent (one-time, run before anything else)

Read and follow `{{WORKFLOW_ROOT}}/_shared/telemetry-consent.md`. It checks whether this machine has been asked about anonymous usage telemetry and, if not, presents a one-time interactive opt-in. It self-skips after the first answer and on non-interactive sessions.

---

## Phase 0: Precondition check

The Intent Layer needs BOTH `.archie/scan.json` (file tree) and `.archie/blueprint.json` (architectural context: components, decisions, responsibilities, depends_on, key_interfaces) at the *effective project root* — which is either the repo root or a specific workspace, depending on monorepo scope. Without the blueprint, per-folder enrichments cannot be grounded in the project's architecture — they'd be generic file summaries, not architectural guides.

### Step 0.a: Resolve the effective project root

A repo can be a single-project (root has the blueprint), a monorepo with a unified root blueprint (`whole` scope), a monorepo with per-workspace blueprints (`per-package`), or a hybrid (both). Intent-layer is heavy; pick **one** blueprint to operate on per invocation. Run the command again if you need to regenerate intent-layer for multiple workspaces.

Read the persisted scope config:

```bash
python3 .archie/intent_layer.py scan-config "$PWD" read 2>/dev/null
```

Branch on the result:

**A. Exit 0, scope is `single` or `whole`** → one blueprint at the repo root.
```bash
PROJECT_ROOT="$PWD"
```

**B. Exit 0, scope is `per-package`** → workspace-level blueprints. Parse the `workspaces` array from the JSON output.
- If exactly one workspace → `PROJECT_ROOT="$PWD/<workspace>"`.
- If multiple → ask the user which workspace's per-folder CLAUDE.md files to regenerate — {{>ask_user}}:
  - **question:** "Which workspace's per-folder CLAUDE.md files should be regenerated? Re-run `{{COMMAND_PREFIX}}archie-intent-layer` separately for each workspace you want to refresh."
  - **header:** "Workspace"
  - **multiSelect:** false
  - **options:** one per workspace, label `<workspace-name>`, description `Path: <workspace>`
- Map the answer: `PROJECT_ROOT="$PWD/<chosen-workspace>"`.

**C. Exit 0, scope is `hybrid`** → root AND per-workspace blueprints exist. Ask which to use as the basis — {{>ask_user}}:
- **question:** "Which blueprint is the basis for this intent-layer run?"
- **header:** "Blueprint"
- **multiSelect:** false
- **options:** first label `Monorepo-wide (root)`, description `Use the root blueprint at .archie/blueprint.json`; then one per workspace, label `<workspace-name>`, description `Path: <workspace>`.
- Map: `Monorepo-wide (root)` → `PROJECT_ROOT="$PWD"`. Workspace name → `PROJECT_ROOT="$PWD/<workspace>"`.

**D. Exit 1 (no config)** → no monorepo scope persisted. Discover subprojects on disk:

```bash
python3 .archie/scanner.py "$PWD" --detect-subprojects
```

The script prints both a human summary on stderr and the full JSON on stdout. Parse the `subprojects` array. For each entry, check whether `<path>/.archie/blueprint.json` exists:

```bash
test -f "$PWD/<subproject-path>/.archie/blueprint.json"
```

Collect the subprojects that pass the test (call this list `WORKSPACE_BLUEPRINTS`). Then:

- **`WORKSPACE_BLUEPRINTS` is empty** → assume single-project: `PROJECT_ROOT="$PWD"`. Step 0.b will surface the missing-blueprint error if there's none at the root either.
- **`WORKSPACE_BLUEPRINTS` non-empty** → workspace blueprints exist without a persisted scope (typical of a repo where `{{COMMAND_PREFIX}}archie-deep-scan` was run inside individual workspace directories). Ask the user to pick one — {{>ask_user}}:
  - **question:** "No monorepo scope is persisted but workspace-level blueprints were found. Pick the workspace to regenerate intent-layer for."
  - **header:** "Workspace"
  - **multiSelect:** false
  - **options:** one per workspace in `WORKSPACE_BLUEPRINTS`, label `<workspace-name>`, description `Path: <workspace>`
  - Map: `PROJECT_ROOT="$PWD/<chosen-workspace>"`.

  Then offer to persist scope so future runs auto-discover — {{>ask_user}}:
  - **question:** "Persist this as `scope=per-package` in archie_config.json so future scan / share / intent-layer commands use the recorded workspaces without re-asking?"
  - **header:** "Persist scope"
  - **multiSelect:** false
  - **options:**
    1. label `Yes — persist as per-package` — description `Records every workspace that has a blueprint into .archie/archie_config.json. Subsequent runs auto-discover them.`
    2. label `No — just this run` — description `Use the chosen workspace only for this run. archie_config.json stays missing.`

  If `Yes`, write the config. Build the workspaces array literally from `WORKSPACE_BLUEPRINTS` and the `monorepo_type` from the `--detect-subprojects` JSON output:
  ```bash
  echo '{"scope":"per-package","monorepo_type":"<detected-or-none>","workspaces":[<array-of-workspace-paths>]}' \
    | python3 .archie/intent_layer.py scan-config "$PWD" write
  ```

For the remaining Phase 0 steps and all subsequent phases, use `$PROJECT_ROOT` instead of `$PWD` when passing the project root as a script argument.

### Step 0.b: Check scan.json

```bash
test -f "$PROJECT_ROOT/.archie/scan.json"
```

- **Exit 0** → scan.json exists. Continue.
- **Exit 1** → scan.json missing. Run the scanner now:
  ```bash
  python3 .archie/scanner.py "$PROJECT_ROOT"
  ```
  Then continue.

### Step 0.c: Check blueprint.json (hard requirement)

```bash
test -f "$PROJECT_ROOT/.archie/blueprint.json"
```

- **Exit 0** → blueprint exists. Continue to Step 0.d.
- **Exit 1** → blueprint missing. **Stop execution.** Print this message verbatim and do not proceed:

  > **Intent Layer requires a blueprint.**
  >
  > Per-folder CLAUDE.md files are architectural descriptions — they need the project's architecture (components, decisions, responsibilities) as grounding. That architecture lives in `.archie/blueprint.json`, which is produced by `{{COMMAND_PREFIX}}archie-deep-scan`.
  >
  > Run `{{COMMAND_PREFIX}}archie-deep-scan` first against this project root, then come back to `{{COMMAND_PREFIX}}archie-intent-layer`.

  Mention the resolved `PROJECT_ROOT` so the user knows where the blueprint was looked for. Do NOT offer a degraded path. Do NOT run a partial blueprint inference. Exit.

### Step 0.d: Sanity-check the blueprint

```bash
python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" blueprint.json --query .components.components
```

If the output is empty or `null`, the blueprint exists but has no components — it's malformed or mid-scan. Print:

> **Blueprint exists but has no components.** Something interrupted a previous `{{COMMAND_PREFIX}}archie-deep-scan`. Re-run `{{COMMAND_PREFIX}}archie-deep-scan` to regenerate the blueprint fully, then come back.

Exit.

---

## Phase 0.25: Detect and reconcile partial state

If a previous `{{COMMAND_PREFIX}}archie-intent-layer` run was interrupted (hit a usage cap, got compacted, Ctrl+C'd), persistent state survives on disk. Before starting a fresh loop, check whether we can continue from where it stopped.

### Detect partial state

```bash
python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" enrich_state.json --query '.done|length' 2>/dev/null
python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" enrich_batches.json --query '.folders|length' 2>/dev/null
```

- Both return numeric N > 0 **and** `enrich_state.json.done|length > 0` → **partial state exists**. Continue to the resume-mode picker.
- Either is `null` / missing / 0 → **no partial state**. Set `RESUME_MODE=fresh` and skip to Phase 0.5.

### Sweep /tmp for orphan enrichments (BEFORE asking the user)

If a previous orchestrator crashed between "subagent wrote /tmp file" and "orchestrator ran save-enrichment", `/tmp` may contain batch outputs that never got registered. Ingest them so they count toward the resume numbers:

```bash
INTENT_RUN_ID=$(python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" enrich_batches.json --query .run_id 2>/dev/null)
[ -z "$INTENT_RUN_ID" ] || [ "$INTENT_RUN_ID" = "null" ] && INTENT_RUN_ID=""
PROJECT_SLUG="${PROJECT_ROOT##*/}"
for tmp in .archie/tmp/archie_enrichment_${PROJECT_SLUG}_${INTENT_RUN_ID}_*.json; do
    [ -f "$tmp" ] || continue
    # Extract batch_id from
    # ".archie/tmp/archie_enrichment_<project>_<run_id>_<id>.json" using pure shell
    # parameter expansion — no external commands so no permission prompts
    # during an otherwise unattended scan.
    prefix=".archie/tmp/archie_enrichment_${PROJECT_SLUG}_${INTENT_RUN_ID}_"
    name="${tmp#$prefix}"
    batch_id="${name%.json}"
    python3 .archie/intent_layer.py save-enrichment "$PROJECT_ROOT" "$batch_id" "$tmp" 2>/dev/null || true
done
```

Re-read `.done|length` after the sweep so the user sees accurate numbers.

### Resolve RESUME_MODE

Three paths depending on `RESUME_INTENT`:

**If `RESUME_INTENT=continue`** → `RESUME_MODE=resume`. Skip the prompt.

**If `RESUME_INTENT=finalize`** → `RESUME_MODE=finalize_partial`. Skip the prompt.

**If `RESUME_INTENT=ask`** → ask the user how to proceed — {{>ask_user}}:

- **question:** "A previous Intent Layer run was interrupted. {N_DONE} of {N_TOTAL} folders are already enriched. What do you want to do?"
- **header:** "Resume"
- **multiSelect:** false
- **options** (exactly these three labels):
  1. label `Resume` — description `Pick up where we stopped. Keeps completed enrichments, processes remaining folders, merges everything. Use when you can continue.`
  2. label `Finalize partial` — description `Merge what's already enriched into per-folder CLAUDE.md files and skip the unfinished folders. Fast, ends in one step. Use when you hit a usage cap and cannot continue.`
  3. label `Fresh start` — description `Discard progress and run from scratch with the mode picker. Use only after major structural changes — you lose the work done so far.`

Map the answer: Resume → `RESUME_MODE=resume`, Finalize partial → `RESUME_MODE=finalize_partial`, Fresh start → `RESUME_MODE=fresh`.

### Check for baseline drift (warn on resume/finalize)

If `RESUME_MODE` is `resume` or `finalize_partial`, verify the last deep-scan baseline hasn't moved since the state was written:

```bash
python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" last_deep_scan.json --query .commit_sha
```

If this SHA differs from what the state was built against (compare via `git log` on the current HEAD), warn:

> **Note:** the blueprint baseline has moved since this Intent Layer run started. The completed enrichments may reference components that no longer exist. Continue if you trust the overlap; otherwise re-run `{{COMMAND_PREFIX}}archie-deep-scan` then `{{COMMAND_PREFIX}}archie-intent-layer` fresh.

Do not block. The user asked to continue; they can judge. The defensive `cmd_merge` skip-missing-folders keeps this safe in the worst case.

---

## Phase 0.5: Select mode (full vs incremental)

**Skip this phase entirely if `RESUME_MODE` is `resume` or `finalize_partial`.** When resuming, the mode was already decided during the prior run and encoded in the existing `enrich_batches.json`. For `finalize_partial` there's no wave loop anyway — only merge runs.

Ask the user whether to regenerate every folder's CLAUDE.md, or only the folders touched since the last deep scan. Incremental is cheaper and faster for routine catch-up; full is right after major structural changes.

**Deep-scan deltas note**: if you're executing this file from `{{COMMAND_PREFIX}}archie-deep-scan` Step 7, the mode was already decided earlier in that command (the `SCAN_MODE` variable). Skip this phase — use `SCAN_MODE` directly.

### Step A: Ask for the mode

Ask the user the mode — {{>ask_user}}:

- **question:** "Regenerate all folder CLAUDE.md files, or only folders changed since the last deep scan?"
- **header:** "Mode"
- **multiSelect:** false
- **options** (exactly these three labels and descriptions):
  1. label `Auto` — description `Detect changes vs the last deep scan. Run incremental if few files changed; full otherwise. Recommended.`
  2. label `Full` — description `Regenerate every folder's CLAUDE.md. Right after major structural changes, rename waves, or when you want a clean slate. Slower.`
  3. label `Incremental` — description `Only re-enrich folders containing files that changed since the last deep scan. Fast, preserves unchanged enrichments.`

Map the answer: Auto → `MODE=auto`, Full → `MODE=full`, Incremental → `MODE=incremental`. Expose `MODE` for Phase 1.

### Step B: Resolve Auto

If `MODE=auto`, run detect-changes to pick full or incremental based on change ratio:

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" detect-changes
```

Parse the JSON output. Set `MODE` to the returned `mode` field (`full` or `incremental`). Print the `reason` to the user so they know why: *"Detected: {mode} ({reason})"*.

If `detect-changes` returns `mode=full` with `reason="no previous deep scan"` — the `last_deep_scan.json` baseline doesn't exist. This shouldn't happen in practice (the blueprint check in Phase 0 implies a deep scan happened), but if it does, proceed with `MODE=full`.

### Step C: Handle the no-op case

If `MODE=incremental` and `affected_folders` is empty (user just ran deep-scan, nothing has changed since), print:

> No folders have changed since the last deep scan. Every folder's CLAUDE.md is already current. Nothing to regenerate.

Exit gracefully. This is a success, not an error.

Otherwise expose `AFFECTED_FOLDERS` (comma-separated) for Phase 1.

---

## Phase 1: Prepare the folder DAG

**Dispatch based on `RESUME_MODE`:**

- **`RESUME_MODE=resume`** → **skip `prepare` AND skip `reset-state`.** The existing `enrich_batches.json` is still valid; `enrich_state.json.done` is what we want to preserve. Just ensure the enrichments dir exists (`mkdir -p`) and jump to Phase 2.
- **`RESUME_MODE=finalize_partial`** → skip this entire phase. Jump to Phase 3 (merge) — no new subagents will spawn.
- **`RESUME_MODE=fresh`** → run the full prepare + reset flow below.

### Fresh-start prepare (`RESUME_MODE=fresh` only)

**If `MODE=incremental`**, mark only the affected folders + their ancestor chain as dirty:

```bash
python3 .archie/intent_layer.py prepare "$PROJECT_ROOT" --only-folders "$AFFECTED_FOLDERS"
```

`AFFECTED_FOLDERS` is the comma-separated list from Phase 0.5 Step B (e.g. `openmeter/billing,openmeter/ledger/entry`). The script marks those folders and every qualifying ancestor as dirty; `next-ready` will only return dirty folders, so unchanged folders keep their existing CLAUDE.md untouched.

**If `MODE=full`**, prepare the whole DAG:

```bash
python3 .archie/intent_layer.py prepare "$PROJECT_ROOT"
```

### Reset state and ensure enrichments dir exists

```bash
python3 .archie/intent_layer.py reset-state "$PROJECT_ROOT"
mkdir -p "$PROJECT_ROOT/.archie/enrichments"
```

Immediately after the `prepare` call (fresh mode) or immediately after the `mkdir -p` call (resume mode), load the temp-file namespace from the plan you will use for the rest of the run:

```bash
INTENT_RUN_ID=$(python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" enrich_batches.json --query .run_id)
PROJECT_SLUG=$(python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" enrich_batches.json --query .project_slug)
```

This builds `.archie/enrich_batches.json` — the parent→children dependency graph over every folder with source files (plus structural parents). Leaves are processed first, then parents receive summaries of their children.

Print a one-line progress note to the user: *"Preparing intent layer — N folders queued ({mode}), processed bottom-up."*  Derive N from:

```bash
python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" enrich_batches.json --query '.folders|length'
```

In incremental mode N is the size of the dirty subset (affected folders + ancestors), not the total qualifying folders — that's expected.

(Wave count is emergent — it depends on the DAG depth and becomes visible as you loop through `next-ready` calls in Phase 2.)

---

## Phase 2: Process folders bottom-up (parallel per wave)

**Skip this entire phase if `RESUME_MODE=finalize_partial`** — no new subagents spawn; jump straight to Phase 3 (merge) with whatever's already in `.archie/enrichments/`.

For `RESUME_MODE=resume` and `RESUME_MODE=fresh` the flow is identical: `next-ready` reads the done list from disk and returns only folders that still need enrichment. The difference is just the starting point of the done list (non-empty for resume, empty for fresh).

**This loop is self-propelled.** Each wave dispatches all of its sub-agents from one orchestration step and waits for every one to finish before the next wave starts (see the dispatch step below). Do NOT stop or hand control back after a wave is dispatched. Stay in the same Archie command run until one of these is true:
- `next-ready` returns `[]` and Phase 3 can start
- a real failure occurs (missing output file, invalid JSON, save-enrichment error)

After each wave finishes, ingest its outputs, call `next-ready`, and immediately dispatch the next wave yourself. Do not wait for the user to nudge you.

### Status-line labeling (honor the current mode)

When you spawn subagents and when you narrate progress to the user, label the run according to `RESUME_MODE` so status lines are accurate:

| RESUME_MODE | MODE | Label to use |
|---|---|---|
| `fresh` | `full` | `"Intent Layer — full generation"` |
| `fresh` | `incremental` | `"Intent Layer — incremental generation"` |
| `resume` | (either) | `"Intent Layer — resume"` (optionally append counts: `"resume (6 remaining)"`) |
| `finalize_partial` | — | `"Intent Layer — finalize partial"` (this phase is skipped anyway) |

Do NOT use "full regeneration" during a resume — the resume path only touches folders that weren't already done, not every folder.

Loop until every folder is enriched.

### Each iteration:

**a. Get the next ready wave:**

```bash
python3 .archie/intent_layer.py next-ready "$PROJECT_ROOT"
```

The script reads done state from `$PROJECT_ROOT/.archie/enrich_state.json` automatically. First call returns all leaf folders.

- If the output is an empty array (`[]`), all folders are done. Proceed to Phase 3.
- Otherwise the output is a JSON array of folder paths that are ready (their children are enriched).

**b. Split the ready list into batches:**

Pipe the JSON output of `next-ready` directly into `suggest-batches`. Do NOT try to pass ready folders as positional argv — with large DAGs (100+ ready folders) bash word-splitting / ARG_MAX / unquoted-variable expansion all fail silently and produce zero batches:

```bash
python3 .archie/intent_layer.py next-ready "$PROJECT_ROOT" | python3 .archie/intent_layer.py suggest-batches "$PROJECT_ROOT"
```

Argv still works for small test cases (`suggest-batches "$PROJECT_ROOT" <ready1> <ready2>`) but the stdin pipe is the canonical pattern for production runs.

Output is a JSON array: `[{"id": "w0", "folders": [...]}, ...]`. Use `id` (NOT `batch_id`) to reference batches.

**c. For each batch, generate the prompt and spawn a {{ANALYSIS_MODEL}} subagent:**

```bash
python3 .archie/intent_layer.py prompt "$PROJECT_ROOT" --folders <comma-separated-folders> --child-summaries "$PROJECT_ROOT/.archie/enrichments/" > .archie/tmp/archie_intent_prompt_${PROJECT_SLUG}_${INTENT_RUN_ID}_<batch_id>.txt
```

Read the prompt file. **Before spawning**, append the following output contract to the prompt text you pass to the subagent (so the subagent writes its result directly to disk — the orchestrator must never copy or transcribe the subagent's output). The "file path named above" for this contract is `.archie/tmp/archie_enrichment_${PROJECT_SLUG}_${INTENT_RUN_ID}_<batch_id>.json`, and the output must be valid JSON with folder paths as keys — no prose, no code fences, no preamble:

```
---
OUTPUT CONTRACT (mandatory):
The output must be valid JSON with folder paths as keys.
{{>output_contract}}
```

Substitute the actual `<batch_id>` in the path before augmenting the prompt.

**Spawn ALL batches of one wave as a single parallel batch** — they're independent by construction. Each batch runs as one {{ANALYSIS_MODEL}} subagent. {{>dispatch_parallel}}

Dispatch every sub-agent for the current wave from one orchestration step, then wait until every sub-agent in that wave has finished before proceeding. Do not hand-roll your own chunking — use the ready wave and suggested batches exactly as produced. The runtime imposes a concurrency cap on how many sub-agents run at once; trust it to schedule the wave correctly. Do not treat "spawned" as completion: a wave is complete only after every output file has been ingested successfully.

**d. After each subagent completes, ingest its pre-written file:**

```bash
python3 .archie/intent_layer.py save-enrichment "$PROJECT_ROOT" <batch_id> .archie/tmp/archie_enrichment_${PROJECT_SLUG}_${INTENT_RUN_ID}_<batch_id>.json
```

This extracts the JSON (handling conversation envelopes, code fences, multi-block merging), saves it to `.archie/enrichments/<batch_id>.json`, and updates `enrich_state.json` so `next-ready` can advance to the next wave.

**IMPORTANT: Never copy or transcribe the subagent's output yourself. The subagent wrote it directly to /tmp — you only need to call save-enrichment. Read the file the subagent wrote; do not reach into the subagent's own transcript files.**

If the subagent's confirmation reply is missing or the file is absent, skip save-enrichment for that batch and surface the failure — do NOT try to recover the output from the transcript file.

**e. Go back to (a) for the next wave.**

---

## Phase 3: Merge enrichments into per-folder CLAUDE.md files

```bash
python3 .archie/intent_layer.py merge "$PROJECT_ROOT"
```

This reads every `.archie/enrichments/*.json` and writes a `CLAUDE.md` into each matching folder. Folders that already had a manually-edited `CLAUDE.md` get their notes preserved.

---

## Phase 4: Clean up temp files

```bash
rm -f .archie/tmp/archie_intent_prompt_${PROJECT_SLUG}_${INTENT_RUN_ID}_*.txt .archie/tmp/archie_enrichment_${PROJECT_SLUG}_${INTENT_RUN_ID}_*.json
```

---

## Phase 5: Summary to user

Print a concise summary:

```
✓ Intent Layer complete — N folders enriched, M CLAUDE.md files written.

Per-folder guidance lives at:
  <folder1>/CLAUDE.md
  <folder2>/CLAUDE.md
  ...

Agents editing deep in the tree will now auto-load the closest folder's CLAUDE.md.
Re-run this command after major structural changes, or let {{COMMAND_PREFIX}}archie-deep-scan regenerate when you re-baseline.
```

Derive N (count of enriched folders) from `.archie/enrich_state.json`:

```bash
python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" enrich_state.json --query '.done|length'
```

To list the enriched folder paths themselves:

```bash
python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" enrich_state.json --query .done
```

M (CLAUDE.md files written) is reported by `merge` on stderr in Phase 3 — capture it from that output rather than re-computing.

## Telemetry (run after the run completes, silent if opted out)

```bash
python3 .archie/telemetry_sync.py record-event --command intent-layer --outcome success --project-root "$PROJECT_ROOT" 2>/dev/null || true
```

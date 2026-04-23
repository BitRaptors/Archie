# Archie Intent Layer — Per-Folder CLAUDE.md Generation

Generate AI-written `CLAUDE.md` for every folder in the project using bottom-up DAG scheduling. Each folder gets a ~80-line architectural description (purpose, patterns, anti-patterns, key files, decisions) so agents editing deep in the tree have folder-local guidance — not just the root CLAUDE.md.

Use this when the user skipped Intent Layer during `/archie-deep-scan` (chose "No — skip Intent Layer" at the prompt), or when `.archie/enrichments/` is empty but a blueprint already exists.

**Prerequisites:** If `.archie/intent_layer.py` doesn't exist, tell the user to run `npx @bitraptors/archie` first.

**CRITICAL CONSTRAINT: Never write inline Python.**
Do NOT use `python3 -c "..."` for inspection, parsing, or transformation. Every operation uses a dedicated `.archie/*.py` command. If you need data not covered by these commands, proceed without it or ask the user. NEVER improvise Python.

### Flags (optional)

If invoked as `/archie-intent-layer --continue` → set `RESUME_INTENT=continue` before anything else. Skip the Phase 0 AskUserQuestion if partial state is detected.

If invoked as `/archie-intent-layer --finalize-partial` → set `RESUME_INTENT=finalize`. Skip the Phase 0 AskUserQuestion if partial state is detected.

Otherwise → `RESUME_INTENT=ask`.

---

## Phase 0: Precondition check

The Intent Layer needs BOTH `.archie/scan.json` (file tree) and `.archie/blueprint.json` (architectural context: components, decisions, responsibilities, depends_on, key_interfaces). Without the blueprint, per-folder enrichments cannot be grounded in the project's architecture — they'd be generic file summaries, not architectural guides.

### Check scan.json

```bash
test -f "$PWD/.archie/scan.json"
```

- **Exit 0** → scan.json exists. Continue.
- **Exit 1** → scan.json missing. Run the scanner now:
  ```bash
  python3 .archie/scanner.py "$PWD"
  ```
  Then continue.

### Check blueprint.json (hard requirement)

```bash
test -f "$PWD/.archie/blueprint.json"
```

- **Exit 0** → blueprint exists. Continue to Phase 1.
- **Exit 1** → blueprint missing. **Stop execution.** Print this message verbatim and do not proceed:

  > **Intent Layer requires a blueprint.**
  >
  > Per-folder CLAUDE.md files are architectural descriptions — they need the project's architecture (components, decisions, responsibilities) as grounding. That architecture lives in `.archie/blueprint.json`, which is produced by `/archie-deep-scan`.
  >
  > Run `/archie-deep-scan` first, then come back to `/archie-intent-layer`.

  Do NOT offer a degraded path. Do NOT run a partial blueprint inference. Exit.

### Sanity-check the blueprint

```bash
python3 .archie/intent_layer.py inspect "$PWD" blueprint.json --query .components.components
```

If the output is empty or `null`, the blueprint exists but has no components — it's malformed or mid-scan. Print:

> **Blueprint exists but has no components.** Something interrupted a previous `/archie-deep-scan`. Re-run `/archie-deep-scan` to regenerate the blueprint fully, then come back.

Exit.

---

## Phase 0.25: Detect and reconcile partial state

If a previous `/archie-intent-layer` run was interrupted (hit a usage cap, got compacted, Ctrl+C'd), persistent state survives on disk. Before starting a fresh loop, check whether we can continue from where it stopped.

### Detect partial state

```bash
python3 .archie/intent_layer.py inspect "$PWD" enrich_state.json --query '.done|length' 2>/dev/null
python3 .archie/intent_layer.py inspect "$PWD" enrich_batches.json --query '.folders|length' 2>/dev/null
```

- Both return numeric N > 0 **and** `enrich_state.json.done|length > 0` → **partial state exists**. Continue to the resume-mode picker.
- Either is `null` / missing / 0 → **no partial state**. Set `RESUME_MODE=fresh` and skip to Phase 0.5.

### Sweep /tmp for orphan enrichments (BEFORE asking the user)

If a previous orchestrator crashed between "subagent wrote /tmp file" and "orchestrator ran save-enrichment", `/tmp` may contain batch outputs that never got registered. Ingest them so they count toward the resume numbers:

```bash
for tmp in /tmp/archie_enrichment_*.json; do
    [ -f "$tmp" ] || continue
    batch_id=$(basename "$tmp" .json | sed 's/^archie_enrichment_//')
    # save-enrichment is idempotent — overwriting an existing
    # .archie/enrichments/<id>.json with the same content is safe,
    # and appending already-done folders to the state is a set-like op.
    python3 .archie/intent_layer.py save-enrichment "$PWD" "$batch_id" "$tmp" 2>/dev/null || true
done
```

Re-read `.done|length` after the sweep so the user sees accurate numbers.

### Resolve RESUME_MODE

Three paths depending on `RESUME_INTENT`:

**If `RESUME_INTENT=continue`** → `RESUME_MODE=resume`. Skip the prompt.

**If `RESUME_INTENT=finalize`** → `RESUME_MODE=finalize_partial`. Skip the prompt.

**If `RESUME_INTENT=ask`** → call `AskUserQuestion`:

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
python3 .archie/intent_layer.py inspect "$PWD" last_deep_scan.json --query .commit_sha
```

If this SHA differs from what the state was built against (compare via `git log` on the current HEAD), warn:

> **Note:** the blueprint baseline has moved since this Intent Layer run started. The completed enrichments may reference components that no longer exist. Continue if you trust the overlap; otherwise re-run `/archie-deep-scan` then `/archie-intent-layer` fresh.

Do not block. The user asked to continue; they can judge. The defensive `cmd_merge` skip-missing-folders keeps this safe in the worst case.

---

## Phase 0.5: Select mode (full vs incremental)

**Skip this phase entirely if `RESUME_MODE` is `resume` or `finalize_partial`.** When resuming, the mode was already decided during the prior run and encoded in the existing `enrich_batches.json`. For `finalize_partial` there's no wave loop anyway — only merge runs.

Ask the user whether to regenerate every folder's CLAUDE.md, or only the folders touched since the last deep scan. Incremental is cheaper and faster for routine catch-up; full is right after major structural changes.

**Deep-scan deltas note**: if you're executing this file from `/archie-deep-scan` Step 7, the mode was already decided earlier in that command (the `SCAN_MODE` variable). Skip this phase — use `SCAN_MODE` directly.

### Step A: Ask for the mode

Call `AskUserQuestion`:

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
python3 .archie/intent_layer.py deep-scan-state "$PWD" detect-changes
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
python3 .archie/intent_layer.py prepare "$PWD" --only-folders "$AFFECTED_FOLDERS"
```

`AFFECTED_FOLDERS` is the comma-separated list from Phase 0.5 Step B (e.g. `openmeter/billing,openmeter/ledger/entry`). The script marks those folders and every qualifying ancestor as dirty; `next-ready` will only return dirty folders, so unchanged folders keep their existing CLAUDE.md untouched.

**If `MODE=full`**, prepare the whole DAG:

```bash
python3 .archie/intent_layer.py prepare "$PWD"
```

### Reset state and ensure enrichments dir exists

```bash
python3 .archie/intent_layer.py reset-state "$PWD"
mkdir -p "$PWD/.archie/enrichments"
```

This builds `.archie/enrich_batches.json` — the parent→children dependency graph over every folder with source files (plus structural parents). Leaves are processed first, then parents receive summaries of their children.

Print a one-line progress note to the user: *"Preparing intent layer — N folders queued ({mode}), processed bottom-up."*  Derive N from:

```bash
python3 .archie/intent_layer.py inspect "$PWD" enrich_batches.json --query '.folders|length'
```

In incremental mode N is the size of the dirty subset (affected folders + ancestors), not the total qualifying folders — that's expected.

(Wave count is emergent — it depends on the DAG depth and becomes visible as you loop through `next-ready` calls in Phase 2.)

---

## Phase 2: Process folders bottom-up (parallel per wave)

**Skip this entire phase if `RESUME_MODE=finalize_partial`** — no new subagents spawn; jump straight to Phase 3 (merge) with whatever's already in `.archie/enrichments/`.

For `RESUME_MODE=resume` and `RESUME_MODE=fresh` the flow is identical: `next-ready` reads the done list from disk and returns only folders that still need enrichment. The difference is just the starting point of the done list (non-empty for resume, empty for fresh).

### Status-line labeling (honor the current mode)

When you spawn subagents via the Agent tool and when you narrate progress to the user, label the run according to `RESUME_MODE` so status lines are accurate:

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
python3 .archie/intent_layer.py next-ready "$PWD"
```

The script reads done state from `.archie/enrich_state.json` automatically. First call returns all leaf folders.

- If the output is an empty array (`[]`), all folders are done. Proceed to Phase 3.
- Otherwise the output is a JSON array of folder paths that are ready (their children are enriched).

**b. Split the ready list into batches:**

```bash
python3 .archie/intent_layer.py suggest-batches "$PWD" <ready1> <ready2> ...
```

Output is a JSON array: `[{"id": "w0", "folders": [...]}, ...]`. Use `id` (NOT `batch_id`) to reference batches.

**c. For each batch, generate the prompt and spawn a Sonnet subagent:**

```bash
python3 .archie/intent_layer.py prompt "$PWD" --folders <comma-separated-folders> --child-summaries "$PWD/.archie/enrichments/" > /tmp/archie_intent_prompt_<batch_id>.txt
```

Read the prompt file. **Before spawning**, append the following output contract to the prompt text you pass to the subagent (so the subagent writes its result directly to disk — the orchestrator must never copy or re-Write the transcript):

```
---
OUTPUT CONTRACT (mandatory):

1. Use the Write tool to save your COMPLETE JSON response to:
   /tmp/archie_enrichment_<batch_id>.json

2. Write only valid JSON with folder paths as keys — no prose, no code
   fences, no preamble.

3. After Writing, reply with a single-line confirmation:
   "Wrote /tmp/archie_enrichment_<batch_id>.json"

DO NOT print the JSON in your response body. Writing to /tmp is already
permissioned (Write(//tmp/archie_*)) — no permission prompt will fire.
```

Substitute the actual `<batch_id>` in both the path and the confirmation string before augmenting the prompt. Spawn a Sonnet subagent (`model: "sonnet"`) with that augmented prompt.

**Spawn ALL batches of one wave in parallel** — they're independent by construction.

**d. After each subagent completes, ingest its pre-written file:**

```bash
python3 .archie/intent_layer.py save-enrichment "$PWD" <batch_id> /tmp/archie_enrichment_<batch_id>.json
```

This extracts the JSON (handling conversation envelopes, code fences, multi-block merging), saves it to `.archie/enrichments/<batch_id>.json`, and automatically marks the folders as done.

**IMPORTANT: Never copy or Write the subagent's output yourself. The subagent wrote it directly to /tmp — you only need to call save-enrichment. Attempting to `cp` from `.claude/projects/.../subagents/*.jsonl` triggers a sensitive-file permission prompt every single batch.**

If the subagent's confirmation reply is missing or the file is absent, skip save-enrichment for that batch and surface the failure — do NOT try to recover the output from the transcript file.

**e. Go back to (a) for the next wave.**

---

## Phase 3: Merge enrichments into per-folder CLAUDE.md files

```bash
python3 .archie/intent_layer.py merge "$PWD"
```

This reads every `.archie/enrichments/*.json` and writes a `CLAUDE.md` into each matching folder. Folders that already had a manually-edited `CLAUDE.md` get their notes preserved.

---

## Phase 4: Clean up temp files

```bash
rm -f /tmp/archie_intent_prompt_*.txt /tmp/archie_enrichment_*.json
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
Re-run this command after major structural changes, or let /archie-deep-scan regenerate when you re-baseline.
```

Derive N (count of enriched folders) from `.archie/enrich_state.json`:

```bash
python3 .archie/intent_layer.py inspect "$PWD" enrich_state.json --query '.done|length'
```

To list the enriched folder paths themselves:

```bash
python3 .archie/intent_layer.py inspect "$PWD" enrich_state.json --query .done
```

M (CLAUDE.md files written) is reported by `merge` on stderr in Phase 3 — capture it from that output rather than re-computing.

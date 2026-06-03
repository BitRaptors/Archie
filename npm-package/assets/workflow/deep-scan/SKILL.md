---
name: archie-deep-scan
description: Comprehensive architecture baseline scan (15-20 min). Two-wave AI analysis producing blueprint.json, per-folder CLAUDE.md, AI-synthesized rules, health metrics, and drift detection. Use for first-time baselines or major refactors.
---

# Archie Deep Scan — Comprehensive Architecture Baseline

Run a comprehensive architecture analysis. Produces full blueprint, per-folder CLAUDE.md, rules, and health metrics.

**Modes:**
- `{{COMMAND_PREFIX}}archie-deep-scan` — full baseline from step 1 (default, proven workflow)
- `{{COMMAND_PREFIX}}archie-deep-scan --incremental` — only process files changed since last deep scan (fast, 3-6 min)
- `{{COMMAND_PREFIX}}archie-deep-scan --comprehensive` — lift quotas + scope caps for a fully comprehensive baseline (slower). Composes with `--incremental`.
- `{{COMMAND_PREFIX}}archie-deep-scan --from N` — resume from step N (runs N through 9)
- `{{COMMAND_PREFIX}}archie-deep-scan --continue` — resume from where the last run stopped

**Prerequisites:** Run `npx @bitraptors/archie` first to install the scripts. If `.archie/scanner.py` doesn't exist, tell the user to run `npx @bitraptors/archie` and try again.

**Recovery when a run stalls or fails** (network drop, sub-agent timeout, `/compact` interruption, etc.):
The only valid recovery options are listed above — `--continue`, `--from N`, or a fresh full run. **There is no separate "fast scan" or "light scan" command** — `{{COMMAND_PREFIX}}archie-deep-scan` is the single entry point for architecture analysis. If sub-agents timed out, prefer `--continue` (resumes from the last completed step using `deep_scan_state.json`). If specific Wave 1 outputs were lost from `/tmp/`, use `--from 3` to redo Wave 1. Do not invent fallback slash commands. If the existing `.archie/blueprint.json` is recent enough for the current task, skipping the rescan is a valid choice; say so explicitly.

## Update notice (run before anything else, silent unless action needed)

```bash
python3 .archie/update_check.py check 2>/dev/null
```

If output is non-empty:
- `UPGRADE_AVAILABLE old new` → tell the user once at the top of your reply: `"Archie {new} is available (installed: {old}). Upgrade: npx @bitraptors/archie@latest \"$PWD\""`. Then continue with the scan — do not block.
- `JUST_UPGRADED old new` → say `"Archie upgraded {old} → {new}."` once, then proceed.

If output is empty: proceed silently. This is informational only.

## Telemetry consent (one-time, run before anything else)

Read and follow `{{WORKFLOW_ROOT}}/_shared/telemetry-consent.md`. It checks whether this machine has been asked about anonymous usage telemetry and, if not, presents a one-time interactive opt-in. It self-skips after the first answer and on non-interactive sessions.

**CRITICAL CONSTRAINT: Never write inline Python.**
Do NOT use `python3 -c "..."` or any ad-hoc scripting to inspect, parse, or transform JSON. Every operation has a dedicated command:
- Normalize blueprint: `python3 .archie/finalize.py "$PROJECT_ROOT" --normalize-only`
- Append health history: `python3 .archie/measure_health.py "$PROJECT_ROOT" --append-history --scan-type deep`
- Inspect any JSON file: `python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" <filename>`
- Query a specific field: `python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" scan.json --query .frontend_ratio`

If you need data not covered by these commands, proceed without it or ask the user. NEVER improvise Python.

## Preamble: Determine starting step

Check the user's message (ARGUMENTS) for flags:

**Depth (independent of the flags above):** Parse this first, regardless of which flag branch runs below. If ARGUMENTS contains `--comprehensive` (the canonical form; a bare `comprehensive` is also accepted), set `DEPTH=comprehensive`. Otherwise set `DEPTH=default`.

> ### Comprehensive Mode Contract (governs EVERY step when `DEPTH=comprehensive`)
> This is the single global rule for comprehensive depth — it overrides any per-step count, everywhere, including steps that carry no explicit comprehensive clause.
>
> **Treat every item-count anywhere in this workflow — `N-M`, "up to N", "top N", "the N most", "soft floor of N", "a handful", "the most important" — as a FLOOR with no ceiling.** Produce every item that genuinely meets its quality bar; never trim to a number, never stop at a "natural" count. The quality bar is unchanged: do NOT pad, invent, or weaken per-item rigor to inflate counts.
>
> Only two limits survive comprehensive mode: **(1)** the architecture diagram stays **8-12 nodes** (readability), and **(2)** the scripts' mechanical safety/context budgets (per-file read size, per-batch token budget, recursion). Everything else — rules, findings, pitfalls, decisions, trade-offs, components, guidelines, examples, drift findings, naming examples, per-field prose length — is uncapped.
>
> Whenever a step dispatches a sub-agent in comprehensive depth, prepend the contract line shown at that dispatch site so the sub-agent inherits this rule.

**If `--from N` is present** (e.g., `{{COMMAND_PREFIX}}archie-deep-scan --from 5`):
1. Set `START_STEP = N` (the number after --from) and `RESUME_ACTION=resume` (so the Resume Prelude rehydrates shell variables from `deep_scan_state.run_context`).
2. Validate prerequisites exist:
```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" check-prereqs N
```
3. If check fails, tell the user which files are missing and which earlier step to run.
4. If check passes, proceed. Do NOT call `deep-scan-state init` — it would wipe the state the Resume Prelude needs to read.

**If `--continue` is present:**
1. Read state (no prompt — `--continue` is an explicit opt-in):
```bash
LAST=$(python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" deep_scan_state.json --query .last_completed 2>/dev/null)
STATUS=$(python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" deep_scan_state.json --query .status 2>/dev/null)
[ -z "$LAST" ] || [ "$LAST" = "null" ] && LAST=0
```
2. If `LAST == 0` or `STATUS == "completed"`: print "No interrupted run found. Starting fresh from step 1." Set `START_STEP=1`, `RESUME_ACTION=fresh`, and run `deep-scan-state init` below.
3. Otherwise: Set `START_STEP = LAST + 1`, `RESUME_ACTION=resume`. Print `"Resuming deep scan from step {START_STEP}."`. Skip the init call.

**If `--incremental` is present:**
1. Check if `.archie/blueprint.json` exists. If not: print "No existing blueprint — running full baseline instead." Set SCAN_MODE = "full", START_STEP = 1, and proceed as default.
2. If blueprint exists, detect changes:
```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" detect-changes
```
3. Read the JSON output:
   - If `mode` is "full" (threshold exceeded or no previous scan): print the `reason` and say "Running full baseline." Set SCAN_MODE = "full", START_STEP = 1.
   - If `mode` is "incremental" and `changed_count` is 0: print "No files changed since last deep scan. Nothing to do." Exit.
   - If `mode` is "incremental": Set SCAN_MODE = "incremental". Save `changed_files` and `affected_folders` from the output. Print "Incremental deep scan: N files changed. Analyzing changes only." Set START_STEP = 1.
4. Initialize state, then persist the run depth + scan mode:
```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" init
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" save-run-context --depth "$DEPTH" --scan-mode "$SCAN_MODE"
```

**If no flags (default — detect interrupted run, otherwise full baseline):**

Before assuming a fresh run, check whether a previous deep-scan was left unfinished. If so, offer the user a choice instead of silently wiping their work.

1. Read state:
```bash
LAST=$(python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" deep_scan_state.json --query .last_completed 2>/dev/null)
STATUS=$(python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" deep_scan_state.json --query .status 2>/dev/null)
[ -z "$LAST" ] || [ "$LAST" = "null" ] && LAST=0
```

2. **If `LAST == 0` or `STATUS == "completed"`** → no interrupted run. Proceed as fresh:
   - Set `SCAN_MODE=full`, `START_STEP=1`, `RESUME_ACTION=fresh`.
   - Initialize state, then persist the run depth + scan mode:
     ```bash
     python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" init
     python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" save-run-context --depth "$DEPTH" --scan-mode "$SCAN_MODE"
     ```

3. **Otherwise** (`LAST > 0` and `STATUS == "in_progress"`) → an interrupted run exists. Figure out which step stopped it and where enrichment state stands:
   ```bash
   ENRICH_DONE=$(python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" enrich_state.json --query '.done|length' 2>/dev/null)
   [ -z "$ENRICH_DONE" ] || [ "$ENRICH_DONE" = "null" ] && ENRICH_DONE=0
   ```
   Build a human-readable label for the last completed step:
   | LAST | step_name |
   |---|---|
   | 1 | scanner |
   | 2 | read accumulated knowledge |
   | 3 | Wave 1 analytical agents |
   | 4 | Wave 1 merge |
   | 5 | Wave 2 reasoning agents (Design/Risk/Overview) |
   | 6 | AI rule synthesis |
   | 7 | Intent Layer |
   | 8 | Cleanup |
   | 9 | Drift detection |

   Ask the user how to proceed — {{>ask_user}}:
   - **question:** (build dynamically) `"A previous deep-scan stopped after Step {LAST} ({step_name})."` — and if `ENRICH_DONE > 0`, append `" The Intent Layer got {ENRICH_DONE} folders in before stopping."` — then `"What do you want to do?"`
   - **header:** "Resume"
   - **multiSelect:** false
   - **options** (exactly these two labels):
     1. label `Resume` — description `Continue from Step {LAST+1}. Preserves all completed work, including any partial Intent Layer batches. Recommended.`
     2. label `Fresh start` — description `Discard all progress and restart from Step 1. Erases the interrupted blueprint, Wave 1 outputs, and the partial Intent Layer state. Use only if the codebase changed significantly.`

   Map the answer:
   - `Resume` → Set `START_STEP = LAST + 1`, `RESUME_ACTION=resume`. Skip `init`. Print `"Resuming from Step {START_STEP}."`.
   - `Fresh start` → Reset everything and start over:
     ```bash
     python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" init
     python3 .archie/intent_layer.py reset-state "$PROJECT_ROOT"
     rm -f .archie/tmp/archie_enrichment_${PROJECT_NAME}_*.json .archie/tmp/archie_intent_prompt_${PROJECT_NAME}_*.txt
     ```
     `reset-state` wipes both `.archie/enrich_state.json` and the `.archie/enrichments/` directory — no `rm -rf` needed in the slash-command layer (keeps the command inside the default Bash permission allowlist so this runs prompt-free).
     Set `SCAN_MODE=full`, `START_STEP=1`, `RESUME_ACTION=fresh`. Print `"Starting fresh. Previous progress discarded."`. Then persist the run depth + scan mode:
     ```bash
     python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" save-run-context --depth "$DEPTH" --scan-mode "$SCAN_MODE"
     ```

4. Regardless of branch above, `RESUME_ACTION` is now set. It gates the Resume Prelude (below) and the Step 7 delta (passes `RESUME_INTENT` to the Intent Layer).

**For every step below:**
- If the step number < START_STEP, skip it entirely.
- If SCAN_MODE is not set, it defaults to "full" (all existing behavior unchanged).
- **Do NOT ask the user any questions during Steps 1–10. Do NOT offer to skip, reduce scope, or present alternatives for any step. Execute every step fully as documented.** This rule applies ONLY to Steps 1–10. It does NOT apply to Phase 0 / Activation: the scope prompt (Step C) and Intent Layer prompt (Step E) in `scope_resolution.md` are mandatory decision gates and MUST still be asked — see below.


## Activation — read these before running any step

Before executing any step, Read these files in order. They establish the
conventions and Phase 0 variables (`SCOPE`, `WORKSPACES`, `MONOREPO_TYPE`,
`PROJECT_ROOT`, `PROJECT_NAME`) that every step assumes are in place.

All paths below are relative to the project root (your cwd). The fragments
live alongside this orchestrator under `{{WORKFLOW_ROOT}}/deep-scan/`.

1. `{{WORKFLOW_ROOT}}/deep-scan/fragments/telemetry-conventions.md` — telemetry mark / finish / write contract used by every step.
2. `{{WORKFLOW_ROOT}}/deep-scan/fragments/compact-resume-contract.md` — how the pipeline survives `/compact` mid-run via `.archie/deep_scan_state.json`.
3. **If `RESUME_ACTION=resume`:** `{{WORKFLOW_ROOT}}/deep-scan/fragments/resume-prelude.md` — rehydrates shell variables from persisted state.
4. `{{WORKFLOW_ROOT}}/_shared/scope_resolution.md` — Phase 0 scope resolution. Establishes `PROJECT_ROOT`, `PROJECT_NAME`, `SCOPE`, `WORKSPACES`, `MONOREPO_TYPE`.

## Step-by-step routing

Before starting any Step N, Read the file in the "Load this file" column.
The router does not contain step content — each step is a self-contained file.
If `START_STEP > N` (the Preamble decided to skip earlier steps), do not Read or run those steps.

| Step | What it does | Load this file before starting |
|---|---|---|
| 1 | Run the scanner | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-1-scanner.md` |
| 2 | Read accumulated knowledge from prior runs | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-2-read-scan.md` |
| 3 | Wave 1 — spawn parallel analytical agents | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-3-wave1/orchestration.md` |
| 4 | Save & merge Wave 1 output | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-4-merge.md` |
| 5 | Wave 2 — reasoning agents: Design · Risk · Overview ({{REASONING_MODEL}}, parallel) | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-5-wave2-reasoning.md` |
| 6 | AI rule synthesis | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-6-rule-synthesis.md` |
| 7 | Intent Layer — per-folder CLAUDE.md | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-7-intent-layer.md` |
| 8 | Cleanup | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-8-cleanup.md` |
| 9 | Drift detection & architectural assessment | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-9-drift.md` |
| 10 | Final telemetry flush | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-10-telemetry.md` |

Step 3's `orchestration.md` in turn references four sub-agent prompt files plus a shared `grounding-rules.md` (all under `{{WORKFLOW_ROOT}}/deep-scan/steps/step-3-wave1/`) — read those as the orchestration instructs.

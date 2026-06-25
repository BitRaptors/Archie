# Automated Sync — Handoff & Reference

**Status:** Implemented on branch `feature/automated-sync` (10 commits, 33 tests passing, whole-branch review clean). Not yet merged.
**Audience:** Anyone maintaining, extending, reviewing, or debugging Archie's sync automation.
**Scope:** This document is self-contained. You do not need any other note to understand, operate, or extend this feature.

---

## 1. What this is, in one paragraph

Archie keeps a **Living Blueprint** (`.archie/blueprint.json`) and a per-folder **intent layer** (`*/CLAUDE.md`) that describe what the codebase currently *is*. Keeping those snapshots current historically required the developer to remember to run `/archie-sync`. This feature makes that maintenance **self-propelling**: background hooks quietly accumulate two durable signals as you work — how much code has changed (*churn*) and the agent's *plans* — and at natural boundaries (end of an agent turn, or a `git commit`) the system **nudges** the agent to run `/archie-sync`. The sync command itself is enriched to consume those signals so the record is richer and survives context loss. Critically, the actual reconciliation into the blueprint and any contract changes **stay agent-mediated** — nothing is silently rewritten.

---

## 2. Why it exists (the problem)

- **Snapshots drift.** Between syncs, the blueprint and intent layer fall behind the code. The longer the gap, the more reconstruction is needed and the lower the fidelity.
- **The valuable signal is ephemeral.** The reasoning behind a change ("we now filter background refresh errors so they don't trigger the purchase dialog") lives in the live agent session. Once context is cleared or compacted, it can only be lossily reconstructed from a diff. The same is true of plans: rich statements of intent that never get committed and vanish when the session ends.
- **Manual sync is easy to forget**, and forgetting is invisible until the drift is large.

The design goal: capture the perishable signals *while they exist*, and prompt for reconciliation at the right moments — without taking the reasoning step away from the agent.

---

## 3. Core design principles

These constrain every part of the implementation. Preserve them when extending.

1. **The agent is the source of truth, not the filesystem.** Only the live agent knows *why* the code changed. Hooks cannot reason; they can only measure cheap mechanical facts and *prompt the agent to act*.
2. **A hook is an alarm clock, not a detector.** A hook fires on an event boundary and surfaces a nudge. It never decides what to record.
3. **Trigger on "considerable work," not "foldable work."** The nudge fires on accumulated change volume or a captured plan — not on whether something is mechanically foldable. This deliberately includes the case where the only output is a *rule or decision worth recording* (which is never auto-applied; see #5).
4. **Plans are durable intent.** A plan is the richest source of decisions/pitfalls/rules and the bridge that lets intent survive context loss. Capture it at the moment it's produced or it's gone.
5. **The fold stays deliberate.** Descriptive facts ("what the code is now") may be reconciled by the agent into the blueprint. **Advisory claims** (decisions, pitfalls, rules, guidelines — the "contract") are recorded as *staged amendments* and surface for explicit acceptance. The contract never moves as a silent side-effect.
6. **Ride existing rails.** Every hook touchpoint piggybacks on a hook registration Archie already installs for both supported CLIs. The feature introduces **no new integration mechanism**, only new payloads on proven events (the single exception is documented in §10).
7. **Never crash, never block (except one deliberate nudge).** Hooks are best-effort: guard on a missing baseline, suppress errors, exit 0. The only intentional non-zero exit is the session-stop nudge.

---

## 4. What the developer experiences

| Phase | What happens | Visible? |
|---|---|---|
| Just installed | Hooks are registered but **dormant** — every hook bails early until `.archie/blueprint.json` exists. | No change |
| After `/archie-deep-scan` (baseline) | Signals begin accruing. | No change yet |
| While editing | Each edit bumps a churn counter; each plan (if plan mode is used) is saved. Sub-second, output-suppressed. | **Invisible** |
| End of an agent turn, once **churn ≥ threshold** OR an unconsumed plan exists | The agent is nudged (see message below) to run `/archie-sync` before stopping. Declinable. | **Yes — the main signal** |
| `git commit` while churn is over threshold | A one-line stderr reminder; the commit still proceeds. | Yes — advisory |
| `/archie-sync` runs | Reads the captured plans + churn, produces a richer record, then clears those signals. | Yes |

Session-stop nudge text (verbatim):
```
Archie: considerable work since last sync (N files / M lines changed[, K captured plan(s)]).
Run /archie-sync to record any behavior change, impact, or rule, then stop.
Decline if nothing is worth recording.
```

Commit advisory text (verbatim):
```
Archie: substantial unrecorded work — consider /archie-sync after this commit.
```

What does **not** change: no editing slowdown; small work (below threshold, no plan) stays silent; the blueprint is never silently rewritten; nothing is committed for you.

---

## 5. Components

All new program logic lives in the standalone, zero-dependency `archie/standalone/sync.py` (Python 3.9+, stdlib only). The hooks are thin shell shims that pipe a tool-call envelope to a `sync.py` subcommand. This keeps testable logic in Python and inherits permission allowlisting for free (see §7).

### 5.1 `sync.py` subcommands (all take the repo root as the **second** positional arg)

| Command | Reads | Writes / Returns | Purpose |
|---|---|---|---|
| `plan-capture <root>` | ExitPlanMode envelope on **stdin** (`tool_input.plan`) | `.archie/tmp/plans/plan_<UTC>.md`; prints `{"ok":true,"captured":bool[,"path":…]}` | Persist a plan as durable intent. No-op (`captured:false`) if no plan text. |
| `plan-list <root>` | `.archie/tmp/plans/` | `{"ok":true,"plans":[relpath,…]}` | List unconsumed plans (for the sync skill + stop nudge). |
| `plan-consume <root>` | `.archie/tmp/plans/` | Moves `plan_*.md` → `.archie/tmp/plans/consumed/`; prints `{"ok":true,"consumed":[name,…]}` | Retire plans after a sync so they don't double-count. |
| `churn-bump <root>` | edit envelope on **stdin** | Updates `.archie/tmp/churn.json`; prints the summary | Accumulate one edit's volume (files touched, edit count, line count). |
| `churn-status <root>` | `.archie/tmp/churn.json`, `.archie/config.json` | `{"ok":true,"files":N,"edits":N,"lines":N,"threshold_files":N,"threshold_lines":N,"crossed":bool}` | Report churn + whether the threshold is crossed. |
| `churn-reset <root>` | — | Deletes `.archie/tmp/churn.json`; prints `{"ok":true,"reset":true}` | Zero the counter after a sync. |

Cross-CLI envelope normalization inside `churn-bump`/`plan-capture`:
- Tool name accepted: `Write`, `Edit`, `MultiEdit` (Claude) **or** `apply_patch` (Codex).
- File path: `tool_input.file_path` **or** `tool_input.path`.
- Content: `tool_input.content` **or** `tool_input.new_string` (MultiEdit/apply_patch `edits[]` arrays are joined).
- Plan text: `tool_input.plan` (identical on both CLIs).

All subcommands tolerate empty/garbage stdin and missing files (never raise).

### 5.2 Hooks (`archie/assets/hook_scripts/`)

| Script | Event / matcher | Blocking | Change | Behavior |
|---|---|---|---|---|
| `churn-track.sh` | `post-tool-use` / `Edit\|Write\|MultiEdit` | No | **New** | Pipes the edit envelope to `churn-bump`. Always exits 0. |
| `post-plan-review.sh` | `post-tool-use` / `ExitPlanMode` | No | **Modified** | Tees the plan envelope to `plan-capture` (one added line), *then* runs the existing contract-gating (`align_check.py`, `arch_review.py`) unchanged. |
| `stop.sh` | `stop` | No* | **Modified** | After existing per-turn cleanup, reads `churn-status` + `plan-list`; if churn crossed **or** a plan exists, prints the nudge to stderr and **exits 2** (the cross-CLI block/continue signal). Otherwise exits 0 silently. |
| `pre-commit-review.sh` | `pre-tool-use` / `Bash` (git commit) | Yes (existing) | **Modified** | After commit detection, prints a non-blocking advisory if churn is crossed. **Does not alter the exit code** and leaves the existing `align_check.py` commit-gating intact. |

\* `stop.sh` is registered non-blocking, but uses `exit 2` as a deliberate, declinable nudge.

Every hook guards on `[ -f "$PROJECT_ROOT/.archie/blueprint.json" ]` and exits 0 early if absent — so nothing fires before a baseline exists.

### 5.3 Manifest registration (`archie/manifest_data.py`)

Exactly **one** new entry in `HOOKS`:
```python
HookDef("post-tool-use", "Edit|Write|MultiEdit", ".archie/hooks/churn-track.sh", blocking=False),
```
The other three hook scripts were already registered; only their bodies changed. `sync.py` is already in `install._STANDALONE_SCRIPTS`, so the new subcommands ship and get permission rules automatically (§7). No connector code was changed.

### 5.4 `/archie-sync` enrichment (`archie/assets/workflow/sync/SKILL.md`)

Two additions to the canonical skill body (rendered per-CLI at install):
- **Step 1b — Pull durable signals:** run `plan-list` + `churn-status`; read each captured plan; **seed advisory claims** from plan decisions/pitfalls/rules; **ground descriptive claims** while treating plan intent as a *candidate to verify against the actual code*, not ground truth; scope the review by the churn file list.
- **Consume on success (in Step 5):** after applying, run `plan-consume` + `churn-reset` so the next cycle starts clean.

### 5.5 Runtime artifacts (created under the auto-gitignored `.archie/tmp/`)

```
.archie/tmp/plans/plan_<UTC>.md          # captured, unconsumed plans
.archie/tmp/plans/consumed/plan_<UTC>.md # plans retired by a sync
.archie/tmp/churn.json                    # { "files": [...], "edits": N, "lines": N }
```
`.archie/tmp/` ships with a self-ignoring `.gitignore` (`*`), so none of these are ever committed.

---

## 6. End-to-end data flow (the loop)

```
ExitPlanMode ──► post-plan-review.sh ──► sync.py plan-capture ──► .archie/tmp/plans/plan_*.md
                                          (then existing contract gating, unchanged)

edit (Edit/Write/apply_patch) ──► churn-track.sh ──► sync.py churn-bump ──► .archie/tmp/churn.json

           ┌──────────────── end of agent turn ────────────────┐
           │  stop.sh: churn-status + plan-list                 │
           │  crossed OR plans>0 ?                               │
           │      yes → stderr nudge + exit 2 (run /archie-sync) │
           │      no  → exit 0 (silent)                          │
           └────────────────────────────────────────────────────┘

git commit ──► pre-commit-review.sh ──► (if crossed) advisory to stderr, commit proceeds

/archie-sync ──► reads plan-list + churn-status (Step 1b)
            ──► agent records (descriptive → eligible/fold; advisory → staged amendment)
            ──► agent reconciles eligible facts into blueprint + intent layer (the fold)
            ──► plan-consume + churn-reset  ◄── closes the loop; next cycle starts clean
```

Invariant to preserve: every signal that is **produced** (`plan-capture`, `churn-bump`) is **consumed** exactly once (`plan-consume`, `churn-reset`) on a successful sync. Do not add a producer without a consumer, or a nudge condition that reads state nothing resets.

---

## 7. Cross-CLI behavior (both supported CLIs)

The feature targets both supported agent CLIs. The connectors map Archie's abstract hook events to each CLI's native mechanism; **no per-CLI feature code was needed.**

| Touchpoint | First CLI (native edit = `Edit`/`Write`/`MultiEdit`, plan mode) | Second CLI (native edit = `apply_patch`) | Notes |
|---|---|---|---|
| Churn tracking | `PostToolUse` / `Edit\|Write\|MultiEdit` | `PostToolUse` / `^apply_patch$` (matcher auto-translated) | Lands on the **same rail as the existing `post-lint.sh`** hook. |
| Plan capture | `PostToolUse` / `ExitPlanMode` | `PostToolUse` / `^ExitPlanMode$` | Lands on the **same rail as the existing `post-plan-review.sh`** hook. |
| Stop nudge | `Stop` event, `exit 2` blocks-and-continues | `Stop` event, `exit 2` | The one genuinely new bet (see §10). |
| `/archie-sync` command | `.claude/commands/archie-sync.md` → rendered `.archie/workflow/<cli>/sync/SKILL.md` | `.agents/skills/archie-sync/SKILL.md` → same rendered body | Command install verified for both. |

**Install wiring (empirically verified):** running the installer for both targets produces:
- a `PostToolUse` / `Edit|Write|MultiEdit` entry pointing at `churn-track.sh` in the first CLI's settings, and a `PostToolUse` / `^apply_patch$` entry in the second CLI's `hooks.json`;
- `churn-track.sh` shipped + executable under `.archie/hooks/`;
- the updated `sync.py` with all six subcommands under `.archie/`;
- the `/archie-sync` command rendered for both CLIs with the new signal steps present;
- permission rules covering `python3 .archie/sync.py <subcommand>` on both CLIs (generated automatically from `_STANDALONE_SCRIPTS`).

**Why no allowlist edit was needed:** hook scripts are copied by `glob("*.sh")` over `assets/hook_scripts/`, and standalone scripts + their permission rules are driven by `_STANDALONE_SCRIPTS` (which already contains `sync.py`). Adding a hook script or a `sync.py` subcommand requires no install/permission bookkeeping.

---

## 8. Configuration / tuning

`.archie/config.json` (project-level, optional):

| Key | Default | Effect |
|---|---|---|
| `churn_threshold_files` | `8` | Distinct files changed since last sync that trips "crossed". |
| `churn_threshold_lines` | `150` | Added lines since last sync that trips "crossed". |

`crossed = (files ≥ threshold_files) OR (lines ≥ threshold_lines)`. Missing/malformed config falls back to defaults. Lower thresholds = more frequent nudges.

Behavioral knobs that are currently fixed (change in code if needed):
- Session-stop nudge: **on**, exit-2 (declinable).
- Commit advisory: **on**, non-blocking. (Make it stronger only via deliberate change to `pre-commit-review.sh` — it must never become a hard commit block by default.)
- Plan retention: plans are **moved** to `consumed/`, never deleted (auditable).

---

## 9. Activation & timing rules

- **Dormant until baseline.** No hook does anything until `.archie/blueprint.json` exists (i.e., after `/archie-deep-scan`). This is intentional — there is nothing to keep current before a baseline.
- **Nudge cadence.** The `Stop` event can fire at the end of each agent turn. The nudge only triggers once churn is over threshold (or a plan is pending), so small/idle turns stay silent. After a successful sync (`churn-reset`), it goes quiet again.
- **Declining does not reset churn.** If the user/agent declines and keeps working while still over threshold, the nudge will recur at the next stop. This is intentional persistence. If it feels naggy for a given workflow, raise the thresholds (§8). A future "snooze" knob is a reasonable enhancement (§12).

---

## 10. Verification status & the one open item

**Verified empirically (no live agent session required):**
- Installer wiring for both CLIs (generated settings/hooks/command files inspected).
- The full script-layer loop on *installed* artifacts: plan captured → churn accrued (tested with the second CLI's `apply_patch`/`path`/`new_string` envelope shape) → stop nudge printed + `exit 2` → `plan-consume` + `churn-reset` clear state.
- 33 automated tests pass (`tests/test_sync.py`, `tests/test_automated_sync_hooks.py`).

**Cannot be verified locally (requires a live run):** whether each CLI's *runtime* actually emits the events and honors `exit 2` on `Stop`. This is the same class of assumption Archie's pre-existing hooks already rely on — with one new element:

> **OPEN ITEM — confirm on a real second-CLI session:** the session-stop nudge is the **first** Archie hook to rely on `exit 2` at the `Stop` event (the previous `stop.sh` only did cleanup and exited 0). On the first CLI this block-and-continue behavior is the documented contract. On the second CLI it is unverified. **Fallback if unsupported:** the nudge text is still printed to stderr (visible), so the only thing lost is the automatic continue — it degrades to a visible reminder, never a silent failure.

Plan capture additionally depends on the second CLI having a plan-mode / `ExitPlanMode` concept at all. If it does not, plan capture is simply **dormant** there (graceful) while the churn + nudge loop continues to work; this is a pre-existing Archie assumption, not introduced here.

---

## 11. Testing

Run:
```bash
python3 -m pytest tests/test_sync.py tests/test_automated_sync_hooks.py -v
```

Coverage:
- `tests/test_sync.py` — the six subcommands: plan capture (incl. no-plan no-op), list/consume lifecycle, churn accumulation across **both** CLI envelope shapes, threshold + config override, reset.
- `tests/test_automated_sync_hooks.py` — `churn-track.sh` updating the counter via subprocess; the `churn-track` `HookDef` registration + the second CLI's matcher mapping; the `stop.sh` nudge (exit 2 + stderr when crossed; silent exit 0 when clean); a presence check that the sync skill references all four new subcommands.

Note: hook tests exercise the scripts and Python directly with synthetic envelopes — they prove the machinery works *given* the events fire. They do not (cannot) prove the CLI runtime fires them; that's the §10 open item.

Test infrastructure note: importing the installable `archie` package transitively pulls `tomllib` (Python 3.11+). On 3.9/3.10 the tests import the standalone module / submodules via a stub-package technique (registering a minimal `archie` package in `sys.modules` with `__path__` set) to avoid that import. Follow the same pattern if you add tests that touch `manifest_data` or `connectors`.

---

## 12. Extending / maintaining

- **Add a tuning knob:** read it in `_churn_thresholds` (or a sibling helper) from `.archie/config.json` with a safe default; document it in §8.
- **Add a new signal:** create a `sync.py <verb>` producer + a consumer, and wire a thin hook shim. Register the hook with one `HookDef`. Update §6's produce→consume invariant. Do **not** ship a producer without a consumer.
- **Change the nudge trigger:** edit `stop.sh` (and/or `pre-commit-review.sh`). Keep exit-code discipline: only `stop.sh` may exit non-zero, and the commit advisory must never change the commit's exit code.
- **Possible enhancements (not built):** a "snooze N turns" knob for the stop nudge; weighting churn by file type; an optional stronger (blocking) commit gate behind a config flag; a per-edit line-count that sums each `edits[]` entry independently rather than joining (current MultiEdit count is an approximation used only as a threshold heuristic).

---

## 13. Known limitations

- **Stop nudge recurs while over threshold** if declined (see §9). Intentional; tune via thresholds.
- **MultiEdit/apply_patch line count is approximate** — `edits[]` `new_string`s are joined with newlines before counting, which can drift by a small amount when individual edits contain newlines. It feeds a threshold only, so exactness isn't required.
- **Plan capture requires a plan-mode concept** on the running CLI (see §10).
- **Everything is post-baseline** — no signal accrues until `/archie-deep-scan` has produced a blueprint.

---

## 14. File & commit inventory

**Files added:**
- `archie/assets/hook_scripts/churn-track.sh`
- `tests/test_automated_sync_hooks.py`
- `docs/automated-sync.md` (this document)

**Files modified:**
- `archie/standalone/sync.py` — six new subcommands + helpers + dispatch + usage text.
- `archie/manifest_data.py` — one new `HookDef`.
- `archie/assets/hook_scripts/post-plan-review.sh` — plan-capture tee.
- `archie/assets/hook_scripts/stop.sh` — nudge.
- `archie/assets/hook_scripts/pre-commit-review.sh` — advisory.
- `archie/assets/workflow/sync/SKILL.md` — Step 1b + consume-on-success.
- `tests/test_sync.py` — subcommand tests.

**Commits on `feature/automated-sync`** (oldest → newest):
1. `feat(sync): add plan-capture/list/consume subcommands for durable plan intent`
2. `feat(sync): add churn-bump/status/reset subcommands (cross-CLI edit volume)`
3. `feat(hooks): track edit churn on post-tool-use for Claude and Codex`
4. `feat(hooks): persist ExitPlanMode plan as durable intent for sync`
5. `feat(hooks): nudge /archie-sync at session stop when work is unrecorded`
6. `feat(sync-skill): read captured plans + churn, consume them on success`
7. `feat(hooks): optional advisory to run /archie-sync at commit time`
8. `fix(hooks): make pre-commit advisory exit-code-safe and drop redundant guard`
9. `docs(sync): list plan-* and churn-* subcommands in usage text`
10. `docs(sync): drop misleading [--json] from plan-list/churn-status usage`

---

## 15. Glossary

- **Living Blueprint** — `.archie/blueprint.json`; the descriptive snapshot of what the code currently is.
- **Intent layer** — per-folder `CLAUDE.md` snapshots of local patterns/conventions.
- **Descriptive claim** — a statement about what the code now does (behavior/structure/dataflow/data/tech/reference). May be folded into the blueprint.
- **Advisory claim** — a decision/pitfall/rule/guideline (the "contract"). Always *staged* for deliberate acceptance; never auto-folded.
- **Churn** — accumulated edit volume (files + lines) since the last sync.
- **Fold** — the agent's reconciliation of eligible descriptive claims into the blueprint/intent layer.
- **Nudge** — the declinable session-stop prompt (and commit advisory) to run `/archie-sync`.

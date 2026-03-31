# Deep Scan Resume Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `--from N` and `--continue` flags to `/archie-deep-scan`, renumber steps 1-9, track state in `.archie/deep_scan_state.json`.

**Architecture:** The slash command (archie-deep-scan.md) gets a preamble that parses arguments, checks state, and determines the starting step. A new `update_state` subcommand in intent_layer.py handles state file writes (avoids inline python). Each step calls it on completion.

**Tech Stack:** Python 3.9+ (zero deps), Claude Code slash command markdown

---

### Task 1: Add `update-state` subcommand to intent_layer.py

**Files:**
- Modify: `archie/standalone/intent_layer.py`

**Step 1: Add state management functions**

Add near the existing state tracking code (around line 240 where `_STATE_FILE` is defined). New subcommand `deep-scan-state` with actions: `init`, `complete-step`, `read`.

```python
_DEEP_SCAN_STATE_FILE = "deep_scan_state.json"

def cmd_deep_scan_state(root: Path, action: str, step: int | None = None):
    """Manage deep scan state for resume capability."""
    state_path = root / ".archie" / _DEEP_SCAN_STATE_FILE

    if action == "init":
        # Fresh run — reset state
        from datetime import datetime, timezone
        state = {
            "completed_steps": [],
            "last_completed": 0,
            "status": "in_progress",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2))
        print("Deep scan state initialized", file=sys.stderr)

    elif action == "complete-step":
        if step is None:
            print("Error: --step required for complete-step", file=sys.stderr)
            sys.exit(1)
        try:
            state = json.loads(state_path.read_text())
        except (OSError, json.JSONDecodeError):
            state = {"completed_steps": [], "last_completed": 0, "status": "in_progress"}
        if step not in state["completed_steps"]:
            state["completed_steps"].append(step)
            state["completed_steps"].sort()
        state["last_completed"] = step
        state["status"] = "completed" if step == 9 else "in_progress"
        state_path.write_text(json.dumps(state, indent=2))
        print(f"Step {step} completed", file=sys.stderr)

    elif action == "read":
        if state_path.exists():
            print(state_path.read_text())
        else:
            print(json.dumps({"completed_steps": [], "last_completed": 0, "status": "none"}))

    elif action == "check-prereqs":
        # Validate prerequisites for a given step
        if step is None:
            print("Error: --step required", file=sys.stderr)
            sys.exit(1)
        prereqs = {
            1: [],
            2: [".archie/scan.json"],
            3: [".archie/scan.json"],
            4: [],  # /tmp files — can't reliably check
            5: [".archie/blueprint_raw.json"],
            6: [".archie/blueprint.json"],
            7: [".archie/blueprint.json", ".archie/scan.json"],
            8: [],
            9: [".archie/blueprint.json"],
        }
        missing = []
        for p in prereqs.get(step, []):
            if not (root / p).exists():
                missing.append(p)
        if missing:
            print(json.dumps({"ok": False, "missing": missing}))
            sys.exit(1)
        else:
            print(json.dumps({"ok": True}))
```

**Step 2: Add CLI routing**

In the `if __name__` section, add:
```python
elif subcmd == "deep-scan-state":
    action = sys.argv[3] if len(sys.argv) > 3 else ""
    step = int(sys.argv[4]) if len(sys.argv) > 4 else None
    cmd_deep_scan_state(root, action, step)
```

**Step 3: Verify**

```bash
python3 archie/standalone/intent_layer.py deep-scan-state /tmp init 2>&1
python3 archie/standalone/intent_layer.py deep-scan-state /tmp complete-step 3 2>&1
python3 archie/standalone/intent_layer.py deep-scan-state /tmp read
```
Expected: state file created, step 3 marked, JSON output shows completed_steps: [3].

**Step 4: Commit**

```bash
git add archie/standalone/intent_layer.py
git commit -m "feat: add deep-scan-state subcommand for resume tracking"
```

---

### Task 2: Rewrite archie-deep-scan.md with renumbered steps and resume preamble

**Files:**
- Modify: `.claude/commands/archie-deep-scan.md`

**Step 1: Add resume preamble**

Replace the current opening (lines 1-8) with a preamble that handles arguments:

```markdown
# Archie Deep Scan — Comprehensive Architecture Baseline

Run a comprehensive architecture analysis. Produces full blueprint, per-folder CLAUDE.md, rules, and health metrics.

**Modes:**
- `/archie-deep-scan` — fresh run from step 1
- `/archie-deep-scan --from N` — resume from step N (runs N through 9)
- `/archie-deep-scan --continue` — resume from where the last run stopped

## Preamble: Determine starting step

Check the ARGUMENTS field for flags:

**If `--from N` is present:**
1. Set START_STEP = N
2. Validate prerequisites:
```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" check-prereqs N
```
3. If prerequisites missing, tell the user which artifacts are needed and which earlier step to run.
4. Initialize state with steps 1 through N-1 marked as completed.

**If `--continue` is present:**
1. Read state:
```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" read
```
2. If status is "none" or "completed": "No interrupted run found. Starting fresh from step 1."
3. If status is "in_progress": Set START_STEP = last_completed + 1. Print "Resuming from step {START_STEP}."

**If no flags (default):**
1. Set START_STEP = 1
2. Initialize fresh state:
```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" init
```

**After each step completes, update state:**
```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step N
```

**Skip steps before START_STEP.** For each step: if step number < START_STEP, skip it entirely.
```

**Step 2: Renumber all steps**

Rename the existing steps:
- Old "Step 1: Detect sub-projects" + "Step 2: Project selection" → move to Preamble (not numbered)
- Old "Step 3: Run the scanner" → **Step 1: Run the scanner**
- Old "Step 4: Read scan results" → **Step 2: Read scan results**
- Old "Step 5: Spawn parallel agents" → **Step 3: Spawn parallel analysis agents**
- Old "Step 6: Save and merge" → **Step 4: Save Wave 1 output and merge**
- Old "Step 7: Reasoning agent" → **Step 5: Reasoning agent**
- Old "Step 7.5: Rules synthesis" → **Step 6: Rules synthesis**
- Old "Step 8: Intent layer" → **Step 7: Intent layer**
- Old "Step 9: Cleanup" → **Step 8: Cleanup**
- Old "Step 10: Drift + assessment" → **Step 9: Drift detection and assessment**

**Step 3: Add state update after each step**

After each step's content, add:
```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step N
```

And before each step, add a skip check:
```
**If START_STEP > N, skip this step.**
```

**Step 4: Add /tmp warning for step 4**

Before Step 4 (Merge), if resuming via --from or --continue, add:
```
**WARNING if resuming:** Step 4 depends on Wave 1 agent output files in /tmp/. These may not survive a system reboot. If merge fails with missing files, re-run from step 3: `/archie-deep-scan --from 3`
```

**Step 5: Commit**

```bash
git add -f .claude/commands/archie-deep-scan.md
git commit -m "feat: /archie-deep-scan --from N and --continue support, renumbered steps 1-9"
```

---

### Task 3: Sync and verify

**Files:**
- Copy: `archie/standalone/intent_layer.py` → `npm-package/assets/`
- Copy: `.claude/commands/archie-deep-scan.md` → `npm-package/assets/`

**Step 1: Sync**

```bash
cp archie/standalone/intent_layer.py npm-package/assets/intent_layer.py
cp .claude/commands/archie-deep-scan.md npm-package/assets/archie-deep-scan.md
```

**Step 2: Verify sync**

```bash
python3 scripts/verify_sync.py
```

**Step 3: Test state management**

```bash
# Init
python3 archie/standalone/intent_layer.py deep-scan-state /tmp init
# Complete steps 1-4
for i in 1 2 3 4; do
  python3 archie/standalone/intent_layer.py deep-scan-state /tmp complete-step $i
done
# Read — should show steps 1-4 completed, status in_progress
python3 archie/standalone/intent_layer.py deep-scan-state /tmp read
# Check prereqs for step 5 (will fail since no blueprint_raw.json in /tmp)
python3 archie/standalone/intent_layer.py deep-scan-state /tmp check-prereqs 5 || echo "Expected: missing prereqs"
```

**Step 4: Install to BabyWeather.Android**

```bash
node npm-package/bin/archie.mjs /path/to/BabyWeather.Android
```

Verify the deep-scan-state subcommand works from the installed location.

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: sync deep scan resume capability, verified"
```

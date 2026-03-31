# Deep Scan Resume/Restart Design

## Problem

`/archie-deep-scan` takes 15-20 minutes. If it crashes at step 5, the user must re-run from scratch — wasting the 10 minutes spent on steps 1-4. Also, if a specific step produced bad output (e.g., rules are wrong), there's no way to re-run just that step and continue.

## Design

### Three invocation modes

- **`/archie-deep-scan`** — fresh run from step 1. Always.
- **`/archie-deep-scan --from 5`** — start from step 5, run 5→6→7→8→9. Assumes steps 1-4 artifacts exist.
- **`/archie-deep-scan --continue`** — reads `.archie/deep_scan_state.json`, resumes from the step after the last completed one.

### Renumbered steps (sequential, no gaps)

| Step | Name | Produces |
|------|------|----------|
| 1 | Scanner | scan.json, skeletons.json |
| 2 | Read scan results | (in-memory batch plan) |
| 3 | Wave 1 agents | /tmp agent output files |
| 4 | Merge | blueprint_raw.json, observations.json |
| 5 | Reasoning agent | blueprint.json (via finalize) |
| 6 | Rules synthesis | rules.json |
| 7 | Intent layer | per-folder CLAUDE.md files |
| 8 | Cleanup | (removes /tmp files) |
| 9 | Drift + assessment | drift_report.json, health_history.json |

Monorepo detection is a preamble (not numbered) — it determines PROJECT_ROOT then the pipeline runs.

### State file: `.archie/deep_scan_state.json`

```json
{
  "completed_steps": [1, 2, 3, 4],
  "last_completed": 4,
  "status": "in_progress",
  "started_at": "2026-03-31T14:00:00Z"
}
```

- Written at the start of a run (status: "in_progress", completed_steps: [])
- Updated after each step completes (append to completed_steps, update last_completed)
- Step 9 completing sets status: "completed"

### Behavior

**Fresh run (`/archie-deep-scan`):**
1. Reset state file to empty
2. Run steps 1→9
3. Each step updates state on completion

**From specific step (`/archie-deep-scan --from 5`):**
1. Validate that prerequisite artifacts exist (e.g., blueprint_raw.json for step 5)
2. If missing: error "Step 5 requires blueprint_raw.json from step 4. Run steps 1-4 first or use --from 4."
3. If present: reset state to show steps 1-(N-1) as completed, run N→9

**Continue (`/archie-deep-scan --continue`):**
1. Read `.archie/deep_scan_state.json`
2. If doesn't exist or status=="completed": "No interrupted run found. Starting fresh." → run from step 1
3. If status=="in_progress": resume from `last_completed + 1`

### Prerequisite validation

Each step has required artifacts:

| Step | Requires |
|------|----------|
| 1 | nothing |
| 2 | scan.json |
| 3 | scan.json |
| 4 | /tmp agent output files (fragile — may not survive reboot) |
| 5 | blueprint_raw.json |
| 6 | blueprint.json |
| 7 | blueprint.json, scan.json, enrich_batches.json |
| 8 | nothing (cleanup) |
| 9 | blueprint.json |

Note: Step 4 depends on /tmp files which don't survive reboots. If resuming from step 4, warn: "Wave 1 agent outputs in /tmp may be gone. Re-run from step 3 if merge fails."

### Implementation

Changes to `archie-deep-scan.md`:
- Add preamble that reads ARGUMENTS for `--from N` or `--continue`
- Add state file read/write at start and after each step
- Add prerequisite checks before each step
- Renumber all steps from 1 to 9

New: state file write is a simple inline python call after each step:
```bash
python3 -c "
import json
from datetime import datetime, timezone
state_path = '$PROJECT_ROOT/.archie/deep_scan_state.json'
try: state = json.load(open(state_path))
except: state = {'completed_steps': [], 'status': 'in_progress', 'started_at': datetime.now(timezone.utc).isoformat()}
state['completed_steps'].append(N)
state['last_completed'] = N
state['status'] = 'completed' if N == 9 else 'in_progress'
open(state_path, 'w').write(json.dumps(state, indent=2))
"
```

Or better: add a `update-state` subcommand to an existing script to avoid inline python.

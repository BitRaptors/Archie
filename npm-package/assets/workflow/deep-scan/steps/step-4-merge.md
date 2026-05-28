## Step 4: Save Wave 1 output and merge

**Telemetry:**
```bash
python3 .archie/telemetry.py mark "$PROJECT_ROOT" deep-scan merge
TELEMETRY_STEP4_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

**If START_STEP > 4, skip this step.**

### If SCAN_MODE = "incremental":

The single incremental agent's output was saved to `.archie/tmp/archie_incremental_$PROJECT_NAME.json` in Step 3. Patch the existing blueprint:

```bash
python3 .archie/merge.py "$PROJECT_ROOT" --patch .archie/tmp/archie_incremental_$PROJECT_NAME.json
```

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 3
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 4
```

### If SCAN_MODE = "full" (default):

Step 4 is a **consumer step**: Step 3 already assigned each Wave 1 sub-agent
its output path and appended the output contract to its prompt before
dispatch. Each sub-agent has now written its file under `.archie/tmp/`.

**Expected files** (skip UI Layer when `frontend_ratio < 0.20`; skip Data when `has_persistence_signal == false`):

- `.archie/tmp/archie_sub1_$PROJECT_NAME.json` (Structure)
- `.archie/tmp/archie_sub2_$PROJECT_NAME.json` (Patterns)
- `.archie/tmp/archie_sub3_$PROJECT_NAME.json` (Technology)
- `.archie/tmp/archie_sub4_$PROJECT_NAME.json` (UI Layer, optional)
- `.archie/tmp/archie_sub5_$PROJECT_NAME.json` (Data, optional)

**If resuming via `--from` or `--continue`:** `.archie/tmp/` is workspace-relative
so the files normally survive reboots, but an interrupted or `--from 4` run
may not have them. If any expected file is missing, re-run from Step 3:
`{{COMMAND_PREFIX}}archie-deep-scan --from 3`. Report which files were
missing — do NOT attempt to re-extract output from a subagent's transcript.

Merge the files that exist:

```bash
python3 .archie/merge.py "$PROJECT_ROOT" .archie/tmp/archie_sub1_$PROJECT_NAME.json .archie/tmp/archie_sub2_$PROJECT_NAME.json .archie/tmp/archie_sub3_$PROJECT_NAME.json .archie/tmp/archie_sub4_$PROJECT_NAME.json .archie/tmp/archie_sub5_$PROJECT_NAME.json
```

`merge.py` warns and skips files that weren't produced (skipped agents) — listing all five paths unconditionally keeps the command stable across full / frontend-only / backend-only repos.

This saves `$PROJECT_ROOT/.archie/blueprint_raw.json` (raw merged data). Verify the output shows non-zero component/section counts. If it says "0 sections, 0 components", the merge failed — check the agent output files.

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 4
```


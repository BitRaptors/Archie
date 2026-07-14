## Step 9: Finalize — health metrics, telemetry, baseline

**Telemetry:**
```bash
python3 .archie/telemetry.py mark "$PROJECT_ROOT" deep-scan finalize
TELEMETRY_STEP9_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

**If START_STEP > 9, skip this step.**

### Phase 1: Health measurement

```bash
python3 .archie/measure_health.py "$PROJECT_ROOT" > "$PROJECT_ROOT/.archie/health.json" 2>/dev/null
```

Save health scores to history for trending:

```bash
python3 .archie/measure_health.py "$PROJECT_ROOT" --append-history --scan-type deep
```

### Phase 2: Write telemetry

Each prior step persisted its start timestamp to `.archie/telemetry/_current_run.json` via `telemetry.py mark` — so the final writer reads entirely from disk (no shell variables required, no /tmp timing file to assemble). This is what makes mid-run `/compact` safe: even if the orchestrator's conversation was compacted, every step's timing is on disk.

If the Intent Layer was skipped (INTENT_LAYER=no), mark it so explicitly:

```bash
if [ "$INTENT_LAYER" = "no" ]; then
  python3 .archie/telemetry.py extra "$PROJECT_ROOT" intent_layer skipped=true
fi
```

Then flush the in-flight file into the final `.archie/telemetry/deep-scan_<timestamp>.json`:

```bash
python3 .archie/telemetry.py finish "$PROJECT_ROOT"
python3 .archie/telemetry.py write  "$PROJECT_ROOT"
```

`write` auto-closes any still-open step with `now`, emits the final timestamped JSON, then deletes `_current_run.json` so the next deep-scan starts fresh. If telemetry fails for any reason, do not abort — telemetry is informational only.

**Legacy fallback:** the old `.archie/tmp/archie_timing.json` + `telemetry.py <root> --command … --timing-file …` invocation still works for any downstream tool that expects it, but the disk-persisted flow above is the compaction-safe canonical path.

### Phase 3: Mark the run complete

Deliberately AFTER the telemetry flush: `complete-step 9` flips the run's `status` to `completed`, which tells `--continue` there is nothing left to resume. If the run is interrupted before this point, status stays `in_progress` and `--continue` simply re-runs Step 9 — every command in this step is idempotent.

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 9
```

Save baseline marker for future incremental runs (use "full" or "incremental" based on SCAN_MODE):
```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" save-baseline SCAN_MODE
```
(Replace SCAN_MODE with the actual mode — "full" or "incremental")

### Phase 4: Closing summary

Present a short wrap-up to the user — a receipt, not a report (10 lines or fewer). State what the scan produced, with counts read via the allowlisted inspect commands (NEVER inline Python):

```bash
python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" blueprint.json --query '.components.components|length'
python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" rules.json --query '.rules|length'
python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" findings.json --query '.findings|length'
python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" enrich_state.json --query '.done|length'
python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" health.json --query .erosion
```

Cover: components discovered, enforcement rules generated, per-folder CLAUDE.md files created (the `enrich_state.json` query above — do not rely on remembering Step 7, a compact may have intervened), findings tracked in `.archie/findings.json`, one health line (erosion score from `health.json`). Point the user at `{{COMMAND_PREFIX}}archie-viewer` for the full picture and `{{COMMAND_PREFIX}}archie-share` to publish it. If a count is unavailable (file missing, query returns nothing), omit that line rather than guessing.

End with: **"Archie is now active. Architecture rules will be enforced on every code change. Run `{{COMMAND_PREFIX}}archie-deep-scan --incremental` after code changes to update the architecture analysis."**

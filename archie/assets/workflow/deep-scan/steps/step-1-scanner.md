## Step 1: Run the scanner

**Telemetry:** persist the step start to disk (compaction-safe), then keep the shell var for readability:
```bash
python3 .archie/telemetry.py mark "$PROJECT_ROOT" deep-scan scan
TELEMETRY_STEP1_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

**If START_STEP > 1, skip this step.**

```bash
# Re-derive DEPTH from persisted state (set in Phase 0) so this step does not
# depend on the shell variable surviving across steps / a mid-run compaction.
DEPTH=$(python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" deep_scan_state.json --query .run_context.depth 2>/dev/null)
COMP_FLAG=""; [ "$DEPTH" = "comprehensive" ] && COMP_FLAG="--comprehensive"
python3 .archie/scanner.py "$PROJECT_ROOT" $COMP_FLAG
python3 .archie/detect_cycles.py "$PROJECT_ROOT" --full 2>/dev/null
```

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 1
```


## Step 8: Clean up

**Telemetry:**
```bash
python3 .archie/telemetry.py mark "$PROJECT_ROOT" deep-scan cleanup
TELEMETRY_STEP8_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

**If START_STEP > 8, skip this step.**

```bash
rm -f .archie/tmp/archie_sub*_$PROJECT_NAME.json .archie/tmp/archie_rules_$PROJECT_NAME.json .archie/tmp/archie_intent_prompt_${PROJECT_NAME}_*.txt .archie/tmp/archie_enrichment_${PROJECT_NAME}_*.json
```

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 8
```

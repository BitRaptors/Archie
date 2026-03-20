# Archie Refresh — Update Architecture Analysis

Refresh the architecture blueprint after code changes.

## Prerequisites

`.archie/blueprint.json` must exist (run `/archie-init` first).

## Process

### Step 1: Run local refresh

```bash
archie refresh
```

This rescans the file tree, updates hashes, and reports what changed since the last analysis.

### Step 2: Check if deep refresh is needed

If the refresh output shows new files, deleted files, or modified files that could affect architecture (new modules, changed entry points, new dependencies), proceed to Step 3.

If only minor changes (typo fixes, content changes within existing patterns), no deep refresh needed.

### Step 3: Deep refresh (if needed)

```bash
archie refresh --deep
```

This generates `.archie/refresh_prompt.md` targeting only the changed files.

Read `.archie/refresh_prompt.md` and spawn a single Sonnet subagent to analyze the changes:

```
Use the Agent tool with subagent_type: "Explore" and model: "sonnet".
Pass the content of .archie/refresh_prompt.md as the prompt.
```

### Step 4: Merge updates

Take the subagent's JSON output and merge it into the existing blueprint:

```bash
source .venv/bin/activate && python3 -c "
import json, sys
sys.path.insert(0, '.')
from archie.coordinator.merger import merge_subagent_outputs, save_blueprint, load_blueprint
from archie.engine.models import RawScan

scan = RawScan.model_validate_json(open('.archie/scan.json').read())
existing = load_blueprint('.')
new_output = {}  # Paste subagent JSON here

merged = merge_subagent_outputs([existing, new_output], scan)
save_blueprint('.', merged)
print('Blueprint updated')
"
```

### Step 5: Re-render and update rules

```bash
source .venv/bin/activate && python3 -c "
import json, sys
sys.path.insert(0, '.')
from archie.renderer.render import render_outputs
from archie.rules.extractor import extract_rules, save_rules

bp = json.loads(open('.archie/blueprint.json').read())
render_outputs(bp, '.')
rules = extract_rules(bp)
save_rules('.', rules)
print('Outputs re-rendered, rules updated')
"
```

### Step 6: Verify

```bash
archie status
```

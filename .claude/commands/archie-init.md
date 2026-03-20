# Archie Init — Full Architecture Analysis

Analyze this repository's architecture and generate enforcement outputs.

## Prerequisites

Run `archie init . --local-only` first if `.archie/scan.json` doesn't exist. This produces the local scan and subagent prompts.

## Process

### Step 1: Read the local scan

Read `.archie/scan.json` to understand the repository structure, frameworks, dependencies, and token counts.

### Step 2: Read subagent prompts

Read all `.archie/subagent_*_prompt.md` files. Each contains instructions for analyzing a specific group of files and filling specific blueprint sections.

### Step 3: Spawn subagents

For each subagent prompt file, spawn a Sonnet subagent using the Agent tool with `subagent_type: "Explore"` and `model: "sonnet"`. Pass the full prompt content. Each subagent should:

1. Read all assigned files listed in the prompt
2. Analyze architecture patterns, decisions, conventions
3. Search the web for any unfamiliar libraries to understand their purpose
4. Return a JSON object with the blueprint sections filled in

Spawn all subagents in parallel (single message with multiple Agent calls).

### Step 4: Merge results

After all subagents complete, run this Python script to merge their outputs:

```bash
source .venv/bin/activate && python3 -c "
import json, sys
sys.path.insert(0, '.')
from archie.coordinator.merger import merge_subagent_outputs, save_blueprint
from archie.engine.models import RawScan

scan = RawScan.model_validate_json(open('.archie/scan.json').read())
outputs = []  # Collect subagent JSON outputs here
# Parse each subagent's JSON output and append to outputs list

merged = merge_subagent_outputs(outputs, scan, repo_name='$ARGUMENTS')
save_blueprint('.', merged)
print(f'Blueprint saved with {len(merged.get(\"components\", {}).get(\"components\", []))} components')
"
```

Alternatively, merge the subagent outputs manually by combining their JSON sections into a single blueprint dict, then save it to `.archie/blueprint.json`.

### Step 5: Render outputs

```bash
source .venv/bin/activate && python3 -c "
import json, sys
sys.path.insert(0, '.')
from archie.renderer.render import render_outputs
bp = json.loads(open('.archie/blueprint.json').read())
files = render_outputs(bp, '.')
print(f'Generated {len(files)} output files:')
for f in sorted(files): print(f'  {f}')
"
```

### Step 6: Extract rules and update hooks

```bash
source .venv/bin/activate && python3 -c "
import json, sys
sys.path.insert(0, '.')
from archie.rules.extractor import extract_rules, save_rules
bp = json.loads(open('.archie/blueprint.json').read())
rules = extract_rules(bp)
save_rules('.', rules)
print(f'Extracted {len(rules)} enforcement rules')
"
```

### Step 7: Verify

Run `archie status` to see the blueprint status and enforcement summary.

## Output

After completion, the following files will exist:
- `.archie/blueprint.json` — structured architecture blueprint
- `.archie/rules.json` — enforcement rules
- `CLAUDE.md` — root architecture context
- `AGENTS.md` — multi-agent guidance
- `.claude/rules/` — Claude Code rule files
- `.cursor/rules/` — Cursor rule files
- `.claude/hooks/` — enforcement hooks (from init --local-only)

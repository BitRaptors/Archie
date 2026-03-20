# Archie Init — Full Architecture Analysis

Analyze this repository's architecture. Zero dependencies — works with any language.

## Step 1: Download and run the scanner

```bash
# Download the standalone scripts (zero dependencies, Python 3.11+ stdlib only)
curl -fsSL https://raw.githubusercontent.com/BitRaptors/Archie/main/archie/standalone/scanner.py -o /tmp/archie_scanner.py
curl -fsSL https://raw.githubusercontent.com/BitRaptors/Archie/main/archie/standalone/renderer.py -o .archie/renderer.py

# Run the scanner on the current repo
python3 /tmp/archie_scanner.py "$PWD"
```

If curl fails (no internet or private repo), create the scripts inline — read `archie/standalone/scanner.py` and `archie/standalone/renderer.py` from the Archie repo and save them to `/tmp/archie_scanner.py` and `.archie/renderer.py`, then run the scanner.

If python3 is not available, tell the user to install Python 3.11+.

After running, `.archie/scan.json` will exist with the full local scan.

## Step 2: Read the scan results

Read `.archie/scan.json`. Note:
- Total files and token count
- Detected frameworks
- Number of dependencies
- Top-level directories (these become subagent groups)

## Step 3: Plan subagent groups

Group files by top-level directory. Each group should be under ~150,000 estimated tokens. For small repos (under 150k total), use a single group.

## Step 4: Spawn subagents

For each file group, spawn a Sonnet subagent using the Agent tool:
- `subagent_type: "Explore"`
- `model: "sonnet"`

Each subagent prompt should include:
1. The list of files to read (from the group)
2. Detected frameworks and dependencies (from scan.json)
3. Instructions to return a JSON object with these blueprint sections:

```
components, architecture_rules, decisions, communication, technology,
frontend, deployment, implementation_guidelines, developer_recipes,
development_rules, pitfalls, quick_reference, architecture_diagram
```

For each section, the subagent should:
- Read all assigned files
- Focus on what AI CANNOT infer from individual files: cross-file relationships, implicit contracts, architecture decisions, integration patterns
- Return valid JSON

**Spawn ALL subagents in parallel** (single message with multiple Agent calls).

## Step 5: Merge results

After all subagents complete, merge their JSON outputs into a single blueprint:
- Combine component lists (deduplicate by name)
- Merge architecture rules (concatenate)
- Merge technology stacks (deduplicate by name)
- For overlapping sections, prefer the subagent with more detail
- Add metadata: `{ "meta": { "repository": "<repo name>", "analyzed_at": "<ISO timestamp>", "schema_version": "2.0.0" } }`

Save the merged blueprint to `.archie/blueprint.json`.

## Step 6: Generate outputs

Run the standalone renderer to generate CLAUDE.md, AGENTS.md, and all rule files:

```bash
# Generate all output files (CLAUDE.md, AGENTS.md, .claude/rules/, .cursor/rules/)
python3 .archie/renderer.py "$PWD"

# Generate per-folder CLAUDE.md files for directory-level context
python3 .archie/intent_layer.py "$PWD"
```

This produces 16+ files: lean root CLAUDE.md, comprehensive AGENTS.md, 7 topic-split rule files under `.claude/rules/` and `.cursor/rules/`, plus per-folder CLAUDE.md files in significant directories.

## Step 7: Generate enforcement rules

```bash
python3 -c "
import json, re, os

bp = json.loads(open('.archie/blueprint.json').read())
rules = []

# File placement rules
for i, r in enumerate(bp.get('architecture_rules', {}).get('file_placement_rules', [])):
    rules.append({
        'id': f'placement-{i}',
        'check': 'file_placement',
        'description': r.get('description', ''),
        'allowed_dirs': [r.get('location', '')] if r.get('location') else [],
        'severity': 'warn',
        'keywords': [w for w in re.findall(r'[a-zA-Z]{3,}', r.get('description', '').lower()) if w not in {'the','and','for','are','this','that','with','from','use','must'}],
    })

# Naming conventions
for i, n in enumerate(bp.get('architecture_rules', {}).get('naming_conventions', [])):
    rules.append({
        'id': f'naming-{i}',
        'check': 'naming',
        'description': f'{n.get(\"target\", \"\")}: {n.get(\"convention\", \"\")}',
        'severity': 'warn',
        'keywords': [n.get('target', ''), n.get('convention', '')],
    })

os.makedirs('.archie', exist_ok=True)
with open('.archie/rules.json', 'w') as f:
    json.dump({'rules': rules}, f, indent=2)
print(f'Extracted {len(rules)} enforcement rules')
"
```

## Step 8: Install enforcement hooks

```bash
mkdir -p .claude/hooks

# inject-context.sh — injects architecture rules into every prompt
cat > .claude/hooks/inject-context.sh << 'HOOKEOF'
#!/usr/bin/env bash
set -euo pipefail
RULES_FILE="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")/.archie/rules.json"
[ ! -f "$RULES_FILE" ] && exit 0
USER_INPUT=$(cat)
PROMPT=$(echo "$USER_INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('user_prompt', ''))
except: print('')
" 2>/dev/null || echo "")
[ -z "$PROMPT" ] && exit 0
python3 << PYEOF
import json
prompt = '''$PROMPT'''.lower()
try:
    rules = json.load(open('$RULES_FILE')).get('rules', [])
except: exit(0)
matched = [r for r in rules if any(k.lower() in prompt for k in r.get('keywords', []))]
matched += [r for r in rules if r.get('severity') == 'error' and r not in matched]
if matched:
    print('[Archie] Architecture rules:')
    for r in matched[:10]:
        print(f'  - {r.get("description", r.get("id", ""))}')
PYEOF
HOOKEOF
chmod +x .claude/hooks/inject-context.sh

# pre-validate.sh — checks code changes against rules
cat > .claude/hooks/pre-validate.sh << 'HOOKEOF'
#!/usr/bin/env bash
set -euo pipefail
RULES_FILE="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")/.archie/rules.json"
[ ! -f "$RULES_FILE" ] && exit 0
TOOL_INPUT=$(cat)
FILE_PATH=$(echo "$TOOL_INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input',{}).get('file_path', d.get('tool_input',{}).get('path','')))
except: print('')
" 2>/dev/null || echo "")
TOOL_NAME=$(echo "$TOOL_INPUT" | python3 -c "
import sys, json
try: print(json.load(sys.stdin).get('tool_name',''))
except: print('')
" 2>/dev/null || echo "")
case "$TOOL_NAME" in Write|Edit|MultiEdit) ;; *) exit 0 ;; esac
[ -z "$FILE_PATH" ] && exit 0
python3 -c "
import json, sys, os, re
fp = '$FILE_PATH'
try: rules = json.load(open('$RULES_FILE')).get('rules', [])
except: sys.exit(0)
errors = []
for r in rules:
    if r.get('check') == 'file_placement':
        dirs = r.get('allowed_dirs', [])
        if dirs and not any(fp.startswith(d) for d in dirs):
            if r.get('severity') == 'error': errors.append(r)
            else: print(f'[Archie] Warning: {r.get(\"description\",\"\")}')
    elif r.get('check') == 'naming':
        pat = r.get('pattern', '')
        if pat and not re.match(pat, os.path.basename(fp)):
            if r.get('severity') == 'error': errors.append(r)
            else: print(f'[Archie] Warning: {r.get(\"description\",\"\")}')
for e in errors:
    print(f'[Archie] BLOCKED: {e.get(\"description\",\"\")}')
    print('  Ask the user to approve this override.')
if errors: sys.exit(2)
" 2>/dev/null || exit 0
HOOKEOF
chmod +x .claude/hooks/pre-validate.sh

echo "Hooks installed"
```

Then register them in `.claude/settings.local.json`:

```bash
python3 -c "
import json, os
path = '.claude/settings.local.json'
settings = {}
if os.path.exists(path):
    try: settings = json.loads(open(path).read())
    except: pass
settings['hooks'] = {
    'UserPromptSubmit': [{'matcher': '', 'hooks': [{'type': 'command', 'command': '.claude/hooks/inject-context.sh'}]}],
    'PreToolUse': [{'matcher': 'Write|Edit|MultiEdit', 'hooks': [{'type': 'command', 'command': '.claude/hooks/pre-validate.sh'}]}],
}
with open(path, 'w') as f:
    json.dump(settings, f, indent=2)
print('Hooks registered in .claude/settings.local.json')
"
```

## Step 9: Summary

Print a summary of everything that was generated:
- `.archie/scan.json` — local scan results
- `.archie/blueprint.json` — architecture blueprint
- `.archie/rules.json` — enforcement rules
- `CLAUDE.md` — lean root architecture context (points to rule files)
- `AGENTS.md` — comprehensive 12-section agent guidance
- `.claude/rules/` — 7 topic-split rule files (architecture, patterns, recipes, pitfalls, dev-rules, mcp-tools, frontend)
- `.cursor/rules/` — same rules with Cursor YAML frontmatter
- per-folder `CLAUDE.md` — directory-level context files
- `.claude/hooks/` — enforcement hooks
- `.claude/settings.local.json` — hook registration

Tell the user: "Archie is now active. Architecture rules will be enforced on every code change in this Claude Code session."

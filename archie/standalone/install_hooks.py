#!/usr/bin/env python3
"""Archie standalone hook installer — creates enforcement hooks and registers them.

Run: python3 install_hooks.py /path/to/repo
Output: Creates .claude/hooks/ scripts and updates .claude/settings.local.json

Zero dependencies beyond Python 3.11+ stdlib.
"""
import json
import os
import stat
import sys
from pathlib import Path


INJECT_CONTEXT_HOOK = r'''#!/usr/bin/env bash
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
prompt_lower = """$PROMPT""".lower()
try:
    rules = json.load(open("$RULES_FILE")).get("rules", [])
except: exit(0)
matched = [r for r in rules if any(k.lower() in prompt_lower for k in r.get("keywords", []))]
matched += [r for r in rules if r.get("severity") == "error" and r not in matched]
if matched:
    print("[Archie] Architecture rules:")
    for r in matched[:10]:
        print(f"  - {r.get('description', r.get('id', ''))}")
PYEOF
'''

PRE_VALIDATE_HOOK = r'''#!/usr/bin/env bash
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
'''


def install(project_root: Path) -> None:
    hook_dir = project_root / ".claude" / "hooks"
    hook_dir.mkdir(parents=True, exist_ok=True)

    # Write hook scripts
    for name, content in [("inject-context.sh", INJECT_CONTEXT_HOOK), ("pre-validate.sh", PRE_VALIDATE_HOOK)]:
        path = hook_dir / name
        path.write_text(content)
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # Update settings.local.json
    settings_path = project_root / ".claude" / "settings.local.json"
    settings: dict = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    settings["hooks"] = {
        "UserPromptSubmit": [
            {"matcher": "", "hooks": [{"type": "command", "command": ".claude/hooks/inject-context.sh"}]}
        ],
        "PreToolUse": [
            {"matcher": "Write|Edit|MultiEdit", "hooks": [{"type": "command", "command": ".claude/hooks/pre-validate.sh"}]}
        ],
    }

    settings_path.write_text(json.dumps(settings, indent=2) + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 install_hooks.py /path/to/repo", file=sys.stderr)
        sys.exit(1)

    root = Path(sys.argv[1]).resolve()
    install(root)
    print("Installed .claude/hooks/inject-context.sh", file=sys.stderr)
    print("Installed .claude/hooks/pre-validate.sh", file=sys.stderr)
    print("Registered hooks in .claude/settings.local.json", file=sys.stderr)

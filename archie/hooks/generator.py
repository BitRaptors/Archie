"""Generate and install Claude Code hook scripts for architecture enforcement."""
from __future__ import annotations

import json
import stat
from pathlib import Path


def generate_hooks() -> dict[str, str]:
    """Return hook script contents keyed by filename."""
    return {
        "inject-context.sh": _inject_context_script(),
        "pre-validate.sh": _pre_validate_script(),
    }


_POST_COMMIT_BLOCK = """\
# Archie: auto-refresh local scan after commit
# Runs in background to avoid slowing down commits

if command -v archie >/dev/null 2>&1; then
    archie refresh >/dev/null 2>&1 &
fi
"""


def install_git_hook(project_root: Path) -> bool:
    """Install a git post-commit hook that runs ``archie refresh``.

    Returns True on success, False if *project_root* is not a git repository.
    The function is idempotent — calling it multiple times will not duplicate
    the archie block.
    """
    git_dir = project_root / ".git"
    if not git_dir.is_dir():
        return False

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    post_commit = hooks_dir / "post-commit"

    if post_commit.exists():
        existing = post_commit.read_text()
        # Already installed — skip.
        if "archie refresh" in existing:
            return True
        # Append to existing hook.
        if not existing.endswith("\n"):
            existing += "\n"
        post_commit.write_text(existing + "\n" + _POST_COMMIT_BLOCK)
    else:
        post_commit.write_text("#!/bin/sh\n" + _POST_COMMIT_BLOCK)

    # Make executable.
    post_commit.chmod(
        post_commit.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )
    return True


def install_hooks(project_root: Path) -> None:
    """Write hook scripts and register them in .claude/settings.local.json."""
    hooks_dir = project_root / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    hooks = generate_hooks()
    for filename, content in hooks.items():
        path = hooks_dir / filename
        path.write_text(content)
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # Update settings.local.json (merge, don't overwrite)
    settings_path = project_root / ".claude" / "settings.local.json"
    if settings_path.exists():
        settings = json.loads(settings_path.read_text())
    else:
        settings = {}

    settings["hooks"] = {
        "UserPromptSubmit": [
            {
                "matcher": "",
                "hooks": [{"type": "command", "command": ".claude/hooks/inject-context.sh"}],
            }
        ],
        "PreToolUse": [
            {
                "matcher": "Write|Edit|MultiEdit",
                "hooks": [{"type": "command", "command": ".claude/hooks/pre-validate.sh"}],
            }
        ],
    }

    settings_path.write_text(json.dumps(settings, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Script generators
# ---------------------------------------------------------------------------

def _inject_context_script() -> str:
    # Use a regular string (not raw triple-quoted) to avoid triple-quote
    # conflicts with embedded shell/python code.
    lines = [
        "#!/usr/bin/env bash",
        "# Claude Code hook: UserPromptSubmit — inject relevant architecture rules.",
        "set -euo pipefail",
        "",
        'RULES_FILE=".archie/rules.json"',
        "",
        "# Fail open: if rules file is missing, exit silently.",
        'if [ ! -f "$RULES_FILE" ]; then',
        "    exit 0",
        "fi",
        "",
        "# Read stdin (Claude sends JSON with session info).",
        'INPUT="$(cat)"',
        "",
        "# Extract user prompt using python3.",
        'USER_PROMPT="$(echo "$INPUT" | python3 -c "',
        "import sys, json",
        "data = json.load(sys.stdin)",
        "print(data.get(\'data\', {}).get(\'user_prompt\', \'\'))",
        '" 2>/dev/null || echo "")"',
        "",
        'if [ -z "$USER_PROMPT" ]; then',
        "    exit 0",
        "fi",
        "",
        "# Match rules against prompt keywords and collect severity=error rules.",
        'MATCHED="$(python3 << \'PYEOF\'',
        "import json, sys, os",
        "",
        "rules_file = os.environ.get(\"ARCHIE_RULES\", \".archie/rules.json\")",
        "user_prompt = os.environ.get(\"ARCHIE_PROMPT\", \"\")",
        "",
        "with open(rules_file) as f:",
        "    rules = json.load(f)",
        "",
        "prompt = user_prompt.lower()",
        "",
        "matched = []",
        "for rule in rules:",
        "    if rule.get(\"severity\") == \"error\":",
        "        matched.append(rule)",
        "        continue",
        "    keywords = rule.get(\"keywords\", [])",
        "    rule_text = (rule.get(\"id\", \"\") + \" \" + rule.get(\"description\", \"\")).lower()",
        "    tokens = rule_text.split()",
        "    found = False",
        "    for kw in keywords:",
        "        if kw.lower() in prompt:",
        "            matched.append(rule)",
        "            found = True",
        "            break",
        "    if not found:",
        "        for token in tokens:",
        "            if len(token) > 3 and token in prompt:",
        "                matched.append(rule)",
        "                break",
        "",
        "if matched:",
        "    print(\"[Archie] Relevant architecture rules:\")",
        "    seen = set()",
        "    for r in matched:",
        "        rid = r.get(\"id\", \"unknown\")",
        "        if rid not in seen:",
        "            seen.add(rid)",
        "            sev = r.get(\"severity\", \"warning\")",
        "            desc = r.get(\"description\", \"\")",
        "            print(f\"  [{sev}] {rid}: {desc}\")",
        "PYEOF",
        ')"',
        "",
        'if [ -n "$MATCHED" ]; then',
        '    echo "$MATCHED"',
        "fi",
        "",
        "exit 0",
    ]
    return "\n".join(lines) + "\n"


def _pre_validate_script() -> str:
    return r'''#!/usr/bin/env bash
# Claude Code hook: PreToolUse — validate file placement and naming rules.
set -euo pipefail

RULES_FILE=".archie/rules.json"
STATS_FILE=".archie/stats.jsonl"

# Fail open: if rules file is missing, exit silently.
if [ ! -f "$RULES_FILE" ]; then
    exit 0
fi

# Read stdin (Claude sends JSON with tool call info).
INPUT="$(cat)"

# Extract tool_name and file_path using python3.
eval "$(echo "$INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
tool_name = data.get('tool_name', '')
file_path = data.get('tool_input', {}).get('file_path', '')
# Shell-safe output
print(f'TOOL_NAME=\"{tool_name}\"')
print(f'FILE_PATH=\"{file_path}\"')
" 2>/dev/null || echo 'TOOL_NAME=""; FILE_PATH=""')"

# Only check Write, Edit, MultiEdit tools.
case "$TOOL_NAME" in
    Write|Edit|MultiEdit) ;;
    *) exit 0 ;;
esac

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Validate against rules.
RESULT="$(python3 -c "
import json, sys, re, os, datetime

rules_file = '$RULES_FILE'
file_path = '$FILE_PATH'
tool_name = '$TOOL_NAME'
stats_file = '$STATS_FILE'

with open(rules_file) as f:
    rules = json.load(f)

filename = os.path.basename(file_path)
violations = []

for rule in rules:
    rule_type = rule.get('check') or rule.get('type', '')
    severity = rule.get('severity', 'warning')
    rid = rule.get('id', 'unknown')
    desc = rule.get('description', '')

    # Check file_placement rules.
    if rule_type == 'file_placement':
        allowed_dirs = rule.get('allowed_dirs', [])
        if allowed_dirs:
            matched = False
            for d in allowed_dirs:
                if file_path.startswith(d):
                    matched = True
                    break
            if not matched:
                violations.append((severity, rid, desc, file_path))

    # Check naming rules.
    if rule_type == 'naming':
        pattern = rule.get('pattern', '')
        if pattern:
            if not re.search(pattern, filename):
                violations.append((severity, rid, desc, file_path))

# Log to stats file.
os.makedirs(os.path.dirname(stats_file) if os.path.dirname(stats_file) else '.', exist_ok=True)
for sev, rid, desc, fp in violations:
    entry = {
        'timestamp': datetime.datetime.utcnow().isoformat(),
        'rule_id': rid,
        'severity': sev,
        'file_path': fp,
        'tool': tool_name,
    }
    with open(stats_file, 'a') as f:
        f.write(json.dumps(entry) + '\n')

# Determine exit.
has_error = any(s == 'error' for s, _, _, _ in violations)
messages = []
for sev, rid, desc, fp in violations:
    if sev == 'error':
        messages.append(f'[Archie BLOCKED] {rid}: {desc} (file: {fp}) — please ask the user before proceeding.')
    else:
        messages.append(f'[Archie WARNING] {rid}: {desc} (file: {fp})')

if messages:
    print('\n'.join(messages))

if has_error:
    sys.exit(2)
sys.exit(0)
" 2>/dev/null)"

EXIT_CODE=$?

if [ -n "$RESULT" ]; then
    echo "$RESULT"
fi

exit $EXIT_CODE
'''

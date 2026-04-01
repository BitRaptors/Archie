#!/usr/bin/env python3
"""Archie standalone hook installer — creates enforcement hooks and registers them.

Run: python3 install_hooks.py /path/to/repo
Output: Creates .claude/hooks/ scripts and updates .claude/settings.local.json

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path


PRE_VALIDATE_HOOK = r'''#!/usr/bin/env bash
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
RULES_FILE="$PROJECT_ROOT/.archie/rules.json"
[ ! -f "$RULES_FILE" ] && exit 0
TOOL_INPUT=$(cat || true)
[ -z "$TOOL_INPUT" ] && exit 0
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
# Skip files outside project root
case "$FILE_PATH" in "$PROJECT_ROOT"*) ;; /*) exit 0 ;; esac
# Get content being written
CONTENT=$(echo "$TOOL_INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    ti = d.get('tool_input', {})
    print(ti.get('content', '') or ti.get('new_string', ''))
except: print('')
" 2>/dev/null || echo "")
export _ARCHIE_FP="$FILE_PATH"
export _ARCHIE_ROOT="$PROJECT_ROOT"
export _ARCHIE_RULES="$RULES_FILE"
# Write content to temp file to avoid shell escaping issues
_ARCHIE_CONTENT_FILE=$(mktemp)
echo "$CONTENT" > "$_ARCHIE_CONTENT_FILE"
export _ARCHIE_CONTENT_FILE
trap "rm -f $_ARCHIE_CONTENT_FILE" EXIT
python3 << 'PYEOF'
import json, sys, os, re, fnmatch

fp = os.environ.get("_ARCHIE_FP", "")
rules_file = os.environ.get("_ARCHIE_RULES", "")
content_file = os.environ.get("_ARCHIE_CONTENT_FILE", "")
content = ""
if content_file:
    try:
        content = open(content_file).read()
    except:
        pass

if not fp or not rules_file:
    sys.exit(0)

rules = []
for rpath in [rules_file, rules_file.replace("rules.json", "platform_rules.json")]:
    try:
        data = json.load(open(rpath))
        rules.extend(data.get("rules", []) if isinstance(data, dict) else data)
    except: pass

# Make file path relative to project root
project_root = os.environ.get("_ARCHIE_ROOT", ".")
rel_path = fp
if fp.startswith(project_root):
    rel_path = fp[len(project_root):].lstrip("/")
filename = os.path.basename(fp)

errors = []
warns = []

for r in rules:
    check = r.get("check", "")
    desc = r.get("description", "")
    sev = r.get("severity", "warn")
    bucket = errors if sev == "error" else warns

    if check == "forbidden_import":
        applies_to = r.get("applies_to", "")
        if applies_to and rel_path.startswith(applies_to) and content:
            for pat in r.get("forbidden_patterns", []):
                try:
                    if re.search(pat, content):
                        bucket.append(desc)
                        break
                except re.error:
                    pass

    elif check == "required_pattern":
        file_pat = r.get("file_pattern", "")
        if file_pat and fnmatch.fnmatch(filename, file_pat) and content:
            required = r.get("required_in_content", [])
            if required and not any(req in content for req in required):
                bucket.append(desc)

    elif check == "forbidden_content":
        applies_to = r.get("applies_to", "")
        if (not applies_to or rel_path.startswith(applies_to)) and content:
            for pat in r.get("forbidden_patterns", []):
                try:
                    if re.search(pat, content):
                        bucket.append(desc)
                        break
                except re.error:
                    pass

    elif check == "architectural_constraint":
        file_pat = r.get("file_pattern", "")
        if file_pat and fnmatch.fnmatch(filename, file_pat) and content:
            for pat in r.get("forbidden_patterns", []):
                try:
                    if re.search(pat, content):
                        bucket.append(desc)
                        break
                except re.error:
                    pass

    elif check == "file_naming":
        applies_to = r.get("applies_to", "")
        file_pat = r.get("file_pattern", "")
        if applies_to and fnmatch.fnmatch(rel_path, applies_to):
            if file_pat:
                try:
                    if not re.match(file_pat, filename):
                        bucket.append(desc)
                except re.error:
                    pass

for w in warns[:5]:
    print(f"[Archie] Warning: {w}")
for e in errors:
    print(f"[Archie] BLOCKED: {e}")
if errors:
    sys.exit(2)
PYEOF
'''


POST_PLAN_HOOK = r'''#!/usr/bin/env bash
# Archie post-plan review — triggers architectural review after plan approval
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
[ ! -f "$PROJECT_ROOT/.archie/blueprint.json" ] && exit 0
python3 "$PROJECT_ROOT/.archie/arch_review.py" plan "$PROJECT_ROOT"
'''

PRE_COMMIT_HOOK = r'''#!/usr/bin/env bash
# Archie pre-commit review — triggers architectural review before git commit
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
[ ! -f "$PROJECT_ROOT/.archie/blueprint.json" ] && exit 0
# Only fire for git commit commands
TOOL_INPUT=$(cat || true)
COMMAND=$(echo "$TOOL_INPUT" | python3 -c "
import sys, json
try: print(json.load(sys.stdin).get('tool_input',{}).get('command',''))
except: print('')
" 2>/dev/null || echo "")
case "$COMMAND" in *git\ commit*|*git\ -C*commit*) ;; *) exit 0 ;; esac
python3 "$PROJECT_ROOT/.archie/arch_review.py" diff "$PROJECT_ROOT"
'''


def _add_hook(hooks_list: list, matcher: str, command: str):
    """Add a hook entry if not already present."""
    if not any(
        h.get("matcher") == matcher
        and any(hh.get("command") == command for hh in h.get("hooks", []))
        for h in hooks_list
    ):
        hooks_list.append({
            "matcher": matcher,
            "hooks": [{"type": "command", "command": command}],
        })


def install(project_root: Path) -> None:
    hook_dir = project_root / ".claude" / "hooks"
    hook_dir.mkdir(parents=True, exist_ok=True)

    # Write hook scripts
    for name, content in [
        ("pre-validate.sh", PRE_VALIDATE_HOOK),
        ("post-plan-review.sh", POST_PLAN_HOOK),
        ("pre-commit-review.sh", PRE_COMMIT_HOOK),
    ]:
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

    # Merge hooks — preserve user's existing hooks, add ours
    hooks = settings.get("hooks", {})
    pre_tool = hooks.get("PreToolUse", [])
    post_tool = hooks.get("PostToolUse", [])

    _add_hook(pre_tool, "Write|Edit|MultiEdit", ".claude/hooks/pre-validate.sh")
    _add_hook(pre_tool, "Bash", ".claude/hooks/pre-commit-review.sh")
    _add_hook(post_tool, "ExitPlanMode", ".claude/hooks/post-plan-review.sh")

    hooks["PreToolUse"] = pre_tool
    hooks["PostToolUse"] = post_tool
    settings["hooks"] = hooks

    # Add permissions so /archie-init and /archie-refresh run without
    # interactive prompts.  Deny rules still take precedence.
    perms = settings.get("permissions", {})
    allow = set(perms.get("allow", []))
    archie_allow = [
        # Running archie scripts
        "Bash(python3 .archie/*.py *)",
        "Bash(python3 .archie/*.py)",
        "Bash(python3 -c *)",
        # Shell utilities Claude uses during orchestration
        "Bash(git *)",
        "Bash(test *)",
        "Bash(cp *)",
        "Bash(wc *)",
        "Bash(cat *)",
        "Bash(echo *)",
        "Bash(for *)",
        "Bash(mkdir *)",
        "Bash(date *)",
        "Bash(rm -f /tmp/archie_*)",
        # Temp files for agent output
        "Write(//tmp/archie_*)",
        "Read(//tmp/archie_*)",
        # Reading/writing archie data & generated files
        "Read(.archie/*)",
        "Read(.archie/**)",
        "Write(.archie/*)",
        "Write(.archie/**)",
        "Edit(.archie/*)",
        "Edit(.archie/**)",
        # Reading project source files for analysis (scan verifies findings)
        "Read(**)",
        # Per-folder CLAUDE.md (intent layer writes these)
        "Write(**/CLAUDE.md)",
        "Edit(**/CLAUDE.md)",
        # Subagent spawning (Wave 1, Wave 2, rules, intent layer)
        "Agent(*)",
    ]
    for entry in archie_allow:
        allow.add(entry)
    perms["allow"] = sorted(allow)
    settings["permissions"] = perms

    settings_path.write_text(json.dumps(settings, indent=2) + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 install_hooks.py /path/to/repo", file=sys.stderr)
        sys.exit(1)

    root = Path(sys.argv[1]).resolve()
    install(root)
    print("Installed .claude/hooks/pre-validate.sh", file=sys.stderr)
    print("Registered hooks in .claude/settings.local.json", file=sys.stderr)

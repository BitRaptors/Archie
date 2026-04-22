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
# Claude Code hook: PreToolUse — validate file placement, naming, and content rules.
set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
RULES_FILE="$PROJECT_ROOT/.archie/rules.json"
PLATFORM_RULES_FILE="$PROJECT_ROOT/.archie/platform_rules.json"
STATS_FILE="$PROJECT_ROOT/.archie/stats.jsonl"

# Fail open: if no rules at all, exit silently.
if [ ! -f "$RULES_FILE" ] && [ ! -f "$PLATFORM_RULES_FILE" ]; then
    exit 0
fi

INPUT="$(cat || true)"
[ -z "$INPUT" ] && exit 0

# Write tool JSON to a temp file so Python can parse it safely
# (shell escaping of `content` with backslashes/quotes is unreliable).
TOOL_JSON=$(mktemp)
printf '%s' "$INPUT" > "$TOOL_JSON"
export _ARCHIE_TOOL_JSON="$TOOL_JSON"
export _ARCHIE_ROOT="$PROJECT_ROOT"
export _ARCHIE_RULES="$RULES_FILE"
export _ARCHIE_PLATFORM_RULES="$PLATFORM_RULES_FILE"
export _ARCHIE_STATS="$STATS_FILE"
trap 'rm -f "$TOOL_JSON"' EXIT

python3 << 'PYEOF'
import json, sys, os, re, fnmatch, datetime

tool_json_file = os.environ.get("_ARCHIE_TOOL_JSON", "")
project_root = os.environ.get("_ARCHIE_ROOT", ".")
rules_file = os.environ.get("_ARCHIE_RULES", "")
platform_rules_file = os.environ.get("_ARCHIE_PLATFORM_RULES", "")
stats_file = os.environ.get("_ARCHIE_STATS", "")

try:
    with open(tool_json_file) as f:
        data = json.load(f)
except Exception:
    sys.exit(0)

tool_name = data.get("tool_name", "")
if tool_name not in ("Write", "Edit", "MultiEdit"):
    sys.exit(0)

tool_input = data.get("tool_input", {})
file_path = tool_input.get("file_path", "") or tool_input.get("path", "")
if not file_path:
    sys.exit(0)

# Skip absolute paths outside project root.
if file_path.startswith("/") and not file_path.startswith(project_root):
    sys.exit(0)

# Extract new content (Write.content, Edit.new_string, MultiEdit.edits[*].new_string).
content = tool_input.get("content", "") or tool_input.get("new_string", "")
if not content and tool_input.get("edits"):
    content = "\n".join(e.get("new_string", "") for e in tool_input["edits"])

# Load all rules from rules.json and platform_rules.json.
rules = []
for rpath in (rules_file, platform_rules_file):
    if not rpath or not os.path.isfile(rpath):
        continue
    try:
        loaded = json.load(open(rpath))
        rules.extend(loaded.get("rules", []) if isinstance(loaded, dict) else loaded)
    except Exception:
        pass

filename = os.path.basename(file_path)
rel_path = file_path
if file_path.startswith(project_root):
    rel_path = file_path[len(project_root):].lstrip("/")

def any_match(patterns, text):
    for p in patterns:
        try:
            if re.search(p, text):
                return True
        except re.error:
            continue
    return False

violations = []

for r in rules:
    check = r.get("check") or r.get("type", "")
    severity = r.get("severity", "warn")
    rid = r.get("id", "unknown")
    desc = r.get("description", "")

    matched = False
    if check == "file_placement":
        dirs = r.get("allowed_dirs", [])
        if dirs and not any(file_path.startswith(d) for d in dirs):
            matched = True

    elif check == "naming":
        pat = r.get("pattern", "")
        if pat and not re.search(pat, filename):
            matched = True

    elif check == "file_naming":
        applies_to = r.get("applies_to", "")
        file_pattern = r.get("file_pattern", "")
        if applies_to and fnmatch.fnmatch(rel_path, applies_to) and file_pattern:
            try:
                if not re.match(file_pattern, filename):
                    matched = True
            except re.error:
                pass

    elif check == "forbidden_import":
        applies_to = r.get("applies_to", "")
        if applies_to and rel_path.startswith(applies_to) and content:
            if any_match(r.get("forbidden_patterns", []), content):
                matched = True

    elif check == "forbidden_content":
        applies_to = r.get("applies_to", "")
        if content and (not applies_to or rel_path.startswith(applies_to)):
            if any_match(r.get("forbidden_patterns", []), content):
                matched = True

    elif check == "required_pattern":
        file_pattern = r.get("file_pattern", "")
        if file_pattern and fnmatch.fnmatch(filename, file_pattern) and content:
            required = r.get("required_in_content", [])
            if required and not any(req in content for req in required):
                matched = True

    elif check == "architectural_constraint":
        file_pattern = r.get("file_pattern", "")
        if file_pattern and fnmatch.fnmatch(filename, file_pattern) and content:
            if any_match(r.get("forbidden_patterns", []), content):
                matched = True

    if matched:
        violations.append((severity, rid, desc, file_path))

# Best-effort stats logging.
if stats_file and violations:
    try:
        d = os.path.dirname(stats_file)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(stats_file, "a") as f:
            for sev, rid, desc, fp in violations:
                f.write(json.dumps({
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "rule_id": rid,
                    "severity": sev,
                    "file_path": fp,
                    "tool": tool_name,
                }) + "\n")
    except Exception:
        pass

has_error = any(s == "error" for s, _, _, _ in violations)
for sev, rid, desc, fp in violations:
    if sev == "error":
        print(f"[Archie BLOCKED] {rid}: {desc} (file: {fp}) — please ask the user before proceeding.")
    else:
        print(f"[Archie WARNING] {rid}: {desc} (file: {fp})")

sys.exit(2 if has_error else 0)
PYEOF
'''

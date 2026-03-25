"""Hook assets -- static Claude Code hook scripts for delivery to target projects."""
import json

# ---------------------------------------------------------------------------
# Hook script content (static -- identical for every project)
# ---------------------------------------------------------------------------

_STOP_REVIEW_AND_REFRESH_SH = r"""#!/bin/bash
# Hook: stop-review-and-refresh (Stop)
#
# Fires when Claude Code finishes responding. Collects changed files
# and calls the smart-refresh API to evaluate alignment and update
# stale docs.

set -euo pipefail

INPUT=$(cat)

CWD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd',''))" 2>/dev/null)

if [[ -z "$CWD" ]]; then
    exit 0
fi

# --- Resolve archie config ---
CONFIG="$CWD/.archie/config.json"
if [[ ! -f "$CONFIG" ]]; then
    exit 0
fi

REPO_ID_FILE="$CWD/.archie/repo_id"
if [[ ! -f "$REPO_ID_FILE" ]]; then
    exit 0
fi

REPO_ID=$(cat "$REPO_ID_FILE")

# --- Collect changed files (deduped) ---
CHANGED_FILES=$(cd "$CWD" && {
    git diff --name-only HEAD 2>/dev/null || true
    git diff --name-only --cached 2>/dev/null || true
    git ls-files --others --exclude-standard 2>/dev/null || true
} | sort -u)

if [[ -z "$CHANGED_FILES" ]]; then
    echo "Stop hook: no changed files detected. Session clean."
    exit 0
fi

FILE_COUNT=$(echo "$CHANGED_FILES" | wc -l | tr -d ' ')

# --- Call smart-refresh API ---
BACKEND_URL=$(python3 -c "import json; print(json.load(open('$CONFIG')).get('backend_url', 'http://localhost:8000'))" 2>/dev/null || echo "http://localhost:8000")

# Build changed files JSON array
CHANGED_FILES_JSON=$(echo "$CHANGED_FILES" | python3 -c "import sys,json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))")

REFRESH_RESULT=$(curl -s -X POST "$BACKEND_URL/api/v1/delivery/smart-refresh" \
    -H "Content-Type: application/json" \
    -d "{\"repo_id\": \"$REPO_ID\", \"changed_files\": $CHANGED_FILES_JSON, \"target_local_path\": \"$CWD\"}" \
    --connect-timeout 3 --max-time 25 2>/dev/null) || true

# --- Format and output smart-refresh results ---
python3 << PYEOF2
import sys, json

refresh_json = '''$REFRESH_RESULT'''
refresh_data = {}
try:
    if refresh_json.strip():
        refresh_data = json.loads(refresh_json)
except Exception:
    pass

refresh_status = refresh_data.get("status", "")
refresh_warnings = refresh_data.get("warnings", [])
refresh_updated = refresh_data.get("updated_files", [])
refresh_suggestions = refresh_data.get("suggestions", [])

error_warnings = [w for w in refresh_warnings if w.get("severity") == "error"]
has_errors = len(error_warnings) > 0

output_lines = []
output_lines.append(f"Session review: $FILE_COUNT file(s) changed.")

# AI architecture warnings
if refresh_warnings:
    output_lines.append(f"Architecture review ({len(refresh_warnings)} finding(s)):")
    for w in refresh_warnings:
        severity = w.get("severity", "warning").upper()
        folder = w.get("folder", "")
        message = w.get("message", "")
        suggestion = w.get("suggestion", "")
        output_lines.append(f"  [{severity}] {folder}: {message}")
        if suggestion:
            output_lines.append(f"    Suggestion: {suggestion}")
    output_lines.append("")

# Updated CLAUDE.md files
if refresh_updated:
    output_lines.append(f"Updated {len(refresh_updated)} CLAUDE.md file(s):")
    for f in refresh_updated:
        output_lines.append(f"  {f}")
    output_lines.append("")

# Suggestions
if refresh_suggestions:
    output_lines.append("Suggestions:")
    for s in refresh_suggestions:
        output_lines.append(f"  {s}")
    output_lines.append("")

if not refresh_warnings:
    output_lines.append("No violations. Architecture looks good.")
    if refresh_status == "refreshed":
        output_lines.append("Intent layer documentation updated.")
elif not has_errors:
    output_lines.append("No critical violations. Review the findings above.")

# Output to stderr if errors, stdout otherwise
text = "\n".join(output_lines)
if has_errors:
    print(text, file=sys.stderr)
    sys.exit(2)
else:
    print(text)
    sys.exit(0)
PYEOF2
""".lstrip()

_CHECK_ARCHITECTURE_STALENESS_SH = r'''#!/bin/bash
# Hook: check-architecture-staleness
# Runs on conversation start. Checks if local architecture files
# are older than the blueprint source and notifies the user.
# Does NOT auto-sync — just surfaces the information.

set -euo pipefail

CONFIG=".archie/config.json"

# Skip if no archie config exists
if [ ! -f "$CONFIG" ]; then
    exit 0
fi

# Read storage path
STORAGE_PATH=$(python3 -c "import json; print(json.load(open('$CONFIG'))['storage_path'])" 2>/dev/null)
if [ -z "$STORAGE_PATH" ]; then
    exit 0
fi

# Skip if no repo_id cached
REPO_ID_FILE=".archie/repo_id"
if [ ! -f "$REPO_ID_FILE" ]; then
    exit 0
fi

REPO_ID=$(cat "$REPO_ID_FILE")
SOURCE_CLAUDE="$STORAGE_PATH/blueprints/$REPO_ID/intent_layer/CLAUDE.md"
LOCAL_CLAUDE="CLAUDE.md"

# Skip if source blueprint doesn't exist
if [ ! -f "$SOURCE_CLAUDE" ]; then
    exit 0
fi

# If local CLAUDE.md doesn't exist at all, suggest sync
if [ ! -f "$LOCAL_CLAUDE" ]; then
    echo "No architecture files found. Run /sync-architecture to provision them."
    exit 0
fi

# Compare modification times
if [ "$SOURCE_CLAUDE" -nt "$LOCAL_CLAUDE" ]; then
    echo "Architecture files are outdated. Run /sync-architecture to update."
fi
'''.lstrip()

# ---------------------------------------------------------------------------
# Assembled map: relative file path -> script content
# ---------------------------------------------------------------------------

HOOK_SCRIPTS: dict[str, str] = {
    ".claude/hooks/stop-review-and-refresh.sh": _STOP_REVIEW_AND_REFRESH_SH,
    ".claude/hooks/check-architecture-staleness.sh": _CHECK_ARCHITECTURE_STALENESS_SH,
}

# ---------------------------------------------------------------------------
# Hook registration settings (.claude/settings.json)
# ---------------------------------------------------------------------------

HOOKS_SETTINGS: dict = {
    "hooks": {
        "Stop": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "./.claude/hooks/stop-review-and-refresh.sh",
                        "timeout": 30,
                    }
                ],
            }
        ],
        "SessionStart": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "./.claude/hooks/check-architecture-staleness.sh",
                        "timeout": 10,
                    }
                ],
            }
        ],
    }
}


# ---------------------------------------------------------------------------
# Skill files (.claude/skills/*.md)
# ---------------------------------------------------------------------------

SKILL_FILES: dict[str, str] = {}

# Load skills from the repo's .claude/skills/ directory at import time.
# Falls back gracefully if the directory doesn't exist (e.g. in tests).
import os as _os
_SKILLS_DIR = _os.path.join(_os.path.dirname(__file__), "..", "..", "..", "..", ".claude", "skills")
_SKILLS_DIR = _os.path.normpath(_SKILLS_DIR)
if _os.path.isdir(_SKILLS_DIR):
    for _fname in sorted(_os.listdir(_SKILLS_DIR)):
        if _fname.endswith(".md"):
            _fpath = _os.path.join(_SKILLS_DIR, _fname)
            try:
                with open(_fpath, encoding="utf-8") as _f:
                    SKILL_FILES[f".claude/skills/{_fname}"] = _f.read()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------


def get_archie_files(repo_id: str, backend_url: str, storage_path: str) -> dict[str, str]:
    """Return the .archie/ config files needed by hook scripts.

    Args:
        repo_id: Repository identifier for this project.
        backend_url: Backend API URL (e.g. "http://localhost:8000").
        storage_path: Absolute path to the archie storage directory.

    Returns a dict mapping relative file paths to their string content.
    """
    config = {
        "storage_path": storage_path,
        "backend_url": backend_url,
    }
    return {
        ".archie/config.json": json.dumps(config, indent=2) + "\n",
        ".archie/repo_id": repo_id + "\n",
    }


def get_hook_files(
    repo_id: str = "",
    backend_url: str = "http://localhost:8000",
    storage_path: str = "",
) -> dict[str, str]:
    """Return all deliverable hook files (scripts + settings.json + skills + archie config).

    Returns a dict mapping relative file paths to their string content,
    ready to be written into a target project.

    When repo_id and storage_path are provided, .archie/ config files are
    included so the hook scripts can locate the blueprint and backend.
    """
    files: dict[str, str] = dict(HOOK_SCRIPTS)
    files[".claude/settings.json"] = json.dumps(HOOKS_SETTINGS, indent=2) + "\n"
    files.update(SKILL_FILES)
    if repo_id and storage_path:
        files.update(get_archie_files(repo_id, backend_url, storage_path))
    return files

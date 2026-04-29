#!/bin/bash
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

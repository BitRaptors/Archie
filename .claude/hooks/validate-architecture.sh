#!/bin/bash
# Hook: validate-architecture (PostToolUse on Write)
#
# Fires after Claude Code creates a new file. Reads the project's
# architecture blueprint and checks if the file is in the correct
# location per file_placement_rules. If not, exits with code 2
# and provides feedback so Claude Code can self-correct.
#
# Only validates NEW file creation (Write tool), not edits to existing files.

set -euo pipefail

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null)

# Only validate Write (new file creation), not Edit
if [[ "$TOOL_NAME" != "Write" ]]; then
    exit 0
fi

FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null)

if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

# Skip non-source files (docs, configs, tests, generated files)
case "$FILE_PATH" in
    *.md|*.json|*.yaml|*.yml|*.toml|*.cfg|*.ini|*.txt|*.lock|*.css|*.html)
        exit 0
        ;;
    *__pycache__*|*node_modules*|*.git/*|*.venv/*|*dist/*|*build/*)
        exit 0
        ;;
esac

# Resolve archie config
CONFIG="$HOME/.archie/config.json"
if [[ ! -f "$CONFIG" ]]; then
    exit 0
fi

STORAGE_PATH=$(python3 -c "import json; print(json.load(open('$CONFIG'))['storage_path'])" 2>/dev/null || true)
if [[ -z "$STORAGE_PATH" ]]; then
    exit 0
fi

# Resolve repo_id
CWD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd',''))" 2>/dev/null)
REPO_ID_FILE="$CWD/.archie/repo_id"
if [[ ! -f "$REPO_ID_FILE" ]]; then
    exit 0
fi

REPO_ID=$(cat "$REPO_ID_FILE")
BLUEPRINT="$STORAGE_PATH/blueprints/$REPO_ID/blueprint.json"
if [[ ! -f "$BLUEPRINT" ]]; then
    exit 0
fi

# Make file_path relative to cwd
REL_PATH="${FILE_PATH#$CWD/}"

# Use python to check file against blueprint placement rules
export BLUEPRINT REL_PATH
RESULT=$(python3 << 'PYEOF'
import json, sys, os, re

blueprint_path = os.environ["BLUEPRINT"]
rel_path = os.environ["REL_PATH"]

try:
    with open(blueprint_path) as f:
        bp = json.load(f)
except Exception:
    sys.exit(0)

rules = bp.get("architecture_rules", {}).get("file_placement_rules", [])
where = bp.get("quick_reference", {}).get("where_to_put_code", {})

if not rules:
    sys.exit(0)

# Extract filename info
basename = os.path.basename(rel_path)
dirname = os.path.dirname(rel_path)
ext = os.path.splitext(basename)[1]

# Try to match the file to a component type based on naming pattern
matched_rule = None
for rule in rules:
    pattern = rule.get("naming_pattern", "")
    location = rule.get("location", "")

    # Check if filename matches the naming pattern
    # Convert glob-like patterns to simple checks
    patterns = [p.strip() for p in pattern.split(" or ")]
    for p in patterns:
        p_clean = p.replace("*", "")
        if p_clean and basename.endswith(p_clean):
            matched_rule = rule
            break
        # Also check exact match
        if p == basename:
            matched_rule = rule
            break
    if matched_rule:
        break

if not matched_rule:
    # No rule matched this file type — skip validation
    sys.exit(0)

# Check if the file is in the expected location
expected_location = matched_rule["location"].rstrip("/")
# Handle "or" in locations (e.g. "worker/auto_browser/services/ or worker/auto_browser/{domain}_service/")
expected_locations = [loc.strip().rstrip("/") for loc in expected_location.split(" or ")]

in_correct_location = False
for loc in expected_locations:
    # Remove template variables for matching (e.g. {domain} -> any segment)
    loc_pattern = re.sub(r'\{[^}]+\}', '[^/]+', loc)
    if re.match(loc_pattern, dirname) or dirname.startswith(loc.split("{")[0].rstrip("/")):
        in_correct_location = True
        break

if in_correct_location:
    sys.exit(0)

# Violation found
component_type = matched_rule.get("component_type", "file")
example = matched_rule.get("example", "")
description = matched_rule.get("description", "")

output = {
    "violation": True,
    "component_type": component_type,
    "current_path": rel_path,
    "expected_location": matched_rule["location"],
    "naming_pattern": matched_rule.get("naming_pattern", ""),
    "example": example,
    "description": description,
}
print(json.dumps(output))
PYEOF
)

# If python exited 0 with no output, the file is fine
if [[ -z "$RESULT" ]]; then
    exit 0
fi

# Check if a violation was found
VIOLATION=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('violation', False))" 2>/dev/null)

if [[ "$VIOLATION" == "True" ]]; then
    COMPONENT_TYPE=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['component_type'])")
    EXPECTED=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['expected_location'])")
    EXAMPLE=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['example'])")
    CURRENT=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['current_path'])")

    cat >&2 << EOF
Architecture violation: "$COMPONENT_TYPE" files belong in $EXPECTED
Current path: $CURRENT
Example: $EXAMPLE

Move this file to the correct location per the project's architecture rules. Check the blueprint's file_placement_rules for details.
EOF
    exit 2
fi

exit 0

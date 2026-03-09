#!/bin/bash
# Hook: pre-validate-architecture (PreToolUse on Write)
#
# Fires BEFORE Claude Code creates a new file. Reads the project's
# architecture blueprint and checks:
#   1. File placement rules (architecture_rules.file_placement_rules)
#   2. Naming conventions (architecture_rules.naming_conventions)
#
# If the file would violate rules, exits with code 2 and provides
# feedback so Claude corrects BEFORE writing.
#
# Only validates Write (new file creation), not Edit.

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

# Skip non-source files (docs, configs, generated files)
case "$FILE_PATH" in
    *.md|*.json|*.yaml|*.yml|*.toml|*.cfg|*.ini|*.txt|*.lock|*.css|*.html)
        exit 0
        ;;
    *__pycache__*|*node_modules*|*.git/*|*.venv/*|*dist/*|*build/*|*.claude/*)
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

# Use python to check file against blueprint placement rules AND naming conventions
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

arch_rules = bp.get("architecture_rules", {})
placement_rules = arch_rules.get("file_placement_rules", [])
naming_conventions = arch_rules.get("naming_conventions", [])

# Extract filename info
basename = os.path.basename(rel_path)
dirname = os.path.dirname(rel_path)
ext = os.path.splitext(basename)[1]
stem = os.path.splitext(basename)[0]

violations = []

# --- Check 1: File placement rules ---
matched_rule = None
for rule in placement_rules:
    pattern = rule.get("naming_pattern", "")
    patterns = [p.strip() for p in pattern.split(" or ")]
    for p in patterns:
        p_clean = p.replace("*", "")
        if p_clean and basename.endswith(p_clean):
            matched_rule = rule
            break
        if p == basename:
            matched_rule = rule
            break
    if matched_rule:
        break

if matched_rule:
    expected_location = matched_rule["location"].rstrip("/")
    expected_locations = [loc.strip().rstrip("/") for loc in expected_location.split(" or ")]

    in_correct_location = False
    for loc in expected_locations:
        loc_pattern = re.sub(r'\{[^}]+\}', '[^/]+', loc)
        if re.match(loc_pattern, dirname) or dirname.startswith(loc.split("{")[0].rstrip("/")):
            in_correct_location = True
            break

    if not in_correct_location:
        violations.append({
            "type": "file_placement",
            "component_type": matched_rule.get("component_type", "file"),
            "current_path": rel_path,
            "expected_location": matched_rule["location"],
            "naming_pattern": matched_rule.get("naming_pattern", ""),
            "example": matched_rule.get("example", ""),
            "description": matched_rule.get("description", ""),
        })

# --- Check 2: Naming conventions ---

def is_snake_case(name):
    """Check if name follows snake_case: lowercase letters, digits, underscores."""
    return bool(re.match(r'^[a-z][a-z0-9]*(_[a-z0-9]+)*$', name))

def is_pascal_case(name):
    """Check if name follows PascalCase: starts with uppercase, no underscores/hyphens."""
    return bool(re.match(r'^[A-Z][a-zA-Z0-9]*$', name))

def is_kebab_case(name):
    """Check if name follows kebab-case: lowercase letters, digits, hyphens."""
    return bool(re.match(r'^[a-z][a-z0-9]*(-[a-z0-9]+)*$', name))

def is_camel_case(name):
    """Check if name follows camelCase: starts with lowercase, no underscores/hyphens."""
    return bool(re.match(r'^[a-z][a-zA-Z0-9]*$', name))

def is_screaming_snake_case(name):
    """Check if name follows SCREAMING_SNAKE_CASE."""
    return bool(re.match(r'^[A-Z][A-Z0-9]*(_[A-Z0-9]+)*$', name))

convention_checkers = {
    "snake_case": is_snake_case,
    "PascalCase": is_pascal_case,
    "pascal_case": is_pascal_case,
    "kebab-case": is_kebab_case,
    "camelCase": is_camel_case,
    "camel_case": is_camel_case,
    "SCREAMING_SNAKE_CASE": is_screaming_snake_case,
    "screaming_snake_case": is_screaming_snake_case,
}

for convention in naming_conventions:
    pattern = convention.get("pattern", "")
    applies_to = convention.get("applies_to", "")
    example = convention.get("example", "")
    conv_name = convention.get("convention", "")

    # Determine if this convention applies to the current file
    # Check applies_to against extension or file pattern
    applies = False

    # Common applies_to values: "Python files", "*.py", "modules", "classes", etc.
    applies_to_lower = applies_to.lower()

    # Check by extension mention
    ext_map = {
        ".py": ["python", "*.py", ".py"],
        ".js": ["javascript", "*.js", ".js", "js files"],
        ".ts": ["typescript", "*.ts", ".ts", "ts files"],
        ".tsx": ["typescript", "*.tsx", ".tsx", "tsx files", "react"],
        ".jsx": ["javascript", "*.jsx", ".jsx", "jsx files", "react"],
        ".rb": ["ruby", "*.rb", ".rb"],
        ".go": ["go ", "*.go", ".go", "golang"],
        ".rs": ["rust", "*.rs", ".rs"],
        ".java": ["java", "*.java", ".java"],
        ".kt": ["kotlin", "*.kt", ".kt"],
        ".swift": ["swift", "*.swift", ".swift"],
    }

    if ext in ext_map:
        for keyword in ext_map[ext]:
            if keyword in applies_to_lower:
                applies = True
                break

    # Check if applies_to mentions "files" generically or matches by pattern
    if not applies and ("all files" in applies_to_lower or "source files" in applies_to_lower):
        applies = True

    # Check glob-style patterns in applies_to (e.g. "*.py", "*_test.py")
    if not applies:
        for token in applies_to.split():
            token_clean = token.strip(",;")
            if "*" in token_clean:
                regex = token_clean.replace(".", r"\.").replace("*", ".*")
                if re.match(regex + "$", basename):
                    applies = True
                    break

    if not applies:
        continue

    # Determine which naming style to check
    checker = convention_checkers.get(conv_name)

    if not checker:
        # Try to detect convention from the pattern field
        for conv_key, conv_func in convention_checkers.items():
            if conv_key.lower() in pattern.lower():
                checker = conv_func
                break

    if not checker:
        continue

    # Check the file stem against the convention
    # Strip known suffixes for checking (e.g. _test, _service, _controller)
    if not checker(stem):
        violations.append({
            "type": "naming_convention",
            "convention": conv_name,
            "applies_to": applies_to,
            "current_name": basename,
            "expected_pattern": pattern or conv_name,
            "example": example,
        })

if not violations:
    sys.exit(0)

print(json.dumps({"violations": violations}))
PYEOF
)

# If python exited 0 with no output, the file is fine
if [[ -z "$RESULT" ]]; then
    exit 0
fi

# Check if violations were found
HAS_VIOLATIONS=$(echo "$RESULT" | python3 -c "import sys,json; v=json.load(sys.stdin).get('violations',[]); print('True' if v else 'False')" 2>/dev/null)

if [[ "$HAS_VIOLATIONS" == "True" ]]; then
    # Format all violations into a single error message
    echo "$RESULT" | python3 -c "
import sys, json

data = json.load(sys.stdin)
violations = data['violations']

messages = []
for v in violations:
    if v['type'] == 'file_placement':
        messages.append(
            f\"File placement violation: \\\"{v['component_type']}\\\" files belong in {v['expected_location']}\n\"
            f\"  Current path: {v['current_path']}\n\"
            f\"  Expected pattern: {v['naming_pattern']}\n\"
            f\"  Example: {v['example']}\"
        )
    elif v['type'] == 'naming_convention':
        messages.append(
            f\"Naming convention violation: {v['current_name']} should follow {v['convention']} ({v['expected_pattern']})\n\"
            f\"  Applies to: {v['applies_to']}\n\"
            f\"  Example: {v['example']}\"
        )

print('\n\n'.join(messages))
print()
print('Fix the file path/name to comply with the project architecture rules before creating this file. Check the blueprint for details.')
" >&2
    exit 2
fi

exit 0

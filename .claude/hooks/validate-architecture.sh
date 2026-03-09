#!/bin/bash
# Hook: validate-architecture (PostToolUse on Write/Edit)
#
# Fires after Claude Code creates or edits a file. Reads the project's
# architecture blueprint and checks:
#   1. File placement rules (architecture_rules.file_placement_rules)
#   2. Naming conventions (architecture_rules.naming_conventions)
#
# If violations found, exits with code 2 and provides feedback so
# Claude Code can self-correct.

set -euo pipefail

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null)

# Validate both Write (new file creation) and Edit (modifications)
if [[ "$TOOL_NAME" != "Write" && "$TOOL_NAME" != "Edit" ]]; then
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

violation = None
naming_violations = []

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
        violation = {
            "component_type": matched_rule.get("component_type", "file"),
            "current_path": rel_path,
            "expected_location": matched_rule["location"],
            "naming_pattern": matched_rule.get("naming_pattern", ""),
            "example": matched_rule.get("example", ""),
            "description": matched_rule.get("description", ""),
        }

# --- Check 2: Naming conventions ---

def is_snake_case(name):
    return bool(re.match(r'^[a-z][a-z0-9]*(_[a-z0-9]+)*$', name))

def is_pascal_case(name):
    return bool(re.match(r'^[A-Z][a-zA-Z0-9]*$', name))

def is_kebab_case(name):
    return bool(re.match(r'^[a-z][a-z0-9]*(-[a-z0-9]+)*$', name))

def is_camel_case(name):
    return bool(re.match(r'^[a-z][a-zA-Z0-9]*$', name))

def is_screaming_snake_case(name):
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

    applies = False
    applies_to_lower = applies_to.lower()

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

    if not applies and ("all files" in applies_to_lower or "source files" in applies_to_lower):
        applies = True

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

    checker = convention_checkers.get(conv_name)

    if not checker:
        for conv_key, conv_func in convention_checkers.items():
            if conv_key.lower() in pattern.lower():
                checker = conv_func
                break

    if not checker:
        continue

    if not checker(stem):
        naming_violations.append({
            "convention": conv_name,
            "applies_to": applies_to,
            "current_name": basename,
            "expected_pattern": pattern or conv_name,
            "example": example,
        })

if not violation and not naming_violations:
    sys.exit(0)

output = {
    "violation": violation,
    "naming_violations": naming_violations,
}
print(json.dumps(output))
PYEOF
)

# If python exited 0 with no output, the file is fine
if [[ -z "$RESULT" ]]; then
    exit 0
fi

# Check if violations were found and format output
HAS_ISSUES=$(echo "$RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
has = bool(data.get('violation')) or bool(data.get('naming_violations'))
print('True' if has else 'False')
" 2>/dev/null)

if [[ "$HAS_ISSUES" == "True" ]]; then
    echo "$RESULT" | python3 -c "
import sys, json

data = json.load(sys.stdin)
violation = data.get('violation')
naming_violations = data.get('naming_violations', [])

messages = []

if violation:
    messages.append(
        f\"File placement violation: \\\"{violation['component_type']}\\\" files belong in {violation['expected_location']}\n\"
        f\"  Current path: {violation['current_path']}\n\"
        f\"  Expected pattern: {violation['naming_pattern']}\n\"
        f\"  Example: {violation['example']}\"
    )

for nv in naming_violations:
    messages.append(
        f\"Naming convention violation: {nv['current_name']} should follow {nv['convention']} ({nv['expected_pattern']})\n\"
        f\"  Applies to: {nv['applies_to']}\n\"
        f\"  Example: {nv['example']}\"
    )

print('\n\n'.join(messages))
print()
print('Fix the file path/name to comply with the project architecture rules. Check the blueprint for details.')
" >&2
    exit 2
fi

exit 0

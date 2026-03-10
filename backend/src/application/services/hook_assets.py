"""Hook assets -- static Claude Code hook scripts for delivery to target projects."""
import json

# ---------------------------------------------------------------------------
# Hook script content (static -- identical for every project)
# ---------------------------------------------------------------------------

_PRE_VALIDATE_ARCHITECTURE_SH = r'''#!/bin/bash
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
'''.lstrip()

_VALIDATE_ARCHITECTURE_SH = r'''#!/bin/bash
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
'''.lstrip()

_STOP_REVIEW_AND_REFRESH_SH = r"""#!/bin/bash
# Hook: stop-review-and-refresh (Stop)
#
# Fires when Claude Code finishes responding. Performs a session-end review:
#   1. Collects changed files via git diff + untracked files (deduped)
#   2. Validates each source file against blueprint's file_placement_rules
#      and naming_conventions
#   3. Checks per-folder CLAUDE.md freshness (local vs intent_layer source mtime)
#   4. Calls smart-refresh API to evaluate alignment and update stale docs
#   5. Outputs combined summary to stderr (violations) or stdout (clean report)
#   6. Exit 2 if violations found, exit 0 if clean

set -euo pipefail

INPUT=$(cat)

CWD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd',''))" 2>/dev/null)

if [[ -z "$CWD" ]]; then
    exit 0
fi

# --- Resolve archie config ---
CONFIG="$HOME/.archie/config.json"
if [[ ! -f "$CONFIG" ]]; then
    exit 0
fi

STORAGE_PATH=$(python3 -c "import json; print(json.load(open('$CONFIG'))['storage_path'])" 2>/dev/null || true)
if [[ -z "$STORAGE_PATH" ]]; then
    exit 0
fi

REPO_ID_FILE="$CWD/.archie/repo_id"
if [[ ! -f "$REPO_ID_FILE" ]]; then
    exit 0
fi

REPO_ID=$(cat "$REPO_ID_FILE")
BLUEPRINT="$STORAGE_PATH/blueprints/$REPO_ID/blueprint.json"
INTENT_LAYER_DIR="$STORAGE_PATH/blueprints/$REPO_ID/intent_layer"

if [[ ! -f "$BLUEPRINT" ]]; then
    exit 0
fi

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

# --- Validate each source file against blueprint ---
export BLUEPRINT CWD CHANGED_FILES INTENT_LAYER_DIR

RESULT=$(python3 << 'PYEOF'
import json, sys, os, re

blueprint_path = os.environ["BLUEPRINT"]
cwd = os.environ["CWD"]
changed_files_raw = os.environ["CHANGED_FILES"]
intent_layer_dir = os.environ["INTENT_LAYER_DIR"]

changed_files = [f.strip() for f in changed_files_raw.strip().split("\n") if f.strip()]

try:
    with open(blueprint_path) as f:
        bp = json.load(f)
except Exception:
    sys.exit(0)

arch_rules = bp.get("architecture_rules", {})
placement_rules = arch_rules.get("file_placement_rules", [])
naming_conventions = arch_rules.get("naming_conventions", [])

# Skip patterns for non-source files
SKIP_EXTENSIONS = {
    ".md", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",
    ".txt", ".lock", ".css", ".html",
}
SKIP_PATH_PARTS = {
    "__pycache__", "node_modules", ".git", ".venv", "dist", "build", ".claude",
}

# --- Naming convention checkers ---

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

all_violations = []

for rel_path in changed_files:
    basename_f = os.path.basename(rel_path)
    dirname_f = os.path.dirname(rel_path)
    ext = os.path.splitext(basename_f)[1]
    stem = os.path.splitext(basename_f)[0]

    # Skip non-source files
    if ext in SKIP_EXTENSIONS:
        continue
    if any(part in rel_path.split("/") for part in SKIP_PATH_PARTS):
        continue

    # --- Check 1: File placement rules ---
    matched_rule = None
    for rule in placement_rules:
        pattern = rule.get("naming_pattern", "")
        patterns = [p.strip() for p in pattern.split(" or ")]
        for p in patterns:
            p_clean = p.replace("*", "")
            if p_clean and basename_f.endswith(p_clean):
                matched_rule = rule
                break
            if p == basename_f:
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
            if re.match(loc_pattern, dirname_f) or dirname_f.startswith(loc.split("{")[0].rstrip("/")):
                in_correct_location = True
                break

        if not in_correct_location:
            all_violations.append({
                "type": "file_placement",
                "component_type": matched_rule.get("component_type", "file"),
                "current_path": rel_path,
                "expected_location": matched_rule["location"],
                "naming_pattern": matched_rule.get("naming_pattern", ""),
                "example": matched_rule.get("example", ""),
                "description": matched_rule.get("description", ""),
            })

    # --- Check 2: Naming conventions ---
    for convention in naming_conventions:
        pattern = convention.get("pattern", "")
        applies_to = convention.get("applies_to", "")
        example = convention.get("example", "")
        conv_name = convention.get("convention", "")

        applies = False
        applies_to_lower = applies_to.lower()

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
                    if re.match(regex + "$", basename_f):
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
            all_violations.append({
                "type": "naming_convention",
                "convention": conv_name,
                "applies_to": applies_to,
                "current_path": rel_path,
                "current_name": basename_f,
                "expected_pattern": pattern or conv_name,
                "example": example,
            })

# --- Check 3: CLAUDE.md freshness ---
stale_claude_mds = []

# Collect unique directories from changed files
dirs_seen = set()
for rel_path in changed_files:
    d = os.path.dirname(rel_path)
    while d:
        dirs_seen.add(d)
        d = os.path.dirname(d)
    dirs_seen.add("")  # root

for d in sorted(dirs_seen):
    local_claude = os.path.join(cwd, d, "CLAUDE.md") if d else os.path.join(cwd, "CLAUDE.md")
    source_claude = os.path.join(intent_layer_dir, d, "CLAUDE.md") if d else os.path.join(intent_layer_dir, "CLAUDE.md")

    if not os.path.isfile(source_claude):
        continue
    if not os.path.isfile(local_claude):
        check_dir = d if d else "."
        stale_claude_mds.append(f"  {check_dir}/CLAUDE.md — missing locally (source exists)")
        continue

    local_mtime = os.path.getmtime(local_claude)
    source_mtime = os.path.getmtime(source_claude)

    if source_mtime > local_mtime:
        stale_claude_mds.append({
            "local": os.path.join(d, "CLAUDE.md") if d else "CLAUDE.md",
            "local_mtime": local_mtime,
            "source_mtime": source_mtime,
        })

output = {
    "violations": all_violations,
    "stale_claude_mds": stale_claude_mds,
    "file_count": len(changed_files),
    "files_checked": [f for f in changed_files
                      if os.path.splitext(f)[1] not in SKIP_EXTENSIONS
                      and not any(part in f.split("/") for part in SKIP_PATH_PARTS)],
}
print(json.dumps(output))
PYEOF
)

if [[ -z "$RESULT" ]]; then
    exit 0
fi

# --- Parse results ---
VIOLATION_COUNT=$(echo "$RESULT" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('violations',[])))" 2>/dev/null)
STALE_COUNT=$(echo "$RESULT" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('stale_claude_mds',[])))" 2>/dev/null)
CHECKED_COUNT=$(echo "$RESULT" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('files_checked',[])))" 2>/dev/null)

# --- Call smart-refresh API ---
BACKEND_URL=$(python3 -c "import json; print(json.load(open('$CONFIG')).get('backend_url', 'http://localhost:8000'))" 2>/dev/null || echo "http://localhost:8000")

# Build changed files JSON array
CHANGED_FILES_JSON=$(echo "$CHANGED_FILES" | python3 -c "import sys,json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))")

REFRESH_RESULT=$(curl -s -X POST "$BACKEND_URL/delivery/smart-refresh" \
    -H "Content-Type: application/json" \
    -d "{\"repo_id\": \"$REPO_ID\", \"changed_files\": $CHANGED_FILES_JSON, \"target_local_path\": \"$CWD\"}" \
    --connect-timeout 3 --max-time 25 2>/dev/null) || true

# --- Combine local validation + smart-refresh results and output ---
python3 << PYEOF2
import sys, json, os

# Local validation results
result_json = '''$RESULT'''
local_data = json.loads(result_json)
violations = local_data.get("violations", [])
stale = local_data.get("stale_claude_mds", [])
file_count = local_data.get("file_count", 0)
checked = local_data.get("files_checked", [])

# Smart-refresh results
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

# Count architecture errors from AI
error_warnings = [w for w in refresh_warnings if w.get("severity") == "error"]
has_violations = len(violations) > 0 or len(error_warnings) > 0

output_lines = []
output_lines.append(f"Session review: {file_count} file(s) changed, {len(checked)} source file(s) checked.")

# Local violations
if violations:
    output_lines.append(f"Found {len(violations)} local validation violation(s):")
    output_lines.append("")
    for v in violations:
        if v["type"] == "file_placement":
            output_lines.append(f'  File placement: "{v["component_type"]}" files belong in {v["expected_location"]}')
            output_lines.append(f"    Current: {v['current_path']}")
            if v.get("example"):
                output_lines.append(f"    Example: {v['example']}")
        elif v["type"] == "naming_convention":
            output_lines.append(f"  Naming: {v['current_name']} should follow {v.get('convention', '')} ({v.get('expected_pattern', '')})")
            output_lines.append(f"    File: {v['current_path']}")
        output_lines.append("")

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

if not violations and not refresh_warnings:
    output_lines.append("No violations. Architecture looks good.")
    if refresh_status == "refreshed":
        output_lines.append("Intent layer documentation updated.")
elif not has_violations:
    output_lines.append("No critical violations. Review the findings above.")

# Output to stderr if errors, stdout otherwise
text = "\n".join(output_lines)
if has_violations:
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

CONFIG="$HOME/.archie/config.json"

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
    ".claude/hooks/pre-validate-architecture.sh": _PRE_VALIDATE_ARCHITECTURE_SH,
    ".claude/hooks/validate-architecture.sh": _VALIDATE_ARCHITECTURE_SH,
    ".claude/hooks/stop-review-and-refresh.sh": _STOP_REVIEW_AND_REFRESH_SH,
    ".claude/hooks/check-architecture-staleness.sh": _CHECK_ARCHITECTURE_STALENESS_SH,
}

# ---------------------------------------------------------------------------
# Hook registration settings (.claude/settings.json)
# ---------------------------------------------------------------------------

HOOKS_SETTINGS: dict = {
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "Write",
                "hooks": [
                    {
                        "type": "command",
                        "command": "./.claude/hooks/pre-validate-architecture.sh",
                        "timeout": 5,
                    }
                ],
            }
        ],
        "PostToolUse": [
            {
                "matcher": "Write|Edit",
                "hooks": [
                    {
                        "type": "command",
                        "command": "./.claude/hooks/validate-architecture.sh",
                        "timeout": 5,
                    }
                ],
            }
        ],
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

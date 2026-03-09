#!/bin/bash
# Hook: stop-review-and-refresh (Stop)
#
# Fires when Claude Code finishes responding. Performs a session-end review:
#   1. Collects changed files via git diff + untracked files (deduped)
#   2. Validates each source file against blueprint's file_placement_rules
#      and naming_conventions
#   3. Checks per-folder CLAUDE.md freshness (local vs intent_layer source mtime)
#   4. If changes warrant it (3+ files changed OR stale CLAUDE.md found),
#      calls backend API to refresh intent layer
#   5. Outputs summary to stderr (violations) or stdout (clean report)
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

# --- Call backend API if refresh warranted ---
# Refresh if 3+ files changed OR any stale CLAUDE.md found
SHOULD_REFRESH="false"
if [[ "$FILE_COUNT" -ge 3 ]] || [[ "$STALE_COUNT" -gt 0 ]]; then
    SHOULD_REFRESH="true"
fi

BACKEND_URL=$(python3 -c "import json; print(json.load(open('$CONFIG')).get('backend_url', 'http://localhost:8000'))" 2>/dev/null || echo "http://localhost:8000")

export REFRESH_STATUS=""
if [[ "$SHOULD_REFRESH" == "true" ]]; then
    REFRESH_RESULT=$(curl -s -X POST "$BACKEND_URL/delivery/apply" \
        -H "Content-Type: application/json" \
        -d "{\"source_repo_id\": \"$REPO_ID\", \"strategy\": \"local\", \"target_local_path\": \"$CWD\", \"outputs\": [\"intent_layer\", \"claude_md\"]}" \
        --connect-timeout 3 --max-time 15 2>/dev/null) || true

    if [[ -n "$REFRESH_RESULT" ]]; then
        # Check if the response indicates success
        API_OK=$(echo "$REFRESH_RESULT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print('ok' if data.get('status') == 'ok' or 'error' not in data else 'error')
except:
    print('error')
" 2>/dev/null)
        if [[ "$API_OK" == "ok" ]]; then
            export REFRESH_STATUS="refreshed"
        else
            export REFRESH_STATUS="api_error"
        fi
    else
        export REFRESH_STATUS="backend_unavailable"
    fi
fi

# --- Output ---
if [[ "$VIOLATION_COUNT" -gt 0 ]]; then
    # Violations found — output to stderr and exit 2
    echo "$RESULT" | python3 -c "
import sys, json

data = json.load(sys.stdin)
violations = data['violations']
stale = data.get('stale_claude_mds', [])
file_count = data.get('file_count', 0)
checked = data.get('files_checked', [])

print(f'Session review: {file_count} file(s) changed, {len(checked)} source file(s) checked.', file=sys.stderr)
print(f'Found {len(violations)} violation(s):', file=sys.stderr)
print(file=sys.stderr)

for v in violations:
    if v['type'] == 'file_placement':
        print(
            f\"  File placement violation: \\\"{v['component_type']}\\\" files belong in {v['expected_location']}\n\"
            f\"    Current path: {v['current_path']}\n\"
            f\"    Expected pattern: {v['naming_pattern']}\n\"
            f\"    Example: {v['example']}\",
            file=sys.stderr
        )
    elif v['type'] == 'naming_convention':
        print(
            f\"  Naming convention violation: {v['current_name']} should follow {v['convention']} ({v['expected_pattern']})\n\"
            f\"    File: {v['current_path']}\n\"
            f\"    Applies to: {v['applies_to']}\n\"
            f\"    Example: {v['example']}\",
            file=sys.stderr
        )
    print(file=sys.stderr)

if stale:
    print(f'Stale CLAUDE.md file(s) detected ({len(stale)}):', file=sys.stderr)
    for s in stale:
        print(f\"  {s['local']} — source is newer than local copy\", file=sys.stderr)
    print(file=sys.stderr)

print('Fix the file paths/names to comply with the project architecture rules.', file=sys.stderr)
" 2>&2

    # Also print refresh status to stdout if refresh was attempted
    if [[ -n "$REFRESH_STATUS" ]]; then
        case "$REFRESH_STATUS" in
            refreshed)
                echo "Intent layer refreshed successfully."
                ;;
            api_error)
                echo "Intent layer refresh attempted but API returned an error."
                ;;
            backend_unavailable)
                echo "Intent layer refresh skipped — backend unavailable."
                ;;
        esac
    fi

    exit 2
fi

# --- Clean report to stdout ---
echo "$RESULT" | python3 -c "
import sys, json, os

data = json.load(sys.stdin)
stale = data.get('stale_claude_mds', [])
file_count = data.get('file_count', 0)
checked = data.get('files_checked', [])

refresh_status = os.environ.get('REFRESH_STATUS', '')

print(f'Session review: {file_count} file(s) changed, {len(checked)} source file(s) checked. No violations.')

if stale:
    print(f'Stale CLAUDE.md file(s) detected ({len(stale)}):')
    for s in stale:
        print(f\"  {s['local']} — source is newer than local copy\")

if refresh_status == 'refreshed':
    print('Intent layer refreshed successfully.')
elif refresh_status == 'api_error':
    print('Intent layer refresh attempted but API returned an error.')
elif refresh_status == 'backend_unavailable':
    print('Intent layer refresh skipped — backend unavailable.')
elif file_count >= 3 or stale:
    pass  # already handled
"

exit 0

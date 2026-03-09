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

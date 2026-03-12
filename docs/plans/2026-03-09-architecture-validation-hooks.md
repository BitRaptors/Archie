# Architecture Validation Hooks Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 3 Claude Code hooks that validate architecture rules before/after edits and refresh intent layer files at session end.

**Architecture:** Three hooks reading `blueprint.json` directly for fast validation. Stop hook additionally calls backend API to refresh CLAUDE.md files. All hooks share a common blueprint resolution pattern (archie config → repo_id → blueprint path).

**Tech Stack:** Bash + Python3 (inline), curl for backend API calls

---

### Task 1: Create PreToolUse hook — pre-validate-architecture.sh

**Files:**
- Create: `.claude/hooks/pre-validate-architecture.sh`

This hook fires BEFORE Claude writes a new file. It checks `file_placement_rules` and `naming_conventions` from the blueprint. If the file would go to the wrong place or have a bad name, it blocks creation (exit 2).

**Step 1: Create the hook script**

```bash
#!/bin/bash
# Hook: pre-validate-architecture (PreToolUse on Write)
#
# Fires BEFORE Claude creates a new file. Checks the blueprint's
# file_placement_rules and naming_conventions. Blocks with exit 2
# if the file would violate rules, so Claude corrects BEFORE writing.

set -euo pipefail

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null)

if [[ "$TOOL_NAME" != "Write" ]]; then
    exit 0
fi

FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null)

if [[ -z "$FILE_PATH" ]]; then
    exit 0
fi

# Skip non-source files
case "$FILE_PATH" in
    *.md|*.json|*.yaml|*.yml|*.toml|*.cfg|*.ini|*.txt|*.lock|*.css|*.html)
        exit 0
        ;;
    *__pycache__*|*node_modules*|*.git/*|*.venv/*|*dist/*|*build/*|*.claude/*)
        exit 0
        ;;
esac

# Resolve blueprint
CONFIG="$HOME/.archie/config.json"
if [[ ! -f "$CONFIG" ]]; then
    exit 0
fi

STORAGE_PATH=$(python3 -c "import json; print(json.load(open('$CONFIG'))['storage_path'])" 2>/dev/null || true)
if [[ -z "$STORAGE_PATH" ]]; then
    exit 0
fi

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

REL_PATH="${FILE_PATH#$CWD/}"

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
naming = bp.get("architecture_rules", {}).get("naming_conventions", {})
violations = []

# --- File placement check ---
basename = os.path.basename(rel_path)
dirname = os.path.dirname(rel_path)

matched_rule = None
for rule in rules:
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
        violations.append(
            f"File placement: {matched_rule.get('component_type', 'file')} files belong in {matched_rule['location']}, "
            f"not {dirname}/. Example: {matched_rule.get('example', 'N/A')}"
        )

# --- Naming convention check ---
# Check scope-based naming rules (e.g. files, classes, functions)
for scope, convention in naming.items():
    if scope in ("files", "modules") and isinstance(convention, dict):
        case_rule = convention.get("case", "")
        suffix_rule = convention.get("suffix", "")
        prefix_rule = convention.get("prefix", "")
        name_no_ext = os.path.splitext(basename)[0]

        if case_rule == "snake_case" and name_no_ext != name_no_ext.lower():
            violations.append(f"Naming: file '{basename}' should be snake_case per naming conventions")
        elif case_rule == "PascalCase" and (name_no_ext[0:1] != name_no_ext[0:1].upper() or "_" in name_no_ext):
            violations.append(f"Naming: file '{basename}' should be PascalCase per naming conventions")
        elif case_rule == "kebab-case" and name_no_ext != name_no_ext.lower().replace("_", "-"):
            violations.append(f"Naming: file '{basename}' should be kebab-case per naming conventions")

        if suffix_rule and not name_no_ext.endswith(suffix_rule):
            violations.append(f"Naming: file '{basename}' should end with '{suffix_rule}'")
        if prefix_rule and not name_no_ext.startswith(prefix_rule):
            violations.append(f"Naming: file '{basename}' should start with '{prefix_rule}'")
    # Also handle string-style conventions like "snake_case for files"
    elif scope in ("files", "modules") and isinstance(convention, str):
        name_no_ext = os.path.splitext(basename)[0]
        if "snake_case" in convention and name_no_ext != name_no_ext.lower():
            violations.append(f"Naming: file '{basename}' should be snake_case per naming conventions")

if violations:
    print(json.dumps({"violations": violations}))
else:
    sys.exit(0)
PYEOF
)

if [[ -z "$RESULT" ]]; then
    exit 0
fi

HAS_VIOLATIONS=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(bool(d.get('violations')))" 2>/dev/null)

if [[ "$HAS_VIOLATIONS" == "True" ]]; then
    VIOLATION_TEXT=$(echo "$RESULT" | python3 -c "
import sys,json
violations = json.load(sys.stdin)['violations']
for v in violations:
    print(f'  - {v}', file=sys.stderr)
" 2>&1)

    cat >&2 << EOF
Architecture violation BEFORE file creation:
$VIOLATION_TEXT

Fix the file path/name before creating it. Check the blueprint's file_placement_rules and naming_conventions.
EOF
    exit 2
fi

exit 0
```

**Step 2: Make executable**

Run: `chmod +x .claude/hooks/pre-validate-architecture.sh`

**Step 3: Commit**

```bash
git add .claude/hooks/pre-validate-architecture.sh
git commit -m "feat: add PreToolUse hook for pre-creation architecture validation"
```

---

### Task 2: Extend PostToolUse hook — validate-architecture.sh

**Files:**
- Modify: `.claude/hooks/validate-architecture.sh`

Extend the existing hook to:
1. Also trigger on `Edit` (not just `Write`)
2. Add naming convention checks (same logic as PreToolUse)

**Step 1: Update the tool name filter**

In `.claude/hooks/validate-architecture.sh`, change lines 17-20:

Old:
```bash
# Only validate Write (new file creation), not Edit
if [[ "$TOOL_NAME" != "Write" ]]; then
    exit 0
fi
```

New:
```bash
# Validate both Write (new file creation) and Edit (modifications)
if [[ "$TOOL_NAME" != "Write" && "$TOOL_NAME" != "Edit" ]]; then
    exit 0
fi
```

**Step 2: Update file_path extraction for Edit tool**

The Edit tool uses `file_path` in `tool_input` (same as Write), so no change needed for path extraction.

**Step 3: Add naming convention check after the placement check**

After the existing python block (line 67-146), before the final violation check, add naming validation to the Python code. Specifically, extend the Python script's violation output to also include naming issues.

Replace the Python block (lines 67-146) with an extended version that adds naming checks identical to those in the PreToolUse hook (see Task 1 Python code, the naming section).

The key addition to the Python code after the placement check:

```python
# --- Naming convention check ---
naming = bp.get("architecture_rules", {}).get("naming_conventions", {})
naming_violations = []

for scope, convention in naming.items():
    if scope in ("files", "modules") and isinstance(convention, dict):
        case_rule = convention.get("case", "")
        name_no_ext = os.path.splitext(basename)[0]

        if case_rule == "snake_case" and name_no_ext != name_no_ext.lower():
            naming_violations.append(f"file '{basename}' should be snake_case")
        elif case_rule == "PascalCase" and (name_no_ext[0:1] != name_no_ext[0:1].upper() or "_" in name_no_ext):
            naming_violations.append(f"file '{basename}' should be PascalCase")
        elif case_rule == "kebab-case" and name_no_ext != name_no_ext.lower().replace("_", "-"):
            naming_violations.append(f"file '{basename}' should be kebab-case")
    elif scope in ("files", "modules") and isinstance(convention, str):
        name_no_ext = os.path.splitext(basename)[0]
        if "snake_case" in convention and name_no_ext != name_no_ext.lower():
            naming_violations.append(f"file '{basename}' should be snake_case")

if naming_violations:
    output["naming_violations"] = naming_violations
    output["violation"] = True
```

**Step 4: Update the bash violation output section to also print naming violations**

After the existing violation stderr output (lines 163-169), add:

```bash
NAMING_VIOLATIONS=$(echo "$RESULT" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for v in d.get('naming_violations', []):
    print(f'  - Naming: {v}')
" 2>/dev/null || true)

if [[ -n "$NAMING_VIOLATIONS" ]]; then
    echo "Naming convention violations:" >&2
    echo "$NAMING_VIOLATIONS" >&2
fi
```

**Step 5: Commit**

```bash
git add .claude/hooks/validate-architecture.sh
git commit -m "feat: extend PostToolUse hook to Edit + naming validation"
```

---

### Task 3: Create Stop hook — stop-review-and-refresh.sh

**Files:**
- Create: `.claude/hooks/stop-review-and-refresh.sh`

This is the main review hook. When Claude finishes responding, it:
1. Checks `git diff` for changed files
2. Validates each against blueprint
3. Checks per-folder CLAUDE.md freshness
4. Calls backend API to refresh intent layer if needed

**Step 1: Create the hook script**

```bash
#!/bin/bash
# Hook: stop-review-and-refresh (Stop event)
#
# Runs when Claude finishes responding. Reviews all changed files
# against the blueprint, checks CLAUDE.md freshness, and refreshes
# intent layer via backend API if needed.

set -euo pipefail

INPUT=$(cat)

CWD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd',''))" 2>/dev/null)
if [[ -z "$CWD" ]]; then
    exit 0
fi

# Check for changed files (staged + unstaged)
CHANGED_FILES=$(cd "$CWD" && git diff --name-only HEAD 2>/dev/null; git diff --name-only --cached 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null)
CHANGED_FILES=$(echo "$CHANGED_FILES" | sort -u | grep -v '^$' || true)

if [[ -z "$CHANGED_FILES" ]]; then
    exit 0
fi

# Resolve blueprint
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
if [[ ! -f "$BLUEPRINT" ]]; then
    exit 0
fi

INTENT_LAYER_DIR="$STORAGE_PATH/blueprints/$REPO_ID/intent_layer"

# --- Phase 1: Validate changed files against blueprint ---
export BLUEPRINT CHANGED_FILES CWD INTENT_LAYER_DIR
VALIDATION_RESULT=$(python3 << 'PYEOF'
import json, sys, os, re

blueprint_path = os.environ["BLUEPRINT"]
changed_files_raw = os.environ["CHANGED_FILES"]
cwd = os.environ["CWD"]
intent_layer_dir = os.environ["INTENT_LAYER_DIR"]

changed_files = [f.strip() for f in changed_files_raw.strip().split("\n") if f.strip()]

try:
    with open(blueprint_path) as f:
        bp = json.load(f)
except Exception:
    sys.exit(0)

rules = bp.get("architecture_rules", {}).get("file_placement_rules", [])
naming = bp.get("architecture_rules", {}).get("naming_conventions", {})

# Skip patterns
SKIP_EXTENSIONS = {".md", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".txt", ".lock", ".css", ".html"}
SKIP_DIRS = {"__pycache__", "node_modules", ".git", ".venv", "dist", "build", ".claude"}

violations = []
checked_count = 0
affected_dirs = set()

for rel_path in changed_files:
    basename = os.path.basename(rel_path)
    dirname = os.path.dirname(rel_path)
    ext = os.path.splitext(basename)[1]

    # Skip non-source files
    if ext in SKIP_EXTENSIONS:
        continue
    if any(skip in rel_path.split("/") for skip in SKIP_DIRS):
        continue

    checked_count += 1
    affected_dirs.add(dirname)

    # File placement check
    matched_rule = None
    for rule in rules:
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
            violations.append(f"  [{rel_path}] Wrong location for {matched_rule.get('component_type', 'file')} — expected: {matched_rule['location']}")

    # Naming check
    for scope, convention in naming.items():
        if scope not in ("files", "modules"):
            continue
        name_no_ext = os.path.splitext(basename)[0]
        if isinstance(convention, dict):
            case_rule = convention.get("case", "")
            if case_rule == "snake_case" and name_no_ext != name_no_ext.lower():
                violations.append(f"  [{rel_path}] Naming: should be snake_case")
            elif case_rule == "PascalCase" and (name_no_ext[0:1] != name_no_ext[0:1].upper() or "_" in name_no_ext):
                violations.append(f"  [{rel_path}] Naming: should be PascalCase")
            elif case_rule == "kebab-case" and name_no_ext != name_no_ext.lower().replace("_", "-"):
                violations.append(f"  [{rel_path}] Naming: should be kebab-case")
        elif isinstance(convention, str):
            if "snake_case" in convention and name_no_ext != name_no_ext.lower():
                violations.append(f"  [{rel_path}] Naming: should be snake_case")

# Check per-folder CLAUDE.md freshness
stale_claude_mds = []
for d in sorted(affected_dirs):
    # Check if there's a per-folder CLAUDE.md in the local project
    local_claude = os.path.join(cwd, d, "CLAUDE.md")
    source_claude = os.path.join(intent_layer_dir, d, "CLAUDE.md")

    if os.path.exists(source_claude):
        if not os.path.exists(local_claude):
            stale_claude_mds.append(f"  {d}/CLAUDE.md — missing locally (source exists)")
        elif os.path.getmtime(source_claude) > os.path.getmtime(local_claude):
            stale_claude_mds.append(f"  {d}/CLAUDE.md — outdated (source is newer)")

# Build output
result = {
    "changed_count": len(changed_files),
    "checked_count": checked_count,
    "violations": violations,
    "stale_claude_mds": stale_claude_mds,
    "affected_dirs": sorted(affected_dirs),
    "needs_refresh": len(changed_files) >= 3 or len(stale_claude_mds) > 0,
}
print(json.dumps(result))
PYEOF
)

if [[ -z "$VALIDATION_RESULT" ]]; then
    exit 0
fi

# Parse results
VIOLATIONS=$(echo "$VALIDATION_RESULT" | python3 -c "import sys,json; [print(v) for v in json.load(sys.stdin).get('violations',[])]" 2>/dev/null || true)
STALE=$(echo "$VALIDATION_RESULT" | python3 -c "import sys,json; [print(v) for v in json.load(sys.stdin).get('stale_claude_mds',[])]" 2>/dev/null || true)
NEEDS_REFRESH=$(echo "$VALIDATION_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('needs_refresh', False))" 2>/dev/null || true)
CHANGED_COUNT=$(echo "$VALIDATION_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('changed_count', 0))" 2>/dev/null || true)
CHECKED_COUNT=$(echo "$VALIDATION_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('checked_count', 0))" 2>/dev/null || true)

# --- Output summary ---
HAS_ISSUES=false

if [[ -n "$VIOLATIONS" ]]; then
    HAS_ISSUES=true
    echo "Architecture violations found:" >&2
    echo "$VIOLATIONS" >&2
    echo "" >&2
fi

if [[ -n "$STALE" ]]; then
    HAS_ISSUES=true
    echo "Stale per-folder CLAUDE.md files:" >&2
    echo "$STALE" >&2
    echo "" >&2
fi

# --- Phase 2: Refresh intent layer if needed ---
if [[ "$NEEDS_REFRESH" == "True" ]]; then
    # Try to refresh via backend API (assumes it's running on localhost:8000)
    REFRESH_RESPONSE=$(curl -s -X POST http://localhost:8000/delivery/apply \
        -H "Content-Type: application/json" \
        -d "{\"source_repo_id\": \"$REPO_ID\", \"strategy\": \"local\", \"target_local_path\": \"$CWD\", \"outputs\": [\"intent_layer\", \"claude_md\"]}" \
        --connect-timeout 3 --max-time 15 2>/dev/null || echo "REFRESH_FAILED")

    if [[ "$REFRESH_RESPONSE" == "REFRESH_FAILED" ]]; then
        echo "Could not refresh intent layer (backend not reachable). Run /sync-architecture manually." >&2
    else
        STATUS=$(echo "$REFRESH_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
        if [[ "$STATUS" == "success" ]]; then
            FILES_COUNT=$(echo "$REFRESH_RESPONSE" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('files_delivered',[])))" 2>/dev/null || echo "?")
            echo "Intent layer refreshed ($FILES_COUNT files updated)." >&2
        else
            echo "Intent layer refresh returned status: $STATUS" >&2
        fi
    fi
fi

if [[ "$HAS_ISSUES" == "true" ]]; then
    echo "" >&2
    echo "Review complete: $CHANGED_COUNT files changed, $CHECKED_COUNT source files checked." >&2
    exit 2
fi

# Clean summary if no issues
if [[ "$CHECKED_COUNT" -gt 0 ]]; then
    echo "Review complete: $CHANGED_COUNT files changed, $CHECKED_COUNT source files checked. No violations found."
fi

exit 0
```

**Step 2: Make executable**

Run: `chmod +x .claude/hooks/stop-review-and-refresh.sh`

**Step 3: Commit**

```bash
git add .claude/hooks/stop-review-and-refresh.sh
git commit -m "feat: add Stop hook for session-end review and intent layer refresh"
```

---

### Task 4: Register hooks in settings.local.json

**Files:**
- Modify: `.claude/settings.local.json`

Add the `hooks` configuration alongside the existing `permissions`.

**Step 1: Update settings.local.json**

The file currently only has `permissions`. Add `hooks` key:

```json
{
  "permissions": {
    "allow": [
      "Bash(git clone:*)",
      "Bash(python3 -m venv:*)",
      "Bash(source:*)",
      "Bash(pip install:*)",
      "Bash(npm install:*)",
      "Bash(node --version:*)",
      "Bash(npm --version:*)",
      "Bash(PYTHONPATH=src timeout 5 python:*)",
      "Bash(PYTHONPATH=src python:*)",
      "Bash(PYTHONPATH=src uvicorn main:app:*)",
      "Bash(npm run dev:*)",
      "Bash(PGPASSWORD=postgres docker exec:*)",
      "Bash(docker compose:*)",
      "Bash(./setup.sh:*)",
      "Bash(PYTHONPATH=src .venv/bin/python:*)",
      "Bash(./start-dev.sh:*)",
      "Bash(pkill:*)",
      "Bash(PGPASSWORD=postgres psql:*)",
      "Bash(psql:*)",
      "Bash(.venv/bin/python:*)",
      "Bash(docker port:*)",
      "Bash(brew services:*)",
      "Bash(pg_lsclusters)",
      "Read(//opt/homebrew/var/postgresql@14/**)",
      "Bash(DOCKER_HOST=unix:///Users/csacsi/.docker/run/docker.sock docker ps:*)",
      "Bash(DOCKER_HOST=unix:///Users/csacsi/.docker/run/docker.sock docker stop:*)",
      "Bash(kill:*)",
      "Bash(xargs -I {} bash -c 'echo \"\"=== {} ===\"\" && ls -la \"\"{}\"\"')",
      "WebSearch"
    ]
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "./.claude/hooks/pre-validate-architecture.sh",
            "timeout": 5
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "./.claude/hooks/validate-architecture.sh",
            "timeout": 5
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "./.claude/hooks/stop-review-and-refresh.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

**Step 2: Commit**

```bash
git add .claude/settings.local.json
git commit -m "feat: register all 3 architecture validation hooks"
```

---

### Task 5: Manual smoke test

**Step 1: Test PreToolUse hook**

Create a test input and pipe it to the hook:
```bash
echo '{"tool_name":"Write","tool_input":{"file_path":"/Users/csacsi/DEV/archie/WRONG_PLACE/service.py"},"cwd":"/Users/csacsi/DEV/archie"}' | ./.claude/hooks/pre-validate-architecture.sh
echo "Exit code: $?"
```

Expected: exit 2 if blueprint has placement rules for services, or exit 0 if no matching rule.

**Step 2: Test PostToolUse hook**

```bash
echo '{"tool_name":"Edit","tool_input":{"file_path":"/Users/csacsi/DEV/archie/backend/src/api/routes/health.py"},"cwd":"/Users/csacsi/DEV/archie"}' | ./.claude/hooks/validate-architecture.sh
echo "Exit code: $?"
```

Expected: exit 0 (correct location).

**Step 3: Test Stop hook**

```bash
echo '{"cwd":"/Users/csacsi/DEV/archie"}' | ./.claude/hooks/stop-review-and-refresh.sh
echo "Exit code: $?"
```

Expected: reviews any uncommitted changes, reports violations or "No violations found".

# Archie Scan Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement `/archie-scan` (fast 1-3 min health check) and rename `/archie-init` to `/archie-deep-scan`, creating a two-command architecture for fighting AI code degradation.

**Architecture:** Scripts do mechanical checks (complexity, cycles, rule violations) in seconds. One orchestrator agent reads findings + skeletons + flagged files and produces a report with health scores, findings, proposed rules, and next task. Predefined platform rules ship with Archie. Project rules accumulate over scans.

**Tech Stack:** Python 3.9+ (zero deps), Claude Code slash commands, JSON artifacts

---

### Task 1: Skeleton extraction in scanner.py

**Files:**
- Modify: `archie/standalone/scanner.py`

**Step 1: Add skeleton extraction function**

Add regex-based symbol extraction after the existing `estimate_tokens()` function (~line 519). The function reads each source file, extracts function/class/method signatures with line numbers, and a 2-3 line file header.

```python
_EXT_TO_LANG = {
    ".py": "python", ".kt": "kotlin", ".kts": "kotlin",
    ".java": "java", ".swift": "swift",
    ".ts": "typescript", ".tsx": "typescript",
    ".js": "typescript", ".jsx": "typescript", ".go": "go",
}

def extract_skeletons(root: Path, files: list[dict]) -> dict[str, dict]:
    """Extract per-file skeletons: header + symbol signatures with line numbers."""
    # Regex patterns per language for function/class/interface signatures
    # Returns {path: {header, symbols: [{kind, name, signature, line}], line_count}}
```

Languages to support with `re.MULTILINE` patterns:
- Python: `class X`, `def x()`, `async def x()`
- Kotlin: `fun x()`, `class X`, `interface X`, `object X`, `data class X`
- Java: `class X`, `interface X`, method signatures with modifiers
- Swift: `func x()`, `class X`, `struct X`, `protocol X`, `enum X`
- TypeScript/JS: `function x()`, `class X`, `interface X`, `const x =`
- Go: `func X()`, `type X struct/interface`
- Fallback: first 20 lines for unsupported languages

**Step 2: Add tokens_by_directory aggregation**

In `run_scan()`, after `estimate_tokens()`, aggregate:
```python
tokens_by_dir = defaultdict(int)
for path, count in tokens.items():
    parent = str(Path(path).parent) if "/" in path else "."
    tokens_by_dir[parent] += count
```

**Step 3: Update run_scan() return and save skeletons**

Add `tokens_by_directory` to scan output. Save skeletons to `.archie/skeletons.json` (separate file, keeps scan.json smaller).

**Step 4: Verify**

Run: `python3 archie/standalone/scanner.py /path/to/BabyWeather.Android 2>&1 | head -5`
Expected: `Skeletons: ~500 files` line in output, `skeletons.json` created in `.archie/`

**Step 5: Commit**

```bash
git add archie/standalone/scanner.py
git commit -m "feat(scanner): add skeleton extraction + tokens_by_directory"
```

---

### Task 2: measure_health.py — Erosion and verbosity measurement

**Files:**
- Create: `archie/standalone/measure_health.py`

**Step 1: Implement cyclomatic complexity measurement**

Measure CC per function using the skeleton symbols + selective file reads. For Python files, use `ast` module for precise CC. For other languages, approximate from regex (count `if/else/for/while/case/catch/&&/||` in function bodies).

Erosion formula from SlopCodeBench:
```python
# mass(f) = CC(f) * sqrt(SLOC(f))
# erosion = sum(mass for f where CC > 10) / sum(mass for all f)
```

**Step 2: Implement verbosity/duplication measurement**

Detect duplicate code blocks (>10 lines with >80% similarity). Use line-hash based approach — hash each line, find sequences of matching hashes across files.

Verbosity = flagged_duplicate_lines / total_LOC

**Step 3: Implement CLI**

```
python3 measure_health.py /path/to/repo
```

Output JSON to stdout:
```json
{
  "erosion": 0.34,
  "verbosity": 0.21,
  "total_functions": 245,
  "high_cc_functions": 14,
  "functions": [
    {"path": "file.kt", "name": "saveSettings", "cc": 18, "sloc": 45, "line": 120}
  ],
  "duplicates": [
    {"files": ["a.kt:10-25", "b.kt:30-45"], "lines": 15, "similarity": 0.92}
  ]
}
```

Reads skeletons.json for function locations, selectively reads files for CC counting.

**Step 4: Verify**

Run: `python3 archie/standalone/measure_health.py /path/to/BabyWeather.Android`
Expected: JSON with erosion score, verbosity score, function-level details

**Step 5: Commit**

```bash
git add archie/standalone/measure_health.py
git commit -m "feat: add measure_health.py — erosion + verbosity scoring"
```

---

### Task 3: check_rules.py — Rule checking engine

**Files:**
- Create: `archie/standalone/check_rules.py`

**Step 1: Implement rule checker**

Reads `.archie/platform_rules.json` (predefined) + `.archie/rules.json` (project-specific). Checks each rule against the codebase using skeletons + selective file reads.

Rule format (same as existing `rules.json` but extended):
```json
{
  "id": "universal-god-function",
  "check": "complexity_threshold",
  "description": "Function exceeds cyclomatic complexity threshold",
  "threshold": 15,
  "severity": "error",
  "source": "predefined"
}
```

Check types:
- `complexity_threshold` — CC > N (uses measure_health output)
- `size_threshold` — lines > N or methods > N
- `forbidden_import` — regex on file content (existing format)
- `required_pattern` — file matching glob must contain pattern (existing format)
- `forbidden_content` — regex on file content (existing format)
- `architectural_constraint` — file glob + forbidden regex (existing format)
- `import_cycle` — circular dependency (uses import graph)

**Step 2: Implement CLI**

```
python3 check_rules.py /path/to/repo
```

Output JSON: list of violations with file, line, rule_id, severity, message.

**Step 3: Verify and commit**

---

### Task 4: detect_cycles.py — Import graph cycle detection

**Files:**
- Create: `archie/standalone/detect_cycles.py`

**Step 1: Implement cycle detection**

Read `scan.json` import_graph. Run DFS-based cycle detection (Tarjan's or simple DFS with back-edge tracking). Report cycles at the module/directory level, not individual files.

```
python3 detect_cycles.py /path/to/repo
```

Output JSON:
```json
{
  "cycles": [
    {"modules": ["common/domain", "page_settings"], "files": ["SettingsRepo.kt", "SettingsFragment.kt"]},
  ],
  "cycle_count": 1
}
```

**Step 2: Verify and commit**

---

### Task 5: platform_rules.json — Predefined checks

**Files:**
- Create: `archie/standalone/platform_rules.json`

**Step 1: Write predefined rules**

Universal rules (any language):
- God-function (CC > 15)
- God-class (> 30 public methods or > 500 lines)
- Deep nesting (> 4 levels)
- Large file (> 500 lines for most languages)

Platform-specific rules (keyed by detected framework from scan.json):
- Android/Kotlin: ViewModel+Context, Fragment+network, missing Koin registration
- Swift/iOS: massive body, ViewController size, actor mutability
- TypeScript/React: conditional hooks, component size, prop drilling
- Python: circular imports, bare except, missing type hints

Each rule has: id, check type, description, threshold/pattern, severity, platform.

**Step 2: Verify structure parses**

Run: `python3 -c "import json; r=json.load(open('archie/standalone/platform_rules.json')); print(f'{len(r[\"rules\"])} predefined rules')"`

**Step 3: Commit**

---

### Task 6: archie-scan.md — The slash command

**Files:**
- Create: `.claude/commands/archie-scan.md`

**Step 1: Write the orchestrator command**

This is the main `/archie-scan` slash command. Structure:

```markdown
# Archie Scan — Fast Architecture Health Check

Run a fast architectural health scan. 1-3 minutes. Run often — each scan improves the next.

## Step 1: Run mechanical checks

[Run scanner, measure_health, check_rules, detect_cycles scripts]
[Load previous scan report if exists]
[Git diff since last scan if available]

## Step 2: Analyze (one agent, follows playbooks)

[Agent gets all script output + skeletons + flagged files]
[Follows predefined check playbooks]
[Discovers patterns, proposes rules]
[Produces architecture overview]
[Scores health metrics]

## Step 3: Generate report

[Write scan_report.md with checkboxes]
[Save to scan_history/]
[Print summary]

## Step 4: User reviews

[User checks/ignores proposed rules]
[Agent processes adoptions into rules.json]

## Playbooks
[Universal checks, platform checks, pattern discovery, health scoring]
```

Key instruction: **the agent is an orchestrator that follows playbooks, not a free-form analyzer.** It reads the predefined checks and applies them systematically. This keeps it fast and consistent.

**Step 2: Commit**

---

### Task 7: Rename archie-init → archie-deep-scan

**Files:**
- Rename: `.claude/commands/archie-init.md` → `.claude/commands/archie-deep-scan.md`
- Modify: `.claude/commands/archie-deep-scan.md` (add health metrics at the end)
- Modify: `npm-package/bin/archie.mjs` (update command list)
- Modify: `CLAUDE.md` (update references)

**Step 1: Rename and update**

Copy archie-init.md to archie-deep-scan.md. Update its title/description. Add Step 10.5 that runs `measure_health.py` and saves health scores to `health_history.json`. Ensure it preserves existing `rules.json` entries (doesn't overwrite user-adopted rules).

**Step 2: Update installer**

In `archie.mjs`, replace `archie-init.md` with `archie-deep-scan.md` in the command copy list. Add `archie-scan.md`. Add new scripts to the script copy list: `measure_health.py`, `check_rules.py`, `detect_cycles.py`. Add `platform_rules.json` to asset copy list.

**Step 3: Keep archie-init.md as alias**

Create a minimal `archie-init.md` that says: "This command has been renamed to `/archie-deep-scan`. Run `/archie-deep-scan` for full analysis, or `/archie-scan` for a fast health check."

**Step 4: Commit**

---

### Task 8: Update install_hooks.py — platform rules support

**Files:**
- Modify: `archie/standalone/install_hooks.py`

**Step 1: Update pre-validate hook**

Extend the pre-validate.sh hook to also check against `platform_rules.json` (currently only checks `rules.json`). The hook script should load both files and merge the rule lists.

**Step 2: Copy platform_rules.json during install**

Add `platform_rules.json` to the installer's file copy list.

**Step 3: Commit**

---

### Task 9: Sync, installer update, verify

**Files:**
- Modify: `npm-package/bin/archie.mjs`
- Copy: all new/modified files to `npm-package/assets/`

**Step 1: Update archie.mjs**

Add to script list: `measure_health.py`, `check_rules.py`, `detect_cycles.py`, `platform_rules.json`
Add to command list: `archie-scan.md`, `archie-deep-scan.md`
Remove from command list: `archie-init.md` (replaced by alias)
Add to gitignore entries: `.archie/scan_report.md`, `.archie/scan_history/`, `.archie/health_history.json`, `.archie/ignored_rules.json`

**Step 2: Sync all files**

```bash
for f in archie/standalone/*.py; do cp "$f" npm-package/assets/$(basename "$f"); done
for f in .claude/commands/archie-*.md; do cp "$f" npm-package/assets/$(basename "$f"); done
cp archie/standalone/platform_rules.json npm-package/assets/
```

**Step 3: Run verify_sync.py**

```bash
python3 scripts/verify_sync.py
```

**Step 4: Install to BabyWeather.Android and test**

```bash
node npm-package/bin/archie.mjs /path/to/BabyWeather.Android
```

Verify all new files appear, no errors.

**Step 5: Commit**

---

### Task 10: End-to-end test on BabyWeather.Android

**Step 1: Run /archie-scan**

In a Claude Code session on BabyWeather.Android, run `/archie-scan`. Verify:
- Completes in < 3 minutes
- Produces `.archie/scan_report.md` with all sections (overview, health scores, findings, proposed rules, next task)
- Health scores are computed (erosion, verbosity, violations)
- Predefined rules produce findings
- Architecture overview is accurate

**Step 2: Run /archie-deep-scan**

Verify it still works as before (same as old `/archie-init`), plus:
- Computes health scores
- Preserves any rules adopted from scan

**Step 3: Run /archie-scan again after deep scan**

Verify the scan now uses blueprint context for richer findings.

**Step 4: Commit final state**

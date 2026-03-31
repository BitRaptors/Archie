# Archie Scan — Architecture Health Check

Analyze this project's architectural health. Behave like a senior architect reviewing a codebase — read what matters, understand the structure, find real problems.

**Prerequisites:** If `.archie/scanner.py` doesn't exist, tell the user to run `npx archie` first.

## Step 1: Gather context (scripts — seconds)

Run the scanner to get the project map and health metrics:

```bash
python3 .archie/scanner.py "$PWD"
python3 .archie/measure_health.py "$PWD" > /tmp/archie_health.json 2>&1
git log --oneline --since="7 days ago" --name-only 2>/dev/null | sort -u | head -50
```

Now read:
- `.archie/skeletons.json` — the full project map: every file's header, function/class signatures, line counts
- `.archie/scan.json` — file tree, import graph, detected frameworks
- `/tmp/archie_health.json` — erosion score, verbosity score, per-function complexity

Also read if they exist (skip if not — that's normal):
- `.archie/blueprint.json` — architectural decisions, component boundaries (from deep scan)
- `.archie/scan_report.md` — previous scan report for trending
- `.archie/health_history.json` — historical health scores
- `.archie/rules.json` — project-specific rules already adopted
- `.archie/ignored_rules.json` — rules user previously rejected

## Step 2: Analyze the architecture

You are a senior architect reviewing this codebase. You have the complete project map (skeletons) and health metrics. Now **understand the architecture and find real problems.**

**You can and should read any source file** when you need to understand something the skeletons don't tell you. The skeletons are your map — they show what exists and where. When you see something suspicious (high complexity, unexpected import, unusual pattern), read the actual file to understand it.

### 2a: Architecture overview

Write a 5-10 line summary. What is this project? How is it organized? What are the key patterns? What are the main data flows?

Read skeletons to understand file structure, imports, and signatures. If the architecture isn't clear from skeletons alone, read a few key files (entry points, main config, DI setup).

### 2b: Health assessment

From the health metrics, report each score with a **plain-language explanation** of what it means and whether it's good or bad:

- **Erosion** (0 to 1): What fraction of the codebase's complexity is concentrated in a few god-functions. 0 = complexity evenly distributed (healthy). 1 = all complexity in a handful of functions (critical). Thresholds: <0.3 good, 0.3-0.5 moderate, >0.5 high — complexity is concentrating.
- **Verbosity** (0 to 1): What fraction of code is duplicated or redundant. 0 = no duplication. Thresholds: <0.05 good, 0.05-0.15 moderate, >0.15 high — significant copy-paste debt.
- **Functions analyzed**: total count, and how many have CC > 10 (complex) or CC > 15 (god-function territory).
- **Top complex functions**: list them, read any that look suspicious.
- **Trend**: compare against previous scan if health_history.json exists.

Present health scores in this format:
```
| Metric | Score | Meaning |
|--------|-------|---------|
| Erosion | 0.41 | Moderate — 41% of complexity mass in high-CC functions |
| Verbosity | 0.003 | Good — minimal code duplication |
```

### 2c: Architectural analysis

This is the core of the scan. Don't check regex patterns — **understand the architecture and find where it's breaking down.**

**Dependency direction:** Read the import graph from scan.json. Trace the dependency flow between modules/packages. Are there layers? Do dependencies flow in one direction? Find violations — a UI component importing from the data layer, a domain model depending on a framework, a feature module importing from another feature module.

**Component responsibilities:** Look at the skeletons. Are there god-classes with too many methods? Files that mix concerns (a ViewModel that does network calls)? Read the suspicious ones to confirm.

**Pattern consistency:** Does the codebase follow its own patterns? If 15 ViewModels extend BaseViewModel but 2 don't, that's drift. If all repositories use constructor injection except one that uses a service locator, that's erosion. The skeletons tell you this — same base class, same structure, same naming — except the outliers.

**Duplication / reimplementation:** Look for functions with the same or similar names in multiple files. AI agents do this constantly — they reimplement helpers instead of importing shared code. Check: are there `loadJson()`, `formatDate()`, `handleError()` style functions duplicated across files?

**Circular dependencies:** Trace the import graph for cycles. If module A imports from B and B imports from A, explain what coupling this creates and why it matters.

**Blueprint violations (if blueprint.json exists):** If a deep scan was run before, the blueprint contains architectural decisions with violation keywords, trade-offs with violation signals, and pitfalls with causal chains. Check if current code violates any of these. Read files to verify.

**For every finding: read the actual file to confirm it's real.** Don't report anything you haven't verified in the source code.

### 2d: Propose rules

Based on what you found, propose **architectural rules** — not refactoring tasks.

Good rules (architectural invariants with reasoning):
- "Domain layer must not import from presentation layer" — *because the domain is the stable core; if it depends on UI, every UI change ripples through business logic*
- "All ViewModels must use constructor injection" — *because the testability decision chain requires ViewModels to be unit-testable without framework setup*
- "Feature modules must not import from each other" — *because independent deployment was a key trade-off; cross-feature imports create hidden coupling*

Bad rules (these are tasks, not rules):
- "Extract dialog boilerplate into base class"
- "Move shared types to a model package"

Each rule should be something that can be **checked on every future code change** — not a one-time refactoring.

**Rules are enforced by the AI reviewer** (runs on every plan approval and pre-commit). The reviewer reads each rule's `rationale` and evaluates whether changes violate the *intent* — this is the primary enforcement channel.

**Optionally**, if a rule can also be expressed as a regex pattern, add mechanical fields (`forbidden_patterns`, `required_in_content`, etc.) so the pre-edit hook can catch obvious violations instantly. Most architectural rules won't have this — that's fine.

**Rule schema:**

Required fields:
```json
{"id": "scan-NNN", "description": "What is forbidden/required", "rationale": "Why — the architectural reasoning", "severity": "error|warn"}
```

Optional mechanical fields (add ONLY when a meaningful regex exists):
- `"check"`: one of `forbidden_import`, `required_pattern`, `forbidden_content`, `architectural_constraint`
- `"applies_to"`: directory prefix scope
- `"file_pattern"`: glob matched against filename
- `"forbidden_patterns"`: regex patterns that violate the rule
- `"required_in_content"`: strings that must appear in matching files

Examples — most rules are rationale-only:
```json
{"id": "scan-001", "description": "Feature modules must not import from each other", "rationale": "Independent deployment was a key trade-off. Cross-feature imports create hidden coupling that prevents releasing features independently.", "severity": "error"}
```
```json
{"id": "scan-002", "description": "Domain layer must not import from presentation layer", "rationale": "The domain is the stable core. If it depends on UI, every UI refactor ripples through business logic.", "severity": "error", "check": "forbidden_import", "applies_to": "domain/", "forbidden_patterns": ["from presentation", "import.*\\.ui\\."]}
```

The **`rationale`** field is REQUIRED. Write 1-3 sentences tracing the constraint back to an architectural decision, trade-off, or pitfall. If a blueprint exists, reference specific decisions. If not, explain the reasoning from what you observed in the codebase.

Use `id` prefix `scan-` with a 3-digit number (e.g., `scan-001`). Start numbering after the highest existing `scan-` id in `.archie/rules.json`.

Present proposed rules as a **numbered checklist**. Keep the full JSON objects internally (you'll need them for adoption), but show the user a clean summary with the reasoning visible:

```
## Proposed Rules

**1.** Domain layer must not import from presentation layer — `error`
*Why:* The domain is the stable core. If it depends on UI, every UI refactor ripples through business logic, breaking the layered architecture.
Violated by: `domain/service.py`, `domain/model.py`

**2.** All ViewModels must use constructor injection — `warn`
*Why:* The testability decision chain requires ViewModels to be unit-testable without framework setup. Service locator breaks this.
Violated by: `UserViewModel.kt`

**3.** Feature modules must not import from each other — `error`
*Why:* Independent deployment was a key trade-off. Cross-feature imports create hidden coupling that prevents releasing features independently.
Violated by: `feed/ProfileHelper.kt`

> **Reply with the numbers to adopt** (e.g., `1, 3` or `all` or `none`).
> Adopted rules take effect immediately — the AI reviewer enforces them on every plan, code change, and commit.
```

Do NOT propose rules that appear in `.archie/ignored_rules.json`.
Do NOT propose rules that already exist in `.archie/rules.json`.

### 2e: Next task

What's the single highest-impact thing to fix right now? Be specific:
- **What**: the action
- **Where**: exact file paths
- **Why**: what improves
- **How**: 2-3 sentence approach

### 2f: Re-baseline check

Recommend `/archie-deep-scan` if:
- No blueprint.json exists (first time — recommend deep scan for full baseline)
- Erosion score increased >0.10 since last deep scan
- Significant structural changes visible in the skeletons

## Step 3: Write the report

Get the current date for the filename:
```bash
date -u +"%Y-%m-%d"
```

Write to `.archie/scan_report_YYYY-MM-DD.md` (using the actual date). Also copy to `.archie/scan_report.md` as the "latest" pointer. This keeps all reports for comparison.

```markdown
# Archie Scan Report
> Scan #N | YYYY-MM-DD | X files analyzed | Y changed in last 7 days

## Architecture Overview
[5-10 lines]

## Health Scores
| Metric | Current | Previous | Trend |
|--------|---------|----------|-------|
| Erosion | X.XX | X.XX | ⚠/✓ |
| Verbosity | X.XX | X.XX | ⚠/✓ |

### Complex Functions
| Function | File | CC |
|----------|------|----|
[top 5]

## Findings
[Ranked by impact. Each finding: what's wrong, which file, evidence from the code, why it matters]

## Proposed Rules
[Checkboxes — architectural invariants only]

## Next Task
**What:** [action]
**Where:** [files]
**Why:** [impact]
**How:** [approach]

## Trend
[Last 5 scans if history exists]

## Recommendations
[Re-baseline recommendation or "No deep scan needed"]
```

Append health scores to `.archie/health_history.json`:
```json
{"timestamp": "ISO-8601", "erosion": 0.00, "verbosity": 0.00, "scan_number": N, "scan_type": "fast"}
```

## Step 4: Present and process adoptions

Print a summary (not the full report). Include health scores, finding count, the **numbered rules table** from section 2d, next task, and path to full report.

The table already includes the adoption prompt:
> **Reply with the numbers to adopt** (e.g., `1, 3` or `all` or `none`).

**Wait for the user's response.** Then process it:

Parse the user's reply:
- Numbers (e.g., `1, 3`) → adopt those rules
- `all` → adopt every proposed rule
- `none` → ignore every proposed rule
- Mixed (e.g., `1, 3, ignore rest`) → adopt the named numbers, ignore the rest

For each **adopted** rule:
1. Read `.archie/rules.json` (create as `{"rules": []}` if missing)
2. Append the rule's full JSON object (with `id`, `check`, `description`, `severity`, and all type-specific fields like `forbidden_patterns`, `applies_to`, `file_pattern`, etc.)
3. Add `"source": "scan-adopted"` to each appended rule
4. Write back. This is the same schema the deep scan uses — `check_rules.py` must be able to enforce it.

For each **ignored** rule:
1. Read `.archie/ignored_rules.json` (create as `{"ignored": []}` if missing)
2. Append each ignored rule's `id` and `description`
3. Write back.

Print confirmation: `Adopted N rules, ignored M. Rules take effect immediately — the AI reviewer will enforce them on every plan, code change, and commit.`

## Cleanup

```bash
rm -f /tmp/archie_health.json
```

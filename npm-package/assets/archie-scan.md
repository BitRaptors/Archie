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

From the health metrics:
- **Erosion score**: how much complexity is concentrated in god-functions
- **Verbosity score**: how much code is duplicated
- **Top complex functions**: list them, read any that look suspicious
- **Trend**: compare against previous scan if health_history.json exists

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

Good rules (architectural invariants):
- "Domain layer must not import from presentation layer"
- "All ViewModels must use constructor injection, not service locator"
- "Repositories must expose Flow, not callbacks"
- "Feature modules must not import from each other"

Bad rules (these are tasks, not rules):
- "Extract dialog boilerplate into base class"
- "Move shared types to a model package"
- "Exclude gradle scripts from scan"

Each rule should be something that can be **checked on every future code change** — not a one-time refactoring. Format:

```
- [ ] Adopt: "rule description" (currently violated by: file1, file2)
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

Write to `.archie/scan_report.md`:

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

Print a summary (not the full report). Include health scores, finding count, proposed rules with checkboxes, next task, and path to full report.

Then:

> Review the proposed rules above. Tell me which to adopt (enforced on future scans) or ignore (won't be proposed again).

Process the user's response:
- Adopted → append to `.archie/rules.json`
- Ignored → append to `.archie/ignored_rules.json`

## Cleanup

```bash
rm -f /tmp/archie_health.json
```

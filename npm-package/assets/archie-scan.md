# Archie Scan — Fast Architecture Health Check

Analyze this project's architectural health. Fast, repeatable — run often, each scan improves the next.

**Prerequisites:** Run `/archie-init` first to set up the project. If `.archie/scanner.py` doesn't exist, tell the user to run `npx archie` and then `/archie-init` first.

**IMPORTANT: Do NOT read all source files. The scripts do the mechanical analysis. You interpret the findings and read ONLY the flagged files to validate and enrich them. Do NOT write inline Python scripts or bash one-liners to parse output — the scripts handle everything.**

## Step 1: Run mechanical checks

Run all scripts in sequence (they're fast — seconds total):

```bash
python3 .archie/scanner.py "$PWD"
```

```bash
python3 .archie/measure_health.py "$PWD" > /tmp/archie_health.json 2>&1
```

```bash
python3 .archie/check_rules.py "$PWD" > /tmp/archie_violations.json 2>&1
```

```bash
python3 .archie/detect_cycles.py "$PWD" > /tmp/archie_cycles.json 2>&1
```

Also check git for recent changes:
```bash
git log --oneline --since="7 days ago" --name-only | sort -u | head -50
```

Now read all of these outputs:
- `/tmp/archie_health.json`
- `/tmp/archie_violations.json`
- `/tmp/archie_cycles.json`

Also read these project files (skip any that don't exist — that's normal):
- `.archie/skeletons.json` — full project map with signatures, imports, headers
- `.archie/scan.json` — file tree, import graph, framework detection
- `.archie/blueprint.json` — architectural decisions, component boundaries (from deep scan)
- `.archie/scan_report.md` — previous scan report for trending comparison
- `.archie/health_history.json` — historical health scores for trend analysis
- `.archie/ignored_rules.json` — rules the user previously rejected (do NOT re-propose these)
- `.archie/rules.json` — project-specific rules already active

## Step 2: Analyze and produce report

You are an architectural health assessor. Follow these playbooks in order. Do not skip any.

### Playbook 1: Architecture Overview

Write a 5-10 line summary proving you understand this project. Cover:
- What kind of project is this (app, library, service, CLI, monorepo)?
- What language(s) and framework(s)?
- How is it organized (modules, layers, features, packages)?
- What are the key architectural patterns (MVC, MVVM, Clean, layered, event-driven)?
- What are the main entry points and data flows?

Base this on skeletons.json (file structure + signatures) and blueprint.json (if available). Do NOT read source files for this — the metadata is sufficient.

### Playbook 2: Health Scoring

From the `/tmp/archie_health.json` output, extract and report:
- **Erosion score** (0-1): fraction of complexity concentrated in high-CC functions. Lower is better.
- **Verbosity score** (0-1): duplicate/redundant code ratio. Lower is better.
- **Top 5 highest-CC functions**: list them with file path, function name, and CC value.

If `.archie/health_history.json` exists, compare current scores to the most recent entry:
- Show trend: rising (worse), falling (better), or stable (within 0.02).
- Flag any functions whose CC grew since last scan.

If `.archie/scan_report.md` exists, note the scan number and increment it. Otherwise this is Scan #1.

### Playbook 3: Findings

From `/tmp/archie_violations.json` (check_rules.py output):
- List all **ERROR-severity** violations. These are real problems — read the flagged file for each one to validate it's not a false positive. Quote the specific code that violates the rule.
- List the top 10 **WARN-severity** violations, ordered by impact. For each one, read the flagged file to confirm the issue.
- If a violation turns out to be a false positive after reading the file, note it as such and skip it.

From `/tmp/archie_cycles.json` (detect_cycles.py output):
- List all circular dependency cycles found.
- For each cycle: name the modules involved, explain what coupling this creates, and why it matters (testing difficulty, build order, change propagation).

Rank all confirmed findings by impact — what would hurt most if left unfixed? Consider: frequency (how many files affected), severity (error vs warn), growth trend (getting worse?), blast radius (how much breaks if this goes wrong).

### Playbook 4: Pattern Discovery and Rule Proposals

Examine skeletons.json for patterns that most of the codebase follows but some files break:
- If 90%+ of files in a category follow a naming convention, propose a rule for the outliers.
- If most classes/modules use a consistent base class, DI pattern, or structural pattern, propose a rule.
- If import ordering or module organization is consistent except for a few files, propose a rule.

**Do NOT propose rules that appear in `.archie/ignored_rules.json`.** The user already rejected these.

**Do NOT propose rules that already exist in `.archie/rules.json`.** They're already active.

Format each proposed rule with a checkbox:
```
- [ ] Adopt: "description of the rule" (affects: list of files that currently violate it)
```

### Playbook 5: Next Task

Identify the single highest-impact item to fix right now. Consider these candidates:
- The highest-CC function that is still growing (trend from health_history.json)
- The most impactful circular dependency to break
- The most common violation pattern (fixing the root cause fixes many violations at once)
- A structural issue that blocks other improvements

Write it as an actionable task:
- **What:** specific action to take (refactor function X, break cycle between A and B, extract pattern into base class)
- **Where:** exact file path(s)
- **Why:** what improves (CC drops by N, M violations resolved, cycle broken)
- **How:** brief sketch of the approach (2-3 sentences max)

### Playbook 6: Re-baseline Check

Recommend the user run `/archie-init` (full deep scan) if ANY of these are true:
- This is the first scan (no `.archie/blueprint.json` exists)
- Erosion score increased by more than 0.10 since the last deep scan
- More than 30% of directories have new violations compared to last scan
- The project structure changed significantly (new top-level modules, major refactors visible in git log)

If none of these are true, confirm the project is within normal parameters.

## Step 3: Write the report

Write the complete report to `.archie/scan_report.md` in this exact format:

```
# Archie Scan Report
> Scan #N | YYYY-MM-DD | X files analyzed | Y files changed in last 7 days

## Architecture Overview
[5-10 lines from Playbook 1]

## Health Scores
| Metric | Current | Previous | Trend |
|--------|---------|----------|-------|
| Erosion | X.XX | X.XX | rising/falling/stable |
| Verbosity | X.XX | X.XX | rising/falling/stable |
| Violations | N | N | rising/falling/stable |
| Cycles | N | N | rising/falling/stable |

### Top Complex Functions
| Function | File | CC | Change |
|----------|------|----|--------|
| name | path | N | +/-N or new |

## Findings

### Errors
[Numbered list of confirmed ERROR-severity violations with file, rule, evidence]

### Warnings
[Numbered list of top WARN-severity violations with file, rule, evidence]

### Circular Dependencies
[List of cycles with modules involved and impact]

## Proposed Rules
[Checkboxes from Playbook 4, or "No new rules to propose." if none]

## Next Task
**What:** [action]
**Where:** [file path(s)]
**Why:** [impact]
**How:** [approach]

## Trend
[Table of last 5 scans from health_history.json if available, otherwise "First scan — no trend data yet."]

## Recommendations
[Re-baseline recommendation from Playbook 6, or "Project is within normal parameters. No deep scan needed."]
```

Then append the current health scores to `.archie/health_history.json`. If the file exists, read it, parse the JSON array, append the new entry, and write it back. If it doesn't exist, create it with a single-element array. Each entry:
```json
{"timestamp": "YYYY-MM-DDTHH:MM:SS", "erosion": 0.00, "verbosity": 0.00, "violations": 0, "cycles": 0, "scan_number": 1, "scan_type": "fast"}
```

## Step 4: Present to user and process adoptions

Print a summary to the user (not the full report — they can read the file). Include:
- Health scores with trend arrows
- Count of errors, warnings, cycles
- The proposed rules with checkboxes
- The next task recommendation
- Path to the full report: `.archie/scan_report.md`

Then say:

> Review the proposed rules above. Tell me which ones to adopt (they'll be enforced on your next scan and in real-time hooks). Tell me which ones to ignore — I won't propose them again.

Wait for the user's response. Then:
- **Adopted rules:** Read `.archie/rules.json` (or start with `{"rules": []}`), append each adopted rule as a new entry, write it back.
- **Ignored rules:** Read `.archie/ignored_rules.json` (or start with `{"ignored": []}`), append each ignored rule description, write it back.

Confirm what was saved.

## Cleanup

```bash
rm -f /tmp/archie_health.json /tmp/archie_violations.json /tmp/archie_cycles.json
```

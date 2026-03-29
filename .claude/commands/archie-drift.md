# Archie Drift — Architecture Divergence Detection

Detect where the codebase diverges from its own architectural patterns. Combines mechanical script analysis with deep AI review.

## Usage modes

The user may invoke this as:
- `/archie-drift` — full drift analysis (script + AI + diff against previous if exists)
- `/archie-drift history` — show trend over time

Check the user's message for which mode. Default to full analysis if no mode specified.

---

## Full analysis

### Phase 1: Mechanical drift scan

```bash
python3 .archie/drift.py "$PWD"
```

This runs instantly — catches pattern divergences, dependency violations, naming violations, structural outliers, anti-pattern clusters. It also saves a timestamped snapshot for future diffing.

### Phase 2: Deep architectural drift (AI)

Identify files to analyze. Use git to find recently changed files:
```bash
git log --name-only --pretty=format: --since="30 days ago" -- '*.kt' '*.java' '*.swift' '*.ts' '*.tsx' '*.py' '*.go' '*.rs' | sort -u | head -100
```
If this returns nothing (new repo or no recent changes), use all source files from the scan:
```bash
python3 .archie/extract_output.py recent-files ".archie/scan.json"
```

For each file (batch into groups of ~15), collect:
- The file's content
- Its folder's CLAUDE.md (per-folder patterns, anti-patterns)
- Its parent folder's CLAUDE.md if it exists

Read `$PWD/.archie/blueprint.json` — specifically `decisions.key_decisions`, `decisions.decision_chain`, `decisions.trade_offs` (with `violation_signals`), `pitfalls` (with `stems_from`), `communication.patterns`, `development_rules`.

Read `$PWD/.archie/drift_report.json` (mechanical findings from Phase 1).

Spawn a **Sonnet subagent** (`model: "sonnet"`) with the file contents, their folder CLAUDE.md files, and the blueprint context. Tell it:

> You are an architecture reviewer. You have the project's architectural blueprint (decisions, trade-offs, pitfalls, patterns), per-folder CLAUDE.md files describing expected patterns, mechanical drift findings (already detected), and source files to review.
>
> Find **deep architectural violations** — problems that pattern matching cannot catch. For each finding, return:
> - `folder`: the folder path
> - `file`: the specific file
> - `type`: one of `decision_violation`, `pattern_erosion`, `trade_off_undermined`, `pitfall_triggered`, `responsibility_leak`, `abstraction_bypass`
> - `severity`: `error` or `warn`
> - `decision_or_pattern`: which architectural decision, pattern, or pitfall this violates (reference by name from the blueprint)
> - `evidence`: the specific code (function name, class, line pattern) that demonstrates the violation
> - `message`: one sentence explaining what's wrong and why it matters
>
> Focus on:
> 1. **Decision violations** — code that contradicts a key architectural decision
> 2. **Pattern erosion** — code that doesn't follow the patterns described in its folder's CLAUDE.md
> 3. **Trade-off undermining** — code that works against an accepted trade-off (check `violation_signals`)
> 4. **Pitfall triggers** — code that falls into a documented pitfall (check `stems_from` chains)
> 5. **Responsibility leaks** — a component doing work that belongs to another component
> 6. **Abstraction bypass** — code reaching through a layer instead of using the intended interface
>
> Do NOT report: style/formatting/naming (the script handles those), generic best-practice violations not grounded in THIS project's blueprint, or issues already in the mechanical drift report.
>
> Return JSON: `{"deep_findings": [...]}`

Save the deep findings:
```
Write /tmp/archie_deep_drift.json with the agent's COMPLETE output text
```
```bash
python3 .archie/extract_output.py deep-drift /tmp/archie_deep_drift.json ".archie/drift_report.json"
rm -f /tmp/archie_deep_drift.json
```

### Phase 3: Present the combined report

Read `$PWD/.archie/drift_report.json` (now contains both mechanical and deep findings).

**If a previous snapshot exists**, the script already auto-diffed and saved `.archie/drift_diff.json`. Read it if it exists — it contains `previous_total`, `current_total`, `new_findings`, `resolved_findings`, and `persisting_findings` counts.

Present to the user:

**If previous snapshot exists — show delta first:**
> Drift: N → M (+/-X) since last run

Then highlight **NEW findings** (regressions) and **RESOLVED findings** (fixed) prominently. Persisting findings get a count only.

**Deep architectural findings** (from AI analysis):
- For each: the file, which decision/pattern it violates, the evidence, and why it matters
- Group related findings (e.g., multiple files violating the same decision)

**Mechanical findings** (from script):
- Pattern divergences, dependency violations, naming violations, structural outliers, anti-pattern clusters
- For each: what diverged, why it matters, suggested action

**Summary:**
- Total: N mechanical + M deep findings
- Health verdict in one sentence
- Top 3 actions to take, ordered by impact

---

## History mode

```bash
python3 .archie/drift.py history "$PWD"
```

Present the snapshot timeline showing how drift has evolved. Highlight trends: improving (fewer findings), worsening (more findings), or stable.

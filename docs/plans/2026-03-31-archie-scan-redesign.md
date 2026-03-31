# Archie Scan Redesign — Fast Incremental + Deep Baseline

## Problem

Archie's current `/archie-init` takes 15-20 minutes and is a one-time ceremony. Users expect a fast, repeatable workflow — run it often, improve gradually. Research (SlopCodeBench, arxiv.org/html/2603.24755v1) proves AI agents degrade codebases in 80% of iterative trajectories. Prompt-based mitigations don't stop the degradation slope. External enforcement with measurable health tracking is needed.

## Design

### Two commands

**`/archie-scan`** — Daily driver. 1-3 minutes. Reads entire project via skeletons + selective full reads. Checks against 40+ predefined universal rules + platform-specific rules + project-learned rules. One orchestrator agent follows playbooks (like Xcode Build Optimization Agent pattern). Produces a report with architecture overview, health scores, findings, proposed rules with adopt/ignore checkboxes, and a suggested next task. User reviews and adopts rules — enforced on future scans and via hooks. Tracks trend over time. Recommends `/archie-deep-scan` when drift threshold exceeded or on first run.

**`/archie-deep-scan`** — Comprehensive baseline. 15-20 minutes. Everything `/archie-scan` does (same health metrics) plus full blueprint (decisions, trade-offs, pitfalls, component boundaries), per-folder CLAUDE.md, comprehensive rules.json, root CLAUDE.md and AGENTS.md. Enriches future `/archie-scan` runs with project-specific architectural knowledge.

### The loop

```
/archie-scan → value in 2 min, proposes rules, recommends deep scan
         ↓ user runs deep scan when ready
/archie-deep-scan → comprehensive baseline, enriches future scans
         ↓ back to daily workflow
/archie-scan → now with blueprint context, richer findings
         ↓ repeated
/archie-scan → rules accumulate, trend tracked
         ↓ drift exceeds threshold
/archie-deep-scan → re-baseline
```

### `/archie-scan` workflow

**Phase 1 — Analyze (always runs, 1-3 min)**

Step 1: Scripts scan the entire project (5-10 seconds, no AI)
- `scanner.py` → file tree, skeletons (signatures, imports, headers), import graph
- `measure_health.py` (NEW) → per-function cyclomatic complexity, per-file verbosity/duplication
- `check_rules.py` (NEW) → predefined checks (universal + platform) + project rules from rules.json
- `detect_cycles.py` (NEW) → circular dependency detection from import graph
- Git diff since last scan (if previous scan exists)
- Compare current skeletons vs previous scan skeletons

Step 2: One orchestrator agent (1-2 min)
- Gets: full skeletons (entire project map)
- Gets: all script findings (complexity hotspots, cycles, violations)
- Gets: blueprint.json (if exists from deep scan)
- Gets: previous scan report (for trending)
- Reads: flagged files fully (god-functions, cycle participants, violations)
- Follows playbooks:
  - Universal architectural checks (40+ predefined)
  - Platform-specific checks (Android/Swift/React/Python/Go/etc.)
  - Project-specific checks (from rules.json + blueprint decisions)
  - Pattern discovery (propose new project-specific rules)
  - Health scoring (erosion + verbosity + architectural integrity)
  - Architecture overview (5-10 line summary proving comprehension)
- Produces: scan_report.md

Step 3: Save (instant)
- `.archie/scan_report.md` — human-readable with checkboxes
- `.archie/scan_history/scan_<timestamp>.json` — machine-readable for trending
- Print summary to user

**Phase 2 — Fix (only if user asks)**

User says "fix finding #3" or "apply the refactoring" → agent applies fix, verifies. Not automatic, not expected. The core value is the report and adopted rules, not automated fixes.

**After user reviews report:**
- Checked rules → added to `rules.json`, enforced by hooks and future scans
- Ignored rules → added to `ignored_rules.json`, never re-proposed
- Health scores → logged to `health_history.json`

### `/archie-deep-scan` workflow

Same as current `/archie-init` (Steps 1-10) with two additions:
1. Computes the same health metrics (erosion, verbosity) using the same scripts
2. Preserves rules.json accumulated from previous scans (doesn't reset learned knowledge)

Produces: blueprint.json, per-folder CLAUDE.md, AGENTS.md, CLAUDE.md, comprehensive rules.json, health scores — all on the same scale as `/archie-scan` for unified trending.

### Predefined checks (shipped with Archie)

**Universal (any language, 40+ checks):**
- God-functions: CC > 15
- God-classes: > 30 public methods or > 500 lines
- Circular dependencies between modules/packages
- Duplicate code blocks (>10 lines repeated)
- Deep nesting (> 4 levels)
- Files with mixed responsibilities (unrelated exports)
- High fan-in functions (called from >10 files)
- High fan-out functions (calls >10 modules)
- Unused/orphan files (imported by nothing)
- Growing functions (CC increased since last scan)

**Platform — Android/Kotlin:**
- ViewModel references android.content.Context
- Fragment does direct network calls
- Repository not using coroutine dispatcher
- Koin module not registered in Application
- Activity/Fragment exceeds 300 lines

**Platform — Swift/iOS:**
- SwiftUI body exceeds 50 lines
- ViewController exceeds 400 lines
- Actor with externally mutable state
- Massive AppDelegate

**Platform — TypeScript/React:**
- Hook called conditionally
- Component exceeds 200 lines
- Prop drilling depth > 3
- useEffect with missing dependencies

**Platform — Python:**
- Circular imports
- God-module (>20 exports)
- Missing type hints on public functions
- Bare except clauses

### Health metrics (computed by both commands)

**Erosion score** (from SlopCodeBench paper):
```
Erosion = Σ(f∈F, CC(f)>10) mass(f) / Σ(f∈F) mass(f)
where mass(f) = CC(f) × √SLOC(f)
```
Fraction of codebase complexity concentrated in high-complexity functions. Rising = bad.

**Verbosity score** (from SlopCodeBench paper):
```
Verbosity = {flagged_lines ∪ clone_lines} / total_LOC
```
Ratio of redundant/duplicated code. Rising = bad.

**Violation count**: rules broken per scan.

**Trend**: direction over last N scans. Both commands produce comparable numbers.

### Scan report format

```markdown
# Archie Scan Report
> Scan #4 | 2026-03-31 | 502 files | 8 changed since last scan

## Architecture Overview
Single-activity Android app (Kotlin) with MVVM + Koin DI.
10 feature pages (page_*) each owning Fragment + ViewModel + Cells.
Shared domain layer with 4 repositories wrapping Retrofit + SharedPreferences.
Cross-feature coordination via MainController SharedFlow event bus.

## Health Scores
| Metric | Current | Previous | Trend |
|--------|---------|----------|-------|
| Erosion | 0.37 | 0.34 | ⚠ rising |
| Verbosity | 0.23 | 0.21 | ⚠ rising |
| Violations | 5 | 4 | ⚠ rising |

## Findings (ranked by impact)
1. [ERROR] SettingsRepositoryImpl.saveSettings() CC=18 (was 11)
2. [WARN] Duplicate error handling across 3 features
3. [WARN] NewFeatureFragment bypasses DI
...

## Proposed Rules
- [ ] Adopt: "Functions exceeding CC>15 must be refactored"
- [ ] Adopt: "All Fragments must use Koin viewModel{} delegation"
- [x] Ignore: "File names must use PascalCase"

## Next Task
Refactor SettingsRepositoryImpl.saveSettings() — CC growing,
on track to become god-function. Extract Firebase upload logic.

## Trend
Erosion:   0.31 → 0.32 → 0.34 → 0.37  ⚠
Verbosity: 0.19 → 0.20 → 0.21 → 0.23  ⚠

💡 For deeper analysis — architectural decisions, component
boundaries, per-folder docs — run /archie-deep-scan
```

### Shared artifacts

| Artifact | Written by | Read by | Purpose |
|----------|-----------|---------|---------|
| `.archie/health_history.json` | Both commands | Both commands | Trend tracking |
| `.archie/rules.json` | Both commands | Both commands + hooks | Grows over time |
| `.archie/ignored_rules.json` | `/archie-scan` | `/archie-scan` | Don't re-propose |
| `.archie/platform_rules.json` | Installer | Both commands | Predefined checks |
| `.archie/blueprint.json` | `/archie-deep-scan` | `/archie-scan` | Project-specific context |
| `.archie/scan_report.md` | `/archie-scan` | User | Latest report |
| `.archie/scan_history/` | Both commands | Both commands | Historical data points |
| `.archie/skeletons.json` | Scanner | Both commands | Project structure map |

### Enforcement hooks

- **Pre-write hook**: checks every file edit against `rules.json` + `platform_rules.json`
- **Post-plan hook**: reviews plan against blueprint decisions (if blueprint exists)
- **Pre-commit hook**: reviews staged changes against architecture

### Re-baseline trigger

When `/archie-scan` detects significant drift (configurable threshold, default 30% of modules showing new violations or erosion score increased >0.10 since last deep scan), it recommends running `/archie-deep-scan`.

### What stays from current implementation

- Scanner (`scanner.py`) — extended with skeleton extraction
- Drift detection (`drift.py`) — extended with health metrics
- Merge (`merge.py`) — used by deep scan
- Renderer (`renderer.py`) — used by deep scan
- Finalize (`finalize.py`) — used by deep scan
- Intent layer (`intent_layer.py`) — used by deep scan
- Install hooks (`install_hooks.py`) — extended with platform rules
- Extract output (`extract_output.py`) — used by deep scan
- Arch review (`arch_review.py`) — used by hooks

### What's new

- `measure_health.py` — cyclomatic complexity + verbosity measurement
- `check_rules.py` — predefined + project rule checking
- `detect_cycles.py` — import graph cycle detection
- `platform_rules.json` — predefined checks per platform
- `.claude/commands/archie-scan.md` — the fast scan slash command
- Rename current `/archie-init` → `/archie-deep-scan`

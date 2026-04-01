# Metrics Implementation Plan — Aligning Archie with SlopCodeBench

Based on the SlopCodeBench paper (arxiv.org/html/2603.24755v1) and the actual source code at github.com/SprocketLab/slop-code-bench.

## Current State

### What we have (exact match with paper)

**Erosion** — `measure_health.py`
- Formula: `Σ mass(CC>10) / Σ mass(all)` where `mass = CC × √SLOC`
- CC threshold: 10 (matches paper, sourced from Radon standards)
- Output: score 0–1, high-CC function count, max CC, per-function breakdown
- Matches the paper's `mass.py` implementation exactly

### What we have (partial match)

**Verbosity** — `measure_health.py`
- Our formula: `duplicate_lines / total_loc`
- Paper's formula: `(AST-Grep flagged lines ∪ clone lines) / LOC`
- We only have the clone detection half. We're missing the AST-Grep half entirely.
- Our clone detection uses exact line hashing (MD5 of normalized lines, 6-line minimum window)
- Paper's clone detection uses AST hashing with variable/literal normalization (3-line minimum), which catches clones with different variable names

### What we're missing entirely

| Metric | Paper source | What it catches |
|--------|-------------|-----------------|
| AST-Grep waste patterns (137 rules) | `configs/slop_rules.yaml` | Identity comprehensions, single-use vars, verbose type conversions, unnecessary lambdas, manual loops replaceable by builtins |
| AST-based clone detection | `redundancy.py` | Structural clones with different variable names/literals |
| Abstraction waste | `waste.py` | Single-use functions, trivial wrappers, single-method classes, unused variables |
| Gini coefficient of complexity | `mass.py` | How unevenly complexity is distributed (complementary to erosion) |
| Top-20% complexity share | `mass.py` | What % of total mass the top 20% of functions hold |
| LOC trending | Per-checkpoint tracking | Monotonic LOC growth detection |
| Maintainability Index | `line_metrics.py` (via Radon) | Composite readability/maintainability score |

---

## Implementation Plan

### Tier 1: Mechanical metrics for `/archie-scan` (scripts, no AI)

These run in seconds, produce numbers, and can trend over time.

#### 1A. AST-Grep waste pattern detection

**What:** Port the paper's 137 AST-Grep rules (or a subset) to detect wasteful Python patterns. Extend with rules for other languages.

**How:**
- The paper's rules live in `configs/slop_rules.yaml` — YAML format, each rule has an `id`, `pattern` (AST-Grep syntax), `severity`, `category`, and `weight`
- AST-Grep (`sg`) is an open-source tool, installable via npm/cargo/brew
- Create `.archie/slop_rules.yaml` containing the rules
- Add a new script `archie/standalone/ast_waste.py` that:
  1. Checks if `sg` (ast-grep) is available, skips gracefully if not
  2. Runs `sg scan --rule .archie/slop_rules.yaml --json` on source files
  3. Deduplicates flagged lines
  4. Returns `{waste_lines: N, total_loc: N, waste_score: float, violations: [...]}`

**Impact on verbosity formula:**
```
verbosity = (clone_lines ∪ ast_grep_flagged_lines) / total_loc
```
This matches the paper exactly.

**Effort:** Medium — rules exist, need wrapper script + integration into `measure_health.py`

**Language support:**
- Python: 137 rules from paper (ready to port)
- Kotlin/Swift/TypeScript: Need to write equivalent rules (many patterns are universal — identity maps, single-use vars, unnecessary wrappers)
- Start with Python, expand per language

#### 1B. AST-based clone detection (upgrade current)

**What:** Replace our MD5 line-hashing with AST-based structural clone detection that normalizes variable names and literals.

**How:**
- The paper's `redundancy.py` uses tree-sitter to parse AST, then:
  1. Normalizes identifiers → `$VAR1, $VAR2, ...`
  2. Normalizes literals → `$STR, $INT, $BOOL`
  3. Hashes the normalized AST subtree
  4. Groups matching hashes across files
  5. Minimum 3 lines (vs our current 6)
- We could either:
  - **Option A:** Require tree-sitter (adds dependency) — most accurate
  - **Option B:** Improve our line-hashing to normalize identifiers via regex (lighter, less accurate)
  - **Option C:** Keep line-hashing for mechanical scan, use AI for semantic detection in deep scan

**Recommendation:** Option C for now. Our line-hashing is good enough for the mechanical layer. The real gap is AST-Grep patterns, not clone detection sophistication. Semantic duplication is already assigned to the deep scan.

**Effort:** Low if Option C, High if Option A

#### 1C. Abstraction waste detection

**What:** Detect single-use functions, trivial wrappers, single-method classes, unused variables.

**How:**
- The paper's `waste.py` uses tree-sitter AST traversal
- We already have skeleton data (function names, call sites) in `skeletons.json`
- Add `archie/standalone/detect_waste.py` that:
  1. Reads `skeletons.json` for function/class/method definitions
  2. Reads `scan.json` for import graph
  3. Cross-references: which functions are called only once? Which classes have one method?
  4. Returns `{single_use_functions: [...], trivial_wrappers: [...], single_method_classes: [...]}`

**Effort:** Medium — skeleton data gives us most of what we need without tree-sitter

#### 1D. Complexity distribution metrics

**What:** Gini coefficient and top-20% share of complexity mass.

**How:**
- Add to `measure_health.py` alongside erosion:
  ```python
  def _gini_coefficient(masses):
      sorted_m = sorted(m for m in masses if m > 0)
      n = len(sorted_m)
      if n == 0: return 0.0
      total = sum(sorted_m)
      weighted = sum((i+1) * v for i, v in enumerate(sorted_m))
      return (2 * weighted - (n + 1) * total) / (n * total)

  def _top20_share(masses):
      sorted_desc = sorted(masses, reverse=True)
      top_count = max(1, math.ceil(len(sorted_desc) * 0.2))
      return sum(sorted_desc[:top_count]) / sum(sorted_desc)
  ```
- Report alongside erosion: `gini=0.65, top20_share=0.82`

**Effort:** Low — pure math, add to existing function

#### 1E. LOC trending

**What:** Track total LOC in health_history.json so we can detect monotonic growth.

**How:**
- `measure_health.py` already computes `total_loc` — just add it to the output
- `archie-scan.md` already appends to `health_history.json` — add `total_loc` field
- Report LOC growth rate in scan: `LOC: 12,450 (+340 since last scan, +8.2% since baseline)`

**Effort:** Very low — one field addition

---

### Tier 2: AI-powered metrics for `/archie-deep-scan`

These require understanding intent and can't be automated mechanically.

#### 2A. Semantic duplication detection (already added)

**What:** Functions with different signatures but same logic.

**Status:** Already added to deep scan drift agent prompt in this session. The agent looks for `semantic_duplication` finding type and Part 6 of the assessment presents results.

**Enhancement:** After deep scan, save the semantic duplication count to `health_history.json` so `/archie-scan` can reference it:
```
| Semantic duplication | 7 groups (from last deep scan on 2026-03-31) | Run /archie-deep-scan to refresh |
```

#### 2B. Architectural lock-in detection

**What:** The paper's #1 degradation pattern — early design decisions that force cascading rewrites.

**How:** Already partially covered by the deep scan's decision chain analysis and pitfall detection. Could be made more explicit:
- In the drift agent prompt, add: "Identify architectural lock-in — places where an early design decision has forced workarounds, god-functions, or cascading patches in later code. Look for functions that grew significantly because the original abstraction couldn't accommodate new requirements."

**Effort:** Low — prompt enhancement

#### 2C. Complexity concentration trajectory

**What:** The paper tracks how specific functions grow over time (e.g., `find_matches_in_file()` growing from 84 to 1,099 lines).

**How:**
- After each scan, save per-function CC to a compact format in `.archie/function_history.json`
- On subsequent scans, compare: which functions grew in CC? Which crossed the threshold?
- Report: "3 functions increased in complexity since last scan: `parse_config()` CC 8→14, `handle_request()` CC 12→19"

**Effort:** Medium — needs per-function tracking infrastructure

---

### Tier 3: Enhanced health table

After implementing tiers 1-2, the scan health table becomes:

```
| Metric | Score | Meaning |
|--------|-------|---------|
| Erosion | 0.41 | Moderate — 41% of complexity mass in high-CC functions |
| Gini | 0.72 | High — complexity very unevenly distributed |
| Verbosity | 0.18 | High — 18% of code is duplicated or wasteful |
|   ├ Clone lines | 0.05 | 5% exact structural duplication |
|   └ AST waste | 0.14 | 14% flagged by waste pattern rules |
| Abstraction waste | 12 | 8 single-use functions, 3 trivial wrappers, 1 single-method class |
| LOC | 12,450 | +340 since last scan (+2.8%) |
| Semantic duplication | 7 groups | From deep scan 2026-03-31 — run /archie-deep-scan to refresh |
```

---

## Priority Order

1. **1E. LOC trending** — trivial, high value for detecting growth
2. **1D. Complexity distribution** — trivial, enriches erosion story
3. **1A. AST-Grep waste patterns** — biggest gap vs paper, highest impact on verbosity accuracy
4. **1C. Abstraction waste** — leverages existing skeleton data
5. **2C. Complexity trajectory** — per-function trending
6. **1B. AST clone upgrade** — lowest priority, current approach is adequate for mechanical layer

## Dependencies

- AST-Grep (`sg` binary) — needed for 1A. Optional dependency, graceful skip if missing.
- No other external dependencies required. Everything else builds on existing `skeletons.json`, `scan.json`, and Python stdlib.

## Paper Alignment Summary

| Paper metric | Archie today | After implementation |
|-------------|-------------|---------------------|
| Erosion | Exact match | + Gini + top-20% share |
| Verbosity (clone) | Partial — line hashing only | Same (AST clones via deep scan) |
| Verbosity (AST-Grep) | Missing | Full — 137+ rules |
| Verbosity (combined) | Missing | Exact paper formula |
| Abstraction waste | Missing | Skeleton-based detection |
| Semantic duplication | Deep scan only | Deep scan + cached in fast scan |
| LOC trending | Missing | Per-scan tracking |
| Complexity trajectory | Missing | Per-function history |
| Gini/concentration | Missing | Added to erosion |
| Maintainability Index | Missing | Consider adding (Radon-based) |

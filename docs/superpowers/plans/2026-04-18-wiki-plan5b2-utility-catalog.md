# LLM Wiki — Plan 5b.2: Utility / Helper Catalog

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the project's reusable utility/helper functions into a single browsable catalog so agents don't reimplement `formatDate`, `deduplicate`, or language-specific extension methods that already exist.

**Architecture:** `scanner.py` gains lightweight language-specific function-extraction (regex-based). Emits `scan.json.symbols[]`. `wiki_builder.py` gains `render_utilities_catalog()` — a single `utilities.md` page grouping functions by a heuristic category (derived from filename + function name). Zero new AI calls; deterministic extraction.

**Tech Stack:** Python 3.9+ stdlib, pytest. Scanner already has framework detection for language routing — we reuse it.

**Depends on:** Plan 5a merged. Independent of Plan 5b.1.

**Reference spec:** Spec gets Section 4.9 "Utilities catalog" in Task 7.

---

## File structure (this plan)

**Modified files:**
- `archie/standalone/scanner.py` — new function-extraction pass for each supported language
- `archie/standalone/wiki_builder.py` — new `render_utilities_catalog()` + `build_wiki` call → `utilities.md`
- `tests/test_scanner.py` — language-specific extraction tests
- `tests/fixtures/sample_sources/` — NEW directory with minimal source files per language for scanner tests
- `tests/test_wiki_builder.py` — render test
- `tests/test_wiki_integration.py` — e2e asserting `utilities.md` exists and has categorized functions
- `npm-package/assets/scanner.py`, `wiki_builder.py` — sync
- `docs/superpowers/specs/2026-04-17-llm-wiki-design.md` — Section 4.9

---

## Scanner extension — language-specific function extraction

### Supported languages (v1 scope — extend later as needed)

- **Swift** (iOS projects): `func name(params) -> Return` patterns, including extension methods
- **TypeScript / JavaScript**: `export function` + `export const X = (…) =>` + class static methods
- **Python**: `def name(params) -> Return` at module level
- **Kotlin**: `fun name(params): Return` (out of scope for v1 — add later)
- **Go**: `func Name(params) Return` (out of scope for v1)

### Extraction heuristic (per language)

A function is a "utility" worth cataloging when:
- `exported` or `public` (language-specific predicate)
- Top-level (not inside a non-utility class) OR an extension method
- File is NOT a test file (filter by path: `*Tests/`, `__tests__/`, `*_test.py`, `*.test.ts`, etc.)
- SLOC ≥ 3 (anti-trivial — uses existing CC/SLOC data from scanner)
- Name does NOT start with `_` (convention for private)

### Output schema

`scan.json.symbols[]`:
```json
{
  "file": "Sources/Extensions/Date+Ext.swift",
  "name": "formatLocalizedDate",
  "kind": "function",
  "signature": "func formatLocalizedDate(_ date: Date, locale: Locale = .current) -> String",
  "exported": true,
  "language": "swift"
}
```

---

## Task 1: Sample source fixtures for scanner tests

**Files:** `tests/fixtures/sample_sources/` (new directory)

Create minimal source files per supported language:
- `fixtures/sample_sources/swift/Extensions.swift` — 3 functions: one `public func`, one `extension String { public func trimmed() }`, one `private func _internalHelper`
- `fixtures/sample_sources/typescript/utils.ts` — 3 functions: `export function formatDate`, `export const deduplicate = (arr) => …`, `function privateHelper`
- `fixtures/sample_sources/python/helpers.py` — 3 functions: module-level `def format_time`, `def _private_helper`, `class Foo: def method`

**Steps:**
- [ ] **Step 1:** Create directory + 3 sample files
- [ ] **Step 2:** Commit: `test(scanner): add sample sources for function extraction`

---

## Task 2: Swift function extraction

**Files:**
- Modify: `archie/standalone/scanner.py`
- Modify: `tests/test_scanner.py`

**New function in scanner.py:**
```python
def _extract_swift_functions(content: str, path: str) -> list[dict]:
    """Regex-based extraction of top-level + extension methods from Swift source."""
```

Handle:
- `public func name(params) -> Return {` → top-level function
- `extension Type { public func name(...) ... }` → extension method
- Skip `private func`, `fileprivate func`, `internal func` (configurable)

Test against `fixtures/sample_sources/swift/Extensions.swift`:
- [ ] **Step 1:** Write test extracting 2 public functions (excluding private)
- [ ] **Step 2:** Verify FAIL
- [ ] **Step 3:** Implement `_extract_swift_functions` using regex patterns described in the plan overview
- [ ] **Step 4:** Verify PASS
- [ ] **Step 5:** Commit: `feat(scanner): extract Swift public functions`

---

## Task 3: TypeScript/JavaScript extraction

**Files:** Same

**Patterns to match:**
- `^export\s+(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)`
- `^export\s+const\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>`
- `^export\s+class\s+(\w+)` (note class for reference) + static methods

Skip: `function _name`, non-exported functions, type aliases.

**Steps:**
- [ ] **Step 1:** Test against `typescript/utils.ts` — expect `formatDate` and `deduplicate` extracted; `privateHelper` skipped
- [ ] **Step 2:** Implement `_extract_typescript_functions`
- [ ] **Step 3:** Verify PASS
- [ ] **Step 4:** Commit: `feat(scanner): extract TypeScript/JavaScript exported functions`

---

## Task 4: Python extraction

**Files:** Same

**Pattern:** `^def\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*([^:]+))?:` at column 0 (no indentation = module-level).

Skip: `_name`, functions inside classes (indented), decorated-only-once (we accept decorator-less and single-decorator forms).

**Steps:**
- [ ] **Step 1:** Test against `python/helpers.py`
- [ ] **Step 2:** Implement `_extract_python_functions`
- [ ] **Step 3:** Verify PASS
- [ ] **Step 4:** Commit: `feat(scanner): extract Python module-level functions`

---

## Task 5: Wire extraction into scanner main loop

**Files:**
- Modify: `archie/standalone/scanner.py`
- Modify: `tests/test_scanner.py`

Extend the scanner's per-file walk so that when a supported language is detected, the corresponding extract function is called and results accumulate into a top-level `symbols[]` array in the scan output.

Filter test files (by path pattern) at this stage.

Integration test:
```python
def test_scan_fixture_project_produces_symbols(tmp_path):
    # Copy sample_sources dir into tmp_path; run scanner; assert symbols[] has expected entries
    ...
```

- [ ] **Step 1:** Integration test
- [ ] **Step 2:** Wire extraction dispatch into scanner main loop
- [ ] **Step 3:** Verify PASS
- [ ] **Step 4:** Commit: `feat(scanner): emit symbols[] with extracted functions`

---

## Task 6: `render_utilities_catalog` + utilities.md

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_builder.py`
- Modify: `tests/test_wiki_integration.py`

**Input sources:**
- `scan.json.symbols[]` (preferred, deterministic)
- Optional: `blueprint.utilities[]` if some future AI step enriches the catalog

**Categorization heuristic:**
- From filename: `DateExt.swift` / `Date+Ext.swift` / `date-utils.ts` / `date_helpers.py` → "Date"
- From function name prefix: `format*` → "Formatting", `is*` / `has*` → "Predicate", `to*` → "Conversion"
- Fallback: "Uncategorized"

**Page structure:**
```markdown
---
type: utilities-catalog
slug: utilities
---

# Utilities catalog

Reusable helper functions discovered in the codebase. Grep the wiki before implementing similar logic.

## Date (3 functions)

- **`formatLocalizedDate(_ date: Date, locale: Locale = .current) -> String`**
  `Sources/Extensions/Date+Ext.swift`
- **`daysBetween(_ a: Date, _ b: Date) -> Int`**
  `Sources/Extensions/Date+Ext.swift`

## String (2 functions)

- **`String.trimmed() -> String`** _(extension)_
  `Sources/Extensions/String+Ext.swift`

## Uncategorized (N)
...
```

Render function signature compactly. Include file path so agents can grep immediately.

**Steps:**
- [ ] **Step 1:** Write unit test for `render_utilities_catalog` with synthetic `symbols[]`
- [ ] **Step 2:** Verify FAIL
- [ ] **Step 3:** Implement. Derive categorization from filename + name patterns.
- [ ] **Step 4:** Write integration test — runs scanner on sample_sources fixture, then wiki_builder, asserts `utilities.md` exists with categorized entries.
- [ ] **Step 5:** Verify PASS
- [ ] **Step 6:** Commit: `feat(wiki): render utilities catalog from scan symbols`

---

## Task 7: Index entry + NPM sync + spec update

**Files:**
- Modify: `archie/standalone/wiki_builder.py` — index gets "Utilities" entry in Browse by type
- Modify: `npm-package/assets/scanner.py`, `wiki_builder.py`
- Modify: `docs/superpowers/specs/2026-04-17-llm-wiki-design.md` — Section 4.9

**Steps:**
- [ ] **Step 1:** Add Utilities row to `## Browse by type` in render_index: `**Utilities (N functions)** — existing helpers; grep before implementing new ones`
- [ ] **Step 2:** Also emit `## Utilities` section in index listing the catalog page link (not per-function)
- [ ] **Step 3:** NPM sync + verify_sync
- [ ] **Step 4:** Add Section 4.9 to spec
- [ ] **Step 5:** Commit: `feat(wiki): add utilities browse entry + sync`

---

## Task 8: Verification on Gasztroterkepek + real-world tuning

**Verification only.**

After Plan 5b.2 merge:

1. Copy the updated scanner.py + wiki_builder.py into Gasztroterkepek's `.archie/`.
2. Re-run `/archie-scan` on Gasztroterkepek (this updates scan.json + triggers incremental wiki).
3. Inspect `.archie/wiki/utilities.md`:
   - Should list `Extensions.swift` methods
   - Should list standalone services' public methods (if they qualify)
4. Check for false positives: obvious non-utility code appearing (e.g., ViewController lifecycle methods). Filter list if needed (heuristic tightening).

- [ ] **Step 1:** Copy scripts + run scan
- [ ] **Step 2:** Inspect utilities.md quality — tune heuristics if needed (tighten `SLOC ≥ 3`? add suffix filters?)
- [ ] **Step 3:** Agent-probe: "Is there a formatDate function?" — should find it
- [ ] **Step 4:** If tuning needed, commit as a follow-up: `fix(scanner): tighten utility filter heuristics`

---

## Self-review checklist

- [ ] All previous tests still pass.
- [ ] Scanner emits `symbols[]` for Swift, TS/JS, Python at minimum.
- [ ] `utilities.md` renders with at least 2 categories on the fixture.
- [ ] `verify_sync.py` passes.
- [ ] Gasztroterkepek smoke shows real utility functions (not false positives dominating).
- [ ] Spec Section 4.9 documents the page format.

## Known follow-ups / explicit non-goals

- **Kotlin / Go / Rust / Java extraction** — add as follow-up when projects appear that need them. The v1 scope covers Swift + TS/JS + Python, which are Archie's current dominant language targets.
- **Function-body content extraction** (to render usage examples) — out of scope. We list name + signature + location only.
- **AI-enhanced categorization** — if filename heuristics prove too weak, a post-scan Haiku pass could re-categorize. Consider if utilities.md gets crowded.
- **Per-function pages** — v1 uses a single flat catalog page. If projects with >100 utilities emerge, consider splitting into `utilities/<category>.md` per-category pages.
- **Calling-convention inference** — current extraction reports signatures literally. No normalization across languages. An agent seeing `func formatDate(_ date: Date)` vs `function formatDate(date: Date)` will understand both.

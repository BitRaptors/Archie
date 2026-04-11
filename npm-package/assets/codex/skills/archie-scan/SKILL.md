---
name: archie-scan
description: Architecture health check for the current project. Runs the Archie scanner, analyzes the codebase against the existing blueprint, and produces AGENTS.md plus rule files. ~1-3 minutes.
---

# archie-scan

Run an architecture health check on the current project. This is the fast,
incremental scan — for the comprehensive baseline, use `archie-deep-scan` instead.

## Steps

1. **Run the deterministic data-gathering scripts.** These populate `.archie/`
   with everything the analysis step needs. No AI involved. Run all three:

   ```bash
   python3 .archie/scanner.py "$PWD"
   python3 .archie/measure_health.py "$PWD" > .archie/health.json 2>/dev/null
   python3 .archie/detect_cycles.py "$PWD" --full 2>/dev/null
   ```

   `scanner.py` writes both `.archie/scan.json` and `.archie/skeletons.json`.
   `measure_health.py` writes its JSON output to stdout — the redirect captures
   it into `.archie/health.json`. `detect_cycles.py` writes
   `.archie/dependency_graph.json` directly.

   If any of these commands fails or the scripts don't exist in `.archie/`, stop
   and tell the user to run `npx @bitraptors/archie .` first.

2. **Read the scan analyzer prompt and follow it.** Your full instructions for the
   analysis step live in a shared prompt file:

   ```bash
   cat .archie/prompts/scan_analyzer.md
   ```

   Read that file in full, then perform the analysis it describes. Your inputs are:

   Always present after step 1 (required):
   - `.archie/scan.json` — file tree, import graph, frameworks
   - `.archie/skeletons.json` — every file's header, imports, class/function
     signatures (this is the primary reading surface — prefer it over reading
     full source files)
   - `.archie/health.json` — erosion, gini, verbosity, per-function complexity
   - `.archie/dependency_graph.json` — directory-level graph with cycles, degrees,
     cross-component edges

   Accumulated state from prior runs (optional — may be missing on early scans):
   - `.archie/blueprint.json` — accumulated architectural baseline (from a prior
     `archie-deep-scan`)
   - `.archie/scan_report.md` — last scan report
   - `.archie/health_history.json` — health trend over time
   - `.archie/function_complexity.json` — per-function complexity history
   - `.archie/rules.json` — adopted rules
   - `.archie/proposed_rules.json` — rules from prior scans not yet adopted

   Produce the JSON output described in the prompt and save it to
   `.archie/scan_analysis.json`.

3. **Render the context files.** This converts the analysis into AGENTS.md and
   rule files using the deterministic renderer.

   ```bash
   python3 .archie/renderer.py "$PWD" --target=codex
   ```

   The `--target=codex` flag ensures only `AGENTS.md` is written (not `CLAUDE.md`).

4. **Run the validator** to cross-check the output against the actual codebase
   and surface any rule violations.

   ```bash
   python3 .archie/validate.py all "$PWD"
   ```

5. **Summarize for the user.** In your final message, report:
   - Top 3 health findings from the analysis
   - Any new rules proposed (and where they came from)
   - Whether `AGENTS.md` was updated and what changed
   - Any validation errors that need attention

## Notes

- This skill does not spawn parallel sub-agents. The analysis runs in your single
  turn. For projects > 50k LOC, this is fine; for very large monorepos, consider
  `archie-deep-scan` which uses parallel Wave 1 / Wave 2 analysis.
- All Archie analysis scripts under `.archie/` are pure Python with no external
  dependencies beyond Python 3.9+.
- The prompt at `.archie/prompts/scan_analyzer.md` is shared with the Claude Code
  version of this command — both targets get the same analysis instructions.

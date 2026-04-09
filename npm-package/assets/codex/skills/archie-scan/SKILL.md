---
name: archie-scan
description: Architecture health check for the current project. Runs the Archie scanner, analyzes the codebase against the existing blueprint, and produces AGENTS.md plus rule files. ~1-3 minutes.
---

# archie-scan

Run an architecture health check on the current project. This is the fast,
incremental scan — for the comprehensive baseline, use `archie-deep-scan` instead.

## Steps

1. **Run the deterministic scanner.** This populates `.archie/scan.json` with the
   file tree, framework detection, and basic metrics. No AI involved.

   ```bash
   python3 .archie/scanner.py "$PWD"
   ```

   If the command fails or `.archie/scanner.py` doesn't exist, stop and tell the
   user to run `npx @bitraptors/archie .` first.

2. **Read the scan analyzer prompt and follow it.** Your full instructions for the
   analysis step live in a shared prompt file:

   ```bash
   cat .archie/prompts/scan_analyzer.md
   ```

   Read that file in full, then perform the analysis it describes. Your inputs are:
   - `.archie/scan.json` (always exists after step 1)
   - `.archie/blueprint.json` (only if a prior deep-scan has run)
   - `.archie/dependency_graph.json` (only if scanner produced one)

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

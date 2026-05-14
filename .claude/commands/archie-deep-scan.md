# Archie Deep Scan — Comprehensive Architecture Baseline

Invoke the `archie-deep-scan` skill via the Skill tool to run a comprehensive architecture baseline scan (15-20 min). The skill produces blueprint.json, per-folder CLAUDE.md files, AI-synthesized rules, health metrics, and drift detection through a two-wave AI analysis.

Pass any arguments the user supplied (e.g. `--incremental`, `--from N`, `--continue`) to the skill via the `args` parameter. The skill's `SKILL.md` lives at `.claude/skills/archie-deep-scan/SKILL.md` and contains the full step-by-step workflow.

If the Skill tool is unavailable, fall back to reading `.claude/skills/archie-deep-scan/SKILL.md` directly and following its instructions.

---
description: Comprehensive architecture baseline (15-20 min). Two-wave AI analysis producing blueprint.json, per-folder CLAUDE.md, AI-synthesized rules, health metrics.
---

Read `.archie/prompts/skill_archie_deep_scan.md` in full and execute the instructions as written.

For Claude Code: the deep-scan body references step files under `.claude/skills/archie-deep-scan/steps/` — those substeps are Claude-specific extensions installed by the npx installer. Other CLIs (Codex, Pi) execute the inlined SKILL body without the substep router; the analysis pipeline produces the same outputs (blueprint, rules, intent layer) regardless.

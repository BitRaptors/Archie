---
name: archie-scan
description: Codex-native architecture health check for Archie. Runs the deterministic scan pipeline and produces scan findings without relying on Claude-only tools.
---

# Archie Scan For Codex

Run Archie's architecture health check in a way that is native to Codex.

This command must not rely on `AskUserQuestion` or Claude's `Agent` tool. If you need input from the user, ask a short plain-text question and wait for the answer.

## Preconditions

- If `.archie/scanner.py` does not exist, stop and tell the user to run `npx @bitraptors/archie "$PWD"` first.
- If you are in `codex exec` with a read-only sandbox, stop and tell the user to rerun with `--sandbox=workspace-write`. The scan writes `.archie/scan.json`, `.archie/health.json`, and related artifacts.
- Use the repo root as the working directory for all commands.

## Phase 0: Resolve scope

Codex does not have `AskUserQuestion`, so adapt the shared Archie scope flow as follows:

- First try:

```bash
python3 .archie/intent_layer.py scan-config "$PWD" read
```

- If config exists, use it.
- If config is missing, detect subprojects:

```bash
python3 .archie/scanner.py "$PWD" --detect-subprojects
```

- If the repo is effectively single-project, persist the `single` scope directly.
- If there are multiple real workspaces, ask the user a concise plain-text scope question that mirrors the shared prompt choices: `Whole`, `Per-package`, `Hybrid`, or `Single`.
- If the user picks `Per-package` or `Hybrid`, ask one follow-up question for the chosen workspaces.
- Persist the chosen config with:

```bash
echo '{"scope":"<chosen>","monorepo_type":"<detected-type>","workspaces":[<array>]}' | python3 .archie/intent_layer.py scan-config "$PWD" write
python3 .archie/intent_layer.py scan-config "$PWD" validate
```

If validation fails because the config drifted, tell the user to rerun with `--reconfigure`.

## Phase 1: Gather deterministic data

Run:

```bash
python3 .archie/scanner.py "$PWD"
python3 .archie/measure_health.py "$PWD" > .archie/health.json 2>/dev/null
python3 .archie/detect_cycles.py "$PWD" --full 2>/dev/null
git log --oneline --since="7 days ago" --name-only 2>/dev/null | sort -u | head -50
```

This should produce:

- `.archie/scan.json`
- `.archie/skeletons.json`
- `.archie/health.json`
- `.archie/dependency_graph.json`

## Phase 2: Read current knowledge

Read these files when present:

- `.archie/scan.json`
- `.archie/skeletons.json`
- `.archie/health.json`
- `.archie/dependency_graph.json`
- `.archie/blueprint.json`
- `.archie/scan_report.md`
- `.archie/health_history.json`
- `.archie/rules.json`
- `.archie/proposed_rules.json`
- `AGENTS.md`

Treat `AGENTS.md` as required context for architectural judgments.

## Phase 3: Analysis

Prefer direct local analysis in Codex. If a safe subagent facility is clearly available, you may use it, but do not depend on it. The command must still complete without Claude-specific agent primitives.

Analyze:

- component structure and dependency direction
- dependency magnets and cycles
- complexity and health hotspots
- new or worsening architectural drift
- candidate enforcement rules grounded in the actual repo

Focus on high-signal findings. Do not pad the output with generic architecture commentary.

## Phase 4: Emit results

Write the scan findings into `.archie/scan_report.md` in the same general shape Archie expects:

- a brief summary
- concrete architectural findings
- health / complexity hotspots
- proposed or adopted rule implications when relevant

If you update any rule-related artifact, keep it consistent with the existing `.archie/*.json` files instead of inventing a new format.

## Completion

Your final response should state:

- what scope was used
- whether the deterministic scan artifacts were refreshed successfully
- the most important findings
- whether any user follow-up is required

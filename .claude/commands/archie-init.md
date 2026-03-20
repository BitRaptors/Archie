# Archie Init — Full Architecture Analysis

Analyze this repository's architecture. Zero dependencies — works with any language.

**Prerequisites:** Run `npx archie-lite` first to install the scripts. If `.archie/scanner.py` doesn't exist, tell the user to run `npx archie-lite` and try again.

## Step 1: Run the scanner

```bash
python3 .archie/scanner.py "$PWD"
```

This produces `.archie/scan.json` with the full local analysis (file tree, dependencies, frameworks, import graph, token counts).

## Step 2: Read the scan results

Read `.archie/scan.json`. Note the total files, detected frameworks, dependencies, and top-level directories. These determine how many subagents to spawn.

## Step 3: Plan subagent groups

Group files by top-level directory. Each group should be under ~150,000 estimated tokens. For small repos (under 150k total), use a single group.

## Step 4: Spawn subagents

For each file group, spawn a Sonnet subagent using the Agent tool with `subagent_type: "Explore"` and `model: "sonnet"`.

Each subagent should read all assigned files and return a JSON object matching the StructuredBlueprint schema. Include these sections: `meta`, `architecture_rules`, `decisions`, `components`, `communication`, `quick_reference`, `technology`, `frontend`, `developer_recipes`, `architecture_diagram`, `pitfalls`, `implementation_guidelines`, `development_rules`, `deployment`.

Tell each subagent to focus on what AI CANNOT infer from individual files: cross-file relationships, implicit contracts, architecture decisions, integration patterns, and conventions that span multiple files.

**Spawn ALL subagents in parallel** (single message with multiple Agent calls).

## Step 5: Merge results

Save each subagent's JSON output to a temporary file (e.g. `/tmp/archie_sub1.json`, `/tmp/archie_sub2.json`). If the output contains markdown or extra text, save the raw text — the merger handles extraction.

Then merge:

```bash
python3 .archie/merge.py "$PWD" /tmp/archie_sub1.json /tmp/archie_sub2.json
```

For a single subagent, you can also pipe directly:

```bash
echo '<subagent output text>' | python3 .archie/merge.py "$PWD" -
```

This produces `.archie/blueprint.json`.

## Step 6: Render outputs

```bash
python3 .archie/renderer.py "$PWD"
```

## Step 7: Generate per-folder CLAUDE.md files

```bash
python3 .archie/intent_layer.py "$PWD"
```

## Step 8: Extract enforcement rules

```bash
python3 .archie/rules.py "$PWD"
```

## Step 9: Install enforcement hooks

```bash
python3 .archie/install_hooks.py "$PWD"
```

## Step 10: Summary

Print what was generated:
- `.archie/blueprint.json` — architecture blueprint
- `.archie/rules.json` — enforcement rules
- `CLAUDE.md` — root architecture context
- `AGENTS.md` — comprehensive agent guidance
- `.claude/rules/` — topic-split rule files
- `.cursor/rules/` — Cursor rule files
- Per-folder `CLAUDE.md` — directory-level context
- `.claude/hooks/` — real-time enforcement hooks

Tell the user: "Archie is now active. Architecture rules will be enforced on every code change."

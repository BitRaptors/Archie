# Archie Init — Full Architecture Analysis

Analyze this repository's architecture. Zero dependencies — works with any language.

**Prerequisites:** Run `npx archie-lite` first to install the scripts. If `.archie/scanner.py` doesn't exist, tell the user to run `npx archie-lite` and try again.

**IMPORTANT: Do NOT write inline Python scripts. Every step uses a pre-installed script from `.archie/`. Just run the bash commands shown. Do NOT generate code to parse JSON, extract data, or create files. The scripts handle everything.**

## Step 1: Run the scanner

```bash
python3 .archie/scanner.py "$PWD"
```

## Step 2: Read scan results

Read `.archie/scan.json`. Note total files, detected frameworks, and top-level directories. If total estimated tokens < 150,000, use 1 subagent. Otherwise split by top-level directory.

## Step 3: Spawn subagents

For each group, spawn a Sonnet subagent (Agent tool, `subagent_type: "Explore"`, `model: "sonnet"`).

Each subagent must read all assigned files and return a JSON object with these sections: `meta`, `architecture_rules`, `decisions`, `components`, `communication`, `quick_reference`, `technology`, `frontend`, `developer_recipes`, `architecture_diagram`, `pitfalls`, `implementation_guidelines`, `development_rules`, `deployment`.

Tell each subagent: "Focus on what AI CANNOT infer from individual files: cross-file relationships, architecture decisions, conventions, integration patterns. Return ONLY valid JSON."

**Spawn ALL subagents in parallel.**

## Step 4: Save subagent output and merge

After each subagent completes, use the Write tool to save its JSON output to a temporary file. Save the COMPLETE output text — the merge script handles JSON extraction.

```
Write /tmp/archie_sub1.json with the first subagent's output
Write /tmp/archie_sub2.json with the second subagent's output (if applicable)
```

Then merge. The merge script normalizes the data to the correct schema automatically:

```bash
python3 .archie/merge.py "$PWD" /tmp/archie_sub1.json /tmp/archie_sub2.json
```

## Step 5: Render all outputs

```bash
python3 .archie/renderer.py "$PWD"
python3 .archie/intent_layer.py "$PWD"
python3 .archie/rules.py "$PWD"
python3 .archie/install_hooks.py "$PWD"
```

Run all four commands. They read `.archie/blueprint.json` and generate everything.

## Step 6: Clean up and summarize

```bash
rm -f /tmp/archie_sub*.json
```

Print what was generated:
- `.archie/blueprint.json` — architecture blueprint
- `CLAUDE.md` — root architecture context
- `AGENTS.md` — comprehensive agent guidance
- `.claude/rules/` — 7 topic-split rule files
- `.cursor/rules/` — Cursor rule files
- Per-folder `CLAUDE.md` — directory-level context
- `.claude/hooks/` — real-time enforcement hooks
- `.archie/rules.json` — enforcement rules

Tell the user: "Archie is now active. Architecture rules will be enforced on every code change."

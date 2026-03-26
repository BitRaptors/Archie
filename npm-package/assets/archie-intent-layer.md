# Archie Intent Layer — AI-Generated Per-Folder CLAUDE.md

Generate per-folder CLAUDE.md files with AI-generated architectural descriptions: purpose, patterns, anti-patterns, code examples. Uses bottom-up DAG scheduling (leaves first, then parents with child context).

**Prerequisites:** Requires `.archie/scan.json` and `.archie/blueprint.json`.

**IMPORTANT: Do NOT write inline Python. Every step uses pre-installed scripts from `.archie/`.**

## Step 1: Prepare the folder DAG

```bash
python3 .archie/intent_layer.py prepare "$PWD"
mkdir -p .archie/enrichments
```

## Step 2: Read the batch plan

Read `.archie/enrich_batches.json`. Note the depth levels and batch IDs.

## Step 3: Process each depth level (deepest first)

For each depth level, process all batches. **All batches within a depth level run in parallel.**

For each batch:

1. Generate the prompt:
```bash
python3 .archie/intent_layer.py prompt "$PWD" <batch_id> --child-summaries .archie/enrichments/ > /tmp/archie_intent_prompt.txt
```

2. Read `/tmp/archie_intent_prompt.txt`

3. Spawn a Sonnet subagent (`model: "sonnet"`) with the prompt content. The subagent must return ONLY valid JSON with folder paths as keys.

4. Save the subagent's JSON output:
```
Write .archie/enrichments/<batch_id>.json with the subagent's JSON output
```

**Wait for all batches in a depth level to complete before moving to the next (shallower) level.** Shallower levels use child summaries from deeper levels.

## Step 4: Merge into CLAUDE.md files

```bash
python3 .archie/intent_layer.py merge "$PWD"
```

## Step 5: Clean up

```bash
rm -f /tmp/archie_intent_prompt.txt
```

Tell the user: "Per-folder CLAUDE.md files have been generated with architectural descriptions."

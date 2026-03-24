# Archie Enrich — AI-Enriched Per-Folder CLAUDE.md

Re-enrich per-folder CLAUDE.md files with AI-generated patterns, anti-patterns, debugging tips, and code examples. Use this after code changes to refresh enrichments, or if you ran `/archie-init` before this feature existed.

**Prerequisites:** Requires `.archie/scan.json` and `.archie/blueprint.json`.

**IMPORTANT: Do NOT write inline Python. Every step uses pre-installed scripts from `.archie/`.**

## Step 1: Prepare the folder DAG

```bash
python3 .archie/enrich.py prepare "$PWD"
mkdir -p .archie/enrichments
```

## Step 2: Process in readiness waves

Maintain a list of done folder paths (starts empty).

**Repeat until done:**

1. Get ready folders (folders whose children are all done, or leaves with no children):
```bash
python3 .archie/enrich.py next-ready "$PWD" <done1> <done2> ...
```
First call with no done folders returns all leaf folders.

2. If the ready list is empty (`[]`), all folders are done. Proceed to Step 3.

3. Get batches for the ready folders:
```bash
python3 .archie/enrich.py suggest-batches "$PWD" <ready1> <ready2> ...
```

4. For each batch, generate the prompt and spawn a subagent:
```bash
python3 .archie/enrich.py prompt "$PWD" --folders <comma-separated> --child-summaries .archie/enrichments/ > /tmp/archie_enrich_prompt.txt
```
Read the prompt file. Spawn a Sonnet subagent (`model: "sonnet"`) with the prompt content. The subagent must return ONLY valid JSON with folder paths as keys.
**Spawn ALL batches in a wave in parallel.**

5. Save each subagent's JSON output:
```
Write .archie/enrichments/<batch_id>.json with the subagent's JSON output
```

6. Add all folders from completed batches to the done list. Go to (1).

## Step 3: Merge enrichments into CLAUDE.md files

```bash
python3 .archie/enrich.py merge "$PWD"
```

## Step 4: Clean up

```bash
rm -f /tmp/archie_enrich_prompt.txt
```

Tell the user: "Per-folder CLAUDE.md files have been enriched with AI-generated developer notes."

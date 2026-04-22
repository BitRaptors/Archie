# Archie Intent Layer — Per-Folder CLAUDE.md Generation

Generate AI-written `CLAUDE.md` for every folder in the project using bottom-up DAG scheduling. Each folder gets a ~80-line architectural description (purpose, patterns, anti-patterns, key files, decisions) so agents editing deep in the tree have folder-local guidance — not just the root CLAUDE.md.

Use this when the user skipped Intent Layer during `/archie-deep-scan` (chose "No — skip Intent Layer" at the prompt), or when `.archie/enrichments/` is empty but a blueprint already exists.

**Prerequisites:** If `.archie/intent_layer.py` doesn't exist, tell the user to run `npx @bitraptors/archie` first.

**CRITICAL CONSTRAINT: Never write inline Python.**
Do NOT use `python3 -c "..."` for inspection, parsing, or transformation. Every operation uses a dedicated `.archie/*.py` command. If you need data not covered by these commands, proceed without it or ask the user. NEVER improvise Python.

---

## Phase 0: Precondition check

The Intent Layer needs BOTH `.archie/scan.json` (file tree) and `.archie/blueprint.json` (architectural context: components, decisions, responsibilities, depends_on, key_interfaces). Without the blueprint, per-folder enrichments cannot be grounded in the project's architecture — they'd be generic file summaries, not architectural guides.

### Check scan.json

```bash
test -f "$PWD/.archie/scan.json"
```

- **Exit 0** → scan.json exists. Continue.
- **Exit 1** → scan.json missing. Run the scanner now:
  ```bash
  python3 .archie/scanner.py "$PWD"
  ```
  Then continue.

### Check blueprint.json (hard requirement)

```bash
test -f "$PWD/.archie/blueprint.json"
```

- **Exit 0** → blueprint exists. Continue to Phase 1.
- **Exit 1** → blueprint missing. **Stop execution.** Print this message verbatim and do not proceed:

  > **Intent Layer requires a blueprint.**
  >
  > Per-folder CLAUDE.md files are architectural descriptions — they need the project's architecture (components, decisions, responsibilities) as grounding. That architecture lives in `.archie/blueprint.json`, which is produced by `/archie-deep-scan`.
  >
  > Run `/archie-deep-scan` first, then come back to `/archie-intent-layer`.

  Do NOT offer a degraded path. Do NOT run a partial blueprint inference. Exit.

### Sanity-check the blueprint

```bash
python3 .archie/intent_layer.py inspect "$PWD" blueprint.json --query .components.components
```

If the output is empty or `null`, the blueprint exists but has no components — it's malformed or mid-scan. Print:

> **Blueprint exists but has no components.** Something interrupted a previous `/archie-deep-scan`. Re-run `/archie-deep-scan` to regenerate the blueprint fully, then come back.

Exit.

---

## Phase 1: Prepare the folder DAG

```bash
python3 .archie/intent_layer.py prepare "$PWD"
python3 .archie/intent_layer.py reset-state "$PWD"
mkdir -p "$PWD/.archie/enrichments"
```

This builds `.archie/enrich_batches.json` — the parent→children dependency graph over every folder with source files (plus structural parents). Leaves are processed first, then parents receive summaries of their children.

Print a one-line progress note to the user: *"Preparing intent layer — N folders queued, processed bottom-up."*  Derive N from:

```bash
python3 .archie/intent_layer.py inspect "$PWD" enrich_batches.json --query '.folders|length'
```

(Wave count is emergent — it depends on the DAG depth and becomes visible as you loop through `next-ready` calls in Phase 2.)

---

## Phase 2: Process folders bottom-up (parallel per wave)

Loop until every folder is enriched.

### Each iteration:

**a. Get the next ready wave:**

```bash
python3 .archie/intent_layer.py next-ready "$PWD"
```

The script reads done state from `.archie/enrich_state.json` automatically. First call returns all leaf folders.

- If the output is an empty array (`[]`), all folders are done. Proceed to Phase 3.
- Otherwise the output is a JSON array of folder paths that are ready (their children are enriched).

**b. Split the ready list into batches:**

```bash
python3 .archie/intent_layer.py suggest-batches "$PWD" <ready1> <ready2> ...
```

Output is a JSON array: `[{"id": "w0", "folders": [...]}, ...]`. Use `id` (NOT `batch_id`) to reference batches.

**c. For each batch, generate the prompt and spawn a Sonnet subagent:**

```bash
python3 .archie/intent_layer.py prompt "$PWD" --folders <comma-separated-folders> --child-summaries "$PWD/.archie/enrichments/" > /tmp/archie_intent_prompt_<batch_id>.txt
```

Read the prompt file. Spawn a Sonnet subagent (`model: "sonnet"`) with the prompt content. The subagent must return ONLY valid JSON with folder paths as keys.

**Spawn ALL batches of one wave in parallel** — they're independent by construction.

**d. After each subagent completes, persist its output:**

```
Write /tmp/archie_enrichment_<batch_id>.json with the subagent's COMPLETE output text
```

```bash
python3 .archie/intent_layer.py save-enrichment "$PWD" <batch_id> /tmp/archie_enrichment_<batch_id>.json
```

This extracts the JSON (handling conversation envelopes, code fences, multi-block merging), saves it to `.archie/enrichments/<batch_id>.json`, and automatically marks the folders as done.

**IMPORTANT: Do NOT try to extract or parse JSON yourself. Do NOT write inline Python to process agent output. The save-enrichment command handles everything.**

**e. Go back to (a) for the next wave.**

---

## Phase 3: Merge enrichments into per-folder CLAUDE.md files

```bash
python3 .archie/intent_layer.py merge "$PWD"
```

This reads every `.archie/enrichments/*.json` and writes a `CLAUDE.md` into each matching folder. Folders that already had a manually-edited `CLAUDE.md` get their notes preserved.

---

## Phase 4: Clean up temp files

```bash
rm -f /tmp/archie_intent_prompt_*.txt /tmp/archie_enrichment_*.json
```

---

## Phase 5: Summary to user

Print a concise summary:

```
✓ Intent Layer complete — N folders enriched, M CLAUDE.md files written.

Per-folder guidance lives at:
  <folder1>/CLAUDE.md
  <folder2>/CLAUDE.md
  ...

Agents editing deep in the tree will now auto-load the closest folder's CLAUDE.md.
Re-run this command after major structural changes, or let /archie-deep-scan regenerate when you re-baseline.
```

Derive N (count of enriched folders) from `.archie/enrich_state.json`:

```bash
python3 .archie/intent_layer.py inspect "$PWD" enrich_state.json --query '.done|length'
```

To list the enriched folder paths themselves:

```bash
python3 .archie/intent_layer.py inspect "$PWD" enrich_state.json --query .done
```

M (CLAUDE.md files written) is reported by `merge` on stderr in Phase 3 — capture it from that output rather than re-computing.

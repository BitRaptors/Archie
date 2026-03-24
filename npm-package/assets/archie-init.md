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

## Step 3: Spawn analysis subagents

For each group, spawn an Opus subagent (Agent tool, `subagent_type: "Explore"`, `model: "opus"`).

Each subagent must read all assigned files and return a JSON object with these sections: `meta`, `architecture_rules`, `decisions`, `components`, `communication`, `quick_reference`, `technology`, `frontend`, `developer_recipes`, `architecture_diagram`, `pitfalls`, `implementation_guidelines`, `development_rules`, `deployment`.

Tell each subagent:

> **GROUNDING RULES — every claim must come from code you READ, never from names or conventions.**
> This applies to ANY codebase — web, mobile, desktop, backend, CLI, library, any language.
>
> 1. **Paths**: Only reference file/directory paths that appear in scan.json file_tree. Do NOT infer conventional paths — every framework has different conventions (Rails uses `spec/`, Go uses `_test.go` files, Swift uses `Tests/`, etc.). Find the ACTUAL paths by reading the code.
> 2. **Component responsibility**: Read the actual source file. Describe what the code DOES, not what the filename or class name suggests. A file named `Publisher.swift` might only subscribe to events. A class named `UserManager` might only read, never write. Only the code tells you which.
> 3. **API/route/endpoint methods**: Read the actual handler code. List ONLY the methods/verbs/actions that are actually implemented. Do NOT assume CRUD from the resource name — a "presets" endpoint might support GET+PUT but not POST. This applies to HTTP routes, gRPC services, GraphQL resolvers, CLI commands, or any interface.
> 4. **File placement rules**: Search the file_tree for where test files, config files, build output, and generated code actually live. Do NOT assume conventional locations — the project might put tests alongside source, in a top-level `test/` dir, or anywhere else.
> 5. **Pitfalls**: Only describe problems grounded in actual code patterns you observed. Describe what the code DOES and the risks of THAT pattern. Do NOT recommend alternatives the code doesn't use as if it does.
> 6. **Build/output paths**: Read the build config, generation logic, or Makefile to find where output is actually written. Do NOT assume any framework's default output directory.
>
> **The rule is simple: if you didn't read it in a file, don't claim it.** Focus on cross-file relationships, architecture decisions, conventions, and integration patterns. Return ONLY valid JSON.

**Spawn ALL subagents in parallel.**

## Step 4: Save subagent output and merge

After each subagent completes, use the Write tool to save its JSON output to a temporary file. Save the COMPLETE output text — the merge script handles JSON extraction.

```
Write /tmp/archie_sub1.json with the first subagent's output
Write /tmp/archie_sub2.json with the second subagent's output (if applicable)
```

Then merge:

```bash
python3 .archie/merge.py "$PWD" /tmp/archie_sub1.json /tmp/archie_sub2.json
```

This saves `.archie/blueprint_raw.json` (raw merged data).

## Step 5: AI-normalize the blueprint

The raw blueprint has correct data but inconsistent field names (subagents return arbitrary shapes). A single AI normalizer call reshapes everything to the canonical schema.

1. Generate the normalizer prompt:
```bash
python3 .archie/normalize.py prompt "$PWD" > /tmp/archie_normalize_prompt.txt
```

2. Read `/tmp/archie_normalize_prompt.txt`

3. Spawn a single Opus subagent (`model: "opus"`) with the prompt content. The subagent must return ONLY valid JSON matching the canonical StructuredBlueprint schema.

   **IMPORTANT:** Tell the normalizer subagent: "Preserve all data exactly as provided. Do NOT infer, add, or change file paths, HTTP methods, or component descriptions. Your job is to reshape the structure, not to add content."

4. Save the subagent's JSON output:
```
Write .archie/blueprint_normalized.json with the subagent's JSON output
```

5. Apply the normalized blueprint:
```bash
python3 .archie/normalize.py apply "$PWD"
```

This saves the canonical `.archie/blueprint.json`.

## Step 6: Render and validate

```bash
python3 .archie/renderer.py "$PWD"
python3 .archie/intent_layer.py "$PWD"
python3 .archie/rules.py "$PWD"
python3 .archie/install_hooks.py "$PWD"
```

Run all four commands. They read `.archie/blueprint.json` and generate everything.

Then validate the output against the actual codebase:

```bash
python3 .archie/validate.py all "$PWD"
```

**Review the validation output.** If there are FAIL results:
- **path_exists failures** (e.g. `public/output` doesn't exist) — the blueprint has a wrong path. Read `.archie/blueprint.json`, find the incorrect path, and fix it to match the actual directory from scan.json. Save the corrected blueprint and re-run the four render commands above.
- **http_methods failures** (e.g. claims GET/POST but exports GET/PUT) — read the actual route file, fix the `key_interfaces.methods` array in the blueprint, save, and re-render.
- **component_verb warnings** — update the component `responsibility` field in the blueprint to match what the code actually does.

After fixes, re-run `python3 .archie/validate.py all "$PWD"` to confirm 0 failures.

## Step 7: AI-enrich per-folder CLAUDE.md

The per-folder CLAUDE.md files generated in Step 6 are deterministic (file lists, component info). This step enriches them with AI-generated patterns, anti-patterns, debugging tips, and code examples using bottom-up DAG scheduling.

1. Prepare the folder DAG:
```bash
python3 .archie/enrich.py prepare "$PWD"
mkdir -p .archie/enrichments
```

2. Process in readiness waves. Maintain a list of done folder paths (starts empty).

   **Repeat until done:**

   a. Get ready folders (folders whose children are all done, or leaves with no children):
   ```bash
   python3 .archie/enrich.py next-ready "$PWD" <done1> <done2> ...
   ```
   First call with no done folders returns all leaf folders.

   b. If the ready list is empty (`[]`), all folders are done. Proceed to step 3.

   c. Get batches for the ready folders:
   ```bash
   python3 .archie/enrich.py suggest-batches "$PWD" <ready1> <ready2> ...
   ```

   d. For each batch, generate the prompt and spawn a subagent:
   ```bash
   python3 .archie/enrich.py prompt "$PWD" --folders <comma-separated> --child-summaries .archie/enrichments/ > /tmp/archie_enrich_prompt.txt
   ```
   Read the prompt file. Spawn a Sonnet subagent (`model: "sonnet"`) with the prompt content. The subagent must return ONLY valid JSON with folder paths as keys.
   **Spawn ALL batches in a wave in parallel.**

   e. Save each subagent's JSON output:
   ```
   Write .archie/enrichments/<batch_id>.json with the subagent's JSON output
   ```

   f. Add all folders from completed batches to the done list. Go to (a).

3. Merge enrichments into CLAUDE.md files:
```bash
python3 .archie/enrich.py merge "$PWD"
```

## Step 8: Clean up and summarize

```bash
rm -f /tmp/archie_sub*.json /tmp/archie_normalize_prompt.txt /tmp/archie_enrich_prompt.txt
```

Print what was generated:
- `.archie/blueprint.json` — architecture blueprint (AI-normalized)
- `.archie/blueprint_raw.json` — raw subagent output (preserved for debugging)
- `CLAUDE.md` — root architecture context
- `AGENTS.md` — comprehensive agent guidance
- `.claude/rules/` — 7 topic-split rule files
- `.cursor/rules/` — Cursor rule files
- Per-folder `CLAUDE.md` — directory-level context (AI-enriched with patterns, anti-patterns, debugging tips, code examples)
- `.claude/hooks/` — real-time enforcement hooks
- `.archie/rules.json` — enforcement rules

Tell the user: "Archie is now active. Architecture rules will be enforced on every code change."

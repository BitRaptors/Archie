## Step 5: Wave 2 — Reasoning agents (Design · Risk · Overview)

**Telemetry:**
```bash
python3 .archie/telemetry.py mark "$PROJECT_ROOT" deep-scan wave2_synthesis
python3 .archie/telemetry.py extra "$PROJECT_ROOT" wave2_synthesis model={{REASONING_MODEL}}
TELEMETRY_STEP5_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

**If START_STEP > 5, skip this step.**

Wave 2 reasoning is split into **up to four sub-agents** that run **in parallel**, all at `{{REASONING_MODEL}}`:

- **Design** — decision chain, architectural style, key decisions, trade-offs, out-of-scope, implementation guidelines, communication-pattern enrichment.
- **Risk** — findings + pitfalls.
- **Overview** — architecture diagram + executive summary.
- **Product** — `product_model` (domain map) + `derived_invariants` (reasoned product laws) + `unenforced_invariants` (the ungrounded gap list). It reasons over the Wave 1 Domain agent's `domain_invariants`. **Spawn on a FULL scan when `domain_invariants` is non-empty.** It is skipped in incremental mode: `derived_invariants`/`unenforced_invariants` are *global* reasoning over the whole law set, not per-change deltas, so they don't compose with a patch merge — the prior full scan's product sections are preserved unchanged by the patch and refresh on the next full scan (Wave 1 still updates the observed `domain_invariants` incrementally).

Key ownership is disjoint, so the outputs merge cleanly. The same dispatch runs in BOTH full and incremental modes — only the injected context preamble and the finalize flag differ (no special-case workflow).

### Findings store (accumulates across all runs)

`.archie/findings.json` is a compounding store — `{{COMMAND_PREFIX}}archie-deep-scan` reads from it and writes back to it. Each run adds new findings, upgrades existing ones (with matching `id`), confirms recurrence, or marks resolution.

Before Wave 2:

- If `$PROJECT_ROOT/.archie/findings.json` exists, the Risk sub-agent loads the `findings` array, upgrades the draft entries, and emits additional findings it discovers.
- If the file is absent (first-ever run, or brand-new project), the Risk sub-agent produces findings from scratch and the file is written as part of the merge.

Either way, after Wave 2 the store reflects accumulated knowledge across every prior scan and deep-scan run.

**Maintainer guardrails — extract before Wave 2 (deterministic preprocessing):**

```bash
python3 .archie/intent_layer.py extract-guardrails "$PROJECT_ROOT"
```

This scans every per-folder `CLAUDE.md` (excluding `.archie/`, `.claude/`, `node_modules/`, etc.), strips Archie's own marker blocks (`<!-- archie:ai-* -->`, `<!-- archie:scoped-* -->`) so the loop reads only maintainer prose, extracts bullets under any `## Anti-Patterns` section, and writes `.archie/maintainer_guardrails.json`. The Design sub-agent's §11 (compound learning) reads that file rather than globbing CLAUDE.md directly — the deterministic extraction guarantees no self-amplification across runs. On the first deep-scan ever (no per-folder CLAUDE.md exist yet), the file is written as `{"version": 1, "guardrails": []}` — §11 is a no-op for that run.

### Dispatch the three sub-agents

For each sub-agent below, Read its prompt file, then ALSO Read `{{WORKFLOW_ROOT}}/deep-scan/steps/step-3-wave1/grounding-rules.md`. Build each sub-agent's full prompt as: **mode preamble** (below) + blank line + agent body + blank line + grounding-rules body + blank line + output contract.

All paths are relative to the project root (your cwd).

| Sub-agent | Prompt file | Output path | Spawn when |
|---|---|---|---|
| Design | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-5a-design.md` | `.archie/tmp/archie_sub_design_$PROJECT_NAME.json` | Always |
| Risk | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-5b-risk.md` | `.archie/tmp/archie_sub_risk_$PROJECT_NAME.json` | Always |
| Overview | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-5c-overview.md` | `.archie/tmp/archie_sub_overview_$PROJECT_NAME.json` | Always |
| Product | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-5d-product.md` | `.archie/tmp/archie_sub_product_$PROJECT_NAME.json` | Full scan + `domain_invariants` non-empty |

**Evaluate the Product spawn gate first (full mode only).** In incremental mode, do NOT spawn Product — skip straight to Design / Risk / Overview. In full mode, count the laws the Wave 1 Domain agent produced (the merged `blueprint_raw.json` already carries `domain_invariants`) using the auto-approved `python3 -c …` form:

```bash
DOMAIN_LAW_COUNT=$(python3 -c "import json,os,sys; p=sys.argv[1]; print(len((json.load(open(p)).get('domain_invariants') or [])) if os.path.exists(p) else 0)" .archie/blueprint_raw.json)
```

Spawn the **Product** sub-agent only when `DOMAIN_LAW_COUNT` is greater than 0. Design, Risk, and Overview always spawn regardless of this count, in both modes.

**Mode preamble — prepend the SAME block to all sub-agent prompts:**

- **Always prepend the depth contract (both scan modes).** When this run's `DEPTH=comprehensive`, prepend this line verbatim (it makes ALL counts in the body floors, so the Risk agent's "soft floor of 3" findings/pitfalls and every other count go unbounded):
  > *COMPREHENSIVE MODE — be exhaustive. Every item-count in these instructions ("N-M", "up to N", "soft floor of N", "top N", "the most important") is a FLOOR, not a ceiling: emit every item that meets the quality bar, with no upper bound and no padding. Exception: keep the architecture diagram to 8-12 nodes.*

  When `DEPTH=default`, prepend nothing and apply the stated caps.

- **If SCAN_MODE = "full" (default):**
  > Produce your sections fresh from the full Wave-1 analysis in `$PROJECT_ROOT/.archie/blueprint_raw.json` (components, communication patterns, technology, deployment, frontend, data models and persistence stores, and `domain_invariants` — the product's observed correctness laws). The Design and Risk agents should read `domain_invariants` per their own instructions (Design links each key decision to the law it preserves; Risk turns each law into a violation pitfall). The Product agent reasons over `domain_invariants` exclusively.

- **If SCAN_MODE = "incremental":**
  > INCREMENTAL UPDATE. The architecture was previously analyzed — `$PROJECT_ROOT/.archie/blueprint.json` is the current full architecture and `$PROJECT_ROOT/.archie/blueprint_raw.json` carries the structural changes from Step 4. These files changed: [list `changed_files`]. Update ONLY the sections you own that are affected by these changes, and return ONLY what changed — unchanged sections are preserved by the patch merge. Use the 4-field contract (`problem_statement`, `evidence`, `root_cause`, `fix_direction`) when writing finding or pitfall entries.

**Output contract — append to each prompt, substituting that sub-agent's output path from the table as the "file path named above":**

```
---
OUTPUT CONTRACT (mandatory):
{{>output_contract}}
```

All sub-agents run at the `{{REASONING_MODEL}}` model. {{>dispatch_parallel}}

The merge step below reads each agent's output file directly — do NOT copy or transcribe a subagent's output yourself.

**Verify the expected output files exist before merging.** Check that
`archie_sub_design_$PROJECT_NAME.json`, `archie_sub_risk_$PROJECT_NAME.json`, and
`archie_sub_overview_$PROJECT_NAME.json` are all on disk under `.archie/tmp/` — and
`archie_sub_product_$PROJECT_NAME.json` too **when the Product agent was spawned** (full
scan with non-empty `domain_invariants`; never in incremental mode). If any expected file is
missing, that sub-agent failed — **STOP, report which file is missing, and do NOT
run the merge or `complete-step 5`.** Re-run Step 5 (`{{COMMAND_PREFIX}}archie-deep-scan
--from 5`) to respawn the agents. Proceeding with a partial merge would mark Step 5
complete with whole sections (e.g. the diagram or executive summary) silently missing,
and resume would not re-run it. All expected files must be present, or none.

**Fold in the per-agent timings** (each sub-agent self-timed its run). This records
how long each of Design/Risk/Overview ran, alongside the step's end-to-end duration:

```bash
python3 .archie/telemetry.py collect-agents "$PROJECT_ROOT" wave2_synthesis
```

### Merge (one finalize call, all files)

After the output files are on disk, merge them in a SINGLE finalize call — this keeps Step 5 atomic (the blueprint is written once), so an interrupted run is recovered by simply re-running Step 5 from the top. The Product file is listed unconditionally; `finalize.py` warns and skips it when the Product agent wasn't spawned (`domain_invariants` empty), keeping the command stable.

- **If SCAN_MODE = "full":**
  ```bash
  python3 .archie/finalize.py "$PROJECT_ROOT" .archie/tmp/archie_sub_design_$PROJECT_NAME.json .archie/tmp/archie_sub_risk_$PROJECT_NAME.json .archie/tmp/archie_sub_overview_$PROJECT_NAME.json .archie/tmp/archie_sub_product_$PROJECT_NAME.json
  ```
- **If SCAN_MODE = "incremental":**
  ```bash
  python3 .archie/finalize.py "$PROJECT_ROOT" --patch .archie/tmp/archie_sub_design_$PROJECT_NAME.json .archie/tmp/archie_sub_risk_$PROJECT_NAME.json .archie/tmp/archie_sub_overview_$PROJECT_NAME.json .archie/tmp/archie_sub_product_$PROJECT_NAME.json
  ```

This single command merges all agents' output (routing `findings` to `findings.json` and deep-merging the rest), normalizes the schema, renders CLAUDE.md + AGENTS.md + rule files, installs hooks, and validates. Review the validation output — warnings are informational, not blocking. The validate step now includes a WARN-only **cross-link integrity** check (pitfall→decision, finding→pitfall, trade_off→decision, decision_chain→key_decisions); since Design and Risk run in parallel, a small number of these warnings is expected and not a failure.

**Backward-check the findings against actual code.** After finalize writes `.archie/findings.json`, run the {{VERIFY_MODEL}} verifier and apply hysteresis. The verifier reads each finding's required `triggering_call_site` field, walks one level out from the cited caller, and decides per finding: `keep` (failure fires there — real finding), `demote` (call site exists but failure doesn't fire — risk class, not current problem), or `drop` (premise unsound for this codebase). The hysteresis layer then applies the verdict with cross-run stability — single-scan flips on unchanged code don't propagate (kills LLM-noise flicker), but a git-diff anchor (a file in the finding's `triggering_call_site` was touched in the last 5 commits) lets a real transition land immediately.

```bash
python3 .archie/verify_findings.py "$PROJECT_ROOT"
python3 .archie/apply_verdicts.py "$PROJECT_ROOT"
```

Both scripts are idempotent and graceful: if the {{VERIFY_MODEL}} verifier CLI is unreachable, every verifier call times out, or `findings.json` is empty, both no-op cleanly. Findings whose status flips to `demoted` or `dropped` here will be filtered out of any user-facing rendering automatically (status-driven filter) — only `status: active` reaches the report.

After finalize completes, regenerate the dependency graph (the blueprint now has component definitions, which enables cross-component edge detection):

```bash
python3 .archie/detect_cycles.py "$PROJECT_ROOT" --full 2>/dev/null
```

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 5
```

# Archie Scan — Architecture Health Check with Compound Learning

Analyze this project's architectural health using parallel agents. Each scan evolves the blueprint — knowledge compounds over time.

**Prerequisites:** If `.archie/scanner.py` doesn't exist, tell the user to run `npx archie` first.

---

## Phase 1: Data Gathering (parallel scripts, seconds)

Run all three scripts simultaneously:

```bash
python3 .archie/scanner.py "$PWD"
```
```bash
python3 .archie/measure_health.py "$PWD" > .archie/health.json 2>/dev/null
```
```bash
python3 .archie/detect_cycles.py "$PWD" --full 2>/dev/null
```
```bash
git log --oneline --since="7 days ago" --name-only 2>/dev/null | sort -u | head -50
```

---

## Phase 2: Read All Existing Knowledge

Read the fresh scan data:
- `.archie/skeletons.json` — every file's header, function/class signatures, line counts
- `.archie/scan.json` — file tree, import graph, detected frameworks
- `.archie/health.json` — erosion, gini, verbosity, complexity per function
- `.archie/dependency_graph.json` — resolved directory-level dependency graph

Read accumulated knowledge (skip any that don't exist — that's normal for early scans):
- `.archie/blueprint.json` — the evolving architectural knowledge base
- `.archie/scan_report.md` — previous scan's report (for trending and resolved/new findings)
- `.archie/health_history.json` — historical health scores
- `.archie/rules.json` — adopted enforcement rules
- `.archie/proposed_rules.json` — rules discovered but not yet adopted
- `.archie/function_complexity.json` — previous complexity snapshot

**This is the compound learning input.** The agents below receive everything Archie has ever learned about this codebase.

---

## Phase 3: Parallel Analysis (3 agents, each can read source files)

Spawn 3 Sonnet subagents in parallel (Agent tool, `model: "sonnet"`). Each agent receives all the data from Phase 2 and can read any source file to verify findings.

**IMPORTANT:** Write each agent's output to a temp file so Phase 4 can read them all.

### Agent A: Architecture & Dependencies

```
Prompt for Agent A:
```

You are analyzing the ARCHITECTURE and DEPENDENCIES of a codebase. You have access to all scan data and the existing blueprint (if any).

**Your inputs:**
- `.archie/dependency_graph.json` — resolved directory-level graph with nodes (degree, component, file count), edges (weight, cross-component, cycles)
- `.archie/skeletons.json` — every file's structure
- `.archie/blueprint.json` — existing architectural knowledge (if any)
- `.archie/scan.json` — import graph, frameworks

**Your job:**
1. **Component analysis:** Identify all logical components. If a blueprint exists, compare — are there new components? Removed ones? Changed responsibilities? If no blueprint, infer components from directory structure and import patterns.

2. **Dependency direction:** Using the dependency graph, trace the dependency flow. Are there layers? Do dependencies flow in one direction? Flag cross-component edges as potential violations. For each violation, READ the actual source file to verify — is it a real architectural violation or an acceptable exception?

3. **Dependency magnets:** Which directories have highest in-degree? These are stability bottlenecks. Read key files in these directories to understand what they provide and whether the coupling is justified.

4. **Tight coupling:** Edges with high weight (many imports). Read files on both sides to understand why the coupling exists.

5. **Circular dependencies:** For each cycle in the graph, read the evidence files. Explain what coupling it creates and why it matters.

6. **Architecture style:** Based on the dependency flow, component structure, and patterns you observe, what is the architecture style? How confident are you? If the blueprint already states one, do you agree based on current evidence?

**Output:** Write a structured JSON report to `/tmp/archie_agent_a_arch.json`:
```json
{
  "components": [{"name": "...", "path": "...", "role": "...", "confidence": 0.9}],
  "architecture_style": {"style": "...", "confidence": 0.85, "evidence": "..."},
  "dependency_violations": [{"from": "...", "to": "...", "severity": "error|warn", "description": "...", "verified_in_file": "...", "confidence": 0.9}],
  "dependency_magnets": [{"directory": "...", "in_degree": N, "risk": "..."}],
  "cycles": [{"directories": [...], "impact": "...", "evidence_files": [...]}],
  "tight_coupling": [{"from": "...", "to": "...", "weight": N, "reason": "..."}]
}
```

```
Save output: /tmp/archie_agent_a_arch.json
```

### Agent B: Health & Complexity

```
Prompt for Agent B:
```

You are analyzing the HEALTH and COMPLEXITY of a codebase. You have access to health metrics, complexity data, and historical trends.

**Your inputs:**
- `.archie/health.json` — current erosion, gini, verbosity, waste, function-level complexity
- `.archie/health_history.json` — historical health scores (for trend analysis)
- `.archie/function_complexity.json` — previous complexity snapshot (for trajectory)
- `.archie/skeletons.json` — file structure
- `.archie/blueprint.json` — existing architectural knowledge (if any)

**Your job:**
1. **Health assessment:** Report each metric with plain-language explanation. Thresholds:
   - Erosion: <0.3 good, 0.3-0.5 moderate, >0.5 high
   - Gini: <0.4 good, 0.4-0.6 moderate, >0.6 high
   - Top-20% share: <0.5 good, 0.5-0.7 moderate, >0.7 high
   - Verbosity: <0.05 good, 0.05-0.15 moderate, >0.15 high

2. **Trend analysis:** Compare against health_history.json. Are things improving or degrading? Which metrics moved most? Is LOC growth justified?

3. **Complexity hotspots:** Identify functions with CC > 10. READ those functions in the source code. Are they genuinely complex? Could they be split? What would break? Compare against previous function_complexity.json — which functions got MORE complex?

4. **Abstraction waste:** Single-method classes, tiny functions (<=2 lines). Read suspicious ones to determine if they're legitimate or over-engineering.

**Output:** Write to `/tmp/archie_agent_b_health.json`:
```json
{
  "health_scores": {"erosion": 0.31, "gini": 0.58, "top20_share": 0.72, "verbosity": 0.003, "total_loc": 9400},
  "trend": {"direction": "improving|degrading|stable", "details": "..."},
  "complexity_hotspots": [{"function": "...", "file": "...", "cc": N, "assessment": "...", "recommendation": "..."}],
  "complexity_trajectory": [{"function": "...", "file": "...", "previous_cc": N, "current_cc": N}],
  "abstraction_waste": {"single_method_classes": N, "tiny_functions": N, "notable": ["..."]}
}
```

```
Save output: /tmp/archie_agent_b_health.json
```

### Agent C: Rules & Patterns

```
Prompt for Agent C:
```

You are analyzing PATTERNS and discovering RULES in a codebase. You look for architectural invariants — things that should always be true.

**Your inputs:**
- `.archie/skeletons.json` — every file's structure
- `.archie/rules.json` — currently adopted rules
- `.archie/proposed_rules.json` — previously proposed rules (adopted or pending)
- `.archie/blueprint.json` — existing architectural knowledge (if any)
- `.archie/scan.json` — file tree, imports, frameworks

**Your job:**
1. **Pattern consistency:** Find patterns the codebase follows — base classes, naming conventions, file organization, import patterns. Then find the outliers that break them. READ the outlier files to understand if they're intentional exceptions or drift.

2. **Duplication / reimplementation:** Look for functions with the same or similar names in multiple files. AI agents do this constantly — they reimplement helpers instead of importing shared code. READ suspicious duplicates to confirm.

3. **Propose new rules:** Based on patterns found, propose architectural rules. Do NOT re-propose rules already in rules.json or proposed_rules.json. Look for DEEPER rules — subtler invariants, behavioral constraints, scoped rules for specific components.

4. **Validate existing rules:** Check if any adopted rules in rules.json are now violated by current code. Check if any proposed rules have become more or less valid since they were proposed (adjust confidence).

**Rule schema:**
Required: `{"id": "scan-NNN", "description": "...", "rationale": "...", "severity": "error|warn", "confidence": 0.85}`

Confidence calibration:
- 0.9-1.0: Verified invariant — N files follow pattern with 0-1 exceptions, you read the files.
- 0.7-0.9: Strong pattern with some exceptions, clear architectural intent.
- 0.5-0.7: Inferred from structure, not verified in every case.
- 0.3-0.5: Speculative, based on best practices not specific evidence.

Be honest. A wrong rule with high confidence is worse than a right rule with low confidence.

Optional mechanical fields (add ONLY when a meaningful regex exists):
- `"check"`: `forbidden_import`, `required_pattern`, `forbidden_content`, `architectural_constraint`
- `"applies_to"`, `"file_pattern"`, `"forbidden_patterns"`, `"required_in_content"`

**Output:** Write to `/tmp/archie_agent_c_rules.json`:
```json
{
  "pattern_findings": [{"pattern": "...", "followers": N, "outliers": ["..."], "severity": "warn|error", "confidence": 0.85}],
  "duplications": [{"function": "...", "locations": ["..."], "recommendation": "..."}],
  "proposed_rules": [{"id": "scan-NNN", "description": "...", "rationale": "...", "severity": "...", "confidence": 0.85}],
  "existing_rule_violations": [{"rule_id": "...", "violated_by": "...", "details": "..."}],
  "rule_confidence_updates": [{"rule_id": "...", "old_confidence": 0.7, "new_confidence": 0.85, "reason": "..."}]
}
```

```
Save output: /tmp/archie_agent_c_rules.json
```

**Wait for all 3 agents to complete before proceeding to Phase 4.**

---

## Phase 4: Synthesis + Blueprint Evolution

Read the outputs from all three agents:
- `/tmp/archie_agent_a_arch.json`
- `/tmp/archie_agent_b_health.json`
- `/tmp/archie_agent_c_rules.json`

Also re-read `.archie/blueprint.json` (the current state of accumulated knowledge).

Now you are the **synthesis agent**. Your job is to merge the three agents' findings with the existing blueprint to produce an evolved blueprint. This is where compound learning happens.

### 4a: Evolve the Blueprint

Read the existing blueprint (or start with `{}` if none exists). Apply these evolution rules:

**Components** (`blueprint.components`):
- If Agent A found new components not in blueprint → add them with the agent's confidence
- If Agent A found components that match existing ones → keep existing data, update confidence if Agent A's is higher
- If a component in the blueprint no longer appears in Agent A's analysis → keep it but add `"status": "not_found_in_latest_scan"` (don't delete — it might be in an unscanned area)

**Architecture style** (`blueprint.decisions.architectural_style`):
- If no blueprint → use Agent A's assessment
- If blueprint exists and Agent A agrees → increase confidence (min of 1.0)
- If blueprint exists and Agent A disagrees → keep blueprint's but add Agent A's assessment as `"alternative_assessment"` with reasoning. Don't overwrite the deep scan's analysis with a scan's inference.

**Health** (`blueprint.meta.health`):
- Always update with Agent B's latest scores
- Add `"trend"` from Agent B's trend analysis
- Add `"last_health_scan"` timestamp

**Pitfalls** (`blueprint.pitfalls`):
- Agent A's dependency violations → add as pitfalls with `"source": "scan-observed"`
- Agent B's complexity hotspots → add as pitfalls with `"source": "scan-observed"`
- Agent C's pattern violations → add as pitfalls with `"source": "scan-observed"`
- Existing pitfalls from blueprint → keep. If a scan-observed pitfall matches an existing one, increase its confidence.
- If a previously scan-observed pitfall is no longer found → mark `"status": "resolved"` with timestamp. Don't delete — the resolution is valuable knowledge.

**Architecture rules** (`blueprint.architecture_rules`):
- Agent C's proposed rules that have confidence >= 0.8 → add to `architecture_rules` with `"source": "scan-inferred"`
- Existing rules from deep scan → keep as-is (higher authority)
- Agent C's rule confidence updates → apply to matching rules

**Development rules** (`blueprint.development_rules`):
- Agent C's pattern findings with confidence >= 0.7 → add as development rules

**Meta** (`blueprint.meta`):
- Update `"last_scan"` timestamp
- Update `"scan_count"` (increment)
- Update `"confidence"` per section — each scan that confirms a section's data increases its confidence slightly (up to 1.0)
- Set `"schema_version": "2.0.0"`

**CRITICAL EVOLUTION RULES:**
- **Never decrease confidence** on data that came from a deep scan unless you have strong contrary evidence from reading source files.
- **Never delete** sections or entries that came from a deep scan. Mark them as stale if needed, but don't delete.
- **Always add** new findings. Accumulate, don't replace.
- **Resolved findings stay** in the blueprint with `"status": "resolved"` — they're part of the project's architectural history.

Write the evolved blueprint to `.archie/blueprint.json`.

### 4b: Write Scan Report

Get the current date:
```bash
date -u +"%Y-%m-%d"
```

Write to `.archie/scan_report_YYYY-MM-DD.md` and copy to `.archie/scan_report.md`.

The report should include:
```markdown
# Archie Scan Report
> Scan #N | YYYY-MM-DD | X files analyzed | Y changed in last 7 days

## Architecture Overview
[5-10 lines from Agent A's analysis]

## Health Scores
| Metric | Current | Previous | Trend |
|--------|---------|----------|-------|
[from Agent B]

### Complexity Trajectory
[functions that got more complex since last scan]

## Findings
[ALL findings from agents A, B, C — ranked by severity then confidence]
[Each finding: what's wrong, which file, evidence from the code, why it matters]
[Mark which findings are NEW vs. RECURRING vs. RESOLVED since last scan]

## Blueprint Evolution
[What changed in the blueprint this scan — new components, updated confidence, resolved pitfalls, new rules added]

## Proposed Rules
[from Agent C — numbered checklist with rationale and confidence]

## Next Task
**What:** [highest-impact action from across all three agents]
**Where:** [exact file paths]
**Why:** [what improves]
**How:** [2-3 sentence approach]

## Recommendations
[Re-baseline with /archie-deep-scan if: no deep scan ever, erosion increased >0.10, major structural changes]
```

### 4c: Update Satellite Files

Append health scores to `.archie/health_history.json`:
```json
{"timestamp": "ISO-8601", "erosion": 0.00, "gini": 0.00, "top20_share": 0.00, "verbosity": 0.00, "total_loc": 0, "scan_number": N, "scan_type": "fast"}
```

Save per-function complexity snapshot to `.archie/function_complexity.json`.

Save ALL proposed rules (from Agent C) to `.archie/proposed_rules.json`:
```
1. Read existing proposed_rules.json (create as {"rules": []} if missing)
2. Append new proposed rules with "source": "scan-proposed" (keep AI-assigned confidence)
3. Skip if a rule with the same id already exists
4. Update confidence on existing proposed rules if Agent C recommended changes
5. Write back
```

### 4d: Clean up temp files

```bash
rm -f /tmp/archie_agent_a_arch.json /tmp/archie_agent_b_health.json /tmp/archie_agent_c_rules.json
rm -f .archie/health.json
```

---

## Phase 5: Present Results and Process Adoptions

Print the summary to the user. Include:
1. **Health scores** table (all metrics with trend)
2. **Blueprint evolution** — what changed in the blueprint this scan (new components, updated confidence, resolved pitfalls, new rules inferred)
3. **All findings** from all agents — ranked by severity. Group as NEW / RECURRING / RESOLVED. This is the most valuable part — don't skip or summarize as counts.
4. **Proposed rules** with numbered checklist from Agent C
5. **Next task**
6. Path to full report

The rule adoption prompt:
> **Reply with the numbers to adopt** (e.g., `1, 3` or `all` or `none`).
> Adopted rules take effect immediately. Skipped rules remain in `/archie-viewer` → Rules tab.

**Wait for the user's response.** Then process:

- Numbers → adopt those rules into `.archie/rules.json` with `"source": "scan-adopted"` (keep AI confidence)
- `all` → adopt every proposed rule
- `none` → skip (rules stay in proposed_rules.json)

Print confirmation: `Adopted N rules, skipped M (available in /archie-viewer → Rules tab). Scan #N complete — blueprint evolved.`

# Semantic Findings — Unified Architectural Analysis for Archie

**Status:** Design, pending approval. Supersedes `docs/SCAN_CONSOLIDATION.md`.

**Audience:** Archie maintainers evolving `/archie-scan` and `/archie-deep-scan`.

---

## TL;DR

Both scan commands produce **Semantic Findings** — a unified output with two tiers (systemic, localized), one shared calibration spec, and explicit synthesis depth (`draft | canonical`). Findings come from agents that are already reading the codebase; no new read passes are added. Deep-scan's Wave 2 produces canonical-quality synthesis and upgrades stored fast-scan drafts each time it runs. Fast-scan runs often and fast, emitting drafts; deep-scan runs rarely and deep, emitting and upgrading to canonical. Count differs by command; quality is identical wherever both produce canonical (i.e., after deep-scan has run).

This supersedes the `SCAN_CONSOLIDATION.md` "triple-the-Phase-2-agent-count" approach. That plan would have *added* codebase reads; this design *harvests* findings from reads that already happen.

---

## Vocabulary

- **Semantic Findings** — the unified output. Replaces "Findings", "deep drift findings", "mechanical drift" as top-level terms. Mechanical drift becomes a `source` within Semantic Findings, not a separate section.
- **Systemic** — overarching issues spanning ≥3 locations or multiple components. Types: `fragmentation`, `god_component`, `split_brain`, `erosion`, `missing_abstraction`, `inconsistency`, `trajectory_degradation`, `boundary_violation`, `responsibility_diffusion`.
- **Localized** — location-specific issues with 1 concrete site. Types: `decision_violation`, `trade_off_undermined`, `pitfall_triggered`, `responsibility_leak`, `abstraction_bypass`, `semantic_duplication`, `pattern_erosion`, `dependency_violation`, `cycle`, `complexity_hotspot`, `rule_violation`, `pattern_divergence`.
- **synthesis_depth** — `draft` (shallower synthesis, fast-scan default) | `canonical` (deep-scan Wave 2, authoritative). Upgraded draft → canonical by Wave 2's upgrade pass.

---

## Finding schema

```json
{
  "id": "sf-<hash>",
  "category": "systemic | localized",
  "type": "<from taxonomy>",
  "severity": "error | warn | info",
  "scope": {
    "kind": "system_wide | cross_component | within_component | single_file",
    "components_affected": ["..."],
    "locations": ["path/to/file:symbol:line", "..."]
  },
  "pattern_description": "one-sentence architectural name — required for systemic, omitted for localized",
  "evidence": "concrete instances (systemic) or single-location detail (localized)",
  "root_cause": "mechanistic explanation — missing abstraction / conflicting decisions / organic growth without refactor / erosion trajectory",
  "fix_direction": "actionable — extract X / consolidate to Y / split Z / add middleware W",
  "blueprint_anchor": "decision:D.3 | trade_off:T.2 | pitfall:P.5 | null",
  "blast_radius": 22,
  "blast_radius_delta": 7,
  "lifecycle_status": "new | recurring | resolved | worsening",
  "synthesis_depth": "draft | canonical",
  "source": "wave1_structure | wave1_patterns | wave2 | phase2 | fast_agent_a | fast_agent_b | fast_agent_c | mechanical"
}
```

### Quality gate (hard requirement)

| Field | Systemic | Localized |
|---|---|---|
| `pattern_description` | required | omit |
| `evidence` instances | ≥3 concrete locations | 1 concrete location |
| `root_cause` | required, mechanistic | required |
| `fix_direction` | required, actionable | required |
| `blast_radius` | required | optional |
| `blueprint_anchor` | populate when applicable | populate when applicable |

A candidate finding that can't fill all required fields is **dropped**. No exceptions. This prevents inflation once count caps are removed.

### No count caps

Every "pitfalls (3-5)" or similar count bracket is removed. Prompt language on both tiers: *"Emit every finding you can substantiate with concrete evidence. No cap. Do not invent to pad. Do not drop to stay under a count."* The quality gate is the only filter.

---

## Pipeline — who produces what

### Deep-scan (`/archie-deep-scan`)

| Producer | Role | Reads | Produces |
|---|---|---|---|
| Wave 1 Structure | draft-tier | all source files + `dep_graph.json` (both existing) | Blueprint facts (existing) + `pattern_observations`: dep-graph pathologies (magnets, cycles, cross-layer edges) + localized `dependency_violation` findings |
| Wave 1 Patterns | draft-tier | all source files (existing) | Blueprint facts (existing) + `pattern_observations`: cross-file pattern anomalies, fragmentation signals, inconsistencies |
| Wave 1 Technology | draft-tier | unchanged | Blueprint facts only — no findings |
| Wave 1 UI Layer | draft-tier | conditional on `frontend_ratio >= 0.20` | Blueprint facts + `pattern_observations` for UI concerns |
| **Wave 2** | **canonical-tier** | Wave 1 output + key source files (existing) + `skeletons.json` + `health.json` + `drift_report.json` + prior `semantic_findings.json` (all new reads — small JSON files, no new code reads) | Blueprint reasoning (existing) + **Tier 2 systemic findings** (primary producer, canonical depth) + **localized**: `decision_violation`, `trade_off_undermined`, `pitfall_triggered`, `responsibility_leak`, `abstraction_bypass` + **upgrade pass**: re-processes recurring draft findings, enriches `root_cause` + `fix_direction`, flips `synthesis_depth` to `canonical` |
| Shrunk Phase 2 | draft-tier | `skeletons.json` + recent-change files + per-folder CLAUDE.md | `semantic_duplication` (near-twin scan + targeted reads on suspect pairs) + `pattern_erosion` (code vs folder's documented patterns) |
| `drift.py` | script | — | Mechanical pattern divergences, structural outliers |
| `health.py` | script | — | Raw CC, erosion, gini, verbosity → consumed by Wave 2 |

### Fast-scan (`/archie-scan`)

| Producer | Role | Reads | Produces |
|---|---|---|---|
| Agent A | draft-tier | `skeletons.json`, `dep_graph.json`, `scan.json`, `blueprint.json` (existing) | Tier 1 observations + **systemic** (draft): `god_component`, `boundary_violation` + **localized**: `dependency_violation`, `cycle`, magnet |
| Agent B | draft-tier | `health.json`, `health_history.json`, `skeletons.json`, `blueprint.json` (existing) | **Localized**: `complexity_hotspot`, `abstraction_bypass` + light **systemic**: `trajectory_degradation` (when history supports) |
| Agent C | draft-tier | `skeletons.json`, `rules.json`, `blueprint.json`, `scan.json` (existing) | **Systemic**: `fragmentation`, `missing_abstraction`, `inconsistency` + **localized**: `pattern_divergence`, `semantic_duplication`, `rule_violation` |
| `drift.py`, `health.py` | script | — | Same as deep-scan |

Fast-scan has **no canonical-tier pass**. Its systemic findings are draft until deep-scan next runs.

---

## Shared calibration — `_shared/semantic_findings_spec.md`

Single source of truth for every finding-producing agent. Contents:

1. **Output schema** — the JSON shape above
2. **Quality gate** — required fields per category
3. **Severity rubric:**
   - cross-layer violation OR cycle crossing documented boundary → `error`
   - CC ≥ 50 → `error`; 25–49 → `warn`; 10–24 → `info`
   - `violation_signals` match → `error`
   - active pitfall manifestation → `error`
   - dependency_magnet fan-in > 20 OR rising trajectory → `error`
   - ≥3 near-twin instances OR any in security-critical path → `error`
4. **Taxonomy** — full type list with definitions and examples
5. **No count caps** — prompt language to emit all substantiable findings
6. **Systemic emission guidance** — examples of good vs bad `pattern_description` / `root_cause` / `fix_direction`
7. **Synthesis depth** — `draft` vs `canonical` meanings; which agents write which
8. **Source string conventions**

Every agent prompt includes: *"Emit findings per `.claude/commands/_shared/semantic_findings_spec.md` — same schema, same severity rubric, same quality gate everywhere."*

**Maintainer protocol:** the spec is the single place to edit calibration. Agent prompts reference it, never inline it. This is the structural fix for the "three copies drift" risk in the original SCAN_CONSOLIDATION.md plan.

**Model → role mapping** lives in operational config (not schema):

```json
{
  "synthesis_models": {
    "draft": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
    "canonical": {"provider": "anthropic", "model": "claude-opus-4-6"}
  }
}
```

Swapping providers is config-only.

---

## Iteration lifecycle

Every scan, aggregation phase compares new findings against `.archie/semantic_findings.json` (previous):

- **new** — not in previous
- **recurring** — match by signature `type + sorted(components_affected)`; evidence locations may drift
- **resolved** — previous finding no longer substantiated by current evidence
- **worsening** — recurring AND `blast_radius` increased; `blast_radius_delta` records the change

### Upgrade mechanism (fast-scan draft → canonical)

Each time deep-scan's Wave 2 runs, after producing its own findings:

1. Reads stored `.archie/semantic_findings.json`
2. Filters to entries with `synthesis_depth: draft` AND `lifecycle_status: recurring` (still-valid drafts)
3. For each, re-processes with canonical-tier context: blueprint decisions, pitfalls, trade-offs, Wave 1 observations
4. Enriches `root_cause` (shallow → mechanistic with history) and `fix_direction` (generic → sequenced)
5. Flips `synthesis_depth` to `canonical`

The upgrade pass is capped at recurring drafts to avoid unbounded re-work. Resolved drafts are discarded; new canonical findings are produced fresh in Wave 2's primary pass.

---

## `/archie-share` and `/archie-viewer` — maintenance surface

Both commands consume the scan output and must keep working across the old → new transition. Backward compatibility is load-bearing: every bundle already in Supabase is immutable and must continue rendering.

### `/archie-share` (`upload.py`)

Today's bundle keys: `blueprint`, `health`, `scan_meta`, `rules_adopted`, `rules_proposed`, `scan_report` (markdown), `semantic_duplications`.

Changes:

1. **Add `semantic_findings`** — the new canonical aggregated output (`.archie/semantic_findings.json`). Becomes the authoritative source for the viewer's new Semantic Findings panel.
2. **Keep `scan_report`** (markdown) — still useful for plain-text consumers and legacy-viewer fallback. It's rendered from the same data anyway.
3. **Keep `semantic_duplications`** during the transition — it's now a strict subset of `semantic_findings` (filter by `type: semantic_duplication`). The old viewer reads this key; keeping it avoids breaking older hosted viewers before they ship the new panel. Mark for removal in a follow-up once the hosted viewer exposes Semantic Findings.
4. **Do NOT bundle** `semantic_findings_wave1.json` / `wave2.json` / `phase2.json` — these are deep-scan internal intermediates. Only the aggregated `semantic_findings.json` ships.
5. **Do NOT bundle raw `drift_report.json`** — mechanical findings are already folded into `semantic_findings.json` via `source: mechanical`. Keeping a duplicate key would invite viewer confusion.

Bundle shape versioning: add a `bundle_version` key at the top level. Old bundles implicitly `v1`. New design ships `v2`. Hosted viewer branches on this key rather than sniffing field presence.

### `/archie-viewer` (`viewer.py`, local + hosted)

Today: tabs for Blueprint, Files, Scan Report, Health, Rules, Dependency Graph. "Drift Findings" panel renders `drift_report.json` via `/api/drift` with error/warn split and categories (`cycles`, `tight_coupling`, etc., plus `deep_findings`).

Changes:

1. **New panel: Semantic Findings.** Primary surface for systemic + localized findings. Served via a new endpoint `/api/semantic-findings` reading `.archie/semantic_findings.json`.
   - **Systemic section first.** Each finding as an expandable card:
     - Header: severity badge + `lifecycle_status` badge (NEW / RECURRING / RESOLVED / WORSENING+N) + `type` + component names
     - Body: `pattern_description`, `evidence` (collapsible list of locations), `root_cause`, `fix_direction`
     - Footer: `blast_radius` visual (dot-count or bar), `blueprint_anchor` as clickable link to blueprint tab, `synthesis_depth` badge (`draft` vs `canonical`)
   - **Localized section second.** Compact tables grouped by category (Dependency violations / Complexity hotspots / Pattern divergences / Rule violations / etc.). Each row compact: severity, location, evidence summary, fix.
   - **Resolved section third.** Collapsed list of resolved findings from this scan.
   - **Mechanical section last.** Items where `source: mechanical`, in compact format.

2. **Filter / sort controls.**
   - Filter by severity (error / warn / info), category (systemic / localized), lifecycle_status, synthesis_depth
   - Sort by severity × blast_radius (default), or chronologically by lifecycle (new first), or alphabetical by type
   - Search by component name / file path

3. **Keep the legacy Drift Findings panel** as a fallback-only render for bundles where `semantic_findings` is absent (`bundle_version: v1` or local `.archie/` with no new file). The panel disappears when `semantic_findings` is present — no visual duplication.

4. **Blueprint tab unchanged in shape** but should surface a *"Systemic findings tagged to this decision / pitfall / trade_off"* sub-section, reading `semantic_findings.json` filtered by `blueprint_anchor`. This is the two-way link the quality-gate's `blueprint_anchor` field promises.

5. **`synthesis_depth` visual treatment.** `draft` findings get a subtle "provisional" badge (e.g., dashed border + text label). `canonical` are the default render. This is how users understand that a fast-scan-originated finding is less deep than a deep-scan one, and sets expectation for upgrade on next deep-scan.

### Hosted viewer (server-side)

The hosted viewer (served via the Supabase-linked URL returned by `upload.py`) must handle both bundle versions. Branching on `bundle_version`:

- `v1` (all existing shared bundles): render the legacy Drift Findings panel from `scan_report` markdown and `semantic_duplications`. No regression for anyone holding old share URLs.
- `v2` (new bundles): render the new Semantic Findings panel from `semantic_findings` data.

Old bundles NEVER auto-upgrade — they stay in v1 shape forever. Only freshly-shared bundles get v2.

### Migration order additions

Insert between steps 8 and 9 of the Migration section:

- **8a.** Update `upload.py` to include `semantic_findings.json` + `bundle_version: "v2"`. Keep legacy keys. Sync to `npm-package/assets/`.
- **8b.** Update `viewer.py` (local) — add `/api/semantic-findings` endpoint + new panel. Keep legacy Drift Findings panel as fallback. Sync to `npm-package/assets/`.
- **8c.** Update hosted viewer — add `bundle_version` branching. Ship new panel code alongside existing. Deploy before any v2 bundle is shared.

### Risk additions

7. **Hosted viewer deploy lag.** If someone shares a `v2` bundle before the hosted viewer supports it, the bundle renders as a fallback (legacy panel on incomplete data) until the viewer ships. Mitigation: deploy hosted viewer changes FIRST; only bump `bundle_version` in `upload.py` after hosted viewer is live in production.

8. **Migration window where both panels could render.** During rollout, if the local viewer ships v2 but an old `.archie/` only has `drift_report.json`, user sees legacy panel. If a fresh `.archie/` has `semantic_findings.json`, user sees new panel. Expected; document in release notes.

---

## Output — `scan_report.md` layout

```
# Scan Report — <repo>

## Executive Summary
Health score: X.XX (trend: ↑↓→)
Systemic findings: N (new: X, recurring: Y, worsening: Z, resolved: W)
Top 3 systemic by severity × blast_radius:
  1. [error] god_component — packages/shared (blast: 22)
  2. [error] fragmentation — auth enforcement (blast: 4)
  3. [warn] missing_abstraction — error handling (blast: 7)

## Systemic Findings (N)

### [error · NEW] god_component — packages/shared
**Pattern:** 22 consumers import from shared across 7 unrelated domains (auth, storage, UI, logging, …).
**Evidence:**
- apps/webui/src/auth.ts:14 — imports auth util
- apps/electron/src/storage.ts:3 — imports storage util
- (20 more)
**Root cause:** shared/ never split; every cross-cutting util added without domain boundary. Decision D.3 (shared-package strategy) treated shared as a primitives layer, but actual usage crosses domain boundaries freely.
**Fix direction:** split into packages/{auth, storage, ui-primitives, logging}; migrate per-domain starting with auth (lowest consumer count).
**Severity:** error — blast radius: 22 components (system_wide scope)
**Blueprint anchor:** decision:D.3 — actively undermined

### [error · RECURRING · WORSENING +5] fragmentation — auth enforcement
… (full treatment, one per finding)

### [warn · NEW] missing_abstraction — error handling
…

## Localized Findings (M)

### Dependency violations (k)
| Sev | From | To | Evidence | Fix |
|---|---|---|---|---|
| error | apps/webui | apps/electron/src/shared | `import { x } from '../electron/…'` (4 sites) | Extract util to packages/ |

### Complexity hotspots (k)
| Sev | Function | CC | Location | Why it matters | Fix |
|---|---|---|---|---|---|
| error | AppShell.render | 669 | apps/electron/AppShell.tsx:45 | Combines layout + routing + state wiring | Split into AppLayout + AppRouter + AppProviders |

### Pattern divergences (k)
### Rule violations (k)

## Resolved Findings (W)
Compressed list, grouped by type.

## Mechanical Findings (p)
Output from drift.py — structural outliers not captured by AI analysis.
```

Systemic section always comes first. Localized uses compact tabular format. Resolved are a compressed list; mechanical is a tail section.

---

## Persistence and `--from 9`

File layout under `.archie/`:

- `semantic_findings_wave1.json` — Wave 1 outputs (observations + localized findings per agent)
- `semantic_findings_wave2.json` — Wave 2 outputs (canonical systemic + localized + upgrade results)
- `semantic_findings_phase2.json` — Shrunk Phase 2 outputs
- `drift_report.json` — mechanical findings (unchanged name)
- `semantic_findings.json` — **aggregated canonical output**, read by viewer and next scan

Fast-scan writes directly to `semantic_findings.json` (after aggregating its three agent temp files + `drift_report.json`). Fast-scan does **not** write `wave1`/`wave2`/`phase2` files — those are deep-scan-only.

`--from 9` iteration path:

1. Phase 0 — health re-measurement
2. Phase 1 — `drift.py`
3. Phase 2 — Shrunk agent re-run (narrow scope, fast)
4. Phase 3 — aggregation: cached `wave1.json` + cached `wave2.json` + fresh `phase2.json` + `drift_report.json` → `semantic_findings.json` + `scan_report.md`

Total `--from 9` runtime: 2-5 minutes — preserved from current behavior.

---

## What changes vs `SCAN_CONSOLIDATION.md`

| Axis | SCAN_CONSOLIDATION.md | This design |
|---|---|---|
| Phase 2 agent count | 1 → 3 (added two) | 1 → 1 shrunk (`semantic_duplication` + `pattern_erosion` only) |
| Codebase reads added | +3 agents × new passes | **0 new code reads** — harvest from Wave 1/2 existing reads |
| Calibration mechanism | Inlined prompt copies in both commands; maintainer discipline | Single `_shared/semantic_findings_spec.md` referenced by all agents |
| Quality framing | Same prompts = same calibration | Same schema + spec + quality gate; synthesis depth explicit (`draft\|canonical`) |
| Findings vocabulary | "Findings" (flat) | "Semantic Findings" unified; systemic vs localized distinguished schema-wise |
| Count cap | Not addressed | Removed; quality gate replaces |
| Output layout | Mechanical drift separate | Integrated via `source` field |
| Fast-scan upgrade | Not addressed | Wave 2 upgrades drafts → canonical on each deep-scan run |
| Per-folder CLAUDE.md | Not explicit | Preserved as Phase 2 input for `pattern_erosion` |
| Blueprint-awareness | Open question, leans deep-scan-only | Wave 2 always blueprint-aware; fast-scan Agent A blueprint-aware when blueprint exists |

---

## Migration order

1. **Write `_shared/semantic_findings_spec.md`** — the single calibration artifact. Design doc only, no code change.
2. **Upgrade fast-scan prompts (Agent A, B, C)** — reference the spec. Emit schema with `systemic` vs `localized`, `synthesis_depth: draft`. Remove count caps; apply quality gate. First shippable change; validates the spec live.
3. **Upgrade Wave 1 prompts (Structure, Patterns)** — add `pattern_observations` output block and localized findings in-domain. Blueprint facts preserved; observations are additive.
4. **Upgrade Wave 2 prompt** — reference spec. Produce Tier 2 systemic + listed localized types; perform upgrade pass on stored drafts. Add reads: `skeletons.json`, `health.json`, `drift_report.json`, prior `semantic_findings.json`.
5. **Shrink Phase 2 in deep-scan** — restrict to `semantic_duplication` + `pattern_erosion`. Remove current broad deep-drift prompt; replace with narrow prompt.
6. **Update Phase 3 aggregation** — merge Wave 1 + Wave 2 + Phase 2 + mechanical outputs into unified `semantic_findings.json`. Compute `lifecycle_status` by diff.
7. **Update Phase 4 / `scan_report.md` rendering** — new layout: Executive Summary → Systemic → Localized → Resolved → Mechanical.
8. **Sync to `npm-package/assets/`** — run `scripts/verify_sync.py`.
9. **Validation run** — `/archie-deep-scan --from 9` on craft-agents-oss. Compare new `scan_report.md` structure + systemic finding quality against prior output. Iterate on spec if calibration misses.

---

## Risks

1. **Wave 2 output size.** Canonical systemic + localized + upgrades + existing blueprint synthesis = larger canonical-tier output per run. Cost rises materially. Mitigation: cap upgrade pass at recurring drafts only; accept cost as quality trade.

2. **Wave 1 dual-job cognitive load.** Wave 1 agents now emit facts AND observations AND localized findings. If prompt isn't cleanly structured (Part 1 facts, Part 2 observations + findings), blueprint facts quality could dilute. Mitigation: strict prompt structure with explicit section boundaries.

3. **Spec file drift from agent prompts.** Spec is canonical; agent prompts reference it. If an agent prompt quietly restates calibration inline, the two can desync. Mitigation: convention + follow-up script (`scripts/verify_shared_prompts.py`) that greps for severity thresholds in agent prompts and flags any not sourced from the spec.

4. **Inflation despite quality gate.** AI may produce low-quality findings that nominally fill required fields. Mitigation: examples in spec file (good vs bad `fix_direction`, good vs bad `root_cause`); quality gate language is explicit on what "mechanistic" and "actionable" mean.

5. **Upgrade-pass race with fixes.** If a finding was genuinely resolved between fast-scans, but deep-scan's upgrade pass processes the draft as "recurring," stale findings could get enriched. Mitigation: upgrade pass runs **after** `lifecycle_status` computation, so resolved drafts are filtered before upgrade.

6. **Blueprint-aware Agent A calibration drift in fast-scan.** When blueprint exists, fast-scan Agent A uses it; when it doesn't (first run), Agent A runs without it. Severity of the same finding may differ pre/post first deep-scan. Acceptable: first-run findings are draft; next deep-scan produces canonical from richer context.

---

## Out of scope (follow-up work)

- Project-configurable severity thresholds (`archie_config.json` override of CC cutoffs, magnet fan-in cutoff, etc.) — useful for different language distributions, deferred to avoid scope creep.
- Shell script enforcing calibration consistency across agent prompts (see Risk 3).
- Viewer updates to surface systemic findings as headline UI elements with blast-radius visualization.
- Rule system: whether systemic findings auto-propose rules (implied but not 1:1). Keep decoupled for now.
- Fourth agent for security / performance categories — current three agents cover architectural surface; security-specific is a different design exercise.

---

## Success criteria

1. Running `/archie-scan` and `/archie-deep-scan --from 9` back-to-back on the same repo produces Semantic Findings that **agree on types and severities** for recurring items; deep-scan's canonical findings show measurably deeper `root_cause` + `fix_direction` than fast-scan's draft versions.
2. Calibration change (e.g., CC error threshold from 50 to 40) is a single edit to `semantic_findings_spec.md`; applies to both commands in one commit.
3. Systemic findings section in `scan_report.md` is the primary reading experience — users find headline issues without scrolling through localized noise.
4. Wave 2 upgrade pass visibly enriches previously-draft findings on second deep-scan run — same finding id, `synthesis_depth: canonical`, deeper text.
5. **No new codebase reads added** — deep-scan read count with this design ≤ deep-scan read count today.

---

## Related

- `docs/SCAN_CONSOLIDATION.md` — superseded by this doc
- `~/.claude/plans/archie-findings-normalization.md` — old executable plan, to be replaced after this design lands

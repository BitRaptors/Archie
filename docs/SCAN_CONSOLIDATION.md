> **⚠️ Superseded.** This plan has been replaced by `docs/plans/2026-04-16-semantic-findings-design.md`. The "triple-the-Phase-2-agent-count" approach described below was reconsidered — it would have *added* codebase reads; the new design harvests findings from existing Wave 1/2 reads. See the design doc for the current direction.
>
> Kept here for history.

---

# Scan Consolidation — `/archie-scan` and `/archie-deep-scan`

**Status:** Planned. Not yet implemented. Tracked at `~/.claude/plans/archie-findings-normalization.md`.

**Audience:** Archie maintainers deciding how to evolve the two scan commands.

---

## TL;DR

Archie has two scan commands today. They answer different questions but should share one Findings engine. Currently they don't — they produce different severities for the same issues, because deep-scan uses a blueprint-anchored "deep drift" agent while fast-scan uses three specialized agents (Architecture, Health, Rules) with calibrated thresholds. Users seeing both run notice the gap.

**Plan:** Keep the two commands distinct in *scope* (baseline vs. incremental). Make them identical in *findings calibration*. One shared three-agent findings engine, two entry points.

---

## Current roles

### `/archie-deep-scan` — architectural baseline

Runs once per project (or on major refactors).

Produces:
- `blueprint.json` — decisions, components, pitfalls, trade-offs, architectural style, implementation guidelines
- `CLAUDE.md`, `AGENTS.md` — context for AI coding agents
- Per-folder `CLAUDE.md` via the intent layer
- Proposed enforcement rules from blueprint extraction
- `scan_report.md` (Phase 4 of Step 9) — findings from the deep-drift agent

Runtime: 15-20 minutes. Two waves of AI + Wave 2 reasoning agent.

**Intent:** build the architectural mental model. "What is this codebase?"

### `/archie-scan` — incremental health check

Runs after every material change. Meant to be cheap and frequent.

Produces:
- Evolved `blueprint.json` (compound learning — merges new observations with existing)
- Refreshed `health.json`, appended `health_history.json`
- `scan_report.md` — ranked findings (NEW / RECURRING / RESOLVED)
- `proposed_rules.json` — new rules discovered
- `semantic_duplications.json` (as of `feature/metrics_pimp`) — Agent C's near-twin function list

Runtime: 1-3 minutes. Three parallel Sonnet agents.

**Intent:** "What broke since last scan? What's getting worse?"

---

## The inconsistency

### Observed symptom

A user ran `/archie-deep-scan` on craft-agents-oss. The shared blueprint had **zero errors, only warnings** — things like *"god-repository pattern: warn"*. Next they ran `/archie-scan`. The new shared blueprint had **errors**: same issues, now tagged `error` severity, plus new ones.

Quote from the investigation: *"in the deep scan only warnings came and 0 errors, and in the /archie-scan we had errors."*

The same codebase. Two different readings.

### Why it happens

Deep-scan's Step 9 Phase 2 runs **one** subagent ("deep drift") with a blueprint-grounded prompt:

> *"You are an architecture reviewer. You have the project's blueprint (decisions, pitfalls, patterns). Find deep architectural violations."*

This prompt is calibrated for documentation: pitfalls are warn-by-default because the blueprint already describes them as "known trade-offs we accept." The agent interprets active manifestations through that lens.

Fast-scan's Phase 3 runs **three** subagents in parallel, each with explicit severity thresholds:

- Agent A (Architecture & Dependencies): cross-layer violations = `error`, cycles crossing boundaries = `error`, dependency magnets = `warn|info`
- Agent B (Health & Complexity): CC > 100 = `error`, 50-99 = `warn`, 10-49 = `info`, trajectory regressions = `warn`
- Agent C (Rules & Patterns): rule violations = `error`, new pattern findings = `warn|info`, semantic duplications = `warn|error` depending on security surface

The same cycle that deep-drift rates warn ("this is a documented trade-off") gets rated error by Agent A ("this is an active boundary violation").

### Concrete examples (craft-agents-oss)

| Issue | Deep-scan rated | Fast-scan rated |
|---|---|---|
| 22-dir mega-cycle in `packages/shared` | *warn (pitfall)* | `error` |
| `apps/webui` importing from `apps/electron/src/shared` | *not flagged* | `error` |
| AppShell (CC 669), FreeFormInput (CC 507), etc. | *listed in CC table but not as findings* | `error` |
| `shouldAllowToolInMode` (CC 105, security-critical) | *not flagged* | `error` |
| Barrel coupling `handlers→src` (weight 52) | *not flagged* | `error` |

The issues exist equally in both outputs; only the severity differs. That's the consolidation problem.

---

## The plan

**Replace deep-scan's single deep-drift agent with fast-scan's three agents, verbatim prompts.** Both commands then emit findings through the same three-agent pipeline with the same calibration.

### What stays distinct

- **Deep-scan Steps 1-8** remain — scanner, Wave 1 fact gathering, Wave 2 reasoning, AI rule synthesis, intent layer. This is the blueprint engine.
- **Fast-scan Phases 1-2** remain — data gathering, reading accumulated knowledge.
- **The scope of each command** remains — one is baseline + blueprint, one is incremental check.

### What gets unified

- **Findings production** — both commands run Agent A / B / C via the same three-agent phase.
- **Severity thresholds** — single source of truth, applies identically to both.
- **Output schema** — same JSON shapes for dependency_violations, complexity_hotspots, pattern_findings, semantic_duplications.
- **`scan_report.md` format** — already the same; no changes needed.

### Deep-scan's structural advantage preserved

Fast-scan sometimes runs against an empty blueprint (first run, or drift-only mode). Deep-scan ALWAYS has a populated blueprint by the time Step 9 Phase 2 runs (Steps 1-7 built it). To leverage this:

Agent A gets a small addendum when invoked by deep-scan:

> *"A blueprint is already populated at `$PROJECT_ROOT/.archie/blueprint.json`. Use `decisions.key_decisions`, `decisions.trade_offs[].violation_signals`, and `pitfalls[].stems_from` to anchor severity. Code matching a documented `violation_signals` entry is `error`-severity — the trade-off boundary is actively crossed."*

Same calibration + richer context. No new agent, no new pipeline.

### Shared prompt maintenance

The three agent prompts currently live only in `archie-scan.md`. When this plan lands, the same text is physically inlined in both slash command markdown files. To avoid silent drift:

1. Source of truth: `.claude/commands/_shared/agent_a_architecture.md`, `_b_health.md`, `_c_rules.md`.
2. `archie-scan.md` and `archie-deep-scan.md` include the inlined copies under a maintainer comment: *"Canonical here — when editing any of the three agent prompts, update BOTH slash commands plus the corresponding `_shared/` fragment in one commit."*
3. (Follow-up, not in this plan) A shell script in `scripts/verify_shared_prompts.py` that diffs the fragments vs. the inlined copies and fails `verify_sync.py` if they diverge.

---

## What breaks, what doesn't

### Doesn't break

- Existing `blueprint.json`, `health.json`, `scan_report.md` files — schemas stay identical.
- Existing shared URLs — bundles are immutable in Supabase; they render on whatever the hosted viewer supports.
- Existing `.archie/archie_config.json` (scope config) — unchanged.
- The `--incremental`, `--from N`, `--continue`, `--reconfigure` flags on deep-scan — all unchanged.

### Might change for users

- Deep-scan's `scan_report.md` will now list errors where it previously listed warns. Anyone with tooling that filters by severity needs to re-tune expectations.
- `drift_report.json`'s structure simplifies — the deep-drift agent output block goes away. The mechanical drift section (from `drift.py`) stays exactly as-is.
- Runtime: deep-scan Step 9 Phase 2 now runs three parallel Sonnet calls instead of one. Wall-clock is similar (parallel); token cost roughly 1.5-2× higher for Phase 2 alone. Overall deep-scan runtime change: negligible compared to Wave 1 + Wave 2.

### Requires one-time attention

- Users with customized `archie-deep-scan.md` (unlikely — it's a slash command, not user-authored) would need to re-apply their changes.

---

## Migration order when this ships

1. **Implement the three `_shared/` fragments** — extract the Agent A / B / C prompts from `archie-scan.md`, no logic change.
2. **Replace deep-scan Step 9 Phase 2** — swap single agent for three. Delete old deep-drift block.
3. **Update Phase 3/4 of deep-scan** — read from three temp files instead of one. Merge with mechanical drift as a fourth source.
4. **Sync to `npm-package/assets/`**.
5. **Verification pass:** run `/archie-deep-scan --from 9` on craft-agents-oss. Reuses existing blueprint, just rebuilds findings. Takes 2-5 min. Diff old vs new `scan_report.md`.

Expected outcome:
- Old deep-scan report: 0 errors, N warnings.
- New deep-scan report: should match or very closely approach the fast-scan's Findings for the same codebase. Errors where fast-scan has errors, consistent rankings for CC-dominated functions and cycles.

If calibration still diverges after this change, iterate on the Agent A addendum — more specific "when to escalate warn → error" guidance.

---

## Design rejected — "just add more agents to deep-scan"

We considered bolting Agent B and Agent C onto the existing deep-drift agent as peers (four-agent phase). Rejected because:

1. Then the deep-drift agent still exists with its (incompatible) calibration — consolidation doesn't happen, we just add volume.
2. Findings output shape differs between the two pipelines — viewer/renderer needs dual parsers.
3. Maintenance cost doubles.

The clean consolidation is a straight swap: deep-scan adopts fast-scan's findings engine, deep-scan's unique value is Steps 1-7 (the blueprint build).

---

## Success criteria

After this plan lands:

1. Running `/archie-scan` and `/archie-deep-scan --from 9` back-to-back on the same repo produces **substantially identical Findings sections** in the two `scan_report.md` outputs. Minor wording differences are acceptable; severity and categories must match.
2. A single prompt change (e.g., upgrading CC threshold from 10 to 15) applies to both commands in one commit.
3. New metric-producing features (like Path C semantic duplications from `feature/metrics_pimp`) write their output once, read by both commands via the same pipeline.
4. The viewer's Findings display logic doesn't branch on "was this a scan or deep-scan blueprint?" — always the same shape.

---

## Open questions for review

1. **Agent A addendum scope:** should it be deep-scan-only, or should fast-scan also get blueprint-awareness when a populated blueprint happens to exist? Leaning deep-scan-only — fast-scan is explicitly "might run on empty blueprint" and we want its calibration to stay robust to that.

2. **Severity thresholds:** current plan uses `CC ≥ 100 = error, 50-99 = warn, 10-49 = info`. Are those right? Different projects (Android vs TypeScript vs Kotlin) have different natural CC distributions. Consider making the threshold project-configurable via `archie_config.json` in a follow-up.

3. **Testing strategy:** we have unit tests for `upload.py`, `scanner.py`, `scan-config`. No tests for slash-command behavior directly (they're prompts). Validation is by re-running on real projects. Should we add a snapshot test — "run `/archie-scan` on a known repo with a pre-recorded scan, compare outputs" — as regression protection?

4. **Backwards compatibility for bundles already on Supabase:** these rendered fine before and will continue to render. No action needed.

---

## Related plans

- `~/.claude/plans/archie-findings-normalization.md` — the executable plan file with task-by-task implementation steps
- `~/.claude/plans/archie-monorepo-mode.md` — the completed workspace scope work (shipped in main via PR #39)

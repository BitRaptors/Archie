# Plan: Richer rules — surface architectural depth at the right moment

Generated: 2026-04-25 (v2.4.4 baseline)

## Context

Real-world signal from openmeter: of 36 AI-synthesized rules, ~15 are codegen/build housekeeping (don't edit `ent/db/*`, run `make gen-api` after TypeSpec changes, include `-tags=dynamic`) and the remaining ~21 "architectural" rules are still single-line forbid/require statements. None capture the depth that the blueprint already has — `decisions.decision_chain`, `trade_offs.violation_signals`, `pitfalls.fix_direction` (ordered steps!), `implementation_guidelines.usage_example` (real code).

The synthesizer is locked in a "rule = regex" frame. Three things reinforce this:

1. **Schema bias.** A rule has `check`, `forbidden_patterns`, `required_in_content`, `applies_to`. No field for "5-step recipe" or "cloneable template." Sonnet compresses every architectural insight into one-line `description` + a regex.
2. **Prompt bias.** Step 6 of `/archie-deep-scan` asks for "architectural rules." Sonnet interprets that narrowly. Path of least resistance is "never edit generated code" (100% confidence, mechanical to enforce, easy to phrase).
3. **No prompt-time recipe surface.** Even rich rules surface only at edit time. An agent starting feature work ("add a new domain") sees nothing telling them HOW to do it — just rules they'll trip on AFTER they start writing code.

## Goal

A coding agent in openmeter (or any Archie-using project) starting a feature should see:

- **Before they write any code:** the recipe — what file shape, what existing example to mirror, which decisions constrain this work.
- **As they write each file:** the regex-checked invariants (current state) PLUS the architectural rationale (decision chain + tradeoff signals) PLUS a canonical example from the codebase.
- **At the end:** the existing forbid/require checks block obvious mistakes.

Not: replace the current rules. Add complementary artifact types and connect existing blueprint richness to existing surfaces.

## Phases

### Phase 0 — Diagnostics (free, ~1-2 hours, no shipping)

Pre-flight checks before touching anything. Some may eliminate work in later phases.

- **Why didn't `rules/extractor.py` contribute to openmeter?** Run it against `openmeter/.archie/blueprint.json` standalone. If it produces output, find why that output isn't merged into `rules.json`. If it produces nothing, find why — bad blueprint shape? Disabled? Removed from pipeline? This is a "free" channel for deterministic structural rules; if we can fix it cheaply, do it.
- **Is `platform_rules.json` loaded?** Trace whether `pre-validate.sh` reads platform rules at all in the openmeter install. The 30 universal checks should be hitting every project; verify they are.
- **Source-field bug.** All 36 of openmeter's rules are missing the `source` field (Sonnet's Step 6 raw output doesn't tag origin). Trivial fix: post-process Step 6 output to stamp `source: "deep-baseline"` on every emitted rule. Lets us trace lineage in `rules.json` itself.

Output: a short note in this plan documenting what we found and which (if any) of these we're fixing alongside Phase 1. Don't expand scope — stay focused on the depth question.

### Phase 1 — Connect blueprint richness to edit-time (Angle 3, ~1 day)

The cheapest uplift. Today's rules are flat strings; the blueprint has the depth. Wire them together.

**Schema change** (additive, backward-compatible):

```json
{
  "id": "tx-001",
  "description": "Wrap helpers accepting *entdb.Client in entutils.Tx...",
  ...existing fields...,
  "see_also": [
    "decisions.key_decisions[3]",
    "pitfalls[7]",
    "implementation_guidelines[2]"
  ]
}
```

`see_also` is an array of dotted-path references into `blueprint.json`. Optional. Older rules without it work unchanged.

**Step 6 prompt update**: when emitting each rule, instruct Sonnet to identify the 1-3 blueprint sections that motivate the rule (the decision that forces it, the pitfall it prevents, the guideline that demonstrates the right shape) and emit them as `see_also` paths. Sonnet already wrote those blueprint sections in Wave 2 — it knows where they are.

**Renderer update** (`pre-validate.sh` + `inject-context.sh` + the rule-rendering path in `renderer.py`):

When a rule with `see_also` fires, follow the pointers and inline the referenced content. The agent now sees:

```
RULE tx-001 [error]: Wrap helpers accepting *entdb.Client in entutils.Tx
WHY (decision[3]): Database transactions span the full charge lifecycle to keep ledger and invoice state consistent...
EXAMPLE (guideline[2]):
  func (a *adapter) AdvanceCharges(ctx, in) error {
      return entutils.Tx(ctx, a.db, func(tx *entdb.Tx) error { ... })
  }
PITFALL avoided (pitfall[7]): Helpers that accept *entdb.Client without wrapping cause partial commits when the outer transaction fails...
```

Instead of just "Wrap helpers accepting `*entdb.Client` in `entutils.Tx`."

**Files touched**:
- `archie/standalone/renderer.py` — schema awareness for `see_also`, blueprint-pointer resolution helper
- `archie/standalone/check_rules.py` (or `pre-validate.sh` directly) — inline pointer expansion at injection time
- `.claude/commands/archie-deep-scan.md` Step 6 prompt — add the see_also instruction
- `tests/test_rules_see_also.py` (new) — schema validation, pointer resolution, missing-pointer fallback, multiple-pointer case

**Backward compat**: existing `rules.json` files without `see_also` work as today. Existing blueprints without the referenced sections (older ones) — pointer resolution returns empty, rule renders as before. Zero regression.

**Ship as 2.4.5 (patch).** Risk-free additive change.

### Phase 2 — Three artifacts from Step 6 (Angle 2, ~2-3 days)

After Phase 1 ships and we see the uplift in real projects, restructure Step 6 to produce richer artifacts directly instead of compressing them.

**Step 6 prompt rewrite**: replace "propose architectural rules" with three sub-asks. Each gets its own JSON output:

```
Sub-ask 1: rules.json (today's shape — forbid/require checks)
  "What enforcement-time invariants in this codebase need a regex check at the
  point of edit? One-line, narrow `applies_to`, high confidence only."

Sub-ask 2: recipes.json (NEW)
  "When a developer adds a NEW {domain, feature, integration, handler, etc.} to
  this codebase, what is the procedural recipe? List the exact files to create,
  the order, the canonical example to mirror. 3-7 steps each. Tied to keywords
  the user might say at the start of feature work."

Sub-ask 3: layering.json (NEW)
  "What is the import-allowed matrix between component groups? Which group may
  import from which? Output an explicit allow/deny graph. This generates
  `forbidden_import` rules deterministically AND surfaces as a prose section."
```

Each output is consumed differently:

- `rules.json` → today's `pre-validate.sh` (edit-time regex checks). Unchanged.
- `recipes.json` → NEW prompt-time injection in Phase 3.
- `layering.json` → renders into `.claude/rules/layering.md` (always-loaded prose) AND deterministically generates `forbidden_import` rules (programmatic, not Sonnet-dependent — closes the gap from Phase 0's deterministic-extractor question).

**Files touched**:
- `archie/standalone/finalize.py` — new schema validators for `recipes.json` and `layering.json`
- `archie/standalone/renderer.py` — render layering into `.claude/rules/layering.md`, render recipes preview into `.claude/rules/recipes.md` (the deeper UX is in Phase 3)
- `.claude/commands/archie-deep-scan.md` Step 6 prompt — three sub-asks, three output files
- `tests/test_step6_artifacts.py` (new) — each sub-output has a clean schema + survives the synthesis loop

**Backward compat**: deep-scans on older blueprints just produce `rules.json` (sub-ask 1) and skip the others if Sonnet returns empty. No change to consumers that don't read recipes/layering yet.

**Ship as 2.5.0 (minor — adds new public output files).** Real new capability.

### Phase 3 — Prompt-time recipe injection (Angle 1, ~1 week)

The deepest change and the highest-leverage one for "actual development effort." After Phase 2, `recipes.json` exists but isn't yet surfaced where it matters.

**Recipe schema**:

```json
{
  "id": "new-domain",
  "trigger_keywords": ["new domain", "add domain", "create package"],
  "intent": "Add a new domain package under openmeter/<name>/",
  "steps": [
    "Create `openmeter/<name>/service.go` with a Service interface...",
    "Create `openmeter/<name>/adapter/ent_adapter.go` mirroring openmeter/billing/adapter/...",
    "Create `openmeter/<name>/httpdriver/handler.go` using pkg/framework/transport/httptransport.Handler[Request,Response]",
    "Register wire provider in `app/common/<name>.go`",
    "Add Kafka topic registration if cross-binary events are needed (see kafka-001)"
  ],
  "canonical_example": "openmeter/billing/",
  "see_also": [
    "decisions.key_decisions[1]",
    "implementation_guidelines[0]"
  ],
  "related_rules": ["layer-001", "layer-002", "kafka-001"]
}
```

**Hook integration**: extend `pre-turn.sh` (or add a new `inject-recipe.sh` for the UserPromptSubmit event). On every user prompt, keyword-match against `recipes.json`. If a match fires, inject the full recipe into the agent's context BEFORE any code is written.

The agent now sees, at the START of feature work:

> User said: "Let's add a new domain for promotions"
> [Archie injection] Recipe `new-domain` matched. Steps: 1) ... 2) ... 3) ... Canonical example: openmeter/billing/. Related rules: layer-001 (Service interface required), layer-002 (Wire providers in app/common/), kafka-001 (Kafka topic provisioning). See decision[1] and guideline[0] for rationale.

This converts Archie from a "block bad edits" tool into a "guide good edits" tool.

**Files touched**:
- `archie/standalone/install_hooks.py` — register the new hook (or extend `pre-turn.sh`)
- `.claude/hooks/inject-recipe.sh` (new) — keyword match, inline injection
- `archie/standalone/recipes.py` (new, optional) — load + match logic if shell-only is too brittle. Probably yes — keyword matching across N recipes with synonyms is cleaner in Python.
- `tests/test_recipes.py` — schema validation, keyword matching, edge cases (multiple recipes match, no match, malformed file)
- Permission allowlist update in `install_hooks.py` if a new script enters the allowlist

**Backward compat**: projects without `recipes.json` see no behavior change. The hook fails open (silent no-op). Existing scan/deep-scan workflows untouched.

**Ship as 2.6.0 (minor — new feature surface).** This is the biggest UX shift.

## Sequencing rationale

| Phase | Cost | Risk | Uplift | Order |
|---|---|---|---|---|
| Phase 0 | 1-2 hr | None | Clarity + maybe free wins | First |
| Phase 1 | ~1 day | Low (additive) | High (immediately makes existing rules richer) | Second |
| Phase 2 | 2-3 days | Med (new schemas) | High (unlocks recipes + layering as data) | Third |
| Phase 3 | ~1 week | Med (new hook surface) | Very high (where the user's real ask lives) | Fourth |

Phase 1 first because it gives 80% of the perceived depth uplift at 10% of the cost — by simply linking what's already in the blueprint to what's already injected at edit time. Phase 2 is the schema work that lets Phase 3 exist. Phase 3 is the biggest UX shift but only works on top of Phase 2's outputs.

We can pause after any phase. Phase 1 alone is shippable as a noticeable improvement to v2.4.5.

## Cross-cutting concerns

- **npm-package sync.** Every Phase touches scripts that need mirroring to `npm-package/assets/`. `scripts/verify_sync.py` catches misses.
- **Permission audit.** No new shell tools. Phase 3's hook should reuse the allowlisted `python3 .archie/*.py *` pattern. Verify with the audit grep before each release.
- **Tests.** Each Phase ships with tests (no skipping). At minimum: Phase 1 schema + pointer resolution + fallback; Phase 2 three-output validation; Phase 3 keyword-match + injection rendering.
- **Real-world validation.** After each Phase, sync the updated scripts into `~/DEV/gbr/openmeter` and run `/archie-scan` (Phase 1) or `/archie-deep-scan --from 6` (Phase 2) or a fresh feature prompt (Phase 3). Confirm the agent sees richer context. The plan succeeds when openmeter's rule view stops feeling shallow.

## Open questions (decide before implementing each phase)

1. **Phase 1 — pointer syntax.** `decisions.key_decisions[3]` (dotted) vs JSON Pointer (`/decisions/key_decisions/3`) vs JSONPath (`$.decisions.key_decisions[3]`). Lean toward dotted — already used in scan-config inspect queries. Consistent with existing tooling.
2. **Phase 2 — should `layering.json` also produce mechanical `forbidden_import` rules?** Yes — closes the deterministic-extractor gap from Phase 0. Adds value with zero AI cost on subsequent runs.
3. **Phase 3 — keyword matcher: substring vs token vs embedding?** Start with substring matching against an explicit `trigger_keywords` array (cheapest, deterministic, debuggable). Embedding-based matching is a future enhancement if substring proves too brittle.
4. **Phase 3 — recipe rendering format.** Inline as prose? Numbered checklist? Separate context-injection block? Lean toward "prose with a clear `## ARCHIE RECIPE: <id>` header" so the agent can reference back to it during the work.
5. **Should we add `recipes.json` to the share bundle?** Probably yes (Phase 3) — a teammate viewing the share viewer should see "this is the recipe they're following," not just rules. Small renderer addition.

## Out of scope

- Embedding-based recipe matching (Phase 3 substring is enough).
- Templates as a separate artifact from recipes (overlap is high; recipe + canonical_example covers the same ground).
- Live recipe updates from PR feedback (loop where merged PRs feed back into recipes). Future work.
- Cross-project recipe sharing (e.g. "this Go-fx project follows the standard fx recipe"). Single-project for now.

## Checkpoints

- After Phase 0: brief writeup in this doc + decisions on Phase 1 schema.
- After Phase 1: openmeter's `rules.json` rules show pointer-followed depth in `.claude/rules/*.md`. Ship 2.4.5.
- After Phase 2: openmeter has a `recipes.json` and `layering.json` after `/archie-deep-scan --from 6`. Ship 2.5.0.
- After Phase 3: agent in openmeter sees the recipe BEFORE writing code. Ship 2.6.0.

# Plan: Richer rules — alignment loop with structured triggers

Generated: 2026-04-25 (v2.4.4 baseline)
Supersedes: an earlier draft of this file that framed the problem as "more enforceable rules". The framing was wrong; this is a rewrite.

## Why we started this

Real-world signal from the openmeter project: of 36 AI-synthesized rules in `.archie/rules.json`, ~15 are codegen/build housekeeping (don't edit `ent/db/*`, run `make gen-api` after TypeSpec changes, include `-tags=dynamic`) and the remaining ~21 "architectural" rules are single-line forbid/require statements. None capture the depth that the blueprint already has — `decisions.decision_chain`, `decisions.trade_offs[].violation_signals`, `pitfalls[].fix_direction` (ordered steps!), `implementation_guidelines[].usage_example` (real code).

All 36 rules came from `/archie-deep-scan` Step 6 (Sonnet rule synthesis). Zero from the mechanical extractor, zero from `platform_rules.json`. The depth limit is in the AI prompt + the rule schema reinforcing each other into a "rule = regex" frame.

## What we actually want

Archie has a semantic map of the codebase — components, decisions, patterns, tradeoffs, the way this team writes code. The job isn't *blocking bad edits at the regex layer*. It's keeping the coding agent moving in the same direction the codebase is already moving, by:

1. **Nudging** — at architectural decision points (drafting a plan, creating a new file, writing a function signature), surface the relevant patterns from the existing codebase as context. The agent writes code that *naturally* fits because it has the right examples.

2. **Catching divergence** — at the same moments, compare what the agent is doing against what the codebase already does. Flag the difference. Severity is driven by what blueprint section got crossed.

These two together form a continuous **architectural alignment loop**: the agent has freedom, but at every decision point it sees the existing pattern AND gets caught when it veers off.

## Severity gradient (the blueprint already encodes it)

| Crossed | Maps to | Response |
|---|---|---|
| `decisions.key_decisions` | `decision_violation` | **Block** — exit 2 with explanation. Load-bearing architectural commitments cannot silently violate. |
| `pitfalls` | `pitfall_triggered` | **Block** — exit 2. Walking into a documented trap. |
| `decisions.trade_offs[].violation_signals` | `tradeoff_undermined` | **Warn** — exit 0 prominent. Agent might have a reason, but it has to be conscious. |
| `components.patterns`, `implementation_guidelines` | `pattern_divergence` | **Inform** — exit 0 quiet. Stylistic mismatch, not wrong. |
| `rules.json` (mechanical, regex-checkable) | `mechanical_violation` | **Block** — exit 2 fast. Existing behavior, unchanged. |

Same detection mechanism produces all five outcomes. The blueprint section determines which.

## Trigger model: structured, not keyword

Free-form NL prompts are too noisy for load-bearing architectural checks. Real prompts paraphrase wildly — "let's add support for promotions" / "build out the promotion feature" / "set up a new module for discounts" all mean "new domain", but a fixed keyword list catches maybe 25% of them.

**Anchor triggers to structured surfaces** — actions, file paths, code shapes, plan text, diffs — not free-form text. The agent's *actions* are far more structured than its *words*.

| Hook | Input | Trigger surface | Latency budget |
|---|---|---|---|
| UserPromptSubmit | Free-form NL | **Topical context only** — keep current `inject-context.sh` keyword behavior for noise-tolerant prose rules. **Do not fire severity-graded checks here.** | Hot |
| ExitPlanMode | Plan text (concrete artifact) | AI classifier subagent (Haiku) | Generous (user just submitted a plan) |
| PreToolUse Write | File path + intended content | Path-glob + dir-shape match (deterministic) | Hot |
| PreToolUse Edit | File path + diff | Path-glob + AST-shape match via tree-sitter (deterministic) | Hot |
| PreToolUse Bash on `git commit` | Full diff | AI classifier subagent (Haiku) on diff | Generous |
| PostToolUse ExitPlanMode | Approved plan | Existing `post-plan-review.sh` extended with classifier output | Generous |

The asymmetry **is** the design: cheap deterministic detection on the hot path (every edit), expensive semantic classification only at moments where there's a single concrete artifact to reason about (plan, commit).

## Pre-computed index

The blueprint is too rich to scan on every edit. At deep-scan time generate `.archie/rule_index.json`:

```json
{
  "by_path_glob": {
    "openmeter/*/": ["pattern-domain-shape", "decision-layer-001"],
    "openmeter/billing/charges/adapter/": ["decision-tx-001"],
    "openmeter/ent/db/**": ["mechanical-gen-001"]
  },
  "by_code_shape": {
    "function_takes_entdb_client": ["decision-tx-001"],
    "uses_context_TODO_or_Background": ["pitfall-ctx-001", "tradeoff-ctx-propagation"],
    "directory_lacks_service_go": ["pattern-domain-shape", "decision-layer-001"]
  },
  "for_classifier": [
    "decision-1", "decision-3", "pattern-7", "pitfall-2", "..."
  ]
}
```

- `by_path_glob` and `by_code_shape` feed the hot-path edit-time hooks (O(1) lookup, then deterministic check).
- `for_classifier` is the candidate list passed to the AI classifier at plan/commit time.

No `by_keyword` map for severity-graded checks. Keyword matching that exists today (`inject-context.sh`) stays untouched for noise-tolerant prose rule injection at prompt time.

## Scan's role in the loop

`/archie-deep-scan` (slow, 15-20 min) establishes the architectural baseline — blueprint, rules, intent files, index. `/archie-scan` (fast, 1-3 min) is the **iteration loop** that keeps the rule set fresh between deep-scans. Without scan staying in the picture, the rule set ages out the moment the codebase moves.

In the new model, scan does three things:

**1. Proposes new rules in the same shape as deep-scan.** Scan's existing AI step (the senior-architect pass) already spots drift — recently-added files diverging from a pattern, new pitfalls emerging, decisions being silently violated. Today it emits flat single-line rules. Going forward it emits the new shape: structured trigger (path-glob / code-shape / classifier candidate), `see_also` pointers, and a `source: "scan"` provenance tag so users can tell scan-born rules from deep-scan baseline ones.

**2. Infers severity from the blueprint anchor, doesn't invent it.** Scan tries to anchor each proposed rule to a blueprint section:

| Anchor | Severity | Rationale |
|---|---|---|
| `decisions.key_decisions[*]` or `pitfalls[*]` | `decision_violation` / `pitfall_triggered` (block) | Rule clarifies an existing load-bearing artifact. |
| `decisions.trade_offs[*].violation_signals` | `tradeoff_undermined` (warn) | Rule formalizes a known tradeoff signal. |
| `components.patterns` or `implementation_guidelines` | `pattern_divergence` (inform) | Rule captures stylistic pattern. |
| No anchor (genuinely new pattern not in blueprint) | `pattern_divergence` (inform) | Default lowest-severity until reasoned about. |

Scan never promotes a rule to `decision_violation` on its own — promotion happens at the next deep-scan, when the rule gets reasoned about with full Wave-2 context (decision chain, tradeoffs, pitfalls). This keeps scan fast and prevents premature blocking.

**3. Adjusts existing rules, not just adds.** Scan can also propose *diffs* to existing rules: trigger too broad (false positives in the recent diff history), trigger too narrow (real divergence missed), `see_also` pointer stale (referenced section moved or got rewritten). Each adjustment carries the same provenance tag (`source: "scan-amended"`). Deep-scan reconciles these on its next run.

**4. Updates the trigger index.** Phase 2's `.archie/rule_index.json` is regenerated whenever rules change. Scan rebuilds the index after appending/amending — cheap operation (a few hundred ms) that keeps the hot-path lookups in sync without waiting for the next deep-scan.

The split is clean: deep-scan is the slow, expensive *reasoning* pass that establishes architectural depth; scan is the fast, frequent *maintenance* pass that keeps the rule set live and the trigger index fresh. Both produce rules in the same shape — only severity-promotion authority and reasoning depth differ.

## Phases

### Phase 0 — Diagnostics (1-2 hr, no shipping)

- **Why didn't `rules/extractor.py` contribute to openmeter?** Run it standalone against openmeter's `blueprint.json`. If it produces output, find why that output isn't merged. If it produces nothing, find why — bad blueprint shape, disabled, removed from pipeline.
- **Is `platform_rules.json` actually loaded?** Trace whether `pre-validate.sh` reads it in the openmeter install.
- **Source-field tagging bug.** All 36 of openmeter's rules are missing the `source` field. Trivial: post-process Step 6 output to stamp `source: "deep-baseline"`. Lets us trace lineage.

Output: short notes documenting findings, fold the cheap fixes into Phase 1.

### Phase 1 — Severity-graded blueprint pointers in rules (~2 days, ships as 2.5.0)

Cheapest big win. Most of the blueprint's architectural depth is already there; rules just don't reference it.

**Schema additions** (additive, backward-compat):

```json
{
  "id": "tx-001",
  "description": "...",
  "severity_class": "decision_violation",   // NEW: maps to the response gradient
  "see_also": [                             // NEW: pointers into blueprint sections
    "decisions.key_decisions[3]",
    "pitfalls[7]",
    "implementation_guidelines[2]"
  ],
  ...existing fields stay...
}
```

`severity_class` makes the gradient explicit on every rule. `see_also` carries the depth.

**Step 6 prompt update**: when emitting each rule, instruct Sonnet to (a) classify the severity, (b) identify the 1-3 blueprint sections that motivate it, (c) emit them as `see_also` paths. Sonnet wrote those sections in Wave 2 — it knows where they are.

**Renderer + hook update**: `pre-validate.sh` follows `see_also` pointers and inlines the referenced content. The agent now sees:

```
RULE tx-001 [decision_violation]: Wrap helpers accepting *entdb.Client in entutils.Tx
  WHY (decisions.key_decisions[3]): Database transactions span the full charge lifecycle...
  EXAMPLE (implementation_guidelines[2]): func (a *adapter) AdvanceCharges(ctx, in) error { return entutils.Tx(... ) }
  PITFALL avoided (pitfalls[7]): Helpers accepting *entdb.Client without wrapping cause partial commits...
```

Backward compat: existing rules without `see_also`/`severity_class` work as today.

**Files touched**: `archie/standalone/renderer.py`, `archie/standalone/check_rules.py` (or `pre-validate.sh`), `.claude/commands/archie-deep-scan.md` Step 6 prompt, `tests/test_rules_see_also.py` (new).

### Phase 2 — Pre-computed trigger index + structured edit-time triggers (~3-4 days, ships as 2.6.0)

This is where the alignment loop actually replaces keyword matching for load-bearing checks.

**Step 6 produces trigger annotations** for every blueprint section it emits. Decisions, patterns, pitfalls each get:

```json
{
  "id": "tx-001",
  "triggers": {
    "path_glob": ["openmeter/billing/charges/**/adapter/**"],
    "code_shape": [
      {
        "kind": "function_signature",
        "must_match": "func * (... *entdb.Client, ...) ...",
        "must_not_be_inside": "entutils.Tx(...)"
      }
    ]
  }
}
```

Sonnet writes these alongside the artifact. Path-glob is straightforward; code-shape uses a small DSL that maps to tree-sitter queries (already in the codebase for skeleton extraction).

**Index generator** (new step in `/archie-deep-scan`, between Steps 6 and 7): walks every artifact's triggers, writes `.archie/rule_index.json`. ~150 lines.

**Hook updates**:
- `pre-validate.sh` reads the index. For an edit:
  1. O(1) path-glob lookup → get candidate IDs
  2. Tree-sitter parse of the diff → match `code_shape` triggers → get more candidate IDs
  3. For each candidate: load the artifact, check if it actually fires
  4. Severity gate: response per `severity_class`
- Edit-time response is identical to today (block on `mechanical_violation` / `decision_violation` / `pitfall_triggered`, warn on `tradeoff_undermined`, inform on `pattern_divergence`)

**Code-shape matchers**: small Python library wrapping tree-sitter queries. Detectors for: `function_takes(type)`, `function_calls(name)`, `function_does_not_call(name)`, `directory_has_file(name)`, `directory_lacks_file(name)`, `import_uses(symbol)`. Roughly 200 lines, reusable across all artifacts.

**Files touched**: `archie/standalone/intent_layer.py` or new `archie/standalone/rule_index.py`, `archie/standalone/code_shape.py` (new), `archie/standalone/check_rules.py` updates, `.claude/commands/archie-deep-scan.md` Step 6 prompt expanded with trigger requirements, `tests/test_rule_index.py` + `tests/test_code_shape.py` (new).

Backward compat: artifacts without triggers are skipped at edit-time, still surface via session-load `.claude/rules/*.md`.

### Phase 3 — AI classifier at plan-time + commit-time (~3-4 days, ships as 2.7.0)

Plan and commit are the highest-leverage moments — single concrete artifact, generous latency budget.

**Classifier subagent**: small Haiku call. Input:
- The plan text (or commit diff)
- Candidate artifact list from `for_classifier` in the index
- Severity classes per artifact

Output: structured diagnostic per artifact:

```json
{
  "diagnostics": [
    {
      "artifact_id": "decision-3",
      "severity_class": "decision_violation",
      "verdict": "violates",
      "evidence": "Plan creates openmeter/promotions/ but does not include service.go with Service interface",
      "suggested_fix": "Add 'Create openmeter/promotions/service.go with type Service interface { ... }' as step 1"
    },
    {
      "artifact_id": "pattern-7",
      "severity_class": "pattern_divergence",
      "verdict": "diverges",
      "evidence": "Plan uses fmt.Errorf for domain errors; existing handlers use models.GenericValidationError",
      "suggested_fix": "Wrap domain errors in models.GenericValidationError"
    }
  ],
  "highest_severity": "decision_violation"
}
```

**Hook updates**:
- `post-plan-review.sh` (extends existing): runs classifier, blocks (exit 2) if any `decision_violation` or `pitfall_triggered` in diagnostics. Renders the structured diagnostic as the rejection message — actionable, references real artifact IDs and files to mirror.
- `pre-commit-review.sh` (extends existing): same classifier on the diff. Last line of defense.

**Latency**: one Haiku call per plan submit / per commit. Plans happen ~hourly, commits maybe 5-10x per hour during active work. Cost is negligible compared to the value.

**Files touched**: `archie/standalone/arch_review.py` extended (or new `align_check.py`), `.claude/hooks/post-plan-review.sh` + `pre-commit-review.sh` updates, `tests/test_align_check.py` (new — fixture-driven, mocking the classifier).

Backward compat: projects without the index (older deep-scans) skip the classifier. Existing arch-review behavior preserved.

### Phase 4 (optional, future) — UserPromptSubmit done right

If real-world use shows we want earlier intervention than plan time, revisit UserPromptSubmit with embeddings or a tiny classifier. Skip until Phases 1-3 are validated.

## Sequencing rationale

| Phase | Cost | Risk | Uplift | Ship |
|---|---|---|---|---|
| 0 | 1-2 hr | None | Clarity, free fixes | Folded into 2.5.0 |
| 1 | ~2 days | Low (additive schema) | High (existing rules become rich) | 2.5.0 |
| 2 | ~3-4 days | Med (new index, code-shape detectors) | Very high (structured edit-time triggers) | 2.6.0 |
| 3 | ~3-4 days | Med (AI classifier, plan/commit catch) | Highest for "the agent goes off-track and we catch it" | 2.7.0 |

Phase 1 first because cheapest and immediately makes existing rules richer at edit time. Phase 2 builds the structured-trigger machinery (replaces today's regex for the hot path). Phase 3 closes the catch loop at plan and commit time. Pause-points after each phase — every one is independently shippable.

## Cross-cutting concerns

- **npm-package sync.** Every phase touches scripts that mirror to `npm-package/assets/`. `scripts/verify_sync.py` catches misses.
- **Permission audit.** Phase 2's index lookup is `python3 .archie/check_rules.py` which is allowlisted (`python3 .archie/*.py *`). No new shell tools. Phase 3's hook spawns a subagent via `Agent(*)` which is also allowlisted. Verify with the permission audit before each release.
- **Tests.** Each phase ships with tests — schema validation (Phase 1), index generation + code-shape matching (Phase 2), classifier output parsing + severity gating (Phase 3).
- **Real-world validation.** After each phase, sync into `~/DEV/gbr/openmeter` and verify: (Phase 1) `pre-validate.sh` shows decision/pitfall pointers when relevant rules fire; (Phase 2) editing `openmeter/billing/charges/adapter/foo.go` to add a `*entdb.Client` function without `entutils.Tx` triggers `decision-tx-001` deterministically; (Phase 3) writing a plan that creates `openmeter/promotions/` without a Service interface gets blocked at ExitPlanMode with structured rejection.

## Open questions (decide per phase)

1. **Phase 1 — pointer syntax.** `decisions.key_decisions[3]` (dotted) vs JSON Pointer. Lean dotted (consistent with existing `inspect --query` tool).
2. **Phase 2 — code-shape DSL.** Hand-rolled small spec mapped to tree-sitter queries vs adopting an existing tool (semgrep would also work). Lean hand-rolled — fewer deps, narrower surface, easier for Sonnet to emit consistently.
3. **Phase 3 — classifier model.** Haiku for cost or Sonnet for accuracy? Lean Haiku — fast, cheap, the structured output schema constrains the model enough.
4. **Phase 3 — block vs warn for `tradeoff_undermined`.** Currently warn. Open question whether some tradeoffs (security, correctness) should block instead. Probably configurable per project.
5. **Index regeneration triggers.** Today the index is generated at `/archie-deep-scan`. Should `/archie-scan` also rebuild it (cheaper, more frequent)? Probably yes for small updates.

## What this delivers

The agent in openmeter (or any Archie-using project) writing a feature now experiences:

- **Before any code is written** (plan time): if the plan crosses a decision or triggers a pitfall, classifier catches it, plan blocked with structured explanation. Agent revises with awareness of the constraint.
- **As each edit happens** (edit time): pre-validate.sh fires deterministically on path/code-shape triggers. Decision/pitfall violations block. Tradeoff signals warn. Pattern divergences inform. Each message includes the referenced blueprint section so the agent sees the why and the canonical example.
- **At commit** (last line of defense): full-diff classifier catches anything edit-time hooks missed (multi-file structural problems, contradictions across the patch). Blocks commit on hard violations.

The "shallow rules" diagnosis from openmeter resolves not by enriching `rules.json` flatly, but by **lifting the architectural enforcement out of regex-on-single-file and into structured triggers + semantic comparison anchored in the blueprint**. The depth that already exists in `decisions`, `pitfalls`, `tradeoffs`, `implementation_guidelines` becomes load-bearing instead of cosmetic.

## Out of scope

- Embedding-based recipe matching (Phase 4 if ever).
- Recipes as a separate artifact type — the patterns + decisions + classifier together cover the same ground without a new schema.
- Live updates from PR feedback (continuous-learning loop). Future.
- Cross-project pattern sharing.

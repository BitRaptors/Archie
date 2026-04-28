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
| PreToolUse Write | File path + intended content | Path-glob + dir-shape match (deterministic) | Hot |
| PreToolUse Edit | File path + diff | Path-glob + AST-shape match via tree-sitter (deterministic) | Hot |
| PostToolUse ExitPlanMode | Plan text | Haiku classifier reads plan + full architectural rule set (existing `post-plan-review.sh` extended) | Generous |
| PreToolUse Bash on `git commit` | Full staged diff | Haiku classifier reads diff + full architectural rule set | Generous |

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
- `for_classifier` is the *architectural* rule set (semantic content: `description` + `why` + `example`) passed to the classifier at plan/commit time. This isn't a narrow shortlist for performance — it's the separation between "regex-checkable mechanical rules" (not useful pre-code) and "semantic architectural rules" (the ones that need reasoning over intent). Typically 30-40 of the 50.

No `by_keyword` map for severity-graded checks. Keyword matching that exists today (`inject-context.sh`) stays untouched for noise-tolerant prose rule injection at prompt time.

## Scan's role in the loop

`/archie-deep-scan` (slow, 15-20 min) establishes the architectural baseline — blueprint, rules, intent files, index. `/archie-scan` (fast, 1-3 min) is the **iteration loop** that keeps the rule set fresh between deep-scans. Without scan staying in the picture, the rule set ages out the moment the codebase moves.

In the new model, scan does three things:

**1. Proposes new rules in the same shape as deep-scan.** Scan's existing AI step (the senior-architect pass) already spots drift — recently-added files diverging from a pattern, new pitfalls emerging, decisions being silently violated. Today it emits flat single-line rules. Going forward it emits the new shape: inline `description + why + example`, `severity_class`, structured `triggers` (path-glob / code-shape / classifier candidate), and a `source: "scan"` provenance tag so users can tell scan-born rules from deep-scan baseline ones.

**2. Infers severity from the blueprint anchor, doesn't invent it.** Scan tries to anchor each proposed rule to a blueprint section:

| Anchor | Severity | Rationale |
|---|---|---|
| `decisions.key_decisions[*]` or `pitfalls[*]` | `decision_violation` / `pitfall_triggered` (block) | Rule clarifies an existing load-bearing artifact. |
| `decisions.trade_offs[*].violation_signals` | `tradeoff_undermined` (warn) | Rule formalizes a known tradeoff signal. |
| `components.patterns` or `implementation_guidelines` | `pattern_divergence` (inform) | Rule captures stylistic pattern. |
| No anchor (genuinely new pattern not in blueprint) | `pattern_divergence` (inform) | Default lowest-severity until reasoned about. |

Scan never promotes a rule to `decision_violation` on its own — promotion happens at the next deep-scan, when the rule gets reasoned about with full Wave-2 context (decision chain, tradeoffs, pitfalls). This keeps scan fast and prevents premature blocking.

**3. Adjusts existing rules, not just adds.** Scan can also propose *diffs* to existing rules: trigger too broad (false positives in the recent diff history), trigger too narrow (real divergence missed), `why` text out of date (referenced decision text was rewritten in the latest deep-scan). Each adjustment carries the provenance tag `source: "scan-amended"`. Deep-scan reconciles these on its next run.

**4. Updates the trigger index.** Phase 2's `.archie/rule_index.json` is regenerated whenever rules change. Scan rebuilds the index after appending/amending — cheap operation (a few hundred ms) that keeps the hot-path lookups in sync without waiting for the next deep-scan.

The split is clean: deep-scan is the slow, expensive *reasoning* pass that establishes architectural depth; scan is the fast, frequent *maintenance* pass that keeps the rule set live and the trigger index fresh. Both produce rules in the same shape — only severity-promotion authority and reasoning depth differ.

## Phases

### Phase 0 — Diagnostics (DONE 2026-04-27)

Findings, recorded so we don't re-diagnose:

**1. `rules/extractor.py` is wired into the wrong code path.** It runs from `archie/cli/init_command.py` (the CLI `archie init` flow), not from the `/archie-deep-scan` slash command. The slash command pipeline goes Step 6 (Sonnet AI synthesis) → `extract_output.py rules` → `rules.json`, with no extractor call anywhere. Run standalone on openmeter's `blueprint.json` it does produce 21 rules (12 placement + 9 naming) — but with a second bug: it reads `fpr.get("allowed_dirs", fpr.get("directories", []))` while the actual blueprint shape produced by Wave 2 has `location` (singular). All 12 placement rules come back with empty `allowed_dirs`, so even if merged they wouldn't enforce anything. Fix in Phase 1: either (a) update extractor to read `location` and call it from the slash command path, or (b) accept that Step 6 covers placement+naming via `architectural_constraint` and retire the extractor. Lean (b) — Step 6's coverage is already richer.

**2. `platform_rules.json` IS wired correctly.** Both `pre-validate.sh` (line 21 of `install_hooks.py`) and `check_rules.py` (line 416) read it. Openmeter has 30 active platform rules (god-function, force-unwrap, layer rules per platform, etc.). Plan's earlier "zero from platform_rules" framing was misleading — they're orthogonal (universal anti-patterns), not disabled. No fix needed.

**3. `source` field is missing because nobody stamps it.** Step 6's prompt schema in `archie-deep-scan.md` (lines 1166-1186) doesn't include `source` as a field, and `extract_output.py cmd_rules` writes Sonnet's output verbatim without post-hoc stamping. Fix in Phase 1: (a) add `"source": "deep_scan"` to the rule schema in the Step 6 prompt, AND (b) stamp `source = "deep_scan"` defensively in `cmd_rules` for any rule missing it (defense-in-depth — can't trust the model to emit every field).

**Cheap fixes folded into Phase 1**: source-field stamp (both prompt + post-hoc), retire the unused extractor wiring (or update its blueprint key mapping if we want to keep it for `archie init`).

### Phase 1 — Inline rule shape with severity + content (~2 days, ships as 2.5.0)

Cheapest big win. Most of the blueprint's architectural depth is already there; rules just don't carry it. Sonnet at Step 6 already writes both the blueprint sections and the rule — it just needs to inline the content directly into the rule instead of flattening it. **No pointers, no indirection** — the rule is what the agent sees, so it carries exactly the strings that go into the message.

**Schema additions** (additive, backward-compat):

```json
{
  "id": "tx-001",
  "severity_class": "decision_violation",
  "description": "Wrap helpers accepting *entdb.Client in entutils.Tx",
  "why": "Database transactions span the full charge lifecycle. Helpers that accept a raw *entdb.Client without wrapping in entutils.Tx cause partial commits when an error occurs mid-flow, leaving inconsistent state in billing tables.",
  "example": "func (a *adapter) AdvanceCharges(ctx, in) error { return entutils.Tx(ctx, a.client, func(tx *entdb.Tx) error { ... }) }",
  "source": "deep_scan",
  ...existing fields stay (id, triggers come in Phase 2)...
}
```

Three new load-bearing fields:
- `severity_class` — maps to the response gradient (`decision_violation`, `pitfall_triggered`, `tradeoff_undermined`, `pattern_divergence`, `mechanical_violation`)
- `why` — the reasoning, copy-pasted from the blueprint section that motivated the rule (decision text, pitfall description, tradeoff signal, pattern rationale)
- `example` — canonical code shape, copy-pasted from `implementation_guidelines.usage_example` when present
- `source` — provenance tag (`deep_scan`, `scan`, `scan-amended`)

**Why no `see_also` pointers.** The agent doesn't read pointers; it reads the rejection message. Either the content lives in the rule and gets shown directly, or it doesn't reach the agent at all. Indirection would mean the hook has to load `blueprint.json`, parse it, walk a path expression, and resolve fragments on every rule fire — extra file read, extra parser, extra failure mode (stale pointer when blueprint changes). Inlining is one file, one read, no resolver code.

**Step 6 prompt update**: when emitting each rule, instruct Sonnet to (a) classify the severity from which blueprint section motivated the rule, (b) inline the relevant `why` text from that section, (c) inline the canonical code shape from `implementation_guidelines.usage_example` when applicable, (d) stamp `source: "deep_scan"`. Sonnet wrote those sections in Wave 2 — copying the content forward costs nothing at generation time.

**Renderer + hook update**: `pre-validate.sh` reads the new fields directly from the rule. Agent sees:

```
RULE tx-001 [decision_violation]: Wrap helpers accepting *entdb.Client in entutils.Tx
  WHY: Database transactions span the full charge lifecycle. Helpers that accept a raw
       *entdb.Client without wrapping in entutils.Tx cause partial commits when an error
       occurs mid-flow, leaving inconsistent state in billing tables.
  EXAMPLE: func (a *adapter) AdvanceCharges(ctx, in) error {
             return entutils.Tx(ctx, a.client, func(tx *entdb.Tx) error { ... })
           }
```

No blueprint read, no pointer resolution. Hook reads rule, prints rule, exits per `severity_class`.

Backward compat: existing rules without `severity_class` default to `mechanical_violation` and render with description-only message. **No in-place migration of existing rules.json** — users on prior Archie versions run a fresh `/archie-deep-scan` to regenerate `rules.json` in the new shape. This is the same upgrade path users already follow when blueprint structure changes (cheaper than building a one-shot migrator that has to handle every prior schema variant).

**Extractor retirement.** `archie/rules/extractor.py::extract_rules()` is removed in this phase along with its callers in `archie/cli/init_command.py` (lines 16, 106, 115) and the corresponding `tests/test_rule_extractor.py` cases. Reasons: (a) the deep-scan slash command never called it, (b) its `allowed_dirs` lookup is stale (reads `allowed_dirs`/`directories`, blueprint produces `location`), (c) Step 6's `architectural_constraint` rules cover placement+naming richer with full semantic content. The other extractor.py functions (`load_rules`, `save_rules`, `promote_rule`, `demote_rule`) are kept — they're used by `archie rules promote/demote` CLI and `check_command.py`. README.md and ARCHITECTURE.md sections that mention "Blueprint extraction" are updated to reflect the new pipeline (Step 6 is the rule producer). After retirement, fresh `archie init` produces empty `rules.json` until the user runs `/archie-deep-scan` or `/archie-scan` — same as projects today that don't run the CLI init flow.

**Test plan** (new file `tests/test_rule_shape.py`):

1. **Schema validation** — every rule in a new-shape `rules.json` parses; `severity_class` is one of the five allowed enums; `source` is one of `deep_scan` / `scan` / `scan-amended` / `adopted`; `description` is non-empty.
2. **Backward-compat rendering** — old-shape rule (no `severity_class` / `why` / `example`) renders the agent message correctly: shows `description`, defaults severity to `mechanical_violation`, omits WHY/EXAMPLE blocks (no empty lines).
3. **New-shape rendering** — full rule (all five fields) renders as the spec at lines 145-155: header line with `RULE id [severity_class]: description`, then `WHY:` block, then `EXAMPLE:` block. Multi-line `why` and `example` indent correctly.
4. **Severity gating** — given a fired rule, `pre-validate.sh` exits 2 for `decision_violation`/`pitfall_triggered`/`mechanical_violation`, exits 0 with `WARN:` prefix for `tradeoff_undermined`, exits 0 with `INFO:` prefix for `pattern_divergence`.
5. **Source-field stamping** — `extract_output.py cmd_rules` stamps `source = "deep_scan"` on rules emitted without one (defense-in-depth against Sonnet omitting it). Rules that already have a `source` are not overwritten.
6. **Regression**: openmeter's 36 existing old-shape rules render without crashing when the new hook is run against them (proves backward compat works on real-world data).

**Files touched**:
- Canonical: `archie/standalone/check_rules.py`, `archie/standalone/extract_output.py`, `archie/standalone/install_hooks.py` (PRE_VALIDATE_HOOK rendering of `why`/`example`), `archie/standalone/renderer.py` (only if rules render into per-folder `.claude/rules/*.md`), `.claude/commands/archie-deep-scan.md` (Step 6 prompt schema)
- npm-package mirrors: `npm-package/assets/check_rules.py`, `npm-package/assets/extract_output.py`, `npm-package/assets/install_hooks.py`, `npm-package/assets/renderer.py`, `npm-package/assets/archie-deep-scan.md`
- Removed: `archie/rules/extractor.py::extract_rules()`, callers in `archie/cli/init_command.py:16,106,115`, `tests/test_rule_extractor.py` (the extract_rules-specific cases)
- New: `tests/test_rule_shape.py`
- Doc updates: `CLAUDE.md` (the Rules System section), `README.md` (the Rules section at line 457), `docs/ARCHITECTURE.md` (section 1 at line 560)
- Sync verification: `scripts/verify_sync.py` after every batch of canonical→asset changes

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

**Files touched**:
- Canonical: new `archie/standalone/rule_index.py` (or extend `intent_layer.py`), new `archie/standalone/code_shape.py`, `archie/standalone/check_rules.py` (consume index), `.claude/commands/archie-deep-scan.md` (Step 6 prompt expanded with trigger requirements + index-build step between Steps 6 and 7)
- npm-package mirrors: `npm-package/assets/rule_index.py`, `npm-package/assets/code_shape.py`, `npm-package/assets/check_rules.py`, `npm-package/assets/archie-deep-scan.md`
- New: `tests/test_rule_index.py`, `tests/test_code_shape.py`
- Sync verification: `scripts/verify_sync.py`
- Installer: `npm-package/bin/archie.mjs` references for any new asset (verify_sync.py catches this)

Backward compat: artifacts without triggers are skipped at edit-time, still surface via session-load `.claude/rules/*.md`.

### Phase 3 — Semantic comparison at plan-time + commit-time (~3-4 days, ships as 2.7.0)

Plan and commit are the highest-leverage moments — single concrete artifact, generous latency budget. This phase does what edit-time hooks structurally can't: **compares the plan's semantic meaning against each architectural rule's semantic content**.

The setup: blueprint rules carry their *meaning* (`description` + `why` + `example`), not just their name. The plan carries its *intent* in natural language. An LLM reads both and reasons across paraphrase — no shared keywords or matching paths required.

Concrete example. Rule `layer-ui-no-domain` says "UI layer must not contain domain logic." Plan says "Add a discount calculator to ui/components/CheckoutForm.tsx." Zero keyword overlap, no path-glob signal, no code yet for tree-sitter to parse. Edit-time hooks see nothing. The classifier reads "discount calculator in CheckoutForm" and the rule's `why` ("pricing decisions belong in domain/, UI receives computed results") and produces:

```json
{
  "rule": "layer-ui-no-domain",
  "verdict": "violates",
  "evidence": "Step 1 puts discount calculation inside CheckoutForm.tsx (UI layer). Computing 15% off is domain logic.",
  "suggested_fix": "Move calculation to domain/billing/promotions/, expose via service, form reads computedTotal."
}
```

**Classifier subagent**: single Haiku call. Input:
- The plan text (or commit diff)
- The architectural rule set with full semantic content (`description` + `why` + `example`) — every rule whose `severity_class` is not `mechanical_violation`. No narrowing, no shortlisting. For openmeter that's ~25-30 of the 36 rules; mechanical regex rules (don't-edit-generated-files, file-naming-regex) are excluded since they don't apply pre-code.
- Severity classes per rule

Output: structured diagnostic per artifact:

```json
{
  "diagnostics": [
    {
      "rule_id": "decision-3",
      "severity_class": "decision_violation",
      "verdict": "violates",
      "evidence": "Plan creates openmeter/promotions/ but does not include service.go with Service interface",
      "suggested_fix": "Add 'Create openmeter/promotions/service.go with type Service interface { ... }' as step 1"
    },
    {
      "rule_id": "pattern-7",
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

**Latency / cost**: one Haiku call per plan submit / per commit. ~5K tokens of rule content + plan/diff fits in a single prompt comfortably. Plans happen ~hourly, commits 5-10x per hour during active work. Per-call cost negligible (~fraction of a cent).

**Why this is the load-bearing phase, not just a "nice to have":**
- Edit-time catches structural violations (an import line crossing layers, a function signature missing `entutils.Tx`).
- Plan-time catches *intent* violations before any code exists — a plan to put domain logic in UI never reaches edit-time because the plan itself gets rejected.
- Commit-time catches semantic leakage that has no structural marker — UI re-implementing pricing in inline arithmetic, no imports involved, just primitives that happen to encode business rules.

The three together cover the spectrum: deterministic on the hot path (Phase 2), semantic at the moments where there's a single concrete artifact and a generous budget (Phase 3).

**Files touched**:
- Canonical: `archie/standalone/arch_review.py` extended (or new `archie/standalone/align_check.py`), `archie/standalone/install_hooks.py` (post-plan-review and pre-commit-review hook bodies)
- npm-package mirrors: `npm-package/assets/arch_review.py` (or `align_check.py`), `npm-package/assets/install_hooks.py`
- New: `tests/test_align_check.py` (fixture-driven, mocking the classifier with canned diagnostic outputs)
- Sync verification: `scripts/verify_sync.py`

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
- **Permission audit.** Verified 2026-04-27 against `npm-package/assets/install_hooks.py:364-401` (the 29-entry allowlist installer): `Bash(python3 .archie/*.py *)` is line 366, `Agent(*)` is line 400. So Phase 2's index lookup (`python3 .archie/check_rules.py`) and Phase 3's classifier subagent spawn (`Agent(*)`) need no new allowlist entries. Re-verify before each release in case the allowlist changes.
- **Tests.** Each phase ships with tests — schema validation (Phase 1), index generation + code-shape matching (Phase 2), classifier output parsing + severity gating (Phase 3).
- **Real-world validation.** After each phase, sync into `~/DEV/gbr/openmeter` and verify: (Phase 1) `pre-validate.sh` renders `description + why + example` inline when relevant rules fire, no blueprint read; (Phase 2) editing `openmeter/billing/charges/adapter/foo.go` to add a `*entdb.Client` function without `entutils.Tx` triggers `decision-tx-001` deterministically; (Phase 3) writing a plan that creates `openmeter/promotions/` without a Service interface gets blocked at ExitPlanMode with structured rejection.

## Open questions (decide per phase)

1. **Phase 1 — duplication risk.** Inlining `why` and `example` into rules duplicates content from `blueprint.json`. Mitigation: same Sonnet pass writes both, so they stay in sync at deep-scan time; scan amends both via `source: "scan-amended"` if the blueprint changes mid-cycle. Acceptable cost for the simpler hot path.
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

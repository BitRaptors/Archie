# Archie System Review — Follow-ups

- **Status:** Backlog of agreed improvement directions. Each item graduates to its own
  design/spec before implementation.
- **Date:** 2026-07-07
- **Source:** whole-system review after landing the delivery review (PR #107), the
  task-story imprint (`docs/archie-task-story-imprint-design.md`), and the review-engine
  v2 spec (`docs/archie-review-engine-v2-design.md`).

---

## The system shape (context for every item below)

Archie is a **three-representation reconciliation system**:

```
1. WHAT WAS WANTED      task story (imprinted from user turns, versioned,
                        session-scoped, provenance-checked facts)
2. WHAT SHOULD HOLD     blueprint mirror + domain invariants + derived laws
                        + rules (seeded by deep-scan; mirror folds via sync,
                        laws move only deliberately)
3. WHAT WAS BUILT       the diff + code (evidence pack / tool loop in v2)

   1 ⋈ 3  edge-A completeness          "built the right thing?"
   3 ⋈ 2  behavioral + universal       "built it right? broke a law?"
          lenses + contract→tracer→challenger
   1 ⋈ 2  edge-C conflict              "is the ask itself illegal?"

   all findings → editor gate (falsification, floors, dedup, no-invent)
               → one verdict artifact (story + facts + provenance + breaks)
```

Differentiators to preserve in every follow-up: grading against *captured* intent with
per-fact provenance; product-law enforcement with a proof loop; clean-room capture;
pure-GitHub-Action zero-infrastructure delivery; base-ref execution security.

---

## F1 — Close the feedback loop (the system writes verdicts but never reads outcomes)

**Priority: HIGH (foundation).**

**Problem.** Nothing records whether a finding was fixed, dismissed, or wrong — so
precision never improves, per repo or globally. The system has no reaction channel;
every mature reviewer has one.

**Direction (zero-infra).**
- Parse 👍/👎 reactions and replies on the verdict comment (GitHub API access already
  exists in `intent_review.py`).
- Store per-finding outcomes (`fixed` / `dismissed` / `not-reproduced`) in
  `.archie/findings.json` keyed by the P1 dedup key.
- Feed outcomes back as calibration: a lens with a high dismissal rate in a repo gets
  its confidence discounted; repeatedly-confirmed patterns get promoted.
- Composes with review-engine v2 §P4 (per-PR memory) — this is the *cross-PR* learning
  layer on top of it.

**Acceptance sketch:** after N dismissals of a finding pattern, the same pattern renders
in "possible issues" (or is suppressed with a disclosed count) instead of "breaks".

## F2 — Anchor re-validation (anchor rot is the weakest joint)

**Priority: HIGH (quietly load-bearing — a law with a dead anchor is silently unenforced).**

**Problem.** Selector routing, invariant enforcement, and edge-C lean on blueprint
anchors (`enforced_at: "worker/main.py:757"`) that decay as code moves. Observed live:
billing invariants anchored in `worker/` never routed for changes in the duplicated
`new_worker/` tree until the parallel-tree tolerance patch — which is a patch, not a fix.

**Direction.**
- `/archie-sync` already walks changed code: add an anchor re-resolution pass that
  verifies each touched invariant's `enforced_at` still points at the cited mechanism
  (cheap text/symbol match), updates moved anchors in the mirror-fold, and **reports**
  (never silently drops) anchors it cannot re-resolve.
- Longer-term: make anchors symbolic (entity/function names + file) rather than
  file:line, resolving to lines only at review time.

**Acceptance sketch:** renaming/moving an anchored file leaves the invariant routable;
an unresolvable anchor surfaces as a sync warning and a verdict-header disclosure.

## F3 — One review engine, two mouths (unify local + CI)

**Priority: HIGH — but do it *inside* the v2 build, not after.**

**Problem.** `sync_review` (local) and `delivery_review` (CI) are drifting
implementations of the same review; all v2 work currently lands only in the CI path.
Fixes/behavior will diverge and the local demo won't match the PR verdict.

**Direction.** Extract a shared review core — evidence pack → fan-out (edges + lenses +
specialist) → gate — consumed by two thin publishers: local (terminal report) and CI
(comment/checks). v2's plan should create the core module first and wire both callers.

**Acceptance sketch:** the same diff produces the same findings locally and in CI, modulo
publisher formatting.

## F4 — Graduated enforcement: use the teeth the verdict already computes

**Priority: MEDIUM. Converges with the in-progress Architecture Integrity Score branch.**

**Problem.** `aggregate_verdict` computes `gate_signal`; everything still exits 0 and
posts a comment. Right for adoption, but there is no opt-in escalation path, and the
review's confirmed findings are exactly the events the AIS (branch
`feature/architecture-integrity-score`) should consume — today they are two unconnected
efforts describing the same judgment.

**Direction.**
- Opt-in (`.archie/config.json` or an `archie-enforce` label): challenger-confirmed
  invariant violations — the system's highest-confidence signal — set a failing
  check/commit status; everything else stays advisory.
- Feed confirmed findings + `gate_signal` into the AIS so the score reflects reviewed
  reality, not just static divergences.

**Acceptance sketch:** a repo with enforcement on fails the check only for
challenger-confirmed `conformance_break`s; default installs behave exactly as today.

## F5 — The "A" problem: capture decisions, not just words

**Priority: MEDIUM severity, SMALL size — a correctness bug in the most-trusted artifact.**

**Problem (observed live).** Clean-room capture records only *user* turns. Mid-session
decisions arrive as agent-question + terse user answer ("A", "yes", "apply the cap") —
the synthesizer sees the answer without the question, so the decision is informationally
invisible. Concretely: the cost-preview story marked the 7-step cap a **non-goal** even
though the user had explicitly approved applying it mid-session; the delivery review then
flagged drift against a decision the user had actually made.

**Direction.** When a user turn looks like an answer (short; follows an agent question),
capture the **question–answer pair**, with the agent's question stored as
`kind: "context"` — usable by the synthesizer to *interpret* the answer, never itself a
source of intent facts (preserves the clean-room property: provenance still requires the
user's words; the question only disambiguates them).

**Acceptance sketch:** a re-run of the cost-preview scenario yields a story in which the
cap decision matches what the user actually approved.

## F6 — Calibrate the constants (every threshold is currently a guess)

**Priority: MEDIUM (maturity wave; also protects against model-upgrade regressions).**

**Problem.** 60% provenance-overlap, `BREAK_CONFIDENCE = 0.6`, 2-pass agreement mapping,
gate floors — all defended by argument, not data. No measured precision/recall exists.

**Direction.** Build a small review eval set on the existing benchmark harness
(`archie/benchmark`): seeded-bug PRs + a handful of historical PRs with known outcomes;
measure per-lens precision/recall; tune thresholds against data; re-run on model changes.
F1's outcome data (dismiss/fix) becomes free labeled data over time.

**Acceptance sketch:** a `benchmark review` mode that reports precision/recall per lens
against the eval set, run before threshold or prompt changes land.

---

## Sequencing

1. **F2 + F1** — protect the foundation everything else stands on (anchors, learning).
2. **F3** — as part of the review-engine v2 build (create the shared core first).
3. **F5** — small, sharp correctness fix; can ride any nearby release.
4. **F4** — after v2 stabilizes; merge paths with the AIS branch.
5. **F6** — maturity wave; seeded by F1's outcome data.

## Related documents

- `docs/archie-review-engine-v2-design.md` — the code-review capability spec (P0–P5).
- `docs/archie-task-story-imprint-design.md` — intent imprint (layer 1).
- `docs/archie-delivery-review-design.md` — the reconciliation triangle.
- Memory: AIS branch (`feature/architecture-integrity-score`), contract-layer direction
  (contract.yaml as agent-consumed product) — F4 and the anchor work should stay
  consistent with both.

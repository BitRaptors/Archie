# Living Blueprint — Snapshot vs. Contract (implementation plan)

- **Status:** Design agreed; ready to plan into work.
- **Builds on:** `docs/archie-intent-review-design.md` + `docs/archie-intent-review-delivery-plan.md`.
- **One-line goal:** split the blueprint into a **mirror** (tracks the code, auto-updated by sync) and a **contract** (the law — changes only by deliberate edit), so the Intent Review reliably catches drift *and* distinguishes a **violation** from an **intended amendment** using the diff — never commit-message prose.

This is not a redesign. The cap test already behaved this way by luck (sync moved the description to 12, left the rules at 7, the review caught the gap). The plan just makes that behavior **the rule**, and makes "did the contract change?" the intent signal.

---

## 1. The two layers

| Layer | Meaning | Blueprint keys / files | Who moves it |
|---|---|---|---|
| **Mirror** (descriptive) | "what the code *is* now" | `components`, `communication`, `data_overview`, `data_models`*, `architecture_diagram`, `technology`, `quick_reference`, decision `how_it_works`/rationale prose | **sync auto-updates** from the diff |
| **Contract** (prescriptive) | "what *must hold*" | `domain_invariants`, `derived_invariants`, `rules.json`, `platform_rules.json`, key `decisions` (forced_by/enables), `pitfalls`, the rendered `.claude/rules/*.md` | **deliberate edit only** |

\* `data_models` is mirror for *shape* changes; a genuinely new persistence guarantee is a contract amendment. Edge case — flag in implementation.

**Principle:** the review's value is detecting when the **mirror drifts from the contract**. A collision fires only when a change contradicts something that *stayed the same*.

---

## 2. Phase 1 — sync's code-fold is contract-readonly (the core change)

Today `/archie-sync`'s fold can write the contract: `_SECTION_MAP` ([sync.py:412-425](archie/standalone/sync.py)) routes a `rule` claim to `rules.json` and `pitfall` to `findings.json`/`pitfalls`; `cmd_fold_apply` re-renders all docs (incl. `.claude/rules/*.md`) via `renderer.generate_all` ([sync.py:607](archie/standalone/sync.py)). That's the path that *could* silently move the law.

**Change A — `_SECTION_MAP` / `cmd_fold_context` ([sync.py:412-485](archie/standalone/sync.py)):** in the **default (descriptive) fold**, only mirror sections are valid edit targets. Advisory/contract kinds (`rule`, contract-level `decision`, `pitfall`-as-invariant) are **not auto-folded** into `rules.json`/invariants — they're recorded in the ledger as **`staged` amendments** (already a concept: `eligible` vs `staged`) and surfaced to the dev, not written to the contract.

**Change B — `cmd_fold_apply` ([sync.py:560-637](archie/standalone/sync.py)):** the re-render must not let a descriptive fold mutate contract artifacts. Render mirror-derived docs from the blueprint; render contract docs (`.claude/rules/*.md`) **from `rules.json` (unchanged)** so they can't drift to match the mirror. Extend the existing guardrail snapshot to assert `rules.json` + the invariant sections are **byte-identical** before/after a descriptive fold.

**Change C — `archie/assets/workflow/sync/SKILL.md` (Step 4 "where edits land"):** rewrite the instruction so the agent's code-fold edits **mirror sections only**; a claim that would change the law is reported as a *proposed amendment* (Phase 2), never folded in place.

**Acceptance:** after a code-fold, `git diff` of `.archie/rules.json`, `domain_invariants`, `derived_invariants`, and `.claude/rules/*.md` is **empty**; only mirror sections + `.archie/changes/*` changed. Add a sync test asserting this on a cap-style change.

---

## 3. Phase 2 — Accept *is* the amendment (no manual rule-editing)

There is **no separate "edit the rules" task**. At the PR the human has exactly two moves:

- **Fix** — change the code to comply. The mirror returns to the old behavior; the contract is never touched. ("The rule still holds.")
- **Accept (merge)** — the change becomes the new baseline, and the contract moves to match it. ("The rule is obsolete; this is the new law.")

The contract move on Accept is **auto-drafted by the system, not hand-written.** The review already knows which rules the change hits (it computed the diff) and which **interlocked** rules must move with them (shared keywords / `forced_by` / `enables` — e.g. `inv-002` → `der-001`/`der-005`/`tra-001`). It drafts that *consistent* amendment; merging applies it. This is the **"auto-drafted amendment"** from the original brainstorm — Archie writes the rule change; the human just takes it or rejects it.

**The merge-vs-fix choice is the intent signal** — no commit prose, no manual editing.

**Mechanism (pick during planning):**
- (a) **In-PR suggestion** — the review posts the drafted contract change as a suggested commit; "Accept" applies it (one action), then merge accepts a consistent branch. Cleanest fit with "merge = acceptance" (the branch already holds the amended contract).
- (b) **On-merge reconcile** — a post-merge step applies the drafted amendment to the contract on `main`.

**Acceptance:** the human never hand-edits `rules.json`; **Accept** yields a *consistent* contract change (all interlocked rules moved together); **Fix** leaves the contract untouched. If the auto-draft is incomplete (misses an interlocked rule), Phase 3's consistency check flags it *before* Accept.

---

## 4. Phase 3 — the review presents Fix-or-Accept (and drafts the amendment)

The review already diffs `rules.json` and separates *changed* rules from *retained* context ([intent_review.py](archie/standalone/intent_review.py) `build_changed_items` / `retained_rules`), so most of this falls out.

**Change A — draft the consistent amendment.** For each drift, compute the contract change Accept would apply: the affected rules **plus their interlocked rules** (shared keywords / `forced_by` / `enables`), with the new values — so Accept has something concrete to take.

**Change B — present each finding as the two moves:**
- **⚠️ Drift — Fix or Accept.** *"The code now does 12; the contract says 7. **Fix** the code, or **Accept** to move `inv-002`/`der-001`/`der-005`→12 and retire `tra-001` (drafted below) as the new baseline."*
- **⚠️ Inconsistent amendment.** If a contract change already on the branch moved one rule but left an interlocked one, flag it *before* Accept ("also update `der-001`").

**Acceptance** — the discussion cases:
- code only, no amendment applied → **Fix-or-Accept drift** (replaces "violation"); the draft is shown.
- drafted amendment applied consistently → **clean Accept**, no inconsistency flag.
- amendment applied partially → **inconsistent amendment** flag.

---

## 5. Worked example (cap 7 → 12)

The dev changes code (cap→12) and runs sync. The mirror says "now 12"; the contract still says 7. The review flags the drift and **drafts** the consistent contract amendment. The dev then has exactly two moves:

| Human move | Mirror | Contract | Result |
|---|---|---|---|
| **Fix** — revert the cap to 7 | back to 7 | unchanged | drift gone, no finding |
| **Accept** — take the drafted amendment + merge | 12 | system moves `inv-002`/`der-001`/`der-005`→12, retires `tra-001` | consistent new baseline |

No manual rule-editing in either path. Safety net: if the auto-draft moved `inv-002` but missed `der-001`, the review flags an **inconsistent amendment** *before* Accept — a half-amendment can't merge.

---

## 6. Out of scope
- Auto-deciding whether an amendment is *correct* (still the human's call on merge — design §11).
- Reading commit/PR prose for intent (deliberately rejected — unreliable).
- Layer-3 raw-code reading (still eval-gated).

## 7. Risks & mitigations
| Risk | Mitigation |
|---|---|
| Phase 1 breaks existing sync users who relied on auto-folding rules | Advisory claims still recorded (as `staged`); only the *auto-write* stops. Document in the SKILL + changelog. |
| `data_models` ambiguity (shape vs guarantee) | Treat as mirror by default; a new persistence *guarantee* is an explicit amendment — flag during impl. |
| Renderer regenerates contract docs from blueprint, re-introducing drift | Phase 1 Change B: render `.claude/rules/*.md` from `rules.json`, not the mirror; assert byte-identity in the guardrail. |
| Dev forgets to amend interlocked rules | Phase 2 Change B completeness help + Phase 3 "inconsistent amendment" bucket catch it. |

## 8. Open questions
1. Phase 2 mechanism for the auto-draft: **in-PR drafted suggestion** (Accept applies it pre-merge) vs. **on-merge reconcile**. Recommend the in-PR suggestion — it keeps "merge = acceptance" literal (the branch already holds the amended contract) and needs no post-merge automation. Who computes the consistent draft: the review model, or a deterministic interlock walk from `forced_by`/`enables`? (Likely model-proposed, deterministically scoped.)
2. Are `decisions` one layer or split (prose = mirror, forced_by/enables = contract)? Likely split — confirm against the schema.
3. Does `renderer.generate_all` cleanly separate mirror-docs from contract-docs today, or does Change B need a renderer split?

## 9. Sequencing
**Phase 1 first** (contract-readonly fold) — it alone makes the drift reliable and fixes the rendered-doc inconsistency you found. **Phase 3** (Fix-or-Accept presentation + the drafted amendment) is the high-value UX step — do it next. **Phase 2** (actually *applying* the draft: in-PR suggestion or on-merge reconcile) last. Each phase ships independently and is testable on its own. Note: with this framing Phase 3 *drafts* the amendment and Phase 2 *applies* it — the human only ever Fixes or Accepts.

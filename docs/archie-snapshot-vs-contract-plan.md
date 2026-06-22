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

## 3. Phase 2 — the deliberate amendment path

When a contract *is* obsolete and should move, there must be an explicit, opt-in way to move it — and it must land in the PR diff so it's reviewable.

**Change A — an amend mode.** Either (pick one during planning):
- (a) **Hand-edit** `rules.json`/invariants in the PR (zero new tooling; the dev just edits the law deliberately), or
- (b) **`/archie-sync --amend` / `/archie-amend`** — an explicit step where the agent reconciles `staged` contract claims *into* `rules.json`/invariants, marked `folded_as: amendment`.

**Change B — completeness help (optional, high-value):** when amending one rule, surface the **interlocked** rules (those sharing keywords/`forced_by`/`enables` — e.g. `inv-002` → `der-001`/`der-005`/`tra-001`) so the dev amends them together and doesn't ship a half-amendment.

**Acceptance:** amending the contract requires a deliberate action; the change appears in the PR's `rules.json`/invariant diff; nothing about a *code* change alone can produce it.

---

## 4. Phase 3 — the review labels amendment vs. violation

The review already diffs `rules.json` and treats changed rules as *changed items* and unchanged ones as *retained* context ([intent_review.py](archie/standalone/intent_review.py) `build_changed_items` / `retained_rules`). So Cases B/C below already largely fall out — Phase 3 is mostly **labeling + visibility**.

**Change A — classify each finding** by whether the rule it concerns was **changed in this PR** (contract moved → *amendment*) or **retained** (contract unchanged → *violation*).

**Change B — render three buckets** instead of one undiscriminated list:
- **✅ Intended amendments (N)** — contract rules this PR deliberately changed. *"Merge accepts these as the new baseline — confirm."* (Visibility for "merge = acceptance.")
- **⚠️ Violations (M)** — the mirror changed but the unchanged contract forbids it.
- **⚠️ Inconsistent amendments** — a changed contract rule contradicts a *retained* one ("you raised `inv-002` to 12 but `der-001` still says 7 — finish the amendment").

**Acceptance** — the three cases from the discussion produce the three buckets:
- **A** code only, contract unchanged → *Violation*.
- **B** contract amended completely → *Intended amendment*, no violation.
- **C** contract amended partially → *Inconsistent amendment*.

---

## 5. Worked example (cap 7 → 12)

| What the dev does | Mirror | Contract | Review says |
|---|---|---|---|
| change code, run sync | "now 12" | unchanged (7) | **Violation** — `inv-002`/`der-001`/`der-005`/`tra-001` |
| change code + amend `inv-002`,`der-001`,`der-005`, retire `tra-001` | "now 12" | all → 12 | **Intended amendment (4 rules)** — confirm & merge |
| change code + amend only `inv-002` | "now 12" | `inv-002`→12, rest 7 | **Inconsistent amendment** — also update `der-001`/`der-005`/`tra-001` |

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
1. Phase 2 path: hand-edit vs. an `--amend` command — which ergonomics? (Recommend starting with hand-edit + Phase 3 visibility; add `--amend` if friction warrants.)
2. Are `decisions` one layer or split (prose = mirror, forced_by/enables = contract)? Likely split — confirm against the schema.
3. Does `renderer.generate_all` cleanly separate mirror-docs from contract-docs today, or does Change B need a renderer split?

## 9. Sequencing
**Phase 1 first** (contract-readonly fold) — it alone makes the drift reliable and fixes the rendered-doc inconsistency you found. **Phase 3** (labeling) is small and high-visibility — do it next. **Phase 2** (amend ergonomics) last, only if hand-editing proves too rough. Each phase ships independently and is testable on its own.

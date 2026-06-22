# Snapshot vs. Contract — Implementation Plan

- **Implements:** `docs/archie-snapshot-vs-contract-plan.md`.
- **Goal, restated in your words:** baseline (rules+blueprint) vs branch (rules+blueprint) → flag the deviation → user **merges** (accept) or **fixes the code**. The one nuance: sync moves the *blueprint* but not the *rules*, so "accept" must also move the rules — drafted by the system, applied on merge.
- **File-sync rule (CLAUDE.md):** every `archie/standalone/*.py` and `archie/assets/**` edit is mirrored to `npm-package/assets/`, then `python3 scripts/verify_sync.py`. Each milestone lists CANONICAL → COPY.

Ship order: **Phase 1 → Phase 3 → Phase 2.** Each is independently shippable and testable.

---

## Phase 1 — sync's code-fold is contract-readonly (the core; ship first)

**Why:** today `_KIND_TARGET` ([sync.py:413-426](archie/standalone/sync.py)) routes advisory claims into the contract (`rule`→`rules.json`, `decision`→`decisions`, `pitfall`→`pitfalls`+`findings.json`, `guideline`→`implementation_guidelines`). A code-fold should never silently move the law — that's what makes the deviation real and reliable.

### M1.1 — Gate the fold to mirror-only
- In `cmd_fold_context` ([sync.py:485](archie/standalone/sync.py)): emit fold edit-targets **only for descriptive kinds** (`behavior`, `structure`, `dataflow`, `data`, `tech`, `reference`). Advisory kinds (`decision`, `pitfall`, `guideline`, `rule`) are **not** emitted as edit targets — they stay in the ledger as `staged` and are reported to the dev as *proposed amendments*, not written.
- Keep `_KIND_TARGET` as the source of truth but split it: `_MIRROR_KINDS` (foldable) vs `_CONTRACT_KINDS` (staged-only in a normal fold).
- **Files:** CANONICAL `archie/standalone/sync.py` → COPY `npm-package/assets/sync.py`.
- **Acceptance:** after a descriptive fold, `git diff` of `.archie/rules.json`, `blueprint.json` `domain_invariants`/`derived_invariants`/`decisions`/`pitfalls`, and `.archie/findings.json` is **empty**.

### M1.2 — Guardrail: assert contract byte-identity
- Extend the guardrail snapshot in `cmd_fold_context`/`cmd_fold_apply` ([sync.py:532, 560](archie/standalone/sync.py)) to capture a hash of `rules.json` + the contract blueprint sections **before** the agent edits, and in `fold-apply` **abort the render** if a descriptive fold changed them (mirrors the existing "dropped a top-level section" guard).
- **Files:** same `sync.py` (CANONICAL → COPY).
- **Acceptance:** a fold that touches a contract section is rejected with a clear message.

### M1.3 — Rendered-doc consistency
- Audit `renderer.generate_all` ([sync.py:607](archie/standalone/sync.py) calls it; logic in `renderer.py`): confirm which `.claude/rules/*.md` derive from `rules.json` (contract) vs from blueprint pattern/decision sections (mirror). Contract-derived docs must render from `rules.json` (unchanged) so they can't drift to match the mirror — the inconsistency seen in the cap test.
- **Files:** `archie/standalone/renderer.py` (CANONICAL → COPY) if a split is needed; else just a test pinning it.
- **Acceptance:** after a descriptive fold, every contract-derived `.claude/rules/*.md` is byte-identical.

### M1.4 — SKILL instructions + tests
- Rewrite `archie/assets/workflow/sync/SKILL.md` Step 4 "where edits land": the code-fold edits **mirror sections only**; a claim that would change the law is reported as a *proposed amendment*, never folded. (CANONICAL → COPY `npm-package/assets/workflow/sync/SKILL.md`.)
- Tests (`tests/test_sync.py`): a cap-style change with a descriptive claim folds the mirror and leaves `rules.json`/invariants/contract-docs untouched; an advisory claim is recorded `staged`, not folded.
- **Acceptance:** `pytest tests/test_sync.py` green; `verify_sync` green.

---

## Phase 3 — review drafts the amendment + presents Fix-or-Accept

**Why:** for "accept" to mean something, the dev needs to see the drafted rule change. The review already separates changed vs retained rules ([intent_review.py](archie/standalone/intent_review.py)); this adds the draft + the two-move framing.

### M3.1 — Draft the consistent amendment
- For each deviation, compute the **interlock set**: the violated rule(s) + rules sharing `forced_by`/`enables`/keywords (e.g. `inv-002` → `der-001`/`der-005`/`tra-001`). Deterministic candidate scoping in the script; the model proposes the new text for each.
- New `emit_findings` field per finding: `proposed_amendment: [{rule_id, current, proposed}]`.
- **Files:** `archie/standalone/intent_review.py` (CANONICAL → COPY).
- **Acceptance:** a cap deviation yields a draft covering all four interlocked rules with new values.

### M3.2 — Render Fix-or-Accept
- `render_comment`: each deviation shows the two moves + the drafted change:
  *"The code now does 12; the contract says 7. **Fix** the code, or **Accept** to apply: `inv-002` 7→12, `der-001` 7→12, `der-005` 7→12, retire `tra-001`."*
- **Acceptance:** comment renders the draft as an applyable block.

### M3.3 — Consistency check (incomplete-amendment safety net)
- If the branch already changed some contract rules but left an interlocked one, flag **inconsistent amendment** ("also update `der-001`") — this already half-exists (changed-vs-retained contradiction); make it explicit.
- **Tests** (`tests/test_intent_review.py`): draft covers the interlock set; partial branch-amendment → inconsistency flag; clean branch-amendment → no flag.

---

## Phase 2 — apply the draft on Accept (novel; ship last)

**Why:** the human only Fixes or Accepts; Accept must move the rules with no hand-editing. Two candidate mechanisms — pick one (see open question):

### M2.1 — (Recommended) in-PR suggested change
- The Action posts the drafted amendment as a **GitHub suggested change** on the `rules.json` lines (or a companion commit). "Accept" = apply the suggestion → the branch's `rules.json` now matches → merge accepts a consistent baseline. Keeps "merge = acceptance" literal.
- Needs: stable line-anchoring of each rule in `rules.json` (it's structured JSON — anchor on the rule object). Falls back to a single "apply this patch" comment if line-level suggestions are infeasible.
- **Files:** `archie/standalone/intent_review.py` (the comment/suggestion payload) → COPY.

### M2.2 — (Alternative) on-merge reconcile
- A second workflow on `push` to the base applies the last drafted amendment to `rules.json` on `main` and commits it. Simpler anchoring, but the law moves *after* merge (a beat later) and needs write-to-main perms.

- **Acceptance:** Accept produces a consistent `rules.json` change with zero hand-editing; Fix leaves `rules.json` untouched; the next PR no longer re-flags the accepted change.

---

## Out of scope
- Auto-deciding whether an amendment is *correct* (human's call on merge).
- Commit/PR prose as an intent source (rejected — unreliable).
- Layer-3 raw-code reading (eval-gated, separate).

## Risks & mitigations
| Risk | Mitigation |
|---|---|
| M1.1 breaks teams relying on advisory auto-fold | Advisory claims still recorded (`staged`) + surfaced; only the silent write stops. Document in SKILL + changelog. |
| Interlock scoping misses a rule → incomplete draft | M3.3 consistency check flags it before Accept; conservative keyword+`forced_by`/`enables` walk. |
| GitHub line-suggestions on JSON are fragile (M2.1) | Anchor on rule-object boundaries; fall back to a patch comment / M2.2. |
| Renderer can't cleanly split contract vs mirror docs | M1.3 is an audit first; only split the renderer if needed. |

## Open questions
1. **Phase 2 mechanism:** in-PR suggestion (M2.1) vs on-merge reconcile (M2.2). Recommend M2.1.
2. **Interlock computation:** deterministic graph walk over `forced_by`/`enables` only, or include keyword overlap? Start with the explicit links; add keywords if recall is low.
3. **`data_models`:** mirror for shape changes, contract for a new persistence *guarantee* — where's the line? Decide in M1.1.

## Sequencing & effort
- **Phase 1** (M1.1–M1.4): the contract-readonly fold. Self-contained, the highest-leverage change, ships alone. *Largest single chunk, but bounded to `sync.py` + SKILL + tests.*
- **Phase 3** (M3.1–M3.4): drafting + Fix-or-Accept rendering. Builds on the working review; medium.
- **Phase 2** (M2.1): applying the draft. Smallest logic, most integration risk (GitHub suggestion mechanics) — do last, behind the others.

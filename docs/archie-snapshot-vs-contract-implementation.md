# Snapshot vs. Contract — Implementation Plan (Phase 1 only)

- **Implements:** `docs/archie-snapshot-vs-contract-plan.md`.
- **Goal (scoped down):** *clearly and reliably see the deviations on the PR.* The review already posts clear, consolidated findings (proven on the cap PR). The one remaining gap: make sure a deviation can't be **hidden** by sync silently moving the rules to match the code.
- **Deferred (revisit later):** drafting the rule amendment + "Fix or Accept" + applying it on merge. Not needed to *see* problems — only to *resolve* them. We'll evolve that once the seeing-problems loop is solid.

---

## What already works (no action)

The Intent Review Action diffs branch vs base, judges with one model call, and posts a consolidated FYI comment. The cap PR showed it works end to end. Nothing to do here.

## The one change: Phase 1 — sync's code-fold can't move the rules

**Why:** today `_KIND_TARGET` ([sync.py:413-426](archie/standalone/sync.py)) lets a fold write the contract (`rule`→`rules.json`, `decision`→`decisions`, `pitfall`→`pitfalls`+`findings.json`, `guideline`→`implementation_guidelines`). If a code-fold ever moves the rules to match the code, the deviation vanishes and the PR shows nothing — a hidden problem. Phase 1 closes that.

### M1.1 — Gate the fold to mirror-only
- `cmd_fold_context` ([sync.py:485](archie/standalone/sync.py)): emit fold edit-targets **only for descriptive kinds** (`behavior`, `structure`, `dataflow`, `data`, `tech`, `reference`). Advisory kinds (`decision`, `pitfall`, `guideline`, `rule`) stay `staged` in the ledger — recorded and surfaced to the dev, **never written** to the contract.
- Split `_KIND_TARGET` into `_MIRROR_KINDS` (foldable) and `_CONTRACT_KINDS` (staged-only).
- **Files:** CANONICAL `archie/standalone/sync.py` → COPY `npm-package/assets/sync.py`.
- **Acceptance:** after a descriptive fold, `git diff` of `.archie/rules.json` + the contract blueprint sections (`domain_invariants`, `derived_invariants`, `decisions`, `pitfalls`) + `.archie/findings.json` is **empty**.

### M1.2 — Guardrail: refuse a fold that touched the contract
- In `cmd_fold_context`/`cmd_fold_apply` ([sync.py:532, 560](archie/standalone/sync.py)): snapshot a hash of `rules.json` + contract sections before the edit; in `fold-apply`, **abort the render** if a descriptive fold changed them (mirrors the existing dropped-section guard).
- **Files:** same `sync.py` (CANONICAL → COPY).
- **Acceptance:** a fold that mutates a contract section is rejected with a clear message.

### M1.3 — Rendered-doc consistency
- Audit `renderer.generate_all` (called at [sync.py:607](archie/standalone/sync.py)): the `.claude/rules/*.md` that derive from `rules.json` must render from `rules.json` (unchanged), not from the mirror — so they can't drift to "12" while the rule says "7" (the inconsistency in the cap test).
- **Files:** `archie/standalone/renderer.py` (CANONICAL → COPY) only if a split is needed; otherwise a test pinning current behavior.
- **Acceptance:** after a descriptive fold, contract-derived `.claude/rules/*.md` are byte-identical.

### M1.4 — SKILL instructions + tests
- `archie/assets/workflow/sync/SKILL.md` Step 4 "where edits land": the code-fold edits **mirror sections only**; a law-changing claim is reported as a *proposed amendment* (deferred work), never folded. (CANONICAL → COPY `npm-package/assets/workflow/sync/SKILL.md`.)
- Tests (`tests/test_sync.py`): a cap-style descriptive fold updates the mirror and leaves `rules.json`/invariants/contract-docs untouched; an advisory claim is recorded `staged`, not folded.
- **Acceptance:** `pytest tests/test_sync.py` green; `python3 scripts/verify_sync.py` green.

---

## Risks & mitigations
| Risk | Mitigation |
|---|---|
| Teams relied on advisory auto-fold into the contract | Advisory claims still recorded (`staged`) + surfaced; only the *silent write* stops. Note in SKILL + changelog. |
| `data_models`: shape (mirror) vs a new persistence *guarantee* (contract) | Treat as mirror by default; flag the guarantee edge case in M1.1. |
| Renderer can't cleanly separate contract-docs from mirror-docs | M1.3 is an audit first; only split the renderer if the audit shows real coupling. |

## Out of scope (for now)
- Drafting / applying rule amendments, "Fix or Accept" UX, on-merge reconcile — **deferred**.
- Auto-deciding violation vs. evolution, commit-prose intent, Layer-3 raw code — unchanged from prior scope.

## Done = 
A descriptive `/archie-sync` fold can never alter the contract, so every code-vs-law deviation reliably reaches the PR. Tests + `verify_sync` green.

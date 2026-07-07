# Review Engine v2 — Context, Stability, Fan-out — Design

- **Status:** Approved direction; ready for implementation planning. Not yet built.
- **Date:** 2026-07-07
- **Branch target:** follow-up to `feature/archie-delivery-review` (PR #107).
- **Motivated by:** empirical weaknesses observed while running the delivery review live on a
  real repo (SubscriberAgent PR #15), plus a capability benchmark against a peer's hosted
  review product (see §12 Provenance).

---

## 1. One-sentence summary

Make the PR code review **code-aware in CI** (evidence pack + a jailed tool loop over the
checkout GitHub already makes), **stable across runs** (N-pass union with agreement
confidence), and **broad** (the designed Lane-1 specialist fan-out) — while staying a
**pure GitHub Action**: one workflow file, one checkout, zero-dependency stdlib scripts,
no control plane, no hosted runtime.

---

## 2. Problem (all observed live this session)

1. **The CI reviewer is context-starved.** The runner has a full checkout
   (`actions/checkout@v5`, `fetch-depth: 0`, `refs/pull/N/merge`), but the CI LLM path
   (`agent_cli._run_api`) is a single Messages-API call with **no tools** — the model sees
   only the diff string + a filename list. Locally, `_run_claude` grants
   `Read,Grep,Glob`, which is why a local diagnostic found a genuine null-safety bug that
   CI runs missed. *The code is there; the model has no hands.*
2. **Findings are nondeterministic.** Three runs on the identical diff produced three
   different finding sets. A reviewer that changes its mind every push gets muted.
3. **One generalist carries the whole bug hunt.** The designed Lane-1 universal specialist
   set was never wired into the PR path; a single generic "behavioral reviewer" call found
   0 findings standalone in a controlled diagnostic.
4. **Latency:** 285 s per review, all LLM calls sequential (8 invariant tracers alone are
   8 × ~25 s), growing linearly with touched invariants.
5. **Silent losses:** diff truncated at `MAX_DIFF_CHARS` without disclosure; gate-suppressed
   findings discarded without trace.

## 3. Design constraint (governing): PURE GITHUB ACTION

Everything below runs inside the existing workflow: `on: pull_request` → checkout →
python3-stdlib scripts + `ANTHROPIC_API_KEY` / `GITHUB_TOKEN`. No server, no queue, no
database, no third-party dependency. Mapping of control-plane functions to native Actions:

| Function | Pure-Action mechanism |
|---|---|
| PR webhooks / trigger | `on: pull_request: [opened, synchronize]` (existing) |
| Intake/skip rules | `should_review()` (existing) |
| Code for the reviewer | the `actions/checkout` workspace (existing — full repo at `refs/pull/N/merge`) |
| Agent runtime | the review script itself loops the Messages API and executes tools locally (§5) |
| Re-trigger dedup | `concurrency: { group: archie-review-<PR#>, cancel-in-progress: true }` (add) |
| Result persistence / memory | the PR comment itself (§9) — no storage |
| Publication | `GITHUB_TOKEN` + `pull-requests: write` via urllib (existing pattern) |

**Accepted limits:** fork PRs run without secrets → review degrades to skip (already
graceful); no cross-PR/org analytics (would be the first thing to genuinely need a
control plane — explicitly out of scope); security model stays `pull_request` +
base-ref script execution (never `pull_request_target`).

Review model statement (shared with the state of the art, see §12): **diff-scoped for
intent and output; context-expanded for proof; editor-gated before publication.**

---

## 4. P0a — Evidence pack (deterministic context push)

**New:** `archie/standalone/evidence_pack.py`
- `build_pack(root, changed_files, import_graph, blueprint, budget_chars=40_000) -> str`
  - Full post-change content of each changed source file (per-file cap ~8k chars, marked
    when truncated).
  - For each changed file, up to 3 consumers (from `reachability.consumers`): ~40 lines
    around the import/usage sites of the changed symbols (regex anchor, no AST).
  - Blueprint slice for touched components: `responsibility` + `key_interfaces` only.
  - Hard total budget with an explicit `[[evidence truncated: N files omitted]]` trailer.
- Pure, no LLM, fully unit-testable (budget respected, truncation disclosed, consumer
  excerpts anchored).

**Consumers:** `behavioral_review.build_prompt(..., evidence="")` appends
`CONTEXT (read-only source excerpts):`; the invariant tracer prompt embeds the excerpts
for its `enforced_at` anchors (currently it *instructs* "read the anchor files", which is
impossible on the CI path). Universal specialists (§7) receive the same pack.

**Also:** disclose diff truncation — when `diff_text` is cut at `MAX_DIFF_CHARS`, the
verdict header states `diff truncated: N of M files reviewed`. Silent truncation reads as
full coverage.

## 5. P0b — Jailed tool loop in the API path (context pull, for proof)

Give `_run_api` an optional agentic mode so CI matches the local `claude -p` capability:

- `agent_cli.run_verifier(..., tools=False)`; when `tools=True` and the API path is taken,
  `_run_api_tools(prompt, api_key, root, model, max_turns=6, budget_tokens=~60k)` runs a
  Messages-API **tool-use loop** (~120–150 lines, stdlib urllib):
  - Tools: `read_file(path, start_line, end_line)` (≤200 lines/call) and
    `grep(pattern, glob)` (bounded matches) — both **jailed to the checkout root**
    (resolved path must be inside `root`; symlinks resolved; `.git/` denied).
  - Hard caps: turn count, total tool bytes, wall-clock. On any cap → return the last
    text (degrade, never fail).
  - Prompt caching: `cache_control` breakpoints on the large static blocks (diff +
    evidence pack) so loop turns re-read them at cache price (§13 cost).
- **Rollout order (deliberate):** verification roles first — the invariant **tracer** and
  **challenger** (`tools=True`), where proof-by-reading matters most. Finder roles stay on
  the P0a pack until evidence shows they need pull access.
- **Verify-anchors rule** (adopted from the peer's model, §12): tool-loop reviewers must
  confirm cited line numbers by reading the file before emitting a finding. Kills the
  `anchor_unchanged` false-drop class at the source instead of gate-guessing.
- CLI path (`_run_claude`) is unchanged — it already has Read/Grep/Glob; this brings CI to
  parity with local.

## 6. P1 — Stability: N-pass union + agreement confidence

- `behavioral_review.review(..., passes=2)` (CI default 2; `ARCHIE_REVIEW_PASSES` env).
  Same prompt run N times **in parallel**; findings unioned.
- Dedup key: `(file, kind, normalized_statement)` — normalized = lowercased alnum tokens,
  >60% Jaccard overlap treated as the same finding (reuse the `_tokens` pattern from
  `story_synthesize`).
- `confidence = max(model_confidence, appearances/passes)`. Feeds the existing
  `BREAK_CONFIDENCE = 0.6` split with zero changes: 2/2 → **break**, 1/2 → **possible
  issue**. Variance becomes legible instead of hidden.

## 6b. P1b — Parallelize everything parallelizable

- `invariant_specialist.review_invariants`: `concurrent.futures.ThreadPoolExecutor`
  (stdlib) over invariants, `max_workers=4`; each contract→tracer→challenger chain stays
  internally sequential.
- `run_pr_gate` step 6: edge-A, behavioral, edge-C, conformance as concurrent futures;
  join before the gate. No shared mutable state — collect via future results.
- `ARCHIE_REVIEW_WORKERS=1` restores serial for debugging.
- Target: 285 s → **~60–90 s** wall-clock.

## 7. P2 — Lane-1 universal specialists in the PR path

**New:** `archie/standalone/universal_specialists.py`
- Four fixed lenses (universal → no selector needed; the existing source-files skip-gate
  still applies):
  1. null-safety & error handling
  2. security (injection, secrets, authz)
  3. resource & performance (N+1, leaks, unbounded growth)
  4. concurrency & state
- `review_universal(root, diff_text, evidence, intent, run=None) -> list[findings]`;
  one category-focused haiku pass per lens (shared diff + pack), run in the P1b pool;
  same falsification requirement; `source="universal:<category>"`,
  `kind="behavioral_break"`. Flows through the existing gate + P1 dedup (overlapping
  findings merge with boosted agreement).
- Categories seeded from Archie's own `platform_pitfalls.json` taxonomy — **not** from
  any peer's business-specific specialist list (§12).

## 8. P3 — Inline review comments (second wave)

- `intent_review.post_review_comments(owner, repo, pr, findings, head_sha, token)`:
  `POST /repos/{o}/{r}/pulls/{n}/reviews` with `comments:[{path, line, side:"RIGHT",
  body}]`, `event:"COMMENT"`. Findings whose anchor survives the changed-lines map go
  inline; the upserted summary comment remains the source of truth; 422 anchor rejection
  falls back silently to the summary. Non-blocking as ever; permissions already granted.

## 9. P4 — Per-PR review memory (second wave)

- Persist posted findings inside the summary comment as an HTML-comment JSON block
  (`<!-- archie-findings: [...] -->`) — invisible on GitHub, zero storage infra, readable
  on the next run through the same comments API.
- Re-review renders: **still open** (P1 dedup key match) / **new** / **✅ resolved since
  last push** (previously reported, gone now, AND its anchor file changed). A finding that
  vanishes without its file changing renders as *"not reproduced (reviewer variance)"* —
  honest about nondeterminism instead of silently flip-flopping.

## 10. P5 — Suggested fixes (second wave)

- Behavioral/universal prompts gain an optional `"suggestion"` field (only when confident;
  ≤5 lines; complete replacement code for the anchored lines).
- Rendered as GitHub ` ```suggestion ` blocks on inline comments (one-click apply).
- Gates: only `confidence ≥ 0.6`; never on `conformance_break` (law questions are
  decisions, not patches). Suggestions are model text → `_sanitize` policy applies to all
  surrounding prose; the suggestion body itself is fenced code (no @-mention/HTML risk in
  fence context, but strip ``` sequences from the model text to prevent fence escape).

---

## 11. Data flow (after wave 1)

```
on: pull_request (opened|synchronize)          concurrency: cancel superseded runs
  checkout (full, refs/pull/N/merge)           ← the code the reviewer reads
  materialize /tmp/archie-base                  ← scripts from base ref (security, unchanged)
  run delivery_review.py:
    intake → diff basis (scoped, truncation DISCLOSED)
    intent: story facts ⊕ PR body               (unchanged)
    EVIDENCE PACK ← changed files + consumers + blueprint slice          [P0a]
    parallel fan-out:                                                     [P1b]
      edge-A completeness
      behavioral ×N passes                                                [P1]
      universal lenses ×4                                                 [P2]
      conformance (decisions)
      invariant tracer→challenger (tool loop, verify anchors)             [P0b]
    union + dedup + agreement confidence                                  [P1]
    editor gate (floors / anchors / dedup)      (unchanged)
    verdict: summary comment (+ inline comments, memory, suggestions)     [P3-P5, wave 2]
```

## 12. Provenance & originality

The **diff-scoped / context-expanded-for-proof / editor-gated** review model is the
publicly convergent shape of modern AI reviewers and matches a peer product's design we
were shown privately. What we adopt is that *general model* plus one concrete rule worth
naming (verify anchors by reading the source). What we deliberately do **not** copy:
their hosted control plane (we are a pure Action), their sandbox runtime (our runner IS
the sandbox), their business-domain specialist list (ours derive from Archie's own
`platform_pitfalls.json` taxonomy and blueprint). What they don't have and we keep as
differentiators: story/intent grading with provenance, domain-invariant enforcement
(contract→tracer→challenger), the base-ref execution security model, and zero-dependency
distribution.

## 13. Cost model & levers

- Model policy: haiku for all finder passes (edge-A, behavioral, universals,
  conformance); sonnet tracer / opus challenger only for touched invariants (existing).
- Prompt caching on the static blocks (diff + evidence pack) — matters most for the P0b
  loop where turns re-send context.
- Skip-gates already bound the floor: docs-only PRs skip; `MAX_FILES` caps giants;
  `concurrency` cancellation stops paying for superseded pushes.
- Budget envs: `ARCHIE_REVIEW_PASSES`, `ARCHIE_REVIEW_WORKERS`, tool-loop turn/byte caps.

## 14. Testing

- evidence_pack: budget/truncation disclosure; consumer excerpt anchoring; no LLM.
- tool loop: path-jail (escape attempts → denied), turn/byte caps → graceful degrade,
  tool-result plumbing with a scripted fake API; anchor-verification behavior.
- P1: union/dedup key (paraphrase-merge, distinct-keep), agreement→confidence mapping,
  parallel result integrity.
- P2: four lenses dispatch, category prompts pure, findings shape → gate-compatible.
- P3/P4/P5: review-comments payload; memory round-trip through the HTML block;
  still-open/new/resolved classification; suggestion gating + fence-escape strip.
- CI smoke: re-run the SubscriberAgent cost-preview PR and assert the null-safety +
  error-swallow class findings now surface from CI (the empirical acceptance test).

## 15. Build order & out of scope

**Wave 1:** P0a → P1(+P1b) → P0b (tracer/challenger first) → P2.
**Wave 2:** P3 → P4 → P5.

**Out of scope (deliberate):** embedding/vector repo index; `pull_request_target` for fork
secrets; org-wide analytics/control plane; full determinism (we make variance legible
instead); LLM-orchestrated review planning.

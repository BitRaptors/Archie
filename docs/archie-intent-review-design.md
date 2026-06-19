# Archie Intent Review — Design & Handoff

- **Status:** Design approved in brainstorm; ready for implementation planning.
- **Date:** 2026-06-19
- **Branch:** `feature/archie-intent-review`
- **Scope of this document:** the POC. The path beyond the POC is captured in §10 so planning
  can see where it leads, but only the POC is in scope for the first implementation plan.

---

## 1. One-sentence summary

A GitHub Action that, when a PR is opened, **reviews the proposed change to the architectural
source of truth** (the Archie blueprint) and posts a plain-language comment telling the reviewer
whether the PR silently weakened an invariant, introduced a contradiction, or has behavior that
breaks a standing rule. **It surfaces; the human decides. It never blocks.**

---

## 2. Motivation — the problem we're solving

Archie maintains a **living blueprint**: a semantic snapshot of a codebase's architecture
(`blueprint.json`) plus synthesized enforceable rules (`rules.json`). When a developer works with
Archie, `/archie-sync` **folds their change back into that blueprint on their branch** — and that
fold can ADD, UPDATE, or **REMOVE** sections, including load-bearing invariants
(`domain_invariants`, key decisions).

Because the team's intended governance model is **"merge = acceptance"** (the blueprint is a
versioned in-repo file; merging a PR accepts whatever blueprint state is on the branch), a folded
edit to the source of truth **becomes organizational law the instant the PR merges** — buried in a
diff that no human reads carefully.

**The danger:** a low-confidence sync that quietly deletes or weakens a `tenant-isolation`
invariant becomes "truth," silently, on merge. There is currently **no checkpoint** between "sync
folded something into the blueprint" and "that something is now law."

**Archie Intent Review is that checkpoint**, placed at the only moment it can still matter: PR
review.

### Why this is defensible (vs. a generic "your code broke a rule" bot)

- It operates on a **structured diff of the blueprint**, not fuzzy raw source code → high
  precision, verifiable explanations, small hallucination surface.
- It catches a class of problem **no linter can** (linters have no semantic source of truth to
  diff against).
- It targets the **corruption of the source of truth**, which is uniquely Archie's concern.

---

## 3. Glossary — the cast of artifacts

| Artifact | What it is | Where |
|---|---|---|
| `blueprint.json` | Semantic architecture snapshot: components, decisions, `domain_invariants`, pitfalls, data models | `.archie/` |
| `rules.json` | Synthesized enforceable rules; each has `severity_class`, `description`, `why` | `.archie/` |
| The **ledger** | `/archie-sync record` output: `claims[]` with `kind`, `statement`, `status`, `evidence_files`, `confidence`, `reconstructed` | `.archie/changes/change_*.json` + `latest.json` |
| The **Action** | The new component — runs in CI on the PR | `.github/workflows/` + script |
| The **reviewer** | A human who reads the Action's comment and makes the calls | — |

### Ledger claim schema (verified against `archie/standalone/sync.py`)

```jsonc
{
  "version": 3,
  "id": "20260619-143022-a1b2c3d",
  "folded": true,                         // Phase 2 marks this true after fold-apply
  "provenance": { "git_head": "...", "branch": "...", "agent": "claude", "reconstructed": false },
  "diff": { "changed_files": [...], "affected_folders": [...], "ratio": 0.0 },
  "claims": [
    { "id": "rule:dunning-cap",
      "kind": "rule",                     // ADVISORY: decision|pitfall|rule|guideline
                                          // DESCRIPTIVE: behavior|structure|dataflow|data|tech|reference
      "status": "eligible",               // eligible = confident + non-reconstructed + evidenced in diff; else staged
      "statement": "Dunning retries capped at 3 per invoice",
      "evidence_files": ["jobs/dunning_job.py"],
      "confidence": "high",
      "reconstructed": false }
  ]
}
```

The `kind` field's advisory/descriptive split gives us **Layer 1 vs Layer 2 separation for free** —
no change to sync is required.

---

## 4. How `/archie-sync` already behaves (verified against `archie/assets/workflow/sync/SKILL.md`)

This is load-bearing context — the design depends on it being true:

- `/archie-sync` is a **two-phase skill**.
- **Phase 1 (`record`)** writes the ledger. It is *mostly descriptive* ("what the code now is");
  advisory rules are an occasional side-output, not the point.
- **Phase 2 (fold)** runs when `eligible > 0`: the agent reconciles blueprint sections + per-folder
  CLAUDE.md using **NO-OP / UPDATE / ADD / REMOVE** ops, then `fold-apply` re-renders
  `CLAUDE.md`/`AGENTS.md`/`rules.json` and marks the record `folded: true`.
- **Sync edits files but does NOT commit** — the developer decides what to commit.

**Consequences for our design:**
1. By the time the dev pushes, `blueprint.json` / `rules.json` are *already modified on the branch*.
2. So **"merge = acceptance" already works via plain git** — no fold-on-merge automation needed.
3. The **cleanest review input is the blueprint/rules git-diff (branch vs `origin/main`)** — the
   ledger is corroborating context, not the primary signal.
4. Because fold includes UPDATE/REMOVE, the source of truth can be **silently weakened** — which is
   exactly what we review for.

---

## 5. End-to-end workflow

**Prerequisite (one-time per repo):** `/archie-deep-scan` → baseline `blueprint.json` + `rules.json`
committed on `main`.

1. **Dev works** on a feature branch in Claude Code (Archie installed).
2. **Dev runs `/archie-sync`.** Phase 1 records the ledger; Phase 2 folds eligible claims into
   `blueprint.json`/`rules.json` on the branch and re-renders. Sync does not commit.
3. **Dev commits** code **+ the folded blueprint changes + the ledger**, pushes, opens a PR.
4. **The Action fires** (`on: pull_request`) and gathers three inputs:
   - **Proposed change to truth:** `git diff` of `.archie/blueprint.json` + `rules.json`, **branch
     vs `origin/main`**.
   - **Evidence behind it:** all `.archie/changes/change_*.json` files new on the branch (NOT just
     `latest.json` — see §8, note 2).
   - **What must still hold:** the retained rules/invariants from the base-ref blueprint.
5. **One Claude API call (Haiku)** judges the blueprint diff against the retained rules, using the
   ledger as corroboration → structured findings.
6. **The Action posts one FYI comment** (upserted — re-pushes update the same comment, no spam).
   **The human reads it and decides** per finding: fix the code, or accept the rule change. Dev
   pushes fixes → Action re-runs → comment updates.
7. **Merge.** The folded blueprint is in the PR, so merging *is* the acceptance — `main`'s baseline
   evolves automatically via git. **No extra automation.**

---

## 6. What the review checks (the brain)

It reads the **blueprint/rules diff** and flags three things:

| Flag | Detected from the diff | Why it matters |
|---|---|---|
| **Silent weakening / removal** | a REMOVE/UPDATE that retires or softens a `domain_invariant` / `decision` | the corruption case — about to become law on merge |
| **Contradiction** | an ADD/UPDATE that conflicts with a *retained* rule | the fold introduced an inconsistency into the source of truth |
| **Behavior-violates-rule** | a descriptive change implying a retained rule is now broken | the undeclared violation (the "magic" catch) |

**The ledger sharpens severity.** A fold that REMOVE'd an invariant whose backing claim was
`confidence: low, reconstructed: true` is a five-alarm flag — *a low-confidence guess just deleted a
load-bearing rule.*

### Two layers — both on structured data, never raw code

- **Layer 1 — rule-vs-rule** (the `rules.json` / decision diff): conflict / duplicate / refine /
  net-new. Highest precision — text-vs-text contradiction detection.
- **Layer 2 — behavior-vs-rule** (the descriptive `blueprint.json` diff + descriptive claims):
  catches undeclared violations *without reading raw code*, because sync already distilled the
  behavior into a claim.

### Deferred — Layer 3

Reading the raw source `git diff` against invariants. This is the low-precision, "because-theater"
zone (a model can always produce a plausible-but-wrong cited explanation). It is **explicitly out of
the POC** and must be gated behind an eval harness before it is allowed to comment, let alone block.

---

## 7. The output — the PR comment

One comment, grouped by flag. Each entry carries:
- the affected rule/invariant,
- what the diff did to it (REMOVE/UPDATE/ADD/contradiction),
- a one-line **because drawn from the two texts** — verifiable, not free-generated prose,
- (where relevant) the ledger confidence/provenance that sharpens severity.

Framing is **FYI to the reviewer — never blocking.** The comment explicitly leaves the
violation-vs-evolution decision to the human and notes that merge accepts the shown blueprint
changes as the new baseline.

**Hard rule — because-or-suppress:** if a finding cannot produce a verifiable, cited because, it is
**suppressed, not shown.** This is the single discipline that keeps the tool out of the cry-wolf
death spiral.

---

## 8. The build (technical)

Two files, dropped into the target repo (least-complex delivery, per the decision in §11):

### File 1 — `.github/workflows/archie-intent-review.yml`
- `on: pull_request` (types: `opened`, `synchronize`)
- `permissions: { pull-requests: write, contents: read }`
- `actions/checkout` with `fetch-depth: 0` (needed to diff against the base ref)
- Runs `intent_review.py` with `ANTHROPIC_API_KEY` (their secret) + `GITHUB_TOKEN` (built-in)

### File 2 — `intent_review.py`
- Zero-dependency Python 3.9+ (Archie's standalone DNA — matches `archie/standalone/*.py`)
- Steps: compute blueprint/rules diff (branch vs base) → load ledger + retained rules → one Claude
  API call (structured JSON output) → upsert the PR comment via the GitHub API.

### Implementation notes for planning
1. **Base ref:** diff against `origin/<base>` (`github.event.pull_request.base.sha`), not the branch's
   own prior state.
2. **Read all branch ledger files, not just `latest.json`.** `latest.json` is overwritten on every
   `record`; if a dev synced multiple times on the branch, earlier harvests live only in
   `change_*.json`. The PR's full intent = the union of all `change_*.json` new on the branch vs base.
3. **Comment upsert:** find an existing comment authored by the Action (tagged with a hidden marker)
   and update it; otherwise create. Prevents spam on `synchronize`.
4. **Model:** Haiku is the default target for cost; confirm it clears the quality bar during the
   first dogfood runs (see §12).
5. **Empty/None states:** no blueprint diff (dev didn't commit blueprint changes), no ledger, or no
   findings → post a minimal/no comment rather than a noisy "nothing found" wall.

---

## 9. Design guardrails (carried over from the adversarial review)

These are non-negotiable for the POC. They each neutralize a specific identified failure mode:

- **Non-blocking** (FYI comment, no CI gate) → avoids the cry-wolf death spiral.
- **Human decides violation-vs-evolution** (the Action never auto-classifies) → avoids the
  *asymmetric* danger where a wrong "it's an intended evolution" call launders a bug into law.
- **Because-or-suppress** → no verifiable cited because, no comment.
- **Structured inputs only** (blueprint diff + ledger), never raw code in the POC → keeps precision
  high and avoids because-theater.

---

## 10. POC scope vs. the road beyond

### In the POC (this plan)
Steps 0–6 of §5 + a normal merge. **The deliverable is that comment, appearing and being correct.**

### Explicitly deferred (NOT in this plan)
- **Layer 3** — raw-code reading, gated behind an eval harness.
- **The judge as a blocking gate** — a CI status check that can fail the PR.
- **Auto violation-vs-evolution categorization.**
- **The eval / observability plane** (Langfuse-style): replay historical PRs, score
  precision/false-evolution, store traces. Reuses `archie/benchmark/` + Supabase when built. This is
  what must exist before the tool is allowed to *block*.
- **The setup webapp + GitHub App + backend** (server-side execution, "connect repo + GitHub +
  Claude key + go"). The scalable solution, only if the POC works.
- **BYO-key onboarding flow.**
- **Post-merge fold automation** — not needed; git already handles acceptance because the fold
  happened on the branch.

---

## 11. Key decisions & rationale (the trail planning should not re-litigate)

| Decision | Choice | Why |
|---|---|---|
| Delivery vehicle for POC | **GitHub Action** (CI-side, their key) | Least-complex way to prove value on a PR. App + backend is the *scalable* path, deferred. |
| Review input | **Blueprint/rules git-diff (branch vs base)**, ledger as context | Sync already folds on the branch, so the diff IS the proposed change to truth — deterministic, no AI to find *what* changed. |
| Judgment depth | **Layers 1 + 2 only** (structured claims/diff) | High precision; Layer 3 (raw code) is the fatal-flaw zone, gated behind eval. |
| Blocking? | **No — FYI only** | Precision bar for a public governance bot is ~95%+; we have no eval data yet. Non-blocking survives socially. |
| Who decides violation-vs-evolution | **The human** | Auto-deciding risks laundering a bug into law (asymmetric miscategorization). |
| Baseline evolution (step 7) | **Automatic via git** (fold already on branch) | No separate automation; "merge = acceptance" falls out of the in-repo blueprint. |

---

## 12. Dependency chain & how to interpret POC results

The review is only as good as a chain that is almost entirely **upstream** of the Action:

> baseline exists → baseline is good (not trivia) → dev ran `/archie-sync` → sync folded well →
> dev committed the blueprint changes.

So the POC tests **three things at once**: the review idea, **plus** sync's fold quality, **plus**
the blueprint's quality. **A weak sync or a trivia blueprint can make a sound idea look like a
failed POC.**

**Interpretation rule:** when a review is bad, first diagnose *was the idea wrong, or was the
upstream input (claim/baseline) wrong?* before concluding anything about the concept.

**De-risking the first run:** dogfood on **Archie's own repo** first, on a PR where you know what
sync should produce — so the first signal isolates the *idea* from *upstream quality*. Note:
Archie's repo is **not currently self-instrumented** (no `.archie/changes/`, empty
`.claude/commands/`), so this requires running deep-scan + sync against Archie itself first.

---

## 13. Open questions for planning

These do not block starting the plan, but the plan must resolve them:

1. **Diff granularity for `blueprint.json`.** It's a large JSON. Do we diff semantically
   (parse + compare keyed sections: `decisions[]`, `domain_invariants[]`, `rules`) or textually
   (raw `git diff` with the model interpreting hunks)? Semantic is more precise but more code.
2. **Which retained rules to feed the model.** All of them, or only those touched/adjacent to the
   diff (to bound prompt size + cost)? Likely a relevance pre-filter.
3. **Comment marker mechanism** for upsert (hidden HTML comment vs. a known title).
4. **Failure/auth modes** — missing `ANTHROPIC_API_KEY`, API error, fork PRs (where secrets are
   unavailable). What does the Action do — skip silently, or post a setup note?
5. **Dogfood prerequisite** — do we instrument Archie's own repo (deep-scan + sync) as part of this
   work, or stand up a separate minimal fixture repo?
6. **Where the two files live in the Archie repo** — canonical source under `archie/standalone/` +
   `archie/assets/` and synced to `npm-package/assets/` per the repo's file-sync rule, or a new
   home? (See `CLAUDE.md` "File Sync".)

---

## Appendix A — Worked example ("Acme Billing")

Baseline rules on `main`:

| ID | Rule | Kind |
|---|---|---|
| R1 | Every tenant-table read/write must be `tenant_id`-scoped. No cross-tenant access. | `domain_invariant` |
| R2 | All money movement goes through `PaymentGateway`. No direct Stripe calls. | `decision` |
| R3 | Webhook handlers must be idempotent (Stripe retries → duplicates → double-charge). | `pitfall` |
| R4 | Background jobs live in `jobs/` and register with the scheduler. | `guideline` |

Task **LIN-482**: *Add automatic dunning — retry failed charges 3× over 5 days, then email.*

The dev builds it, but: the nightly sweep queries charges **globally (no tenant scoping)**, and the
retry calls **`stripe.Charge.create()` directly**. They run `/archie-sync`; eligible claims fold
into the blueprint on the branch. The PR's blueprint diff + ledger drive this comment:

> **📐 Archie Intent Review — LIN-482**
>
> **⚠️ Silent weakening (Layer 1)** — the fold UPDATE'd **R1 · Tenant Isolation** to allow an
> unscoped global sweep "for performance". Backing claim: `confidence: medium`. *Intended change to
> R1, or should the sweep loop per-tenant?* Your call.
>
> **⚠️ Behavior-violates-rule (Layer 2, undeclared)** — descriptive claim *"DunningJob calls
> `stripe.Charge.create()` directly"* conflicts with **R2 · Centralized Payments**. The retry path
> bypasses `PaymentGateway`. *(Not declared as a rule — surfaced from behavior.)*
>
> **🔁 Refines (Layer 1)** — declared *"Webhook handlers must log a `dedupe_key`"* strengthens
> **R3**. On merge, R3 gains the clause.
>
> **✨ Net-new (Layer 1)** — *"Dunning retries capped at 3 per invoice"* — no baseline rule covers
> this. Will be added on merge.
>
> *Archie surfaces; it doesn't block. Merge accepts the rule changes above as the new baseline.*

The reviewer fixes R2 (route through `PaymentGateway`) and R1 (loop per-tenant), keeps the refine +
net-new, merges. The R2 catch — which **nobody declared** — is the catch that pays for the tool.

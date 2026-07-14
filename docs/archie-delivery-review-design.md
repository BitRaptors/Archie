# Archie Delivery Review — Design

- **Status:** Design drafted in brainstorm; pending user review → implementation planning.
- **Date:** 2026-07-01
- **Branch:** TBD (proposed `feature/archie-delivery-review`)
- **Related:** builds on `archie-intent-review-design.md` (blueprint-diff judge, PR gate),
  the Architecture Integrity Score work, and the paused product-knowledgebase reconciliation thesis.

---

## 1. One-sentence summary

A code-review capability that stops reviewing *code in isolation* and reviews **delivery**:
by reconciling three inputs — **what was asked** (intent), **what should stay true** (blueprint),
and **what was done** (the diff + its behavior) — it tells you whether the coding agent **built the
real intent and didn't break anything.**

---

## 2. Motivation — why conformance review isn't enough

Everything Archie does today is **conformance review**: "does this code obey our stored model
(blueprint + rules)?" That's necessary but structurally limited — any review that checks against the
blueprint is forever downstream of it, and it cannot answer the questions a human reviewer actually
asks:

- **Behavioral:** will this crash / lose data / be slow / leak? (the code's own behavior)
- **Intent:** did this build what was actually requested? (completeness vs. the ask)

In the agent era the bottleneck is no longer "write the code" — agents produce code fast. The
bottleneck is **"did the agent deliver the ticket without collateral damage."** No existing tool
answers this, because it requires three inputs at once and only Archie holds the middle one
(a persistent architectural model) *and* runs alongside the agent (so it can capture the intent).

---

## 3. The model — three inputs, one triangle

```
        INTENT  (ticket · agent prompt · PR body · commits)
              /                              \
         A: did code                     C: does the ask
         deliver the ask?                conflict with
              /                          architecture?
             /                                \
   DIFF + CODE ──────── (shared reality) ──── BLUEPRINT
   (behavioral)          B: did code           (invariants,
                         break / violate?       decisions)
```

Three edges, each catching a class the other two cannot:

- **A — Intent ⋈ Diff** — *did it build the thing?* Acceptance criterion has no implementing or
  reachable code. ("PR claims rate-limiting; the limiter is never wired to the route.")
- **B — Diff ⋈ Blueprint + behavioral** — *did it break the thing?* Violates an invariant/decision,
  **or** introduces a crash / data-loss / perf / security regression.
- **C — Intent ⋈ Blueprint** — *should it be built this way?* The requirement itself contradicts a
  standing invariant — flag the **ticket**, before the code is the problem.

The blueprint is now **one leg of three**, not the whole engine.

---

## 4. Findings taxonomy (one set, all surfaces)

| Kind | Meaning | Edge |
|---|---|---|
| `intent_unmet` | Acceptance criterion has no implementing / reachable code | A |
| `intent_partial` | Delivered, but error path / edge case missing | A |
| `intent_drift` | Code does things no ticket or prompt asked for | A |
| `conformance_break` | Violates an invariant / decision | B |
| `behavioral_break` | Crash / data-loss / perf / security introduced | B |
| `intent_conflict` | The requirement itself contradicts the architecture | C |

Every finding uses the **evidence schema** (§6.4): `assumptions · evidence · falsification · confidence · anchor`.

---

## 5. Inputs — how intent is resolved (incl. the no-ticket case)

Intent is a **confidence ladder**, not present/absent. Take the highest-confidence source available;
degrade gracefully.

| Source | Confidence | Notes |
|---|---|---|
| Linked ticket (Linear/Jira) | High | Structured acceptance criteria |
| Agent task prompt / session transcript | High/Med | The "just user input" case — often better than a ticket |
| PR title + body | Med | |
| Commit messages | Low-Med | |
| Inferred from the diff | Low | Advisory only |
| Nothing capturable | — | Skip intent leg → run B only; or ask once |

**Two rules make the no-ticket case safe:**

1. **Normalize every source to one shape** — `intent_spec { goals[], acceptance_criteria[],
   non_goals[], source, confidence }`. A raw prompt is reduced by an LLM to implied acceptance
   criteria; identical downstream path regardless of origin.
2. **Weight findings by source confidence** (the anti-noise valve). High-confidence source →
   assertive intent findings. Inferred-from-diff → advisory only ("*if* the goal was X, Y looks
   missing — confirm?"). This prevents confident-but-wrong intent findings when there's no ticket.

**Capture — effortlessly.** A per-branch intent record `.archie/intent/<branch>.json`, populated by:

- **Passive (primary):** a hook reads the coding-agent session and extracts the task prompt — zero
  friction. *This is the differentiator: intent captured at the moment it's expressed (the prompt),
  not reconstructed after the fact (the PR body).*
- **Inline:** `/archie-sync "add rate limiting to export"`.
- **Prompted once:** first sync on a branch with no detectable intent asks one line.

Captured at branch start, **refined as signal arrives** (prompt → commits → PR body → ticket link;
merge, never overwrite), reused by sync and the PR gate.

---

## 6. Shared review core (built once, used by all three surfaces)

| Component | What it is |
|---|---|
| **6.1 intent resolver** | Runs the ladder → `intent_spec`; maintains `.archie/intent/<branch>.json` |
| **6.2 diff_basis** | merge-base ladder (`--base → gh pr view → graphite → origin/HEAD → main`) + provider-SHA path |
| **6.3 selector** | Non-reviewing router. Deterministic: intersect changed files with blueprint sections (`persistence_stores`, `domain_invariant` cited files, `decision.forced_by`). Semantic lane (Haiku) for fuzzy universal domains. Decides *who runs*; never reviews. |
| **6.4 evidence schema** | Every finding carries `assumptions · evidence · falsification · confidence · anchor`. `falsification` = "here is how you'd prove me wrong" — a required, code-checkable refutation test that makes every finding falsifiable. |
| **6.5 reconciliation reviewer** | Takes `{intent_spec, blueprint_slice, diff+code}` → findings across edges A/B/C |
| **6.6 specialist registry** | **Lane 1 universal** (bundled, skill-backed) — categories drawn from Archie's own `platform_pitfalls.json` (force-unwraps, god-functions, injection, N+1, layer violations, etc.); not a fixed external list. **Lane 2 derived** (blueprint-grounded): invariant-integrity, decision-integrity, data-lifecycle. The invariant specialist uses the **contract → tracer → challenger** loop (§6.6a). |
| **6.7 behavioral engine** | Blueprint-free lane: reasons about the code itself (crash/data-loss/perf/security) + **reachability/blast-radius tracing** over the real call/import graph (from the scanner). Its edge over a generic bot: the code graph, git history, and finding memory — not the model. |
| **6.8 editor gate** | Validates, dedups vs persistent store (+ PR threads at PR time), suppresses, strips provenance, **cannot invent**. Generalizes deep-scan's current verifier. |
| **6.9 intake** | Eligibility: skip bot / too-many-files / skip-label; honor override-label. PR-time only. |

All findings land in **one feed** — `.archie/findings.json` (stable ids + hysteresis) — through
**one editor gate**, using **one schema**.

### 6.6a The invariant specialist — `contract → tracer → challenger`

The sophisticated Lane-2 specialist runs a three-role loop. **Provenance note:** this is Archie's
adaptation of the well-documented *planner → executor → critic* agent pattern (ReAct + self-critique),
with one Archie-native difference — **the contract is not planned per-change; it is read directly off
the stored `domain_invariant`.** Archie already holds the invariant (bound / lifecycle / idempotency /
tenant-scope) with its cited anchors, so there is no per-run planning step to derive it.

- **contract** — pull the touched `domain_invariant`'s stored guarantee + anchors. (Data, not an agent.)
- **tracer** *(Sonnet)* — trace the change from write → intermediate state → consumer-visible behavior;
  return one verdict per contract; mark under-proven rather than assume safe.
- **challenger** *(Opus)* — agree / challenge / rebut; reject findings that stop at intermediate state,
  are unreachable, contradicted, or unrelated to the change.

---

## 7. Workflows

### 7.1 deep-scan — seeds the inventory (no ticket → edge B only)

```
1. Scanner          → file tree, frameworks, counts, call/import graph (feeds 6.7)
2. Wave 1 (Sonnet)  → blueprint facts (Structure · Patterns · Tech · Data · Domain)
3. Wave 2 (Opus)    → Design · Risk · Overview · Product   (Risk emits proof-schema findings)
4. Normalize        → blueprint.json (domain_invariants, decisions, persistence_stores)
5. Render           → CLAUDE.md, rules, per-folder CLAUDE.md
6. COLD-READ REVIEW:
     for each domain_invariant / store / decision → run its Lane-2 specialist over cited code (no diff)
     run Lane-1 universal specialists over matching globs
     run behavioral engine (6.7) over hotspots        (confidence-gated — no diff anchor)
7. EDITOR GATE      → drop no-falsification / low-confidence; dedup; stable ids; hysteresis → findings.json
8. Finalize         → health + inventory count
```
**You see:** `Baseline built. 12 open problems (4 high · 6 med · 2 low).`

### 7.2 archie-sync — continuous, on-branch (light reconciliation)

```
1. diff_basis      → merge-base HEAD <base> → changed files + hunks
2. resolve_intent  → intent record for this branch (prompt / inline / ticket link)
3. Fold change into blueprint + rules on the branch     (existing sync behavior)
4. selector on the delta → touched invariants/decisions/stores → Lane-2 specialists
   GATE: delta touches no invariant/decision files AND no behavioral hotspot → skip review
5. reconcile (delta vs intent vs touched blueprint):
     A: still on track for the ticket?      B: just broke / violated something?
   Heavy specialists (contract→tracer→challenger) run on commit/pre-push, not every keystroke
6. EDITOR GATE     → dedup vs findings.json (skip known/suppressed) → update inventory
```
**You see (non-blocking):** `on track for ARCH-123 · 1 acceptance criterion not yet implemented · no breaks`

### 7.3 PR gate — full three-way reconciliation (GitHub Action)

```
1. INTAKE          → find/create PR; skip bot / too-many-files / skip-label; honor override-label
2. diff_basis      → provider base_sha / head_sha → diff files
3. resolve_intent  → ticket(s) + PR body + commits → intent_spec (merged with branch record)
4. intent_review.py (existing) → judge blueprint/rules diff: did the fold weaken an invariant?
5. selector        → full set: Lane-2 derived + Lane-1 universal
6. reconcile whole diff across edges A / B / C  (read diff first, expand into checkout to prove)
7. EDITOR GATE     → dedup vs store + PR threads; strip provenance; reject speculation/style/
                     test-only/low-confidence; verify each anchor maps to a changed line
8. PUBLISH         → DELIVERY VERDICT + inline comments + Architecture Integrity Score + check state
```
**You see:**
> **Delivery review — ARCH-123**
> Built the intent? **3 / 4 acceptance criteria.** Criterion 2 (tenant-scoped export) — query isn't scoped, `export.py:44`.
> Broke anything? **1 invariant** (`tenant-isolation`), **0 crashes**, 1 perf risk (N+1 at `export.py:51`).
> Requirement conflict? None.

The through-line: same `resolve_intent → selector → reconcile → editor gate → findings.json` core in
all three. Only three things differ per surface: **what's reviewed** (whole repo / branch delta / PR
diff), **the diff basis** (none / merge-base / provider SHA), and **where it surfaces** (inventory /
status line / PR comment + verdict).

---

## 8. Trade-offs & mitigations

- **Whole-repo cold read (deep-scan) loses the diff anchor** — the strongest noise suppressor.
  *Mitigation:* confidence-gate cold-read findings hard; cap initial inventory; rely on hysteresis.
- **Sync reviews in-progress, intent-less, possibly-broken code.** *Mitigation:* selector skip-gate;
  heavy specialists only on commit/pre-push; intent-source confidence weighting keeps intent findings
  advisory until a real signal exists; never blocks.
- **Blueprint-in-flux during sync** (reviewing against a source of truth being folded).
  *Mitigation:* review against the pre-fold blueprint snapshot within a sync run.
- **PR gate redundancy** (sync already surfaced most). *Mitigation:* PR gate's net-new value is base-
  drift + universal specialists + the intent *verdict*; dedup vs store prevents echo.
- **Everything rides on blueprint quality (edge B/C).** *Mitigation:* behavioral engine (6.7) and
  edge A are blueprint-free, so review degrades to "still finds real bugs" when the blueprint is weak.
- **Editor gate is a single point of failure.** *Mitigation:* golden test suite; the benchmark
  harness (blind judge-Claude) as the standing eval for gate precision/recall.

---

## 9. Build order

1. **Shared core:** evidence schema (§6.4) + editor gate (§6.8, generalize the verifier) + diff_basis
   (§6.2) + selector (§6.3).
2. **Behavioral engine (§6.7)** — the genuinely-new blueprint-free lane; reachability first.
3. **Intent resolver (§6.1)** + per-branch record + normalization + confidence weighting.
4. **Wire deep-scan** (closest — already has a verifier + scanner graph).
5. **Wire sync** (highest leverage — the effortless moment).
6. **Wire PR gate** (intake + full reconciliation + delivery verdict + publication).

---

## 10. Open questions

- Call/import graph: reuse scanner output, or a new lightweight per-language extractor?
- Linear ingestion: MCP vs. direct API; how ticket ids are linked (branch pattern vs. PR link).
- Passive prompt capture: which hook / transcript surface, and privacy posture.
- Does the delivery verdict feed the Architecture Integrity Score, or sit beside it?
- Heavy-specialist debounce: exact sync trigger (commit? pre-push? idle?).

---

## 11. Provenance & originality

This design was shaped partly by a conversation with a peer about a proprietary, PR-time code-review
system. That prompted an explicit audit so the feature is defensibly Archie's own — in concept **and**
in internals. Findings of that audit:

### 11.1 What is genuinely Archie-native (the reason this feature exists)

Nothing below has an analog in the peer system; each derives from Archie's own assets:

- **The reconciliation triangle** (intent ⋈ blueprint ⋈ diff) → a *delivery verdict*: "did the agent
  build the intent and break nothing." The peer system has no persistent model and no intent-vs-code
  reconciliation — it reviews a diff against a PR body.
- **Intent as a confidence ladder with passive prompt capture** from the coding-agent session (§5).
  The peer system's only intent source is the PR description.
- **Blueprint-derived specialist routing** (§6.3) — specialists selected from a semantic domain model,
  not a hand-authored glob list.
- **`domain_invariants` as stored contracts** (§6.6a) — read off the blueprint, not planned per change.
- **Persistent findings store with hysteresis and cross-run recurrence** — the peer system is
  stateless per PR.
- **Three surfaces**, especially **sync reviewing before the PR exists** — the peer system is PR-only.
- **Whole-repo cold read** (§7.1) — the peer system is explicitly diff-only.

### 11.2 Convergent industry patterns (independently standard; used freely)

Multi-agent review, diff-first + merge-base scoping, an LLM-judge/critic reliability pass, structured
findings with confidence, file-type specialists, and not leaking internal ids into comments are all
public prior art (CodeRabbit, Greptile, Graphite Diamond, the ReAct / self-critique literature). We
use them as commodities.

### 11.3 Deliberately renamed / re-provenanced to avoid mirroring the peer's confidential internals

- Finding fields use Archie terms — **`falsification`** (not the peer's "disproof"), **evidence
  schema** (not "proof schema"). Consumer-tracing language is Archie's, not the peer's
  "downstream frontier / terminal invariant."
- The invariant specialist is framed as **`contract → tracer → challenger`** and provenanced to the
  public *planner → executor → critic* pattern, with the Archie-native twist that the contract is
  **stored, not planned** (§6.6a).
- The universal specialist set is drawn from Archie's own **`platform_pitfalls.json`**, not mirrored
  from the peer's set.

### 11.4 Hard exclusions

The peer's **business-specific specialists** (e.g. cart-serializer, MCP-auth, network-policy,
maintenance-task) are **never** ported — they leak the peer's domain and are irrelevant here. Lane-1
categories come only from Archie's own pitfall catalog.

### 11.5 Guardrail for implementation

When this becomes code, build the two closest mechanisms (the LLM-judge editor gate, the
planner-critic loop) from the **public** references cited above and from Archie's existing
`verify_findings.py` / `apply_verdicts.py` — not by reconstructing the peer's described design. As a
courtesy (the concept is clearly ours, but the influence was real), consider giving the peer a
heads-up. Flag any genuine IP question to counsel; architectures and methods are generally not
copyright-protected, but a disclosed confidence deserves respect regardless.

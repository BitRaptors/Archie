# Impact ladder + temperature lever — design

**Date:** 2026-07-16
**Status:** Draft for review
**Problem owner:** user feedback — "Archie finds as many problems as possible even when there are no major ones; users fix and fix but never reach a state where none are left."

## 1. Problem

Archie has no "done" state by construction:

- `measure_health.py` emits raw scalars (erosion, gini, top20_share) with no pass/fail line.
- The Risk agent prompt carries a "soft floor of 3 findings" — it is nudged to always say something.
- The score worklist *was* the worst offender. Evidence from a real user project
  (SubscriberAgent, deep scan 2026-07-03, pre-2.10.0): `score.json` showed grade **F**,
  710 open divergences, a **404-item worklist that was 100% generic mechanical hygiene**
  (128× growing-complexity, 82× god-function, 50× monster-file, 21× any-type, …).
  Zero of the 69 reasoned project rules appeared in that number. That subsystem was
  removed end-to-end in commit `c37b8e5` (2026-07-14, "Deemed useless") — which fixed
  the wall but left a vacuum: there is now **no headline "am I done?" signal at all**.
  This design's above-the-line count and clear state is the replacement.
- Meanwhile the genuinely beloved output — **error surfacing** — is real but scattered:
  in the same scan, ~5–7 items of true gold (PII-leak pitfall pf_0005, over-billing
  pitfall pf_0004, live stale-read regression f_0004, unbounded-rerun gap-001,
  divergent-migrations finding f_0003) live across `findings.json`, blueprint
  `pitfalls`, and `unenforced_invariants`, mixed with or drowned under the 404.
- Severity does not track impact: the one live regression (f_0004) is tagged `warn`;
  the two most valuable items in the scan are pitfalls, not findings.

The frustration is **A: no finish line** — not primarily noise volume, and not triage UX.

## 2. Solution overview

Two additions, one principle:

1. **Impact ladder** — every user-facing problem item carries an `impact` tier:

   | Tier | Name | Meaning | Example (SubscriberAgent) |
   |------|------|---------|---------------------------|
   | ① | `regression` | Already misbehaving; a live caller fires the failure mode today | f_0004 stale Firestore reads |
   | ② | `hazard` | Not broken yet, but a realistic path to outage / data loss / money loss / security | pf_0004 over-billing, pf_0005 PII leak |
   | ③ | `erosion` | A real architectural decision or invariant undermined; maintainability cost only | pf_0001 triplicated logic, untracked DDL |
   | ④ | `preference` | Stylistic / hygiene; negligible functional gain | naming-case rules, god-function counts |

2. **Temperature lever** — a user-controlled, per-project setting that draws a
   display-time line across the ladder. Four levels, named by what they admit
   (not low/medium/high): **Regressions · Hazards · Erosion · Everything**.
   Level *Hazards* shows tiers ①+②; *Everything* shows all four.

**Principle: the scan finds everything; the dial filters at display time.** The
compounding store, the verifier, and hysteresis keep working on the full corpus.
Turning the dial is instant, needs no rescan, and is fully reversible. "Done" =
no items at or above the current temperature — a stable, reachable finish line,
because the store underneath is stabilized by verifier + hysteresis.

Nothing is hidden dishonestly: below-the-line items are always counted in a
"N quieter items parked below the line" affordance that raises the dial on click.

### Non-goals

- No change to edit-time rule enforcement (`pre-validate.sh`, `severity_class`
  gating). Rules and findings stay separate taxonomies; the temperature never
  silences a blocking rule.
- No LLM-generated tier-④ findings. The emission prompt stays hardened against
  stylistic nits; ④ exists only as the label on the already-deterministic
  mechanical/universal outputs (platform rules, score worklist).
- No removal or weakening of the fix-prompt feature (see §8).

## 3. What gets a tier, and how

The temperature governs **all problem streams the user sees**, not just
`findings.json`:

| Stream | Where | Tier assignment |
|--------|-------|-----------------|
| Findings | `.archie/findings.json` | LLM tags `impact` at emission (new OUTPUT CONTRACT field); verifier corrects the ①/② boundary |
| Pitfalls | blueprint `pitfalls` | LLM tags `impact` at emission; ① disallowed by construction (a live-firing pitfall must become a finding) |
| Gaps | blueprint `unenforced_invariants` | LLM tags `impact` (② or ③) |

(The former fourth stream — the `score.json` mechanical worklist — was removed with
the scoring subsystem in `c37b8e5`. If a hygiene surface returns in any form, its
items map deterministically to ③/④ via a static table, never per-item LLM calls,
and render as a single aggregated row.)

### Tier derivation is mostly latent already

- `kind: behavioral_break` + verifier-confirmed firing `triggering_call_site` ⇒ ①.
- `kind: behavioral_break` where the site exists but does not fire ⇒ ② — this is
  exactly the verifier's existing `demote` semantics (`verify_findings.py:73-76`).
- `kind: conformance_break` ⇒ ③ by default; the emitter may raise to ② only with
  an explicit consequence path (outage / data loss / money / security) stated in
  the finding.
- ④ never comes from the LLM emitter.

The LLM `impact` tag is therefore a *seed*; the verifier is the *authority* on
the ①/② boundary (its charter — "does this actually fire?" — is precisely that
line). The verifier does not rule on ③ vs ④ (taste, not code-checkable).

### Emission changes (`step-5b-risk.md`, `step-5-wave2-reasoning.md`)

- Add `"impact": "regression|hazard|erosion"` to the finding OUTPUT CONTRACT
  (after `kind`); `"impact": "hazard|erosion"` to the pitfall contract.
- One added instruction block defining the tiers with the consequence-path rule
  for ②, and: impact describes *user gain from fixing*, independent of confidence.
- Clarify the "soft floor of 3" as an **emission floor on the store**, explicitly
  not to be met by padding with low-impact items: "if fewer than 3 findings meet
  the bar, say so — do not lower the bar to reach 3."
- Comprehensive mode unchanged: emit every tier that meets the quality bar;
  temperature filters at view time.

### Verifier + hysteresis changes

- Extend the verdict JSON (`verify_findings.py`) with
  `impact_verdict: confirm | correct_to_regression | correct_to_hazard`
  (scoped to the ①/② line only).
- `apply_verdicts.py`: impact transitions ride the existing hysteresis — add
  `impact_history` beside `verdict_history`; a tier change requires 2 consecutive
  matching verdicts OR a git-anchored material change, same as status transitions.
  This prevents LLM flicker from moving items across the user's line between scans.
- **Downgrade guard:** a finding whose impact would drop *below the user's current
  temperature* due to a verdict is surfaced in the scan receipt ("1 item moved
  below your line: f_00NN — reason"), never silently vanished. Protects the
  beloved error-surfacing signal from silent dilution.

### Gates

- Per-impact confidence floors layered on the existing per-kind floors
  (`editor_gate.py` / `finalize.py::DEFAULT_COLD_FLOORS`): claimed `regression`
  requires the highest floor (0.7), `hazard` 0.6, `erosion` 0.5. A false
  regression is the worst outcome; it gets the highest bar before entering the store.
- Dedup keys unchanged (`impact` stays out of `_dupe_key`).
- `finding_merge.py` impact reconciliation: when merged passes disagree on impact,
  keep the **higher** tier and flag `impact_contested: true` for the verifier to
  settle. Never silently keep the lower tier (that could hide a real regression
  above-the-line).
- `finalize._merge_findings_into_store` preserves `impact`, `impact_history`,
  `impact_contested` across upserts, same as `status`.

### Legacy data

Findings/pitfalls without `impact` (pre-upgrade stores) derive a provisional tier:
`behavioral_break → hazard`, `conformance_break → erosion`, pitfall `severity:
error → hazard` else `erosion`. Provisional tiers are marked and re-tagged on the
next scan.

## 4. Temperature: storage, seeding, semantics

### Storage — per-project, net-new state

`~/.archie/config.json` is machine-global by contract; wrong home. The
temperature lives in a new top-level key in `.archie/findings.json`:

```json
{
  "temperature": {
    "level": "hazard",
    "source": "seeded",          // "seeded" | "user"
    "seeded_reason": "erosion 0.74, 404 hygiene items parked",
    "set_at": "2026-07-16T..."
  },
  "findings": [ ... ]
}
```

`source: "user"` is sticky — once the user moves the dial, seeding never
overwrites it (re-seed only shown as a suggestion chip).

### Seeding rule (user decision: Archie suggests the default; combines health + load)

Computed lazily by the viewer on first load if absent (health may not exist yet
mid-scan — Step 9 writes `health.json` after Step 5 writes findings), and
(re)computed at Step 9 finalize when `source != "user"`:

1. Baseline from health (stable anchor): `erosion >= 0.5` OR `top20_share >= 0.7`
   ⇒ baseline **Hazards**; else baseline **Erosion**.
2. Load nudge (one notch max): if items at the baseline level number > 25,
   go one level colder; if 0 items at baseline and < 10 at the next level,
   one level warmer.
3. Clamp: the seed is always **Hazards** or **Erosion**. Never *Regressions*
   (the coldest level is a user choice, not a default — and it would hide
   hazards like a PII leak by default) and never *Everything* (the nudge in
   step 2 clamps at these bounds).

The seeded reason is stored and rendered under the dial ("Suggested from this
scan: erosion 0.74 and 404 hygiene items — start with what can hurt you").

### "Done" semantics

- The report headline counts only at-or-above-temperature items:
  "N items above the line · fix these and you're done at this temperature."
- Empty above-the-line list ⇒ explicit green clear state: "Clear at this
  temperature — nothing above the line. Raise it when you want more."
- The Step 9 closing receipt reports the same number (items at/above the seeded
  or user temperature), replacing the raw `.findings|length` count, plus the
  parked count. The receipt and the viewer can never contradict each other.

## 5. The headline signal (replaces the removed score)

The Structural Integrity Score was removed in `c37b8e5` after proving to be a
frustration engine (see §1). The report currently has **no** headline
"how am I doing / am I done?" signal. The temperature's above-the-line count
becomes that signal:

- Headline: "N items above the line" (+ the done/clear state when N = 0).
- Below it, one aggregated context row for parked items — never itemized nagging.
- Unlike the old grade, this number **converges**: fixing an above-the-line item
  moves it, hygiene churn does not. That is the property the old score lacked.

## 6. Surfacing (viewer + share)

- `ReportPage.tsx` active-findings filter gains one predicate:
  `impactAtOrAbove(f.impact, temperature)`. Same filter applied to pitfall
  and gap rendering.
- `rankFindings` gains `impact` as the primary sort key (regressions first) —
  a default-order win even before the user touches the dial.
- The dial UI: 4-segment control labeled **Regressions / Hazards / Erosion /
  Everything** with one-line hints; seeded-suggestion chip; parked-items
  affordance ("N quieter items parked below the line — raise the temperature
  to see them") that bumps the level one notch.
- `Finding` interface + `normalizeStructuredFinding` carry `impact`,
  `impact_history`, `impact_contested`.
- Share bundles (`upload.py`) keep shipping the whole store; the recipient's
  viewer applies the bundled `temperature` as its initial level and may turn
  the dial freely. (Accepted: share recipients can see below-the-line items;
  the share payload was never a tier-based trust boundary.)

## 7. Explicit non-interaction with rules/hooks

`severity_class` (5 rule classes, edit-time enforcement) and `impact` (4 finding
tiers, report-time surfacing) are parallel, deliberately distinct vocabularies:

- The temperature never reaches `pre-validate.sh`; a `decision_violation` blocks
  at any temperature.
- A `preference` tier item never blocks an edit.
- CLAUDE.md documents both tables side by side to prevent conflation.
- (Future, out of scope) Step 6 rule synthesis could inherit `severity_class`
  from the motivating finding's impact — noted, not built now.

## 8. Fix-prompt feature — preserved, explicitly

`share/viewer/src/lib/fixPrompt.ts` (`buildFixPrompt`) — the per-item
copy-paste "fix this" prompt with the resolved blueprint context chain — is
**unchanged and remains attached to every rendered item at every temperature**,
including parked items once revealed. The lever strengthens it: a bounded
above-the-line list makes "fix everything above the line" a finishable session.
No change to the builder itself; `impact` may be added to the prompt header as
one context line ("Impact: hazard — realistic over-billing path") — additive only.

## 9. Touched surfaces + sync obligations

Canonical → copies (verified by `scripts/verify_sync.py` before commit):

| Canonical | Copies |
|-----------|--------|
| `archie/standalone/{verify_findings,apply_verdicts,editor_gate,finding_merge,finalize}.py` | `npm-package/assets/*.py` |
| `share/viewer/src/**` (`findings.ts`, `ReportPage.tsx`, dial component, `fixPrompt.ts` header line) | `npm-package/assets/viewer/**` AND `archie/assets/viewer/**` |
| `archie/assets/workflow/deep-scan/steps/{step-5b-risk,step-5-wave2-reasoning,step-9-finalize}.md` | per existing workflow-asset shipping |

## 10. Testing

- Unit: tier derivation for legacy findings; seeding rule (health × load matrix,
  stickiness of `source: "user"`); impact merge reconciliation (higher-tier wins +
  contested flag); hysteresis on impact transitions (2-consecutive / git-anchor);
  per-impact floors in `editor_gate`.
- Viewer: filter predicate per level; done/clear band; parked count arithmetic;
  dial persistence round-trip through `findings.json`.
- Receipt: closing summary count equals viewer above-the-line count on the same store.
- Regression: existing stores without `impact` load, render, and re-tag cleanly.

## 11. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Tier misassignment hides a real regression below the line | Highest confidence floor on ①; merge keeps higher tier; verifier owns ①/② line; downgrade guard surfaces any below-line move in the receipt |
| Impact flicker between scans breaks "done stays done" | Impact transitions ride existing hysteresis (2-consecutive or git-anchor) |
| Two adjacent taxonomies confuse contributors | §7 side-by-side doc; temperature code never imports hook code |
| Seed lands wrong for a given team | Dial is one click, sticky, with the seed reason shown; seeding is a suggestion after first user touch |
| Triple viewer sync under-counted | §9 table + `verify_sync.py` gate |
| Verifier fail-open leaves tiers unverified (observed in SubscriberAgent) | Separate fix task already spawned (parser robustness + visible fail-open warning); design assumes verifier works but degrades safely — unverified impact stays at emitted tier, marked provisional |

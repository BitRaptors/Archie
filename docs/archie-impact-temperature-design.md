# Impact ladder + temperature lever — design

**Date:** 2026-07-16 (rev 2, post adversarial review)
**Status:** Draft for review
**Problem owner:** user feedback — "Archie finds as many problems as possible even when there are no major ones; users fix and fix but never reach a state where none are left."

## 1. Problem

Archie has no "done" state by construction:

- `measure_health.py` emits raw scalars (erosion, gini, top20_share) with no pass/fail line.
- The Risk agent prompt carries a "soft floor of 3 findings" — it is nudged to always say something.
- The score worklist *was* the worst offender. Evidence from a real user project
  (SubscriberAgent, deep scan 2026-07-03, pre-2.10.0): `score.json` showed grade **F**,
  710 open divergences, a **404-item worklist that was 100% generic mechanical hygiene**.
  That subsystem was removed end-to-end in `c37b8e5` (2026-07-14, "Deemed useless") —
  which fixed the wall but left a vacuum: there is now **no headline "am I done?"
  signal at all**. This design's above-the-line count and clear state is the replacement.
- The beloved output — **error surfacing** — is real but scattered: in the same scan,
  ~5–7 items of true gold (PII-leak pitfall pf_0005, over-billing pitfall pf_0004, live
  stale-read regression f_0004, unbounded-rerun gap-001) live across `findings.json`,
  blueprint `pitfalls`, and `unenforced_invariants`.
- Severity does not track impact: the one live regression (f_0004) is tagged `warn`.

The frustration is **A: no finish line** — not primarily noise volume, and not triage UX.

## 2. Solution overview

Two additions, one principle:

1. **Impact ladder** — every user-facing problem item carries an `impact` tier:

   | Tier | Name | Meaning | Example (SubscriberAgent) |
   |------|------|---------|---------------------------|
   | ① | `regression` | Already misbehaving; a live caller fires the failure mode today | f_0004 stale Firestore reads |
   | ② | `hazard` | Not broken yet, but a realistic path to outage / data loss / money loss / security | pf_0004 over-billing, pf_0005 PII leak |
   | ③ | `erosion` | A real architectural decision or invariant undermined; maintainability cost only | pf_0001 triplicated logic, untracked DDL |
   | ④ | `preference` | Stylistic / hygiene; negligible functional gain. **Reserved** — no producer exists post-`c37b8e5`; kept in the schema for a future hygiene surface, never LLM-emitted | (naming-case checks) |

2. **Temperature lever** — a user-controlled, per-user-per-project setting that draws a
   display-time line across the ladder. **Three levels** (tier ④ has no producer, so a
   fourth level would be dead UI):

   | Level | Shows | Hint copy |
   |-------|-------|-----------|
   | **Broken now** | ① | "already misbehaving" |
   | **Can hurt you** | ①+② | "outage · money · data" |
   | **Everything** | ①+②+③ (+④ when a producer exists) | "incl. architecture debt" |

   Level names deliberately avoid "Erosion": the health metric `erosion` appears on the
   same screen and the collision would read as the same concept.

**Principle: the scan finds everything; the dial filters at display time.** The
compounding store, the verifier, and hysteresis keep working on the full corpus at
every temperature. Turning the dial is instant, needs no rescan, and is reversible.

**The two liveness rules** (settled during review):

- **Findings flow is always live.** New ①/② from ongoing development surface above
  the line immediately at the current level. "Done" is *done as of scan #N*; the next
  scan may honestly disturb it — because the code changed, never because the line moved.
- **The line moves only by a human hand.** Archie recommends (see §4 seeding + chip),
  the user clicks. The dial never repositions itself: a silently moving finish line is
  indistinguishable from no finish line.

Nothing is hidden dishonestly: below-the-line items are always counted in a
"N quieter items parked below the line" affordance that raises the dial on click.

### What "done" counts — findings only

The countdown headline ("N items above the line · fix these and you're done at this
temperature") counts **findings only**. Findings are point-in-time *instances* with a
full lifecycle (verifier, hysteresis, resolved/dropped) — they can genuinely reach zero.

Pitfalls and gaps are durable *classes* of problem: regenerated each scan
(`finalize._reset_reasoning_sections` clears and rebuilds them), no resolved status,
no dismissal path. A class cannot be fixed into nonexistence, so counting it toward
"done" makes the finish line structurally unreachable — the adversarial review's
top finding. Instead, ②-tier pitfalls and gaps render as a separate **standing
guardrails** band: visible, impact-tagged, filtered by the same temperature, never
part of the countdown. Copy frames them as posture, not backlog: "4 standing
guardrails at this level — things Archie watches for, not tasks to finish."
(A pitfall acknowledge/park lifecycle is explicitly v2.)

### Non-goals

- No change to edit-time rule enforcement (`pre-validate.sh`, `severity_class`).
  Rules and findings stay separate taxonomies; the temperature never silences a
  blocking rule; a `preference`-tier item never blocks an edit.
- No LLM-generated tier-④ output. The emission prompt stays hardened against nits.
- No removal or weakening of the fix-prompt feature (§8).

## 3. Impact tiers: assignment, correction, stability

### Assignment

| Stream | Where | Tier assignment |
|--------|-------|-----------------|
| Findings | `.archie/findings.json` | LLM tags `impact` at emission; verifier corrects (below) |
| Pitfalls | blueprint `pitfalls` | LLM tags `impact` (② or ③; ① disallowed — a live-firing pitfall must become a finding). Platform-seeded pitfalls (`merge_platform_pitfalls`) get static tiers in the catalog |
| Gaps | blueprint `unenforced_invariants` | LLM tags `impact` (② or ③) |

Derivation is mostly latent: `behavioral_break` + verifier-confirmed firing
`triggering_call_site` ⇒ ①; `behavioral_break` not firing ⇒ ②;
`conformance_break` ⇒ ③ by default.

**Raising ③ → ② requires a structured consequence path, not prose.** New emission
field, mandatory whenever `impact: hazard` is claimed on a conformance finding,
pitfall, or gap:

```json
"consequence_path": {
  "asset": "customer PII in screenshots",     // named asset at risk
  "entry_point": "worker/main.py:568",        // where the path starts, verifiable
  "trigger": "status string rename"           // what realistically sets it off
}
```

Missing or unverifiable `consequence_path` ⇒ the item gates to ③. This is the
anti-inflation guard on the exact boundary the default dial sits on: LLMs narrate
plausible consequences fluently, so the claim must be falsifiable, not rhetorical.

### Emission changes (`step-5b-risk.md`, `step-5-wave2-reasoning.md`)

- Add `"impact"` + optional `"consequence_path"` to the finding and pitfall
  OUTPUT CONTRACTs. **Remove the hardcoded `"status": "active"`** from the finding
  contract (see merge rule below; also fixes a live resurrection bug independent of
  this design — separate task spawned).
- One instruction block defining tiers; impact = user gain from fixing, independent
  of confidence.
- Clarify the "soft floor of 3" as an emission floor on the store, never met by
  padding: "if fewer than 3 findings meet the bar, say so — do not lower the bar."
- Comprehensive mode unchanged.

### Correction — the verifier owns tier moves, in both directions

Extend the verdict JSON (`verify_findings.py`) with
`impact_verdict: confirm | correct_to_regression | correct_to_hazard | correct_to_erosion`.

- ①/② line: the verifier's charter ("does this actually fire?") — unchanged rationale.
- **`correct_to_erosion` is the downward path** the first draft lacked: it fires when
  a claimed ② has a `consequence_path` that doesn't hold up (asset not reachable from
  the entry point, trigger unrealistic). Without it the ladder is a one-way inflation
  ratchet and the above-the-line count is monotone non-decreasing — the removed
  score's failure mode, rebuilt.
- Relation to the existing `demote` verdict (which sets `status: demoted` and hides
  the item): `demote` remains "this should not be a finding at all — it duplicates a
  pitfall class with no live instance." `correct_to_hazard` is "keep it as a finding,
  it's instance-anchored, but it isn't firing." The verifier picks exactly one.
- The verifier does not rule on ③ vs ④ (taste, not code-checkable — and ④ has no
  LLM producer anyway).

### Stability — prior-wins merge (replaces the broken "same as status" rule)

Adversarial review, critical: `finalize._merge_findings_into_store` does
`merged = dict(nf)` and preserves prior fields only when the new emission *lacks*
them. Since every emission now carries `impact`, the fresh single-shot tier would
overwrite the stabilized one every scan — hysteresis bypassed at the source.

Rule: **for verifier-managed fields (`impact`, `status`, `verdict_history`,
`pending_*`, `demoted_at`, `dropped_at`), the prior store wins on merge.** A
re-emission that disagrees on `impact` is recorded as
`impact_signal: {value, scan}` — a pending vote, not a write. The tier actually
moves only via (a) an `impact_verdict` from the verifier, or (b) two consecutive
scans emitting the same disagreeing tier, or (c) a git-anchored material change to
the anchor file — i.e., the exact hysteresis discipline `apply_verdicts.py` already
applies to `status`. New ids take their emitted tier directly (nothing prior to win).

Reconciliation lives in `_merge_findings_into_store` — **not** `finding_merge.py`,
which serves the edit-time review path where findings carry no impact (review
finding, cut from rev 1).

**Downgrade guard:** any verdict- or hysteresis-driven tier move that crosses below
the user's current temperature is written by `apply_verdicts.py` into a
`last_scan_changes` block in `findings.json` at Step 5, and the Step 9 receipt
renders it: "1 item moved below your line: f_00NN — reason." Never silently vanished.

**Pitfall/gap tier stability (honest limitation):** these streams have no verifier
and no hysteresis; their tiers are re-tagged each scan. Mitigations: the structured
`consequence_path` requirement (the main flicker source is the ②/③ call), static
tiers for platform-seeded pitfalls, and the standing-guardrails band not being a
countdown (a flickering guardrail annoys; it does not break a promised finish line).
Full pitfall lifecycle is v2.

### Gates

- Per-impact confidence floors **layered at the finalize call site**
  (`gate_and_merge`), not inside `editor_gate.gate()` — `gate()` is shared with
  `sync_review`/`delivery_review`, which run advisory floors and carry no impact.
  Floors: `regression` 0.7, `hazard` 0.6, `erosion` 0.5. A false regression is the
  worst outcome; it gets the highest bar before entering the store.
- Dedup keys unchanged (`impact` stays out of `_dupe_key`).

### Legacy data

Findings/pitfalls without `impact` derive a provisional tier:
`behavioral_break → hazard`, `conformance_break → erosion`, pitfall
`severity: error → hazard` else `erosion`. Provisional tiers are marked and
re-tagged next scan.

## 4. Temperature: storage, seeding, semantics

### Storage — gitignored, per-user, per-project

**`.archie/settings.local.json`** (net-new file, added to the installer's gitignore
block, mirroring the established `.claude/settings.local.json` pattern):

```json
{
  "temperature": {
    "level": "can_hurt_you",
    "source": "seeded",            // "seeded" | "user"
    "seeded_reason": "erosion 0.74 — start with what can hurt you",
    "set_at": "2026-07-16T..."
  }
}
```

Rationale (adversarial review, critical): `findings.json` is *committed* in repo
mode — a dial stored there is team-shared through git, letting one dev's
"Broken now" + `source: "user"` stickiness silently park the PII hazard for every
teammate; it also merge-conflicts and churns diffs in a machine-generated file.
A gitignored local file is per-human, conflict-free, identical in repo and
detached storage modes, and shrinks the blast radius of unsupported writers.
The key is validated-and-repaired on every read; its schema (including "set
`source: "user"` only on human request") is documented in CLAUDE.md as a contract,
because coding agents *will* be asked to "turn Archie down" and will edit the file.

`source: "user"` is sticky — seeding never overwrites it.

**Write surface: the viewer dial only** (user decision). The viewer local server
gains one endpoint (`POST /api/temperature` — net-new; today `do_POST` allows only
rules/exposure) writing `settings.local.json`. Since no scan-pipeline process
writes that file, there is no dial-vs-scan write race (findings.json stays
scan-owned). Everything else is a reader; the Step 9 receipt points to
`/archie-viewer` for changes. Share-mode viewers default to **Can hurt you**, dial
free, nothing persisted (the share bundle does not carry a temperature — it's a
per-user preference, not scan data).

### Seeding — once, at first scan; recommendations forever after

- **The seed happens once**: the first scan that finds no `temperature` key writes
  one with `source: "seeded"`. It is never auto-recomputed after that — the
  adversarial review showed auto-reseeding creates a treadmill (clear all hazards →
  quiet baseline → auto-warm one notch → parked items pop above the line: the
  reward for finishing is a refilled list).
- Seed rule: baseline **Can hurt you** if `erosion >= 0.5` or (`top20_share >= 0.7`
  and `total_functions >= 25` — the small-repo guard: below 25 functions
  `top20_share` is degenerate, up to 1.0 on trivial repos); else **Everything**.
  Load nudge (one notch, clamped to these two levels): > 25 items at baseline ⇒
  colder; 0 at baseline and < 10 at the next ⇒ warmer. Never seed **Broken now**
  (it would hide hazards like a PII leak by default). If `health.json` doesn't
  exist yet (viewer opened mid-scan), fall back to load-only with baseline
  **Can hurt you**; Step 9 finalize writes the full seed if the key is still absent.
- **The recommendation chip is ongoing and always current**: every scan recomputes
  what the seed *would* be. When it disagrees with the current setting, the viewer
  shows a visible chip with the reason — "You've been clear at Can hurt you for 4
  scans — widen to Everything?" / "Hazard load tripled this scan — narrow to focus?"
  One click to accept (which sets `source: "user"`). The chip recommends; only the
  human moves the line.

### "Done" semantics

- Headline: "N items above the line · fix these and you're done at this
  temperature" — findings only (§2).
- Empty above-the-line list ⇒ green clear state stamped as an **event, not a
  timeless state**: "Clear as of scan #12 (2026-07-16) at Can hurt you."
  `last_clear` is persisted in `settings.local.json`; a later scan that disturbs
  it reports "2 new items above the line since your last clear."
- The Step 9 receipt prints the same count + the parked count + the standing
  guardrails count, all at the stored temperature.

## 5. The headline signal (replaces the removed score)

The report currently has no headline "how am I doing?" signal (score removed in
`c37b8e5`). The above-the-line findings count becomes that signal:

- Headline: "N items above the line" (+ done/clear event state when N = 0).
- One aggregated context row for parked items; the standing-guardrails band for
  ②-tier classes.
- Unlike the old grade, the number **converges**: fixing an above-the-line finding
  moves it; hygiene churn and class-level posture do not.

### One counting module

"N above the line" is computed in exactly one place: a small pure function
(`impact_filter.py`, standalone) that reads findings + temperature and returns
`{above, parked, guardrails}`. Step 9 calls it via an allowlisted command
(the current `inspect --query '.findings|length'` cannot express the filter and
already miscounts — it includes demoted/dropped entries the viewer hides). The
viewer TypeScript implements the same predicate; a parity test pins the two
implementations to identical outputs on shared fixtures. The receipt line and the
viewer can still differ *in time* (the receipt is a frozen transcript; the dial
moves afterwards) — the receipt therefore prints the temperature it counted at.

## 6. Surfacing (viewer + share)

- `ReportPage.tsx` active-findings filter gains the predicate
  `impactAtOrAbove(f.impact, temperature)`; pitfalls/gaps render through the same
  predicate into the standing-guardrails band.
- `rankFindings` gains `impact` as the primary sort key (regressions first) — a
  default-order win even before the user touches the dial.
- Dial UI: 3-segment control (**Broken now / Can hurt you / Everything**) with
  hint subtitles; recommendation chip (§4); parked-items affordance that bumps the
  level one notch.
- `Finding` interface + `normalizeStructuredFinding` carry `impact`,
  `impact_signal`, `consequence_path`.

## 7. Explicit non-interaction with rules/hooks

`severity_class` (5 rule classes, edit-time enforcement) and `impact` (4 finding
tiers, report-time surfacing) are parallel, deliberately distinct vocabularies.
The temperature never reaches `pre-validate.sh`; a `decision_violation` blocks at
any temperature. CLAUDE.md documents both tables side by side. (Future, out of
scope: Step 6 rule synthesis inheriting `severity_class` from the motivating
finding's impact.)

## 8. Fix-prompt feature — preserved, explicitly

`share/viewer/src/lib/fixPrompt.ts` (`buildFixPrompt`) is unchanged and remains
attached to every rendered item at every temperature, including parked and
guardrail items. The lever strengthens it: a bounded above-the-line list makes
"fix everything above the line" a finishable session. Optional additive header
line ("Impact: hazard — realistic over-billing path") only.

## 9. Validation before build

The riskiest assumption is that the LLM emitter assigns hazard-vs-erosion
consistently — the entire default level sits on the one boundary with the weakest
natural grounding. **Before implementation**: re-run impact tagging N times over
the existing SubscriberAgent store (plus two other repos), measure cross-run tier
agreement. Prompt-only, zero code. If the ②/③ call flickers badly even with the
structured `consequence_path`, the field's schema needs hardening before anything
ships.

## 10. Touched surfaces + sync obligations

Canonical → copies (verified by `scripts/verify_sync.py` before commit):

| Canonical | Copies |
|-----------|--------|
| `archie/standalone/{verify_findings,apply_verdicts,finalize}.py`, new `impact_filter.py` | `npm-package/assets/*.py` |
| `share/viewer/src/**` (`findings.ts`, `ReportPage.tsx`, dial + chip + guardrails band, temperature endpoint client) | `npm-package/assets/viewer/**` AND `archie/assets/viewer/**` |
| `archie/standalone/viewer.py` (POST /api/temperature) | `npm-package/assets/viewer.py` |
| `archie/assets/workflow/deep-scan/steps/{step-5b-risk,step-5-wave2-reasoning,step-9-finalize}.md` | per existing workflow-asset shipping |
| `npm-package/bin/archie.mjs` (gitignore block gains `settings.local.json`) | — |

## 11. Testing

- Unit: legacy tier derivation; seed rule (health × load matrix, small-repo guard,
  health-absent fallback, seed-once semantics, `source: "user"` stickiness);
  prior-wins merge + `impact_signal` hysteresis (2-consecutive / git-anchor /
  verdict paths); `correct_to_erosion` and demote-vs-correct disambiguation;
  per-impact floors at the finalize call site only; `consequence_path` gate
  (missing ⇒ ③).
- Counting: `impact_filter.py` unit tests + TS↔Python parity test on shared
  fixtures; receipt count = viewer count at same temperature and store.
- Viewer: filter predicate per level; clear-event stamping + `last_clear`
  round-trip; parked and guardrail counts; POST /api/temperature validation +
  repair-on-read.
- Regression: stores without `impact` load, render, re-tag; demoted finding
  re-emitted as active stays demoted (shared with the spawned resurrection-bug task).

## 12. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Hazard inflation on the ②/③ line (default level) | Structured `consequence_path` (falsifiable, not prose); `correct_to_erosion` downward path; receipt tracks hazard share per scan and warns on jumps |
| Regression false-positives dilute the beloved signal | Highest confidence floor on ①; verifier owns ①/②; downgrade guard surfaces every below-line move |
| Emission overwrites stabilized tiers | Prior-wins merge; emitted tier is a pending vote under existing hysteresis |
| Pitfall/gap tier flicker (no hysteresis exists) | consequence_path gate; static platform tiers; guardrails band is posture, not countdown; lifecycle is v2 |
| Teammate/agent moves someone's line | Per-user gitignored storage; schema documented as contract; validate-and-repair on read |
| Auto-reseed treadmill | Seed once; ongoing recommendation chip; only a human moves the line |
| Tiny-repo degenerate seed | `total_functions >= 25` guard on top20_share; erosion anchor unaffected |
| Verifier fail-open leaves tiers unverified (observed in the wild) | Separate fix task spawned; unverified impact stays at emitted tier, marked provisional |
| Triple viewer sync under-counted | §10 table + `verify_sync.py` gate |

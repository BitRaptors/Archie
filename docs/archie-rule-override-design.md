# Rule Override & Ratification — Design

**Status:** approved direction, pre-implementation
**Date:** 2026-07-07
**Motivating incident:** a user deliberately chose to violate `inv-003` ("run cost is
never stored") on a test branch. The agent asked for confirmation, the user authorized
the override — and then hit three independent hard walls: the edit-time hook
(`pre-validate.sh`, exit 2), the commit-time classifier (`align_check.py`, exit 2), and
the harness's anti-tampering boundary when the agent tried to neutralize the second
hook. The work could not be committed without tampering with enforcement machinery.
The user's authorization existed only in conversation; no gate could see it.

## Problem

Archie's enforcement has no concept of an **authorized violation**. The severity model
(`decision_violation` → block) was built to stop *unattended agent drift*, but it is
applied as an absolute wall with no door for the *informed human owner*. Consequences:

1. Deliberate and accidental violations are indistinguishable to every gate.
2. The block messages advertise no sanctioned path forward, so agents invent
   tampering-shaped workarounds (rewording code to dodge signal strings, neutralizing
   hook scripts) — destroying exactly the audit trail enforcement exists to protect.
3. The only existing escape hatch (`ARCHIE_DISABLE_ALIGN_CHECK=1`) is the wrong shape:
   global, silent, unaudited, undiscoverable, and commit-gate-only.

## Principles

- **Stop-and-confirm, not wall.** A gate's job is to make sure the human *knows* a law
  is being crossed — not to make crossing impossible. First fire blocks; an explicit
  human confirmation converts subsequent fires to visible warnings.
- **The conversation is the authorization.** No user-run scripts, no ceremony. The
  agent's confirmation question (AskUserQuestion / prose) is the approval flow; the
  agent records the outcome. Archie stays a tool the developer mostly doesn't touch.
- **Accountability over prevention.** An override is a committed, PR-visible,
  review-surfaced record. Bypass becomes loud instead of impossible. An agent *could*
  write an ack unprompted — but it lands in the diff and the PR comment, which converts
  tampering from silent to self-incriminating.
- **Two records, two owners.** `findings.json` stays what it is: *what the machine
  observed* (volatile — verifier + hysteresis may rewrite it). The override record is
  *what the human ruled* (durable — nothing machine-managed may erase it).
- **Sync is the single blueprint writer.** The ack is an input signal; folding it into
  the blueprint, docs, and the staged-amendment contract flow is sync's existing job.
  No second writer, no ack-time blueprint mutation.
- **Merge = ratification. Laws stay evidence-derived.** A merged override kills the old
  law; it never authors the new one. The next deep scan derives the replacement
  invariant from what the code actually does (cite-or-omit), keeping the blueprint a
  description of reality, never override prose.

## Lifecycle (block → confirm → carry → ratify → re-derive)

```
edit blocked (exit 2)                                 [gate: pre-validate.sh]
      │  block message now names the sanctioned path
      ▼
agent asks user  ──"proceed"──▶  agent writes ack     [.archie/overrides.json]
      │                          (instant; no sync needed)
      ▼
same rule now WARNs on this branch — edits + commit pass
      │                                               [gates consult acks]
      ▼
/archie-sync folds it in                              [existing claim machinery]
  · records the break as a staged `rule`/`decision` amendment claim
  · reconciles descriptive blueprint as usual
  · re-render annotates affected docs: "override staged — not enforced on branch"
      ▼
PR opens — delivery review surfaces it                 [CI]
  · "⚠️ Staged amendment: inv-003 — store cost — authorized by <user>"
  · joined with findings by rule id; NOT counted in breaks
  · unacknowledged violations still count as breaks
      ▼
merge = ratification                                   [human PR review is the real gate]
      ▼
first sync on base applies the ratified amendment      [deliberate contract change]
  · edits rules.json / domain_invariants (retire or amend the rule)
  · re-renders docs; archives the ack entry to history
      ▼
next deep scan re-derives                              [evidence-based evolution]
  · old invariant no longer observable → not re-derived
  · new pattern observed → new invariant born from code
  · Wave-2 agents see the tombstone → derived laws / decision chain rebuilt,
    not inherited
```

Stage mapping (the user's model): **deepscan** = laws born/re-derived · **sync** =
blueprint evolves + amendments staged/applied · **CI message** = overrides surfaced to
human reviewers. No stage requires the user to run a script.

## Records

### `.archie/overrides.json` (new; committed — the `.archie/.gitignore` template
already keeps snapshot JSON tracked)

```json
{
  "version": 1,
  "overrides": [
    {
      "rule_id": "inv-003",
      "reason": "store cost — perf decision, accepts drift risk",
      "authorized_by": "Gabor Bakos <gabor@mindone.app>",   // git user at ack time
      "branch": "demo/archie-v2-retest",
      "created_at": "2026-07-07T14:12:00Z",
      "status": "acked"          // acked → ratified → archived (see lifecycle)
    }
  ]
}
```

- `status: "acked"` — written by the agent at confirmation. Gates downgrade this rule
  **on this branch** (branch match) from BLOCK to WARN.
- `status: "ratified"` — set by the first sync on base after merge, immediately before
  it applies the contract change; entry then moves to
  `.archie/overrides_history.jsonl` (append-only archive) and is removed from the
  active file. Between merge and that sync, an `acked` entry whose branch is merged is
  treated as ratified by readers (gates + deep scan) — suppression is correct even
  before the bookkeeping catches up.
- The agent writes the ack **only on explicit user confirmation** (the rule-block
  footer and the ack helper's docstring both state this). There is no user-facing CLI.

### `findings.json` (unchanged)

Stays purely observational. The delivery review joins findings ↔ overrides by
`rule_id` at render time; no ack state is ever stored on a finding.

## Component changes

### 1. Ack helper (`sync.py override-ack` subcommand — agent-run only)

`python3 .archie/sync.py override-ack <root> <rule_id> --reason "..."` appends the
entry (git user, current branch, timestamp). Idempotent per (rule_id, branch). Exists
so hook footers can name one exact command and the write is atomic + validated —
the agent never hand-edits the JSON.

### 2. `pre-validate.sh` (edit gate)

- Load `overrides.json`; a fired blocking rule with an active ack for the current
  branch is rendered as
  `WARN (overridden by <user>: <reason>)` instead of `BLOCKED`, and does not cause
  exit 2.
- Every genuine BLOCK gains a footer:
  `To proceed with explicit user authorization: ask the user, then run
  python3 .archie/sync.py override-ack . <rule_id> --reason "<their reason>"`.
  This fixes discoverability — the sanctioned door is named at the moment of blocking.
- Writes to `.archie/overrides.json` itself are exempt from rule matching (no
  recursive blocking of the ack).

### 3. `align_check.py` (commit gate)

- Same consultation: diagnostics for acked rules are demoted from blocking to WARN
  with the override note; `highest_severity` computed after demotion.
- Same footer on genuine blocks.
- `ARCHIE_DISABLE_ALIGN_CHECK` is retained (latency escape) but the footer never
  mentions it; the ack is the sanctioned rule-dispute path.

### 4. Sync integration (fold-in)

- Sync SKILL.md gains a step: read active acks for the current branch; for each,
  record the break via the existing claim flow (`sync.py record`) as an advisory
  `rule`/`decision` claim referencing the ack (`override_ref: <rule_id>`). Advisory
  claims are already always `staged` — the ack simply becomes a **staged contract
  amendment** in the machinery that already exists for exactly this
  ("the user accepts a broken rule by recording it as a claim").
- The render step annotates affected rendered docs (rule files, product-laws.md):
  the rule is shown with an "override staged — not enforced on `<branch>`" marker
  instead of stating the dead law as live truth.

### 5. Delivery review (CI + local sync review)

- `run_pr_gate`/`render_verdict`: load `overrides.json` from the checkout; join with
  confirmed findings by rule id.
  - Finding with matching ack → moved out of the break count into a distinct
    **"⚠️ Acknowledged overrides"** section: rule, reason, authorizer, date.
    A deliberate, disclosed override does not paint the PR red; the human merge
    decision is the real gate.
  - Finding without ack → counts as a break, unchanged.
  - Ack without any matching finding → flagged "stale ack — violation no longer
    observed; remove before merge".
- The local sync review (`sync.py review`) renders the same acknowledged/stale
  distinction in its status line (shared review core → shared treatment).

### 6. Ratification (first sync on base after merge)

- Sync detects active acks whose `branch` is merged into the current base branch
  (`git merge-base --is-ancestor`): marks them `ratified`, applies the amendment to
  the contract — retire (or amend) the rule in `rules.json` and the invariant in
  `blueprint.json` `domain_invariants` — re-renders docs, archives the entry to
  `overrides_history.jsonl`. This is the "deliberate contract change" sync's own
  philosophy requires; the merge is the deliberateness.

### 7. Deep scan (re-derivation)

- Deep-scan prompt additions (Domain + Wave-2 agents): active/ratified overrides are
  handed in as tombstones — "these laws were deliberately overridden; do not carry
  them or their derived laws forward; re-derive this area from current code".
- Finalize step archives consumed tombstones.

## Edge cases

- **Parallel branches override the same/different rules** → ordinary git merge
  conflict on `overrides.json`; rare, resolved like any conflict.
- **Abandoned PR** → ack dies with the branch; nothing leaked to base.
- **User overrides, then review talks them out of it (code reverted)** → the stale-ack
  flag in the delivery review says "remove before merge"; if merged anyway, sync's
  ratification step still applies it — the amendment claim is by then contradicted by
  code, and the next deep scan (evidence-based) simply re-derives the old law. Self
  -healing, at the cost of one scan cycle.
- **Agent writes an ack unprompted** → visible in the diff, named in the PR comment
  with `authorized_by`; social/review accountability, by design (prevention is
  impossible without recreating the hardlock).
- **Teammate pulls after merge but before sync-on-base** → enforcement correct
  immediately (ack travels via git; merged-branch acks read as ratified); narrative
  docs lag until the next sync run. Accepted window, same lag class as any doc.
- **Multiple rules fired by one change** (the incident fired `inv-003` and `trd-002`)
  → each rule needs its own ack; the block footer lists every fired rule id.

## Out of scope (YAGNI)

- Commit-message trailer overrides (could be added later as sugar; the ack file covers
  both gates today).
- Expiry/TTL on acks (branch lifecycle bounds them naturally).
- Auto-generating the *new* law from the override reason (laws stay evidence-derived
  by deep scan, never authored by override prose).
- Org-level policy (e.g. "only leads may override") — accountability surface first;
  policy can sit on top later.

## Testing strategy

- Unit: ack write (idempotency, branch/user stamping); gate demotion in
  `pre-validate.sh` (fired+acked → warn+exit 0; fired+unacked → block+footer;
  acked-other-branch → still blocks); `align_check` demotion incl.
  `highest_severity` recompute; delivery-review join (acked → section not break;
  unacked → break; stale ack flagged); ratification branch-merged detection +
  contract edit + archive; overrides-file write exemption.
- Integration: replay the incident — block → ack → edit passes → commit passes →
  verdict shows acknowledged section.

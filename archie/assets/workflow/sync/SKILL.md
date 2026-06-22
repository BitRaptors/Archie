---
name: archie-sync
description: Reconcile this session's code delta back into the Living Blueprint and per-folder intent layer so they stay an accurate snapshot of the codebase. Mostly descriptive (what the code now is), not rules. Pure producer — edits files only, never commits or opens a PR.
---

# Archie Sync — keep the snapshot current

The blueprint and per-folder CLAUDE.md are **living snapshots of the codebase**. Capture
the work just done and **reconcile** it back so those snapshots stay accurate. No git
writes — record + edit files only; the user decides what to commit.

**Prerequisites:** Archie must already be installed (`.archie/sync.py` exists). If it
doesn't, tell the user to run `npx @bitraptors/archie "$PWD"` and try again.

## Phase 1 — record the change ledger

### Step 1 — Get context: PROVIDE or BUILD

Produce *statements about what the code now is* (not a changelog of your edits):

- **PROVIDE** — you hold the reasoning: emit statements from what you know. Real
  `confidence`, `reconstructed: false`.
- **BUILD** — context cleared/compacted or fresh session: read `git diff` and derive
  statements from the change itself. Structural facts are fine; mark inferred intent
  `confidence: "low"`, `reconstructed: true`. Don't invent beyond the diff.

### Step 2 — Record

Pipe a JSON array of statements. **Descriptive kinds are the default** — what the code
now is. Advisory kinds (decision/pitfall/rule) only when a change genuinely establishes
one; they are NOT the point.

```json
{ "statement": "MainViewModel now filters background subscription-refresh errors so they no longer surface the purchase dialog",
  "kind": "behavior",
  "evidence_files": ["path/touched/by/this/change.ext"],
  "confidence": "low | medium | high", "reconstructed": false }
```

Descriptive kinds: `behavior` (what a component/flow now does) · `structure` (component/
layer/file role added·changed·removed) · `dataflow` (a changed interaction/event/dependency)
· `data` (data-model/persistence) · `tech` (stack/dependency) · `reference` (a quick-ref
fact). Advisory (optional): `decision` · `pitfall` · `rule`.

```bash
echo '<your JSON array>' | python3 .archie/sync.py record .
```

(Add `--agent claude` under Claude Code, or `--agent codex` under Codex, to tag the
record's provenance.)

A statement is **eligible** to fold only if `confidence: medium|high`, `reconstructed:
false`, and grounded in a file inside the diff; else it's `staged` (provisional).

## Phase 2 — reconcile eligible statements into the snapshot

If `record` reported `eligible > 0`, fold them. **The fold is your job** — you reconcile;
the script resolves scope and re-renders.

### Step 3 — Get the scoped targets

```bash
python3 .archie/sync.py fold-context .
```

Returns, per eligible statement, the descriptive `blueprint_sections` to reconcile, the
`edit_file`, and the touched per-folder CLAUDE.md (`intent_files`). **Read only those
sections** — not the whole blueprint.

### Step 4 — Reconcile (do NOT just append)

For each statement, read the target section of the CURRENT snapshot and pick ONE op:

- **NO-OP** — already described accurately → change nothing. (Common — "it's already
  there." Don't manufacture an edit.)
- **UPDATE** — described but now wrong → correct it in place.
- **ADD** — not represented → add it to the right section.
- **REMOVE** — the section describes behavior the code no longer has → remove/correct it.

Where edits land — **the descriptive MIRROR only** (what the code is now):
- `behavior`/`structure` → `.archie/blueprint.json` `components[]` (responsibilities) / `communication`
- `dataflow` → `communication`, `architecture_diagram`
- `data` → `data_models` / `persistence_stores` / `data_overview`
- `tech` → `technology` · `reference` → `quick_reference`

**Do NOT touch the CONTRACT (the law).** Advisory claims (`decision`/`pitfall`/`rule`/
`guideline`) are recorded `staged` and surface under `staged_amendments` in `fold-context` —
they are PROPOSED changes for a separate, deliberate decision, NOT something a code-fold
applies. A fold must never edit `.archie/rules.json`, `domain_invariants`,
`derived_invariants`, `decisions`, or `pitfalls`; **`fold-apply` refuses a render that moved
them.** (Why: the PR Intent Review catches code-vs-law drift — if a fold silently moved the
law to match the code, the deviation would be hidden.)

Then **reconcile the intent layer**: for each touched folder in `intent_files`, update the
**descriptive (AI-authored) section** of that folder's CLAUDE.md to match the code now —
same NO-OP/UPDATE/ADD/REMOVE discipline, **touched folders only**. These are the folder
snapshots; edit them directly. Preserve every untouched section; never drop a whole
top-level blueprint key.

### Step 5 — Apply

```bash
python3 .archie/sync.py fold-apply .
```

Re-renders root `CLAUDE.md` / `AGENTS.md` / rule docs from your edited blueprint, validates
that no top-level section was dropped (aborts the render otherwise), and marks the record
folded. It does **not** mass-rewrite per-folder CLAUDE.md — those you reconciled directly
in Step 4.

### Step 6 — Report what changed ARCHITECTURALLY (not a file list)

Lead with the architectural meaning, plain language:

- **What the snapshot now says that it didn't before** — the changed behavior/structure/
  flow, named at the component or boundary it concerns. e.g. "the subscription layer now
  distinguishes background refresh errors from user-initiated ones" — not "added pf_0010".
- **What was corrected** — if you UPDATEd/REMOVEd a now-false section, say what it used to
  claim and what it says now.
- **Where it lives** — which component/folder snapshot now reflects it.

Rules of the report: don't lead with entry IDs, row counts, or a list of files. Keep
mechanics (version, branch, that blueprint/intent were updated, nothing committed) to ONE
closing line. If the fold was mostly NO-OPs (already current), say that plainly.

Review the ledger any time: `python3 .archie/sync.py list .`

---
description: Record what changed in this session into the Living Blueprint change ledger (Phase 1 — produces a reviewable change file; does NOT modify blueprint.json or any CLAUDE.md).
---

# /archie-sync — record the change ledger (Phase 1)

Capture the work just done into a versioned change record under `.archie/changes/`.
This is **Phase 1: produce output only.** It writes a single change file and changes
**nothing else** — not `blueprint.json`, not any `CLAUDE.md`. The user reviews the
output and decides what to do with it.

This command performs **no git writes** — no commit, no branch, no PR. It only reads the
diff.

## Step 1 — Get sufficient context: PROVIDE or BUILD

You must produce a set of *intent claims* describing the architectural decisions in this
change. Choose one route:

- **PROVIDE** — if you still hold the reasoning from this session (you did the work and
  remember why): emit claims from what you actually know. Set `confidence` to your real
  certainty and `reconstructed: false`.
- **BUILD** — if you do NOT (context was cleared or compacted, or this is a fresh
  session): run `git diff` for the changed range and build the claims from the change
  itself. Record structural facts you can read off the diff, and mark any inferred "why"
  as a hypothesis: `confidence: "low"`, `reconstructed: true`. **Do not invent rationale
  the diff does not support** — fewer honest claims beat confident guesses.

## Step 2 — Emit the payload

Produce a JSON array of claims. Each claim:

```json
{
  "type": "decision | rule | pitfall | guideline",
  "title": "short title",
  "rationale": "the why, one or two sentences",
  "evidence_files": ["path/touched/by/this/change.ext"],
  "confidence": "low | medium | high",
  "reconstructed": false
}
```

Tag every claim with the `evidence_files` it is grounded in (the files this change
actually touched) and an honest `confidence`. A claim only becomes fold-eligible later
if it is `confidence: medium|high`, `reconstructed: false`, and at least one
`evidence_file` is inside the diff. Everything else is recorded as provisional. It is
fine to emit an empty array `[]` to record just the structural diff with no intent.

## Step 3 — Record it

Pipe the payload to the recorder (works identically in Claude Code and Codex):

```bash
echo '<your JSON array>' | python3 .archie/sync.py record . --agent claude
```

(Use `--agent codex` when running under Codex.) Then report the printed summary to the
user — version, branch, how many claims are `eligible` vs `staged`, and the path to the
change file. Remind them it is review-only: nothing was folded into the blueprint.

To review the ledger so far:

```bash
python3 .archie/sync.py list .
```

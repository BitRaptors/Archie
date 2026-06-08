---
description: Capture this session's work into the Living Blueprint — record the change (diff + intent), then fold eligible claims into blueprint.json, rules.json, and the per-folder intent layer. Pure producer (no commit/PR).
---

# /archie-sync — evolve the Living Blueprint

Capture the work just done and fold it into Archie's living dataset. Two phases run in one
command. **No git writes** — record + edit files only; the user decides what to commit.

## Phase 1 — record the change ledger

### Step 1 — Get context: PROVIDE or BUILD

Produce a set of *intent claims* describing the architectural decisions in this change:

- **PROVIDE** — if you still hold the reasoning from this session: emit claims from what
  you know. Real `confidence`, `reconstructed: false`.
- **BUILD** — if you do NOT (context cleared/compacted, or a fresh session): run `git diff`
  and build claims from the change itself. Structural facts you can read off the diff are
  fine; mark any inferred "why" as `confidence: "low"`, `reconstructed: true`. Do not
  invent rationale the diff doesn't support.

### Step 2 — Record

Pipe a JSON array of claims to the recorder:

```json
{ "type": "decision | rule | pitfall | guideline",
  "title": "short title", "rationale": "the why",
  "evidence_files": ["path/touched/by/this/change.ext"],
  "confidence": "low | medium | high", "reconstructed": false }
```

```bash
echo '<your JSON array>' | python3 .archie/sync.py record . --agent claude
```

(`--agent codex` under Codex.) A claim is **eligible** to fold only if it is
`confidence: medium|high`, `reconstructed: false`, and grounded in a file inside the diff;
everything else is recorded as `staged` (provisional) and is NOT folded.

## Phase 2 — fold eligible claims into the blueprint + intent layer

If `record` reported `eligible > 0`, fold them. **The fold is your job (AI)** — you
understand the claims; the script only resolves scope and re-renders.

### Step 3 — Get the scoped edit targets

```bash
python3 .archie/sync.py fold-context .
```

This returns, per eligible claim, the `edit_file` and `blueprint_section` to touch and the
per-folder CLAUDE.md in scope. **Read only those sections** (not the whole blueprint).

### Step 4 — Edit (the understanding step)

For each target, decide the operation and edit the source of truth:

- **ADD** a new section · **CHANGE/supersede** a section that this change made false ·
  **AUGMENT** an existing section · **REMOVE** one no longer true · **NEW** descriptive section.
- `decision` → `blueprint.json` `decisions.key_decisions[]` (keep `decision_chain` /
  `forced_by` / `enables` consistent).
- `pitfall` → `blueprint.json` `pitfalls[]` **and** add a verifier-shaped entry to
  `.archie/findings.json` (`id`, `problem_statement`, `evidence`, `first_seen`,
  `confirmed_in_scan`, `status`).
- `guideline` → `blueprint.json` `implementation_guidelines`.
- `rule` → `.archie/rules.json` (`id`, `kind`, `topic`, `severity_class`, `description`,
  `why`, `applies_to`).
- Set/curate each section's `applies_to` scope so it lands in the right per-folder file.
- Do **not** hand-edit per-folder CLAUDE.md Archie blocks — they re-render from the blueprint.
- Preserve every untouched section. Never drop a whole top-level blueprint key.

### Step 5 — Apply

```bash
python3 .archie/sync.py fold-apply .
```

This re-renders root `CLAUDE.md` / `AGENTS.md` / rule docs from your edited blueprint,
propagates the edited scoped sections into the matching per-folder `CLAUDE.md` via
`inject-scoped` (no-op if the intent layer is absent), validates that no top-level section
was dropped (aborts the render if so), and marks the change record `folded`.

### Step 6 — Report

Tell the user: version, branch, what folded vs stayed staged, which files changed
(blueprint, rules, root + per-folder CLAUDE.md). Remind them nothing was committed.

Review the ledger any time:

```bash
python3 .archie/sync.py list .
```

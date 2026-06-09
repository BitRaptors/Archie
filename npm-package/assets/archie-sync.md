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

### Step 6 — Report what changed ARCHITECTURALLY (not a file list)

Lead with the architectural meaning, in plain language. The user wants to know how the
system's architecture is now *described differently* — not which IDs or files moved. For
the fold as a whole (and per significant claim), answer:

- **What the blueprint now asserts that it didn't before** — the new constraint /
  invariant / decision, named at the boundary or component it governs. e.g. "the
  subscription layer now distinguishes user-initiated errors (may show UI) from background
  refresh errors (must stay silent)" — not "added pf_0010".
- **What was corrected** — if you superseded or augmented an existing section because it
  was no longer true, say what the blueprint *used to* claim, why that was wrong, and what
  it says now.
- **Where it bites** — which component / layer / boundary this governs, and what a future
  agent editing that area will now be told or enforced to do at edit time.

Rules of the report:
- Do NOT lead with entry IDs (`pf_…`, `f_…`, rule ids), row counts, or a list of
  re-rendered CLAUDE.md files. That accounting is noise.
- Keep the mechanics to ONE closing line: record version + branch, that the
  blueprint/rules/findings were updated and docs re-rendered, and that nothing was
  committed (the diff is the user's to review).
- If the fold produced no real architectural change (pure re-render), say exactly that —
  don't dress it up.

Review the ledger any time:

```bash
python3 .archie/sync.py list .
```

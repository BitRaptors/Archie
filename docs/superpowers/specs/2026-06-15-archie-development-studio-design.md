# Archie Development Studio — Design Spec

**Date:** 2026-06-15
**Branch:** `feature/development-studio`
**Status:** Approved design, pre-implementation

## What This Is

A development workflow system for Archie, set up by `/archie-start-development-studio`,
that brings issue tracking + an autonomous development loop into any target project.
Adapted from the BedtimeApp `wds-5-agentic-development` model, but tightly integrated
with Archie's enforcement layer (blueprint, rules, hooks) — which is the differentiator
over a plain ticket system: the **blueprint drives planning** and the **hooks/rules
enforce implementation**.

Decided scope:
- Issue tracking **and** the autonomous loop (full package).
- Command surface: one setup command + a small command family.
- Tightly integrated with Archie's blueprint/rules/hooks.
- `/archie-work` is **autonomous after plan approval** (Ralph model).
- Implementation approach: **hybrid** — deterministic mechanics in Python, the
  reasoning (plan/implement/review/loop) in prompt markdown.

## Architecture (Hybrid)

Deterministic, error-prone mechanics live in a zero-dependency Python script;
the semantic/reasoning layer lives in prompt markdown the agent reads. This mirrors
Archie's existing split (deterministic `renderer.py` vs. AI `deep-scan`).

### New standalone script: `archie/standalone/studio.py`
(canonical → synced to `npm-package/assets/studio.py`)

Subcommands (Python never runs git — it only writes files):
- `studio.py init <project>` — scaffold folders, template, empty INDEX, the workflow
  doc, and patch AGENTS.md with a pointer block. Idempotent.
- `studio.py new <project> --title "..." --type feature --label backend` — allocate ID,
  create ticket file in `planned/` from template, refresh INDEX.
- `studio.py move <project> ISS-NNN <status>` — move file between status folders +
  refresh INDEX. Rejects unknown statuses.
- `studio.py index <project>` — fully regenerate INDEX.md from ticket frontmatter.
  Tables are always derived, never hand-edited.
- `studio.py next <project>` — return the next ticket per Ralph priority
  (blocked → surface, in-progress → continue, planned → promote, empty → idle).

### Scaffolded structure in the target project
```
.archie/issues/
├── INDEX.md              # derived (studio.py index regenerates it)
├── WORKFLOW.md           # full workflow description (the single source AGENTS.md points to)
├── _TEMPLATE.md          # ticket template
├── planned/  in-progress/  in-review/  done/  blocked/
├── epics/                # EPIC-NNN.md (optional)
└── evidence/ISS-NNN/     # iter-NN-*.png|txt
```

### Prompt files (`.archie/prompts/`, copied by the npm installer)
- `skill_archie_studio_setup.md` — body of the setup command
- `skill_archie_studio_work.md` — body of the autonomous loop
- `skill_archie_studio_issue.md` — interactive new-issue creation

### Command files (`.claude/commands/` → synced to `npm-package/assets/`)
- `archie-start-development-studio.md` — thin router to the setup prompt
- `archie-issue.md` — new ticket
- `archie-work.md` — run the loop on the next ticket

### AGENTS.md patch (lean)
The setup writes the full workflow into `.archie/issues/WORKFLOW.md` and inserts only a
short marked pointer block into AGENTS.md:

```
<!-- ARCHIE:STUDIO:START -->
## Development Studio
This project uses Archie's development studio for issue tracking and the agentic
development loop. **Before any code change, read `.archie/issues/WORKFLOW.md`** —
it defines the required workflow, ticket lifecycle, and autonomous execution rules.
<!-- ARCHIE:STUDIO:END -->
```

Idempotent: re-running replaces the block between the markers; never duplicates.
No AGENTS.md → create it; exists without markers → append the block.

## Ticket File Format

Frontmatter + markdown (adapted from BedtimeApp TIT-NNN → ISS-NNN):
```yaml
---
id: ISS-NNN
title: Short imperative title
status: planned        # planned | in-progress | in-review | done | blocked
labels: [backend]
branch: feature/ISS-NNN-short-slug
assignee: csaba
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: feature          # feature | bugfix | refactor | chore
epic: EPIC-NNN         # optional
---
## Context
## Plan            # checkbox list, one box per verifiable step
## Implementation Notes
## Iteration Log    # iter NN (YYYY-MM-DD HH:MM): what / result / next
## Last Test Run    # command / result / summary / ran (overwritten each iter)
## Evidence         # links to evidence/ISS-NNN/iter-NN-*
## Blocker          # only if status: blocked
## Review Notes
## Testing
```

## The Loop (`/archie-work`)

Runs on the ticket chosen by `studio.py next`. Five phases, **autonomous after Plan
approval**. Stops only on: blocker / destructive action / 2 consecutive failed fix
attempts on the same root cause (→ `status: blocked`, write Blocker, stop).

0. **Pick** — `next` per Ralph priority. Blocked present → surface, stop. Each ticket is
   self-contained; read from the file, not from conversation.
1. **Scope & Plan** — read the ticket AND `.archie/blueprint.json` (relevant
   `decisions`, `domain_invariants`, `pitfalls`, `components` for the touched folders).
   Write the Plan as a checkbox list, annotating which rule/invariant each step must
   preserve. Create branch `<type>/ISS-NNN-<slug>`, move `planned/`→`in-progress/`.
   **Wait for approval here.**
2. **Setup** — verify runtime/deps, run baseline tests (distinguish regression vs.
   pre-existing), confirm Archie hooks (`pre-validate.sh`) are installed.
3. **Implement** — step by step in dependency order. **Archie integration is live here:**
   `pre-validate.sh` enforces against `rules.json` on each edit (decision_violation /
   pitfall_triggered / mechanical_violation = block exit 2; tradeoff = warn; divergence =
   info). On a block, the agent fixes using the rule's `WHY`+`EXAMPLE` blocks. After each
   checkbox: Iteration Log + Last Test Run + `[x]` + commit (`feat(ISS-NNN): ...`).
4. **Verify** — every acceptance criterion one by one, capture evidence to
   `evidence/ISS-NNN/iter-NN-*`. Where a domain invariant is touched, test it concretely
   (balance bounds, lifecycle immutability, idempotency, tenant scoping per blueprint).
5. **Finalize** — debug cleanup, full test + lint/type, optional `validate.py` + `drift.py`
   (does the implementation still match the blueprint), PR description, `in-progress/`→
   `done/`, INDEX refresh, commit.

**Review** (between 4 and 5): separate review agent on the diff; findings → `Review Notes`;
status `in-review`. `arch_review.py` is an optional extra signal.

## ID Allocation, INDEX, Git

- **ID allocation (`new`):** scan all ticket frontmatter across every status folder
  (incl. done), take max `ISS-NNN`, +1, zero-padded to 3. Same for `EPIC-NNN`. ID lives in
  both filename and frontmatter; `index` checks they agree. Single-user/local → no race.
- **INDEX (always derived):** `index` rebuilds the whole file from frontmatter. Sections:
  Next IDs, Roadmap (epic order = autonomous priority), Epics table, Blocked table, Active
  table (in-progress + in-review + planned), Done table (last 20). Never hand-edited; every
  `move` calls `index`. Frontmatter parsing follows the Archie convention (NUL-safe file
  lists, never whitespace `.split()`).
- **Git/branch:** one ticket = one branch = one logical change. Planning phase on `main`
  (create ticket + push so it's visible). Branch `<type>/ISS-NNN-<slug>`. Commits:
  `docs(issues): add/plan/close ISS-NNN`, implementation `feat|fix|refactor|chore(ISS-NNN):
  ...`. `studio.py` never runs git — the agent does, per prompt instructions (so existing
  push/destructive-action guardrails apply).

## Edge Cases

- `init` re-run with existing `issues/` → idempotent; never deletes tickets, only adds
  missing folders/template, replaces AGENTS.md marker block.
- No AGENTS.md → create; exists without markers → append block.
- `next` finds a blocked ticket → surface + stop (don't promote).
- Ticket filename/frontmatter ID mismatch → `index` warns.
- Corrupt/frontmatter-less file in `issues/` → skip + warn, don't crash.
- `move` to unknown status → reject (only the 5 known statuses).
- No `blueprint.json` (deep-scan never ran) → `work` warns that integration is degraded
  (loop runs without enforcement/guidance), suggests `/archie-deep-scan`.

## Testing (pytest, `tests/`)

`studio.py` per subcommand: ID allocation (gaps, max across status folders), INDEX
generation determinism, idempotent init, AGENTS.md marker replacement, status move +
regression back, corrupt-frontmatter skip, NUL-safe parsing. The prompt/loop isn't
unit-testable, but the scaffold output is validated.

## File Sync (before commit)

Everything authored at canonical locations (`archie/standalone/`, `.claude/commands/`,
`.archie/prompts/`), then copied to `npm-package/assets/` + `archie.mjs` installer
references, finally `python3 scripts/verify_sync.py`.

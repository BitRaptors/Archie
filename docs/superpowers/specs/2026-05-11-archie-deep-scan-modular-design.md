# Design: Modularize `archie-deep-scan` Slash Command

**Date:** 2026-05-11
**Branch:** `refactor/archie-deep-scan-modular`
**Status:** Approved (brainstorming complete, ready for plan)

## Problem

`.claude/commands/archie-deep-scan.md` is a 1906-line monolith. The single
file holds:

- The slash-command preamble and step-router logic (~250 lines)
- Phase 0 scope resolution (137 lines) — already duplicated as
  `.claude/commands/_shared/scope_resolution.md`
- Step 3 Wave-1 parallel agent orchestration plus 4 full sub-agent prompts
  (542 lines)
- Step 5 Wave-2 reasoning agent prompt (297 lines)
- Step 6 rule synthesis prompt with examples (252 lines)
- Steps 1, 2, 4, 7–10 (60–200 lines each)
- The Scan Report markdown template (70 lines)
- Cross-cutting fragments: telemetry conventions, compact/resume contract,
  resume prelude

Symptoms:

1. **Editing is risky.** A change to one step's prompt is hard to scope —
   the surrounding 1900 lines all share variable names and shell context, so
   diff review is painful and regressions slip in.
2. **Per-edit context cost.** Every time an agent works on a single step it
   loads the whole 1906-line file even when only ~150 lines are relevant.
3. **Phase 0 is duplicated** — the canonical `_shared/scope_resolution.md`
   exists but the deep-scan still inlines its own copy, so they drift.
4. **Search-and-jump is awkward** — "find Step 6's example list" requires
   scrolling past two other massive prompts; even `grep` returns matches
   from unrelated sections because the IDs overlap.

The B-Mad skill pattern (e.g. `bmad-agent-builder/`) solves the same shape
of problem with a slim router SKILL.md that loads `references/<topic>.md`
files on demand. We want the same progressive-disclosure benefit while
keeping the existing slash-command UX (`/archie-deep-scan`) intact.

## Goal

Refactor `.claude/commands/archie-deep-scan.md` into:

1. A **slim router** (~120–150 lines) at the same path — preserves the
   slash-command UX and the existing user-invocation surface.
2. A sibling **`archie-deep-scan/` directory** holding self-contained step
   files, sub-agent prompts, fragments, and templates that the router
   loads on demand.
3. A **single canonical Phase 0** — delete the inline duplicate from the
   router, point at `_shared/scope_resolution.md` (which already exists).

The change is **purely structural**. The behavior of `/archie-deep-scan`
against a real project must be identical to before — same files written
to disk, same telemetry, same blueprint/rules outputs.

## Non-Goals

- No behavioral change. No new step, no removed step, no different prompts
  to sub-agents (the prompt text is moved, not rewritten).
- No conversion to the newer skill-directory layout
  (`.claude/skills/<name>/SKILL.md`). The slash-command path stays.
- No change to the underlying Python scripts in `archie/standalone/` or
  `.archie/`. The scripts the command shells out to are unchanged.
- No change to the `/archie-scan` command (incremental scan). It can
  reuse the same shared fragments later in a follow-up, but that is out
  of scope here.
- No update to the user-facing docs (README, landing page, etc.). The
  refactor is internal.

## Solution

### Final directory layout

```
.claude/commands/
  archie-deep-scan.md                       ← slim router (~120-150 lines)
  _shared/
    scope_resolution.md                     ← already exists, router calls it directly
  archie-deep-scan/
    steps/
      step-1-scanner.md
      step-2-read-scan.md
      step-3-wave1/
        orchestration.md                    ← incremental vs full branch + dispatch logic
        structure-agent.md
        patterns-agent.md
        technology-agent.md
        ui-layer-agent.md
        grounding-rules.md                  ← shared rules referenced by all 4 agents
      step-4-merge.md
      step-5-wave2-reasoning.md
      step-6-rule-synthesis.md
      step-7-intent-layer.md
      step-8-cleanup.md
      step-9-drift.md
      step-10-telemetry.md
    fragments/
      compact-resume-contract.md
      resume-prelude.md
      telemetry-conventions.md
    templates/
      scan-report.md
```

Mirrored under `npm-package/assets/` with the same tree shape (see
"npm-package mirroring" below).

### Router file shape (`archie-deep-scan.md`)

Target: 120–150 lines. Contains only:

1. **Title + 1-paragraph description** (what the command does, when to use it).
2. **Args block** — preserved as-is from current file.
3. **Activation sequence** — explicit "Read these files first" list:
   - `archie-deep-scan/fragments/telemetry-conventions.md`
   - `archie-deep-scan/fragments/compact-resume-contract.md`
   - If `RESUME_ACTION=resume`: `archie-deep-scan/fragments/resume-prelude.md`
   - `_shared/scope_resolution.md` (Phase 0)
4. **Step-by-step routing table** — markdown table:
   ```
   | Step | What it does | Load this file before starting |
   |---|---|---|
   | 1 | Run the scanner | archie-deep-scan/steps/step-1-scanner.md |
   | 2 | Read scan results | archie-deep-scan/steps/step-2-read-scan.md |
   | 3 | Wave 1 parallel agents | archie-deep-scan/steps/step-3-wave1/orchestration.md |
   | 4 | Save & merge Wave 1 | archie-deep-scan/steps/step-4-merge.md |
   | 5 | Wave 2 reasoning | archie-deep-scan/steps/step-5-wave2-reasoning.md |
   | 6 | Rule synthesis | archie-deep-scan/steps/step-6-rule-synthesis.md |
   | 7 | Intent Layer | archie-deep-scan/steps/step-7-intent-layer.md |
   | 8 | Cleanup | archie-deep-scan/steps/step-8-cleanup.md |
   | 9 | Drift detection | archie-deep-scan/steps/step-9-drift.md |
   | 10 | Final telemetry | archie-deep-scan/steps/step-10-telemetry.md |
   ```
5. **Loading discipline statement** — explicit rule:
   > Before starting any Step N, you MUST read the file listed in the
   > routing table for that step. The router does not contain step content
   > — each step is a self-contained file. Loading step files in
   > advance is also fine; loading them lazily as you reach each step
   > saves context.
6. **Skipping rules** — when to skip steps based on `START_STEP` (already
   present in the current file; keep the same logic).

What the router does **NOT** contain: any inline prompt, any sub-agent
instructions, any per-step shell logic. Those live in step files.

### Step 3 Wave-1 sub-structure

Step 3 is unique because its "step" is really an orchestration prelude
plus 4 (or 3) full sub-agent prompts. Layout:

- `step-3-wave1/orchestration.md` — the dispatcher. Decides
  incremental-vs-full mode, decides whether to spawn the UI Layer agent
  based on `frontend_ratio`, and tells the AI which sub-agent prompt
  files to embed into the 4 parallel `Agent` tool calls.
- `step-3-wave1/structure-agent.md` — full prompt body for the structure
  sub-agent.
- `step-3-wave1/patterns-agent.md` — full prompt body for the patterns
  sub-agent.
- `step-3-wave1/technology-agent.md` — full prompt body for the
  technology sub-agent.
- `step-3-wave1/ui-layer-agent.md` — full prompt body for the UI Layer
  sub-agent.
- `step-3-wave1/grounding-rules.md` — the shared "GROUNDING RULES"
  appendix all four prompts reference. Extracted so it lives in exactly
  one place; each agent prompt ends with "Read
  `archie-deep-scan/steps/step-3-wave1/grounding-rules.md` and apply".

The orchestrator does **not** inline the prompts — when it dispatches
Agent calls, it passes the *contents* of the relevant agent file as the
sub-agent prompt. The orchestrator's job is to read the files, compose
them, and dispatch.

### Fragments — what counts as a fragment vs. a step

Steps are *sequential phases of the deep scan pipeline.* Fragments are
*cross-cutting rules every step relies on.* Concretely:

- `telemetry-conventions.md` — the once-per-run statement of how
  telemetry mark/finish/write works. Every step uses telemetry, no step
  *is* telemetry.
- `compact-resume-contract.md` — explains how the pipeline survives a
  `/compact` mid-run via `.archie/deep_scan_state.json`. Applies to
  every step.
- `resume-prelude.md` — the shell prelude that rehydrates state from
  `deep_scan_state.json` when `RESUME_ACTION=resume`. Runs *before*
  step routing, not as a step.

The router loads all three fragments up front (the third only when
resuming). After that, each step file is free to assume the conventions
are in place.

### Templates

Currently the Scan Report markdown template lives inline in Step 9. We
move it to `archie-deep-scan/templates/scan-report.md` so Step 9's prose
("Phase 4 — write scan_report.md using this template") can stay short,
and the template can be edited independently.

If future steps grow their own embedded templates (a blueprint header
template, a drift report header, etc.), they go in `templates/`.

### Router loading semantics

The router contains explicit instructions in plain English. Claude reads
the router when the user types `/archie-deep-scan`. The instructions
say "Before starting Step N, Read this file." The AI uses the Read tool
to pull each step file into context only when it reaches that step. This
is exactly the pattern B-Mad uses, and it's how the AI already loads
shared fragments today (e.g. `_shared/scope_resolution.md` is referenced
by other commands using a "Load this and apply" instruction).

No new tooling needed. Just discipline in the router's wording.

### npm-package mirroring

The current `npm-package/assets/` is a flat directory containing every
canonical asset. The verifier in `scripts/verify_sync.py` walks pairs of
canonical and asset paths and asserts byte-for-byte equality.

We change the asset directory to mirror the canonical tree:

```
npm-package/assets/
  archie-deep-scan.md
  _shared/
    scope_resolution.md
  archie-deep-scan/
    steps/
      step-1-scanner.md
      ...
    fragments/
      ...
    templates/
      ...
  (other archie-* commands and scripts unchanged)
```

Two updates needed:

1. `scripts/verify_sync.py` — extend the asset-discovery glob from
   `npm-package/assets/archie-*.md` to recursive
   `npm-package/assets/archie-deep-scan/**/*.md`, and add the
   `_shared/` mirror to its known-pair list. Keep the existing
   flat-file logic for the other commands and Python scripts.
2. `npm-package/archie.mjs` (the npm installer that copies assets into
   a target project) — switch from copying individual files to
   recursive directory copy for the `archie-deep-scan/` subtree and
   `_shared/`. Verify the installer creates target directories that
   don't exist yet.

### Validation strategy

Smoke test, not unit test. We run `/archie-deep-scan` against a real
project before and after the refactor and compare outputs.

- **Before refactor:** snapshot the current outputs from a clean run of
  `/archie-deep-scan` on a small reference project (suggestion:
  `/Users/csacsi/DEV/Gasztroterkepek.iOS` — known-good, used in earlier
  enforcement-split smoke test).
- **After refactor:** run again against the same project, diff the
  outputs.

Acceptable differences: nothing. The refactor must produce identical
`blueprint.json`, `rules.json`, `scan_report.md`, `.claude/rules/*`,
per-folder `CLAUDE.md` files, etc. If any output differs, the refactor
broke behavior and the diff identifies where.

Practical workflow: run before-scan once, save outputs to
`/tmp/archie-before/`. After refactor, run again to
`/tmp/archie-after/`. Diff the directories with `diff -r`.

This isn't automated in CI (Archie's CI doesn't run live AI scans), but
the workflow is documented in the plan as a required final task.

## Components

| Component | Responsibility | Change |
|---|---|---|
| `.claude/commands/archie-deep-scan.md` | Slash-command entry point | Shrink from 1906 → ~150 lines (router only) |
| `.claude/commands/archie-deep-scan/steps/*.md` | One file per pipeline step | NEW |
| `.claude/commands/archie-deep-scan/steps/step-3-wave1/*.md` | Step 3 orchestrator + 4 sub-agent prompts + grounding rules | NEW |
| `.claude/commands/archie-deep-scan/fragments/*.md` | Cross-cutting conventions | NEW |
| `.claude/commands/archie-deep-scan/templates/*.md` | Output templates (Scan Report) | NEW |
| `.claude/commands/_shared/scope_resolution.md` | Phase 0 logic | UNCHANGED — router now references the existing file |
| `npm-package/assets/` | Mirror of canonical commands | Tree-mirror the new subtree |
| `scripts/verify_sync.py` | Sync verifier | Add recursive walk for `archie-deep-scan/` and `_shared/` |
| `npm-package/archie.mjs` | npm installer | Add recursive copy for new subtrees |

## Data flow

1. User types `/archie-deep-scan`.
2. Claude Code expands the slash-command file content (the slim router)
   into the prompt.
3. Router instructions tell the AI:
   - Read `fragments/telemetry-conventions.md`
   - Read `fragments/compact-resume-contract.md`
   - If resuming: Read `fragments/resume-prelude.md`
   - Read `_shared/scope_resolution.md` (Phase 0)
4. AI starts executing Phase 0 from the shared file.
5. AI reaches Step 1. Following the routing table, it reads
   `steps/step-1-scanner.md` and executes it.
6. After Step 1 completes, AI reads `steps/step-2-read-scan.md` and
   executes. And so on through Step 10.
7. For Step 3, the AI first reads `step-3-wave1/orchestration.md`, then
   based on its instructions reads the 4 sub-agent prompt files plus
   `grounding-rules.md`, composes the Agent tool calls (passing each
   sub-agent file's content as the `prompt`), and dispatches them in
   parallel.
8. Step 9 reads `templates/scan-report.md` and uses it to render the
   final report.

The flow is identical to today's behavior — just with file reads
between phases instead of all instructions being inline.

## Error handling

- **Missing step file**: if any referenced file doesn't exist, the AI's
  Read tool returns an error. The user sees a clear "file not found"
  message and the run halts. Mitigation: the migration plan moves files
  one step at a time and verifies the router reference exists before
  committing each move.
- **Sync drift** (canonical vs. mirror): `verify_sync.py` catches it
  before commit. Each phase of the migration runs verify_sync.
- **npm install regression**: a user who installs `@bitraptors/archie`
  after this lands gets the new tree. Verified by running
  `npx @bitraptors/archie /tmp/test-project` post-refactor and inspecting
  the copied files.
- **Resume contract breakage**: the `RESUME_ACTION=resume` path is
  load-bearing. We test it by intentionally interrupting a deep scan and
  re-running with the resume flag in the smoke-test step of the plan.

## Testing

No automated test suite is added — the refactor is pure file movement
with no logic change. Validation is:

1. **`pytest tests/` still passes** — no Python files change behavior,
   so all renderer/finalize/upload tests must keep passing.
2. **`scripts/verify_sync.py` passes** after each phase commit.
3. **Smoke test against Gasztroterkepek.iOS** — described in
   "Validation strategy" above. Output diff must be empty.
4. **`grep -r "Phase 0" .claude/commands/`** returns only the
   `_shared/scope_resolution.md` definition and the router's reference
   to it. Inline Phase 0 must be gone after the migration.

## Migration / rollout

Performed in the implementation plan as a sequence of small commits, one
per logical extraction (per Step, per fragment), so each commit is
reviewable and reversible.

Recommended order:

1. **Phase 1** — extract fragments and templates first (small,
   independent, low-risk).
2. **Phase 2** — extract steps with self-contained prompts (Steps 1, 2,
   4, 7, 8, 10).
3. **Phase 3** — extract Step 9 (drift detection) + its templates/.
4. **Phase 4** — extract Step 3 (the biggest carve-out, includes the
   sub-directory).
5. **Phase 5** — extract Step 5 (Wave 2 reasoning prompt).
6. **Phase 6** — extract Step 6 (rule synthesis prompt).
7. **Phase 7** — collapse the router; delete inline Phase 0, reference
   `_shared/scope_resolution.md`.
8. **Phase 8** — update `verify_sync.py` to walk the tree. Mirror to
   npm-package/assets/. Update `archie.mjs` installer.
9. **Phase 9** — smoke test against Gasztroterkepek.iOS, verify
   identical output. Push branch and open PR.

Each phase ends with a commit + push so progress is visible and any
phase can be reviewed in isolation.

## Out of scope (deferred)

- Same refactor for `/archie-scan` (incremental scan command). It is
  ~300 lines today; the cost/benefit is lower. Can be done in a
  follow-up using the same patterns.
- Converting the slash command to a full B-Mad-style skill directory
  (`.claude/skills/archie-deep-scan/SKILL.md`). Discussed during
  brainstorming and rejected because (a) breaks the slash-command UX,
  (b) doubles the install surface area, (c) provides no additional
  value beyond what the slim router + references pattern already gives.
- Adding a CI check that runs an actual `/archie-deep-scan` on a
  fixture project. The AI dependency makes this expensive and flaky;
  manual smoke test in the plan is sufficient.

## Open questions

None blocking. Implementation can begin.

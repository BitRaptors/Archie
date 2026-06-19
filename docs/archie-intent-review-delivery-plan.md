<!-- Generated via a 9-agent research+critique+revise workflow on 2026-06-19. Implements docs/archie-intent-review-design.md. -->

# Archie Intent Review POC — End-to-End Delivery Plan

> Implements `docs/archie-intent-review-design.md` (approved). This plan does not re-litigate the design's decisions (§11) or scope (§10); it makes them buildable. All file paths are repo-relative to `/Users/hamutarto/DEV/Repos/Archie`.

---

## 1. Overview & goal

Archie Intent Review is a GitHub Action that fires on PR open/synchronize, computes a **deterministic structured diff of the architectural source of truth** (`.archie/blueprint.json` + `.archie/rules.json`, branch vs `origin/<base>`), corroborates it with the sync ledger (`.archie/changes/change_*.json`), makes **one Claude Haiku call** to *judge* (not re-derive) that diff against the *retained* rules/invariants, and posts **one upserted FYI comment** flagging silent weakening, contradiction, or behavior-violates-rule. It surfaces; the human decides; it never blocks. The deliverable is **two files dropped into a target repo** (`intent_review.py` + `archie-intent-review.yml`) plus one idempotent `gh`-based setup script, all authored canonically in `archie/` and file-synced to `npm-package/assets/` per the repo's three-tier distribution rule.

**Definition of done for the POC:**
1. On a real PR to Archie's own repo that folds a blueprint change, the Action posts a correct, verifiable, cited FYI comment grouped by flag — and re-pushes update the same comment (no spam).
2. The comment honors **because-or-suppress** (§7): every finding carries a cited `because`; findings that can't are dropped, not shown.
3. Empty/None states (no blueprint diff, no ledger, no findings) produce a minimal or no comment, never a noisy wall (§8 note 5).
4. The Action degrades safely on fork PRs (no secret → skip cleanly **before any GitHub write**) and on malformed/missing JSON.
5. `python3 scripts/verify_sync.py` passes with the new files wired in **at every interim commit** (not just at the end); `pytest tests/` green.
6. The dependency chain (§12) is satisfied: Archie's repo is self-instrumented (deep-scan baseline on `main`, sync run on the test branch) so the first signal isolates the *idea* from *upstream quality*.

---

## 2. Architecture recap

**Two installed files** (design §8), one CI setup helper.

### Inputs the Action gathers (design §5 step 4)
1. **Proposed change to truth** — structured diff of `.archie/blueprint.json` + `.archie/rules.json`, **branch vs `origin/<base>`** (`github.base_ref`). The base versions are fetched via `git show <base-sha>:.archie/blueprint.json` *after* an explicit `git fetch` of the base ref (see §4). The branch versions are already on disk after `actions/checkout`.
2. **Evidence behind it** — the **union of all** `.archie/changes/change_*.json` new on the branch, NOT `latest.json` alone (`latest.json` is overwritten on every `record`; each sync writes a unique versioned file via `sync.py` `_next_version`).
3. **What must still hold** — the *retained* rules/invariants from the base-ref blueprint (rules untouched by the diff), pre-filtered by relevance to bound tokens.

### Division of labor — deterministic script vs. model (critique gap M6, design §4/§11)
The diff is **deterministic by design**: "no AI to find *what* changed." Therefore:
- The **script** owns and computes: `diff_op` (REMOVE/UPDATE/ADD/CONFLICT), `rule_id`/keyed id, `layer` (1 vs 2, derived from section + ledger `kind`), and the ledger join.
- The **model** owns only *judgment*: `type` (which flag), `what_changed` (human prose), `because` (cited rationale), and whether to suppress.
- The model's output object **echoes** the script's `diff_op`/`rule_id`/`layer` for traceability, but the script **overwrites** those fields from its own diff before rendering — the model's claimed op is never trusted over the deterministic diff. There is therefore no reconciliation ambiguity.

### Real schemas this consumes (from research)
- **`blueprint.json` invariant-bearing sections** (deep-scan): `domain_invariants[]`, `derived_invariants[]`, `unenforced_invariants[]` (each `{id, entity, category, domain_role, invariant, mechanism, enforced_at[], evidence[], failure_mode, confidence: stated|inferred, keywords[]}`); `decisions.key_decisions[]` (`{title, forced_by, enables, rationale, alternatives_rejected}` — **no id**); `decisions.trade_offs[]` (carry `violation_signals`); `decisions.decision_chain` (root + `forces[].violation_keywords`); `pitfalls[]` (`{id, problem_statement, root_cause, fix_direction, evidence}`).
- **`rules.json`** is `{rules: [...]}` or a flat legacy list; each rule: `{id, kind, topic, severity_class, description, why, example, source, forced_by, enables, alternative, keywords[], triggers{path_glob[], code_shape[]}, check, applies_to, file_pattern, forbidden_patterns[]}`. Both new and legacy shapes must parse. **A missing or empty `rules.json` (on either side) is treated as `{rules: []}`, never an error** — fresh `archie init` writes an empty `rules.json`, but a repo may predate that, so the absent file is also the empty case.
- **Ledger claim** (archie-sync / design §3): `{id, kind, status: eligible|staged, statement, evidence_files[], confidence: low|medium|high, reconstructed: bool}` inside a record with `{version, id, folded, provenance{git_head, branch, reconstructed}, diff{changed_files[], affected_folders[], ratio}, claims[]}`. The `kind` advisory/descriptive split gives **Layer 1 vs Layer 2 for free** (design §3): advisory = `decision|pitfall|rule|guideline`, descriptive = `behavior|structure|dataflow|data|tech|reference`.

### One Haiku call → FYI comment
`claude-haiku-4-5` (exact id, no date suffix) at `https://api.anthropic.com/v1/messages`, `anthropic-version: 2023-06-01`, structured output forced via `tool_use` + `input_schema` (Haiku 4.5 has no `output_config.format`). `max_tokens: 4096` (the Acme worked example alone produces four prose findings; 2048 risks truncation). Comment upserted on `/repos/{owner}/{repo}/issues/{pr}/comments` via hidden marker `<!-- archie-intent-review -->`.

---

## 3. Milestones

> File-sync rule (CLAUDE.md §"File Sync"): author **canonical first**, then byte-copy to the npm asset, then run `scripts/verify_sync.py`. Every code milestone below lists CANONICAL → COPY. **Critical sequencing fix:** the installer/checker wiring (formerly M7) is split — its blocking parts move into **M1** so the repo never enters a sync-failing state. CLAUDE.md mandates `verify_sync.py` before every commit; the moment `intent_review.py` exists in both trees without the `archie.mjs` entry, the checker fails and blocks all interim commits.

### M1 — Installer/checker wiring + `intent_review.py` core (load + diff + glob)
**Goal:** make the repo sync-clean for the new files *first*, then build deterministic diff + input assembly (no AI yet).

**M1a — Wiring (do this in the same commit that first creates the two `.py` files, before any other work):**
- Add `"intent_review.py"` to the script list in `npm-package/bin/archie.mjs` (line 359 `const script of [...]`). This makes the installer copy it into every target `.archie/` on `npx` install. **This is required and accepted** — there is no allowlist mechanism in `verify_sync.py`; the script installing everywhere is fine because the workflow invokes it from `.archie/`.
- Add `"intent_review.py"` to `_STANDALONE_SCRIPTS` in `archie/install.py` (the list at line 52) **AND** to the mirrored `npm-package/assets/_install_pkg/install.py` (byte-checked by `check_install_pkg_mirror` in `verify_sync.py` — editing only the canonical fails the check).
- Extend `scripts/verify_sync.py` with the **three concrete checker edits** the byte-identical guarantee actually requires (none exist today; see §6 "verify_sync edits"). Land these in M1a so they're green the instant the new files appear.
- Do **NOT** add to `manifest_data.py:COMMANDS`, do **NOT** write a SKILL.md, do **NOT** add a `_copy_github_workflows()` to `install.py` — intent-review is not a user-facing skill, and the setup script is the **sole** installer of the workflow `.yml` (see §5 / §8 decision). The `npx` installer does not inject `.github/workflows/`.

**M1b — Core script (`intent_review.py`):**
- Skeleton: read env (`ANTHROPIC_API_KEY`, `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, `GITHUB_BASE_REF`, `GITHUB_EVENT_PATH`), stdlib-only.
- **Derive owner/repo/PR number explicitly** (critique low gap): split `GITHUB_REPOSITORY` on `/` → `owner, repo`; parse `json.load(open(GITHUB_EVENT_PATH))["pull_request"]["number"]` → `pr_number`. Implement `parse_event_context()` returning `(owner, repo, pr_number, base_ref)`; fail clean (exit 0) if the payload lacks `pull_request`.
- **Early fork-PR / no-secret guard FIRST**, before any diff or GitHub call: if `ANTHROPIC_API_KEY` is empty → log + `exit 0` (fork PRs have read-only `GITHUB_TOKEN` and no secret; exiting before any write means even the "cannot parse" marker is never attempted on a fork, satisfying "degrade safely on fork PRs").
- Implement `fetch_base_file(repo_root, rel_path, base_ref)` via `subprocess git show <base_ref>:<path>` returning `(exists, dict|None, error)`. Missing-on-base (`returncode != 0` with "does not exist"/"Invalid object") → treat all branch items as ADD. Apply the same to `rules.json`: **base-side AND branch-side missing/empty `rules.json` → empty list, not crash.**
- Implement `keyed_diff(base_section, branch_section, id_field, title_field)` → list of `{id, status: REMOVE|UPDATE|ADD, base_item, branch_item, fields_changed}`. Fall back to `_hash_title()` when `id` absent (domain_invariants on older blueprints; all of `key_decisions`/`trade_offs`).
- Wire the section→key map: keyed-by-`id` = `domain_invariants`, `derived_invariants`, `unenforced_invariants`, `rules.rules`, `platform_rules.rules`; keyed-by-`name` = `data_models`, `persistence_stores`; heuristic-by-`title` = `decisions.key_decisions`, `decisions.trade_offs`, `decisions.out_of_scope`. Everything else → textual hunk (suppress if > 500 tokens).
- Implement `glob_ledger(repo_root, base_ref)`: enumerate `.archie/changes/change_*.json`, union all claims new on the branch (records not present on base ref). Defensive parse; skip malformed records.
- Compute `retained_rules`: base-ref rules whose `id` is NOT in the diff's UPDATE/REMOVE set, pre-filtered by keyword overlap with changed invariant/decision titles (design §13 Q2 → relevance pre-filter, see §4).
- Malformed/missing JSON: catch `json.JSONDecodeError`; if branch blueprint unparseable → post marker comment "Cannot parse blueprint.json; manual review needed." then exit 0. (This path runs only after the secret guard, so it never fires on a fork.)

**Deliverable files:**
- CANONICAL `archie/standalone/intent_review.py` → COPY `npm-package/assets/intent_review.py`
- Edits: `archie/install.py` (+ `npm-package/assets/_install_pkg/install.py` mirror), `npm-package/bin/archie.mjs`, `scripts/verify_sync.py`

**Acceptance criteria:** `python3 scripts/verify_sync.py` exits 0 with the new files present. Given fixtures (`tests/fixtures/blueprint_domain_invariants.json`, `tests/fixtures/legacy_rules.json`), the diff emits correct REMOVE/UPDATE/ADD on `domain_invariants[]` and `rules[]` by id, and on `key_decisions[]` by title hash; reordered-but-unchanged arrays produce zero diffs; missing base file → all-ADD; missing/empty `rules.json` either side → empty list; malformed JSON handled without crash; `parse_event_context` extracts owner/repo/PR correctly from a sample event payload.
**Dependencies:** none.

### M2 — Anthropic structured-output call + finding schema
**Goal:** turn the assembled diff into structured *judgments* (the script already computed *what* changed).
**Tasks:**
- Implement `call_anthropic(blueprint_diff, rules_diff, ledger_claims, retained_rules, max_retries=3)`: urllib POST, headers `x-api-key`/`anthropic-version: 2023-06-01`/`content-type`, `claude-haiku-4-5`, `max_tokens: 4096`, `tool_use` with the `emit_findings` `input_schema` (§5). Read `block["input"]` directly (already a dict — no second `json.loads`). Retry on 429/500/502/503 with `min(2**attempt, 60)` backoff, honoring `Retry-After`.
- **Script overwrites deterministic fields:** after the model returns, for each finding the script replaces `diff_op`/`rule_id`/`layer` with the values from its own keyed diff (matched on the finding's referenced item), discarding the model's echo. A finding the model emits that references no real diff item is dropped.
- Build the prompt: system = "architecture reviewer; the diff op and which rule changed are GIVEN — judge whether it's a silent weakening / contradiction / behavior-violates-rule, and produce a cited because; because-or-suppress"; user = changed sections (with their deterministic `diff_op`/ids) + retained rules + ledger claims (token-bounded payload, §4).
- Enforce **because-or-suppress** post-hoc: drop any finding whose `because` is empty/blank before it reaches the comment (design §7, §9).
- **Severity sharpening via the explicit, conservative ledger join (critique medium gap, §4):** map ledger confidence/`reconstructed` onto a finding *only* when the join succeeds (claim `evidence_files` ∩ invariant `enforced_at` file paths AND keyword overlap above threshold). When the join fails, the finding still surfaces (a REMOVE is the corruption case) but **without** the confidence sharpener rather than guessing — guessing is exactly the because-theater the design forbids.

**Deliverable files:** same `intent_review.py` (CANONICAL → COPY).
**Acceptance criteria:** With a known REMOVE of a `domain_invariant`, the call returns a `silent_weakening` finding naming the invariant id with the script's deterministic `diff_op: REMOVE` and a cited `because`; a finding lacking a because is suppressed; a finding whose model-claimed op disagrees with the diff has the op overwritten from the diff; a join that fails emits the finding without confidence; wrong model id / missing key fails loudly (`RuntimeError`).
**Dependencies:** M1.

### M3 — PR comment upsert
**Goal:** one comment, deduped, FYI framing.
**Tasks:**
- Implement `post_or_update_comment(owner, repo, pr_number, findings)`: GET `/repos/{owner}/{repo}/issues/{pr_number}/comments`, find body containing `<!-- archie-intent-review -->`, PATCH if found else POST. (PR number = issue number for this endpoint; owner/repo/pr_number are passed in from `parse_event_context`, M1b.)
- Render body grouped by flag (Silent weakening / Contradiction / Behavior-violates-rule), each with affected rule/invariant, the deterministic `diff_op`, the cited `because`, and ledger confidence/provenance **only where the join succeeded** (design §7; example §Appendix A of design doc).
- Footer: "Archie surfaces; it doesn't block. Merge accepts the rule changes above as the new baseline."
- Empty/None states: zero findings AND there *was* a blueprint diff → minimal "No findings — blueprint changes consistent with retained rules." No blueprint diff at all → post nothing (return before any GitHub call), per §8 note 5.
- Exit code 0 always (non-blocking, design §9).

**Deliverable files:** same `intent_review.py` (CANONICAL → COPY).
**Acceptance criteria:** First run POSTs; second run on same PR PATCHes the same comment id (verified by marker); no-diff run posts nothing; findings render grouped with cited becauses.
**Dependencies:** M2.

### M4 — Workflow YAML (single canonical source)
**Goal:** the CI entry point that runs the script — authored **once**, consumed by the setup script.
**Tasks:**
- Author the static workflow (no template tokens): `on: pull_request` (`opened`, `synchronize`); `permissions: { pull-requests: write, contents: read }`; `actions/checkout@v4` with `fetch-depth: 0`; `actions/setup-python@v5` (`3.11`); an explicit base-ref fetch step; then `python3 .archie/intent_review.py`.
- **Explicit base-ref fetch (critique medium gap):** `fetch-depth: 0` fetches the PR head history but does **not** guarantee `origin/<base>` is resolvable. Add a step before the script:
  ```yaml
  - name: Fetch base ref
    run: git fetch --no-tags --depth=1 origin "${{ github.base_ref }}"
  ```
  The script then diffs against `origin/${GITHUB_BASE_REF}`. (Verify on a real Action run, not just locally — critique flags this as a CI-only failure mode.)
- Pass `ANTHROPIC_API_KEY` (secret) + `GITHUB_TOKEN` (built-in) as `env`. Use `pull_request` (NOT `pull_request_target`) — fork-PR secret limitation accepted for POC (design §8). The script's M1b guard exits 0 silently when the secret is empty.

**Deliverable files:**
- CANONICAL `archie/assets/workflows/archie-intent-review.yml` (new **`workflows/` plural** dir, distinct from the singular skill `workflow/` tree) → COPY `npm-package/assets/workflows/archie-intent-review.yml`. Installed to target `<repo>/.github/workflows/archie-intent-review.yml` **by the setup script only**.

**Acceptance criteria:** Valid GitHub workflow schema; the fetch step makes `origin/<base>` resolvable; running it on a PR invokes the script; fork PR run skips cleanly; `verify_sync.py` confirms the canonical↔asset `workflows/` byte mirror.
**Dependencies:** M1–M3 (script must exist to invoke). M4 is the **sole** definition of the YAML — M5 copies it, never re-authors it.

### M5 — `gh` setup script (copies the canonical YAML, no heredoc duplicate)
**Goal:** one-command, idempotent CI enablement, with a **single source of truth** for the workflow YAML.
**Tasks:**
- The setup script does prereq checks (git repo, origin remote, `gh` installed + authed, `.archie/blueprint.json` baseline), silent `ANTHROPIC_API_KEY` via stdin → `gh secret set` (client-side encrypted), then **installs the workflow by copying the already-present asset**, not by embedding a heredoc. The script resolves the YAML from one of two locations in priority order: (1) `.archie/workflows/archie-intent-review.yml` (the path the `npx` installer would have to place — see note below), else (2) the script's own sibling `setup-archie-intent-review.sh`-adjacent `workflows/archie-intent-review.yml` (present when run from a checked-out Archie asset bundle). This collapses the dual-source-of-truth problem the critique flagged: there is no second copy of the YAML body to drift.
- **Note on YAML availability:** because the `npx` installer copies `.py` scripts but the plan deliberately does **not** auto-inject `.github/workflows/`, the setup script needs the canonical `.yml` on disk to copy. Ship the canonical `.yml` alongside the setup script in the asset bundle (`archie/assets/workflows/` and its mirror) and have the setup script look there. If neither location resolves, the script `die`s with a clear message ("canonical workflow YAML not found — reinstall archie assets"), rather than falling back to an embedded copy.
- Actions-enabled probe (cosmetic warning only — `gh workflow list` can succeed even when Actions are disabled; treat its result as advisory), fork-PR caveat summary.

**Deliverable files:**
- CANONICAL `archie/assets/setup-archie-intent-review.sh` → COPY `npm-package/assets/setup-archie-intent-review.sh`. One-time installer helper (NOT copied into target `.archie/`; run from the repo root by the user).

**Acceptance criteria:** Re-runnable without cleanup (secret overwrite, workflow upsert); fails loudly if `.archie/blueprint.json` missing, `gh` unauthed, or canonical YAML unresolvable; secret never echoed to history; the installed `.github/workflows/archie-intent-review.yml` is **byte-identical** to `archie/assets/workflows/archie-intent-review.yml` (no heredoc divergence possible). `verify_sync.py` confirms the `.sh` canonical↔copy.
**Dependencies:** M4 (canonical YAML must exist to copy), M1–M3 (script the YAML invokes).

### M6 — Dogfood on Archie's own repo (instrumentation is a hard prerequisite)
**Goal:** prove the comment appears and is correct, isolating idea from upstream quality (design §12, §13 Q5).
**Tasks (sequenced — the instrumentation step gates M5's acceptance too, not just M6):**
- **Instrument Archie itself FIRST and commit the baseline to `main` before cutting the dogfood branch.** Run `/archie-deep-scan` to produce `.archie/blueprint.json` + `rules.json`; verify the baseline is non-trivia (real `domain_invariants`/`decisions`, not housekeeping) — a trivia blueprint invalidates the POC signal. **This `main` baseline is also what makes `setup-archie-intent-review.sh`'s `.archie/blueprint.json` prereq check pass; without it M5 cannot be exercised at all.** This step is independent code and can start in parallel with M1, but it MUST land on `main` before M5's acceptance run and before M6's branch.
- Cut a feature branch with a **deliberate, known** change whose fold should REMOVE/UPDATE a load-bearing invariant or contradict a retained rule (mirror the design's Acme worked example, Appendix A). Run `/archie-sync` so Phase 2 folds onto the branch; commit code + folded `blueprint.json`/`rules.json` + `.archie/changes/change_*.json`.
- Run `setup-archie-intent-review.sh`, push, open the PR, observe the comment.
- **Diagnose any bad review** per the interpretation rule (§7 below / design §12) BEFORE concluding the idea failed.

**Deliverable files:** committed `.archie/` baseline on `main`; a dogfood PR; a short results note (in PR description, NOT a tracked `.md`).
**Acceptance criteria:** Comment posts, is correct and cited, updates on re-push; at least one finding matches the planted intent; any miss is attributed to an idea-vs-upstream cause.
**Dependencies:** baseline-on-`main` (the instrumentation step) precedes M5's acceptance run AND M6; M6's PR step needs M1–M5 complete.

### M7 — Tests
**Goal:** ship-ready test coverage. (Wiring + checker edits moved to M1a; M7 is now tests only.)
**Tasks:**
- Unit tests (`tests/test_intent_review.py`): `keyed_diff` (REMOVE/UPDATE/ADD, title-hash fallback, reorder no-op), `fetch_base_file` (missing/malformed, missing-rules→empty), `glob_ledger` (multi-`change_*.json` union, skip malformed, dedup by claim id), `parse_event_context` (owner/repo split, PR number parse, missing-`pull_request` clean exit), the deterministic-field-overwrite logic, the conservative ledger-join (match success annotates, join failure surfaces-without-confidence), comment-body rendering, and the because-or-suppress filter.
- Mock urllib for the Anthropic + GitHub calls (no network in tests).
- **Parallelization caveat (sequencing fix):** only the M1 diff/glob/event-parse tests are writable from the start. Tests for `call_anthropic` (M2) and `post_or_update_comment` (M3) can't be written until those signatures are fixed — schedule them after M2/M3 respectively, not "from M1."

**Deliverable files:** `tests/test_intent_review.py`.
**Acceptance criteria:** `pytest tests/ -v` green.
**Dependencies:** M1 (for M1-scope tests); M2/M3 (for their respective tests).

**Suggested order:** M1 (incl. M1a wiring + checker, M1b core) → M2 → M3 → M4 → M5 → M6. The instrumentation step of M6 (deep-scan + sync baseline on `main`) starts in parallel with M1 but must merge to `main` before M5's acceptance run. M7 tests track their milestone (M1 tests with M1, M2/M3 tests after those land). **Any later YAML change touches only M4's canonical asset — M5 copies it, so there is exactly one place to edit.**

---

## 4. Blueprint/rules diff algorithm

Deterministic, zero-dependency. The script computes `diff_op` and keyed ids; the model never re-derives them (§2).

**Base-ref fetch:** the workflow runs `git fetch --no-tags --depth=1 origin "$GITHUB_BASE_REF"` (M4) so `origin/<base>` resolves. The script then runs `git show origin/<base_ref>:.archie/blueprint.json` (and `rules.json`, `platform_rules.json`) via `subprocess.run([...], timeout=10)`, returning `(exists, dict|None, error)`. `returncode != 0` with "does not exist"/"Invalid object" → file absent on base (new on branch) → all-ADD. Missing/empty `rules.json` either side → empty list. JSON parse failure on the branch blueprint → "cannot parse" marker comment, exit 0. Branch versions read directly from disk (checkout already placed them). Use `origin/<base_ref>`, never local `HEAD`/`main`.

**Keyed semantic diff** (preferred — high precision):
```
For each keyed section:
  base_by_key   = { item[id_field] or _hash_title(item[title_field]): item }
  branch_by_key = { ... same ... }
  REMOVE = keys in base not in branch
  UPDATE = keys in both whose dicts differ (emit fields_changed)
  ADD    = keys in branch not in base
```
- **Keyed by `id`:** `domain_invariants[]`, `derived_invariants[]`, `unenforced_invariants[]`, `rules.rules[]`, `platform_rules.rules[]`.
- **Keyed by `name`:** `data_models[]`, `persistence_stores[]`.
- **Heuristic by `title` hash** (no id field): `decisions.key_decisions[]`, `decisions.trade_offs[]`, `decisions.out_of_scope[]`. Caveat: a RENAME reads as REMOVE+ADD, not UPDATE — note this in the finding rendering so the model isn't misled.
- **`_hash_title()`** = `"title_" + md5(title)[:8]`; also the fallback when a `domain_invariant` lacks `id` (older blueprints).

**Textual fallback:** `components[]`, `communication[]`, `architecture_diagram`, `architecture_rules`, and `decisions.architectural_style` (a single dict, not an array) → send the raw `git diff` hunk **only if < 500 tokens**; suppress larger hunks (too noisy for semantic review).

**Token bounding** (design §13 Q2 → relevance pre-filter): send only sections WITH changes + the changed items themselves (not the whole 50–150 KB blueprint) + `retained_rules` pre-filtered to those whose `keywords`/`description` overlap the changed invariant/decision titles + the unioned ledger claims. Target payload ~5 KB / ~5000 tokens.

**Severity sharpening — the explicit, conservative ledger join (critique medium gap):** a domain_invariant has `enforced_at[]` (file:line) and `keywords[]`; a ledger claim has `evidence_files[]` (file paths) and a free-text `statement`. There is no shared id, so the join is defined as:
```
match(diff_item, claim) is TRUE iff
    file_set(claim.evidence_files) ∩ file_set(diff_item.enforced_at paths)  is non-empty
    AND  keyword_overlap(claim.statement tokens, diff_item.keywords)  >= THRESHOLD
```
On match, pull the claim's `confidence` + `reconstructed` and apply the sharpener (e.g. REMOVE of a `domain_invariant` backed by `confidence: low, reconstructed: true` = highest severity, design §6). **On no match, the finding still surfaces but carries no confidence annotation** — an unmatched REMOVE is the corruption case and must be shown; it simply loses the ledger-confidence sharpener rather than receiving a guessed one. Guessing an attribution is the because-theater the design forbids.

**Edge cases:** rules files optional → missing = empty list. Both rule sources (`rules.json` + `platform_rules.json`) diffed.

---

## 5. Finding JSON schema (model output) + flag mapping

The model is forced to call `emit_findings` (Haiku 4.5 has no `output_config.format`; must use `tool_use` + `input_schema`). The model **judges**; the script **owns** `diff_op`/`rule_id`/`layer` and overwrites them post-call (§2):

```json
{
  "name": "emit_findings",
  "description": "Emit structured review findings. The diff op and which rule changed are GIVEN to you per item — judge the TYPE and produce a cited BECAUSE. Because-or-suppress: omit any finding lacking a verifiable cited because.",
  "input_schema": {
    "type": "object",
    "properties": {
      "findings": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "type":         { "type": "string", "enum": ["silent_weakening", "contradiction", "behavior_violates_rule"] },
            "rule_name":    { "type": "string", "description": "Which retained rule/invariant this is about." },
            "what_changed": { "type": "string" },
            "because":      { "type": "string", "description": "Verifiable, cited rationale drawn from the two texts. Empty/uncited => finding is dropped." },
            "diff_op":      { "type": "string", "enum": ["REMOVE","UPDATE","ADD","CONFLICT"], "description": "ECHO of the given op; the script overwrites this from its deterministic diff." },
            "rule_id":      { "type": "string", "description": "ECHO of the given id; the script overwrites this." },
            "layer":        { "type": "integer", "enum": [1,2], "description": "ECHO of the given layer; the script overwrites this." }
          },
          "required": ["type", "rule_name", "what_changed", "because"]
        }
      },
      "severity_notes": { "type": "array" }
    },
    "required": ["findings", "severity_notes"]
  }
}
```

Note `diff_op`/`rule_id`/`layer` are **not required** of the model and are **echo-only** — the script overwrites each from its own keyed diff before rendering, and drops any finding that references no real diff item. This removes the disagreement-with-no-reconciliation-rule problem.

**Mapping to the three flags (design §6) and Layers — all computed by the script:**

| `type` | Detected from (deterministic) | Layer (script-set) | Diff source |
|---|---|---|---|
| `silent_weakening` | REMOVE/UPDATE retiring or softening a `domain_invariant` / `decisions.key_decisions` | **Layer 1** (rule-vs-rule) | keyed diff of `domain_invariants[]` / `decisions` |
| `contradiction` | ADD/UPDATE conflicting with a *retained* rule | **Layer 1** (text-vs-text) | `rules.json` diff vs retained rules |
| `behavior_violates_rule` | a **descriptive** claim/blueprint change implying a retained rule is now broken | **Layer 2** (behavior-vs-rule) | descriptive `blueprint.json` diff + descriptive ledger claims (`behavior|structure|dataflow|data|tech|reference`) |

The ledger `kind` split supplies Layer 1 vs Layer 2: advisory kinds (`decision|pitfall|rule|guideline`) → Layer 1; descriptive kinds → Layer 2 (design §3). **Layer 3 (raw code) is out of scope.** **Because-or-suppress** is enforced twice: the prompt instructs it, and `intent_review.py` drops any finding with empty/blank `because` post-call (design §7).

---

## 6. Setup script + verify_sync edits (verbatim, runnable)

> **Single source of truth for the YAML:** the setup script **copies** the canonical `archie/assets/workflows/archie-intent-review.yml` (resolved on disk) — it does **not** embed a heredoc copy. This eliminates the silent-divergence risk the critique identified.

> **Fork-PR / secret caveat (call-out):** uses the `pull_request` event (non-blocking FYI). Per GitHub's security model, **fork PRs cannot access repository secrets** — so `ANTHROPIC_API_KEY` is unavailable and the Action skips silently *before any GitHub write* on external contributions. Accepted for the POC. Switching to `pull_request_target` to cover forks is a deliberate security tradeoff, explicitly out of scope.

### The setup script (`archie/assets/setup-archie-intent-review.sh`)

```bash
#!/usr/bin/env bash
# setup-archie-intent-review.sh
#
# Idempotent setup for the Archie Intent Review GitHub Action.
# Prereq checks, secure secret setup, workflow install (copies the canonical
# YAML — no embedded duplicate), Actions probe, fork-PR caveat.
#
# Usage: bash setup-archie-intent-review.sh
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-.}"
WORKFLOW_FILE="${REPO_ROOT}/.github/workflows/archie-intent-review.yml"

log_info()    { echo -e "${BLUE}i ${NC}$*"; }
log_success() { echo -e "${GREEN}OK ${NC}$*"; }
log_warn()    { echo -e "${YELLOW}! ${NC}$*"; }
log_error()   { echo -e "${RED}x ${NC}$*"; }
die() { log_error "$1"; exit 1; }

# Resolve the canonical workflow YAML (single source of truth). Priority:
#  1. .archie/workflows/  (if the npx bundle ever places it there)
#  2. <script dir>/workflows/  (running from a checked-out asset bundle)
resolve_workflow_src() {
    local candidates=(
        "${REPO_ROOT}/.archie/workflows/archie-intent-review.yml"
        "${SCRIPT_DIR}/workflows/archie-intent-review.yml"
    )
    for c in "${candidates[@]}"; do
        if [ -f "$c" ]; then printf '%s\n' "$c"; return 0; fi
    done
    return 1
}

# ===== SECTION 1: PREREQUISITES =====
log_info "Checking prerequisites..."

git rev-parse --git-dir >/dev/null 2>&1 || die "Not inside a git repository. Run from the repo root."
log_success "Inside a git repository"

git config --get remote.origin.url >/dev/null 2>&1 || die "No 'origin' remote found."
log_success "Git remote 'origin' found"

command -v gh >/dev/null 2>&1 || die "gh CLI not found. Install from https://github.com/cli/cli or 'brew install gh'."
log_success "gh CLI is installed ($(gh --version | head -1))"

gh auth status >/dev/null 2>&1 || die "gh CLI not authenticated. Run 'gh auth login' first."
GITHUB_ACCOUNT="$(gh api user --jq .login)"
log_success "gh authenticated as ${GITHUB_ACCOUNT}"

[ -f "${REPO_ROOT}/.archie/blueprint.json" ] || die ".archie/blueprint.json not found. Run '/archie-deep-scan' first to establish the baseline."
log_success ".archie/blueprint.json baseline exists"

WORKFLOW_SRC="$(resolve_workflow_src)" || die "Canonical workflow YAML not found (looked in .archie/workflows/ and ${SCRIPT_DIR}/workflows/). Reinstall archie assets."
log_success "Canonical workflow YAML resolved: ${WORKFLOW_SRC}"

# ===== SECTION 2: SECRET SETUP =====
log_info "Setting up ANTHROPIC_API_KEY secret (available to GitHub Actions on this repo)..."
printf 'Enter your ANTHROPIC_API_KEY (will not be displayed): '
read -rs ANTHROPIC_API_KEY
echo ""
[ -n "$ANTHROPIC_API_KEY" ] || die "ANTHROPIC_API_KEY cannot be empty."

printf '%s' "$ANTHROPIC_API_KEY" | gh secret set ANTHROPIC_API_KEY
unset ANTHROPIC_API_KEY
log_success "ANTHROPIC_API_KEY secret set (stored encrypted on GitHub)"

# ===== SECTION 3: WORKFLOW INSTALL (copy canonical, no heredoc) =====
log_info "Installing workflow file..."
mkdir -p "$(dirname "$WORKFLOW_FILE")"
cp "$WORKFLOW_SRC" "$WORKFLOW_FILE"
log_success "Workflow installed at ${WORKFLOW_FILE} (byte-identical to canonical)"

# ===== SECTION 4: ACTIONS ENABLEMENT PROBE (advisory) =====
log_info "Probing GitHub Actions (advisory only)..."
REPO_SLUG="$(git config --get remote.origin.url | sed 's|.*github.com[:/]||; s|\.git$||')"
if gh workflow list -R "$REPO_SLUG" >/dev/null 2>&1; then
    log_success "Actions appear enabled (probe is advisory; verify in repo settings if unsure)"
else
    log_warn "Could not verify Actions status — you may need to enable Actions on GitHub"
fi

# ===== SECTION 5: SUMMARY & CAVEATS =====
log_success "Setup complete."
echo ""
echo "Next steps:"
echo "  1. Commit .github/workflows/archie-intent-review.yml"
echo "  2. Push and open a PR"
echo "  3. The Action posts an FYI comment on the PR"
echo ""
echo -e "${YELLOW}Fork PR limitation:${NC}"
echo "  - Uses the 'pull_request' event (non-blocking FYI)."
echo "  - Fork PRs cannot access repo secrets; the Action skips silently on them."
echo "  - To cover fork PRs, 'pull_request_target' is a security tradeoff (out of scope)."
echo ""
log_info "To rotate the key later: gh secret set ANTHROPIC_API_KEY"
log_info "Design doc: docs/archie-intent-review-design.md"
```

> The setup script ships **alongside** `workflows/archie-intent-review.yml` in the asset bundle so `resolve_workflow_src` finds it. The bundle layout under `archie/assets/` (and its `npm-package/assets/` mirror) is: `setup-archie-intent-review.sh` + `workflows/archie-intent-review.yml`.

### The canonical workflow YAML (`archie/assets/workflows/archie-intent-review.yml`)

```yaml
name: Archie Intent Review
on:
  pull_request:
    types: [opened, synchronize]

permissions:
  pull-requests: write
  contents: read

jobs:
  intent-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Fetch base ref
        run: git fetch --no-tags --depth=1 origin "${{ github.base_ref }}"

      - name: Run Archie Intent Review
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: python3 .archie/intent_review.py
```

### verify_sync.py edits (three concrete checks — none exist today)

The current `verify_sync.py` only globs `*.py`/`*.json` for content equality, mirrors the **singular** `workflow/` tree, and has **no allowlist**. To make the byte-identical guarantee real, M1a adds, inside `check_archie_asset_mirrors` (or a new sibling function called from `main`):

1. **`workflows/` (plural) byte-mirror** — parallel to the existing singular-`workflow/` block (lines ~173–204): compare every file under `archie/assets/workflows/` against `npm-package/assets/workflows/`, flagging missing, stale, and content-differing files.
2. **`.yml` content check** — the new mirror must compare `.yml` bytes (the main loop only does `.py`/`.json`); the plural-dir block above handles this by globbing all files, not just `*.py`/`*.json`.
3. **Setup `.sh` canonical→copy** — add a direct byte check `archie/assets/setup-archie-intent-review.sh` ↔ `npm-package/assets/setup-archie-intent-review.sh` (the `.sh` is not covered by any existing glob), mirroring the `archieignore.default`/`gitignore.default` pattern already in `check_archie_asset_mirrors` (lines ~165–171).

These are explicit code edits in M1a, not afterthoughts — without them the `.yml` mirror and the `.sh` have **zero** sync enforcement and will silently drift.

---

## 7. Testing & dogfood strategy

**Unit (no network, M7):** mock urllib for both Anthropic and GitHub. Cover `keyed_diff` (REMOVE/UPDATE/ADD + title-hash fallback + reorder-is-no-op), `fetch_base_file` (missing → all-ADD, malformed → "cannot parse", missing-rules → empty), `glob_ledger` (multi-file union, skip malformed, dedup by claim id), `parse_event_context` (owner/repo split, PR number, missing-`pull_request` clean exit), the deterministic-field-overwrite, the conservative ledger-join (match annotates, no-match surfaces-without-confidence), comment-body rendering grouped by flag, and the because-or-suppress filter.

**Instrument Archie itself first (design §12, §13 Q5 → instrument in-repo, no separate fixture):**
1. Run `/archie-deep-scan` on Archie's own repo; commit `.archie/blueprint.json` + `rules.json` to `main`. **Verify the baseline is substantive** — real `domain_invariants` and `decisions`, not housekeeping trivia. A trivia baseline must be fixed before dogfooding, or the POC signal is meaningless. **This baseline-on-`main` also unblocks the `setup-archie-intent-review.sh` prereq check (M5 acceptance) — it is a hard prerequisite for M5, not only M6.**
2. On a branch, make a planted change mirroring the design's Appendix A (e.g. fold UPDATEs a load-bearing invariant to "allow unscoped X for performance," plus a descriptive claim contradicting a retained `decision`). Run `/archie-sync` (Phase 2 folds on-branch), commit code + folded blueprint/rules + `change_*.json`.
3. Run the setup script, push, open the PR, read the comment.

**Interpreting a bad review (design §12 interpretation rule — non-negotiable):** the POC tests three things at once — the *review idea*, *sync's fold quality*, and *the blueprint's quality*. When a review is wrong or empty, **first diagnose whether the idea was wrong OR the upstream input (claim/baseline) was wrong** before concluding anything about the concept. Checklist: (a) Did the baseline actually contain the invariant the review should have caught? If not → blueprint-quality problem, not idea. (b) Did sync fold the planted change with an eligible claim? If not → sync-quality problem. (c) Only if both upstream stages produced correct inputs and the review still missed/misfired is it an *idea* signal. Dogfooding on Archie's own repo (where you control what sync should produce) is what isolates the idea from upstream quality.

---

## 8. Risks, mitigations & resolved open questions

### Decisions this plan commits to (critique-flagged ambiguities, now resolved)
- **Single owner of `.github/workflows/archie-intent-review.yml`:** the **setup script**, exclusively. The `npx` installer does **NOT** auto-inject the workflow (it can't set the Actions secret anyway, and a double-writer would clobber a user's file on every `npx` run). No `_copy_github_workflows()` is added to `install.py` — this also removes the need to mirror an `install.py` workflow-injection change.
- **Single source of truth for the YAML:** the canonical `archie/assets/workflows/archie-intent-review.yml`. The setup script copies it; there is no heredoc duplicate, so no equivalence test is needed (the dual-source problem is designed out, not tested around).
- **No allowlist in `verify_sync.py`:** `intent_review.py` is added to `archie.mjs` + both `install.py` copies and installs to `.archie/` everywhere. Accepted.

### Risks & mitigations
| Risk | Mitigation |
|---|---|
| `latest.json` read as single source → miss earlier syncs | Glob ALL `.archie/changes/change_*.json`; union claims (design §8 note 2). |
| Whole 50–150 KB blueprint blows token budget/cost | Send only changed sections + changed items + relevance-filtered retained rules; ~5 KB payload (§4). |
| `key_decisions`/`trade_offs` have no `id` → RENAME reads as REMOVE+ADD | Title-hash keying; flag this limitation in finding text. |
| Model re-derives `diff_op`/ids and disagrees with the diff | Script computes these deterministically and overwrites the model's echo (§2, §5). |
| Wrong ledger attribution = because-theater | Conservative join (file-overlap AND keyword threshold); no match → surface without confidence, never guess (§4). |
| Because-theater (plausible-but-wrong cited prose) | Structured inputs only (Layer 3 deferred); because-or-suppress in prompt AND post-call (design §9). |
| Cry-wolf death spiral | Non-blocking FYI, exit 0 always, minimal/no comment on empty states. |
| Fork PR has no secret → confusing failure / failed write | Script early-exits 0 when `ANTHROPIC_API_KEY` empty, **before any GitHub call** (so the read-only fork `GITHUB_TOKEN` is never exercised). |
| `origin/<base>` unresolvable in CI despite `fetch-depth: 0` | Explicit `git fetch --no-tags origin "$github.base_ref"` step in the workflow (M4, §6); verify on a real Action run. |
| Missing/empty `rules.json` on either side | Treated as `{rules: []}`, not an error (§2, §4). |
| `max_tokens` truncates multi-finding output | `max_tokens: 4096` (Acme example alone has 4 prose findings). |
| `verify_sync.py` blocks interim commits | Wiring + the three checker edits land in **M1a**, before the new files exist standalone — repo never sync-fails. |
| Two script-list sources (`archie.mjs` + `install.py` + its mirror) | Add to all three in M1a; note a future single-source refactor. |

### Design §13 open questions — resolved
1. **Diff granularity** → semantic-keyed where keys exist (`id`/`name`), title-hash for `key_decisions`/`trade_offs`, textual hunks (<500 tok) otherwise.
2. **Which retained rules to feed** → relevance pre-filter on keyword/description overlap with changed titles.
3. **Comment marker** → hidden HTML comment `<!-- archie-intent-review -->`, clean upsert.
4. **Failure/auth modes** → missing key/fork PR → skip silently, exit 0 **before any GitHub write**; API error → retry then `RuntimeError`; malformed branch JSON → "cannot parse" marker comment.
5. **Dogfood prerequisite** → instrument Archie's own repo (deep-scan + sync); baseline-on-`main` is a hard prerequisite for M5 acceptance and M6.
6. **Where the files live** → `archie/standalone/intent_review.py` → `npm-package/assets/`; workflow in new `archie/assets/workflows/` (plural) → `npm-package/assets/workflows/`; setup script `archie/assets/setup-archie-intent-review.sh` → `npm-package/assets/`; **no** `manifest_data.py:COMMANDS` entry, **no** SKILL.md, **no** `.github/workflows` injection by the `npx` installer.

### Genuinely still open (flag for implementer)
- **Are `derived_invariants` / `unenforced_invariants` keyed-diffed like `domain_invariants`, or sent textually?** Both carry `id` (keyable), but `unenforced_invariants` are gaps not stated law — recommend: keyed-diff `derived_invariants` (reasoned law), treat `unenforced_invariants` as advisory (don't raise silent-weakening on its removal). Confirm during M2 prompt tuning.
- **Does a pure `key_decision.rationale` UPDATE (title unchanged) warrant a finding** without a backing ledger claim? Recommend surfacing only when a ledger claim corroborates, to keep precision high. Validate in M6.
- **`fold_guardrail` sub-section protection** — the guardrail only checks top-level blueprint keys, not nested arrays. A fold could drop the entire `domain_invariants[]` *contents* without tripping it. The review *catches* this (REMOVE of every invariant id), but note the on-branch guardrail won't.

---

## 9. Out of scope (carried over from design §10)

- **Layer 3** — raw source `git diff` read against invariants (the because-theater zone; gated behind an eval harness before it may comment, let alone block).
- **Blocking gate** — a CI status check that can fail the PR.
- **Auto violation-vs-evolution categorization** — the human decides (avoids laundering a bug into law).
- **The eval / observability plane** (Langfuse-style: replay historical PRs, score precision/false-evolution, store traces; reuses `archie/benchmark/` + Supabase). Prerequisite for any future blocking mode.
- **The setup webapp + GitHub App + backend** (server-side execution, "connect repo + GitHub + Claude key + go").
- **BYO-key onboarding flow.**
- **`npx`-installer injection of `.github/workflows/`** — deliberately excluded; the setup script is the sole workflow installer (§8 decision).
- **Post-merge fold automation** — unneeded; the fold already happened on the branch, so git's "merge = acceptance" handles baseline evolution automatically.

Canonical deliverable paths (for the implementer): `archie/standalone/intent_review.py`, `archie/assets/workflows/archie-intent-review.yml`, `archie/assets/setup-archie-intent-review.sh`, `tests/test_intent_review.py`; edits to `archie/install.py`, `npm-package/assets/_install_pkg/install.py`, `npm-package/bin/archie.mjs`, `scripts/verify_sync.py`; byte-copies under `npm-package/assets/` (`intent_review.py`, `workflows/archie-intent-review.yml`, `setup-archie-intent-review.sh`).
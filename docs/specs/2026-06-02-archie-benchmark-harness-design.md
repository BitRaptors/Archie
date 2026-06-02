# Archie Benchmark Harness — Design

**Date:** 2026-06-02
**Status:** Approved (design) — pending implementation plan
**Scope:** Internal benchmarking tool that measures Archie's effectiveness by running the *same* task with and without Archie's generated context, capturing efficiency + quality metrics, and storing results in Supabase. Website display is a **separate follow-up spec**.

---

## 1. Purpose

Prove (or disprove) Archie's value with hard numbers. For a given repository and a given coding task, run an identical headless Claude Code session in two arms:

- **control** — repo without any Archie artifacts.
- **treatment** — repo with the full Archie experience: root `CLAUDE.md` / `AGENTS.md`, per-folder `CLAUDE.md` context files, rules, **and** the real-time enforcement hooks.

For each arm we capture **tool calls, tokens, cost, wall-clock duration** (efficiency) **and a blind judge-Claude quality score** (correctness/completeness/conventions). Measuring cost alone is misleading — an agent that does nothing is cheapest — so quality is a first-class output.

The benchmark is an **internal tool** (the team runs it on controlled repos to produce marketing numbers). The Supabase write key lives in a local `.env` / CI secret; results are written directly. No end-user consent/anonymization layer is in scope.

---

## 2. Key Decisions (resolved during brainstorming)

| Decision | Choice |
|---|---|
| What we measure | Efficiency (tool calls, tokens, cost, time) **+ quality** (judge score) |
| Execution engine | **Claude Code headless** — `claude -p ... --output-format stream-json` |
| Treatment contents | **Everything**: context docs + rules + enforcement hooks |
| Arm source | **Branch-based**: a treatment branch (with Archie files) and a control branch (without). Tool can prep both from a plain repo. |
| Quality measurement | **Blind judge-Claude** scored against a rubric (no pre-written tests required) |
| Repetitions | **Configurable, default 3** per arm (average + spread) |
| Tool scope | **Internal** — direct Supabase write via service key |
| Website | **Out of scope** — separate follow-up spec |
| Deep-scan prep (when repo has no Archie yet) | **Semi-automatic**: tool prepares branch + installs Archie, then pauses for the user to run `/archie-deep-scan` interactively, then resumes |
| Config format | **JSON** (zero-dep; YAML/TOML rejected — Archie targets Python 3.9+, stdlib only) |

**Critical invariant:** the deep-scan that *generates* the treatment artifacts is **never** counted in the measured metrics. It runs before measurement, on a separate branch, and its cost is logged separately as `prep_cost`.

---

## 3. Architecture

New **internal** Python package (zero-dep stdlib; **not** copied into the npm package, **not** a `standalone/` script):

```
archie/benchmark/
  __init__.py
  cli.py          # entry: `python3 -m archie.benchmark {auto,run,prep} <args>`
  config.py       # JSON config read + validation
  isolation.py    # git worktree lifecycle: add / cwd / cleanup / prune
  runner.py       # one `claude -p` run in a worktree, stream-json
  metrics.py      # stream-json parse -> {tool_calls, tool_breakdown, tokens, cost, duration, turns, completed}
  judge.py        # blind judge-Claude call -> rubric scores (forced JSON)
  diff.py         # `git diff` + untracked files for an arm
  store.py        # Supabase PostgREST write (urllib, service key from .env) + offline fallback
  orchestrator.py # full run: prep -> (arm x repetition) matrix -> aggregate -> store -> summary
  schema.sql      # versioned Supabase DDL (tables + summary view)
tests/benchmark/  # pytest; claude/supabase/git external calls mocked
```

Each file has a single responsibility and is independently testable. `runner`, `judge`, and `store` wrap the only external side effects (claude CLI, HTTP) so they mock cleanly. `cli.py` is a thin arg-parse + `orchestrator` call.

---

## 4. Config format (JSON)

One file describes one benchmark case:

```json
{
  "name": "bedtime-add-sleep-timer",
  "repo": "/Users/csacsi/DEV/BedtimeApp",
  "task_prompt": "Add a sleep timer feature: a setting that stops audio playback after a chosen duration. Wire it into the existing player and settings UI.",
  "model": "claude-sonnet-4-6",
  "repetitions": 3,
  "branches": {
    "treatment": "archie-bench/with-archie",
    "control":   "archie-bench/no-archie"
  },
  "judge": {
    "model": "claude-opus-4-8",
    "rubric": ["correctness", "completeness", "follows_conventions", "no_regressions"]
  },
  "timeout_seconds": 3600
}
```

Rules:

- **`task_prompt` is byte-for-byte identical** across both arms and **never mentions Archie**. The presence of context files is the only difference.
- `model` is the same for both arms (fixed, so the model is not a confounding variable).
- `branches`: if both exist → start from them. If missing, the CLI offers prep (§6).
- `judge.rubric`: customizable; each axis scored 1–10 plus a short justification.
- `timeout_seconds`: hard cap per `claude -p` run (default **3600**), overridable.

---

## 5. Data flow — one sample (one arm, one repetition)

1. **Worktree:** `git worktree add <repo>/.archie/benchmark/worktrees/<branch>-<rep> <branch>` → fresh isolated checkout. Every repetition gets its own worktree (Claude mutates files; worktrees are not shared).
2. **Run** in the worktree (`cwd=<worktree>`):
   ```
   claude -p "<task_prompt>" \
     --model <model> \
     --output-format stream-json --verbose \
     --permission-mode acceptEdits
   ```
   Both arms get **identical** harness flags. The treatment arm picks up Archie hooks from the repo's `.claude/settings` and auto-loads `CLAUDE.md`; the control arm has neither — that is the measured difference.
3. **Metrics** (`metrics.py`) from the stream-json events:
   - **tool_calls**: count of `tool_use` blocks in `assistant` messages, **also broken down by type** (Edit / Read / Bash / …).
   - **tokens**: from the final `result` event `usage`: `input`, `output`, `cache_read`, `cache_creation`.
   - **cost**: `result.total_cost_usd`.
   - **duration**: `result.duration_ms` (plus our own wall-clock as a sanity check).
   - **turns**: `result.num_turns`.
   - **completed**: `result.subtype == "success"` (not timeout/error).
4. **Diff:** in the worktree, `git add -A && git diff --cached` → full change-set text, stored for the judge (kept after worktree removal).
5. **Cleanup:** `git worktree remove --force` (in `finally`).

Raw stream-json optionally saved to `.archie/benchmark/<name>/<branch>-<rep>.jsonl` for debugging.

---

## 6. `auto` command — from a plain repo to finished numbers

Entry: `python3 -m archie.benchmark auto <repo-path> --prompt "..."` (or task from a config file). The tool drives the whole flow:

1. **Check:** repo is a clean git working tree (else stop, so uncommitted state never contaminates measurement). Record the base commit/branch.
2. **Control branch** (`archie-bench/no-archie`): branch off the base. If Archie files exist (`CLAUDE.md`, `AGENTS.md`, `.claude/`, `.archie/`, per-folder `CLAUDE.md`s), **delete and commit** them. If absent, leave untouched.
3. **Treatment branch** (`archie-bench/with-archie`): branch off the base.
   - If Archie files already exist → use as-is.
   - If absent → **semi-automatic prep**: the tool runs `npx @bitraptors/archie <repo>` (installs scripts + commands), then **pauses** with instructions: *"Open Claude Code on this worktree, run `/archie-deep-scan`, commit the results, then press Enter."* The user runs it interactively (more robust than headless deep-scan), returns, presses Enter. The tool **verifies** the Archie files now exist (fails clearly if not) and commits anything uncommitted.
   - The deep-scan cost is **excluded from measurement**. Because prep is interactive (semi-automatic), the tool cannot directly meter its token cost; `prep_cost_usd` is **best-effort and nullable** — if `.archie/telemetry/` from the deep-scan run is present, the tool reads duration/cost from it, otherwise the field stays null. The point is only that prep is never folded into sample metrics.
4. **Benchmark:** the `run` flow on both branches (default 3 repetitions, blind judge).
5. **Aggregate + Supabase write + console summary.**

Idempotent branch prep: if a `archie-bench/*` branch already exists, the tool asks (reuse / regenerate / abort) — never silently overwrites.

---

## 7. Blind judge-Claude

- The judge is a **separate `claude -p` call** with fresh context (does not see the benchmark runs or Archie).
- Input: the `task_prompt` + both arms' diffs labeled **"Variant A" / "Variant B" in a randomized order** (the tool records the mapping). The judge cannot tell which is the Archie arm → no bias.
- Randomization uses a **fixed seed** derived from the sample id (no time/`random`-without-seed dependence), stored as `judge_seed` for reproducibility.
- Output is **forced JSON**: per-rubric-axis score 1–10 + short justification + overall score. `judge.py` validates; on malformed JSON it retries **once**.
- Scoring is **pairwise per repetition**: each (A, B) pair → one judge call (N calls, not N²). Per-arm judge scores are averaged.
- `judge.model` defaults to Opus (stronger judge), overridable in config.

---

## 8. Supabase schema

Two tables in the existing project, written directly via PostgREST with the **service key** (`.env`: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`).

**`benchmark_runs`** — one row per benchmark run:

```
id              uuid pk (default gen_random_uuid())
name            text          -- config.name
repo_name       text          -- repo basename only (not full path)
task_prompt     text
model           text
judge_model     text
repetitions     int
git_base_commit text          -- base commit (reproducibility)
prep_cost_usd   numeric null  -- deep-scan prep cost, SEPARATE & best-effort (null if not metered)
archie_version  text
created_at      timestamptz default now()
```

**`benchmark_samples`** — one row per (arm × repetition):

```
id                    uuid pk
run_id                uuid fk -> benchmark_runs.id
arm                   text          -- 'control' | 'treatment'
repetition            int
tool_calls            int
tool_breakdown        jsonb         -- {"Edit":4,"Read":9,"Bash":2,...}
input_tokens          int
output_tokens         int
cache_read_tokens     int
cache_creation_tokens int
cost_usd              numeric
duration_ms           int
num_turns             int
completed             bool          -- result.subtype == success
quality_score         numeric null  -- judge overall (0–10)
quality_detail        jsonb null    -- per-axis breakdown + justification
judge_seed            int
created_at            timestamptz default now()
```

- Aggregates (per-arm mean/spread/savings-%) are **not** stored twice — a DB **view** `benchmark_summary` computes them from samples; the website (separate spec) reads the view.
- DDL ships as versioned `archie/benchmark/schema.sql` (run against Supabase manually / in CI).
- `store.py`: if `.env` keys are missing → **does not crash**; saves locally to `.archie/benchmark/<name>/results.json` and warns (offline mode).

---

## 9. Error handling, isolation safety, cleanup

- **Worktree-leak protection:** every worktree is created and removed in `try/finally` (`git worktree remove --force`). `git worktree prune` at run start and end. Temp root is a known location (`<repo>/.archie/benchmark/worktrees/`) so leftovers are cleanable on restart.
- **One failed sample does not sink the run:** if a `claude -p` times out/errors, that sample is recorded with `completed=false` and partial metrics; others continue. The aggregate reports how many samples dropped.
- **Fairness guards:** the tool verifies (a) `task_prompt` is byte-identical across arms, (b) `model` and harness flags are identical, (c) both branches descend from the same `git_base_commit`. Any violation → stop, do not write noisy data.
- **Prep separation:** deep-scan prep happens entirely before measurement, on a separate branch; measured `claude -p` runs start from fresh worktrees where Archie files are already committed — prep tokens/time never leak into sample metrics.
- **Secrets:** `.env` is never logged; only `repo_name` (basename) goes to the DB, not the full path.

---

## 10. Testing

`tests/benchmark/`, pytest, all external calls mocked (no real `claude`/Supabase in tests):

- `metrics.py`: fixed stream-json fixtures (success, timeout, tool-heavy, zero-tool) → correct tool count, token sums, completed flag.
- `config.py`: valid/invalid configs, missing fields, identical-prompt invariant.
- `isolation.py`: worktree add/remove on a throwaway temp git repo (may run real git, fast).
- `diff.py`: known change → expected diff text, untracked files included.
- `judge.py`: mocked judge response parse, malformed JSON → 1 retry, seed determinism.
- `store.py`: mocked HTTP → correct payload shape; missing `.env` → offline fallback file.
- `orchestrator.py`: end-to-end with mocks (fake runner+judge+store) → matrix and aggregation correct; a failed sample does not sink the run.

**Edge cases covered:** empty diff (Claude did nothing) → `completed=true` but low quality; mid-run timeout; both arms identical; missing Supabase key; pre-existing benchmark branch; non-clean working tree; missing Archie files after deep-scan prep (verification fails).

---

## 11. Out of scope (explicit)

- Website / dashboard display of results — **separate follow-up spec** (will read the `benchmark_summary` view).
- End-user-facing shipped benchmark (consent gating, anonymization, edge-function ingest).
- Anthropic Agent SDK / raw API execution paths (headless Claude Code only).
- Automatic headless deep-scan (semi-automatic interactive prep chosen instead).

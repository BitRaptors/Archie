# Archie Benchmark Harness (internal)

Measures Archie's effectiveness: runs the **same** task headlessly on a control
branch (no Archie) and a treatment branch (full Archie docs + hooks), capturing
tool calls / tokens / cost / time + a blind judge-Claude quality score, and writes
results to Supabase. **Not** shipped via npm.

## Setup — do this before your first benchmark

Provide Supabase credentials so results are stored (see [Supabase](#supabase) for
detail). In short:

```bash
cp archie/benchmark/secrets.env.example .archie-bench/secrets.env
# edit .archie-bench/secrets.env: real SUPABASE_URL + service_role key
python3 -m archie.benchmark verify   # auto-loads .archie-bench/secrets.env; checks tables + creds
```

This must be filled in **before** you benchmark if you want results in Supabase. If
you skip it, runs still work but fall back to **offline mode** (a local
`results.json`), and nothing is written to the database.

## Usage

```bash
# 1. Author a config (see example below) — JSON, zero-dep.
# 2. From a plain repo, prep branches then run:
python3 -m archie.benchmark auto /path/to/repo --prompt "Add a sleep timer feature"

# Or with a config file:
python3 -m archie.benchmark run config.json     # branches must already exist
python3 -m archie.benchmark prep config.json    # only create/refresh branches
```

If the repo has no Archie files yet, `auto`/`prep` create the branches, then pause
so you can run `/archie-deep-scan` interactively on the treatment branch. That
deep-scan is **never** counted in the measured metrics.

## Config

```json
{
  "name": "bedtime-add-sleep-timer",
  "repo": "/Users/you/DEV/BedtimeApp",
  "task_prompt": "Add a sleep timer feature ...",
  "model": "claude-sonnet-4-6",
  "repetitions": 3,
  "branches": {"treatment": "archie-bench/with-archie", "control": "archie-bench/no-archie"},
  "judge": {"model": "claude-opus-4-8", "rubric": ["correctness", "completeness", "follows_conventions", "no_regressions"]},
  "timeout_seconds": 3600
}
```

## Supabase

Copy the credentials template and fill it in (the copy lives in gitignored
`.archie-bench/`, so real keys are never committed):

```bash
cp archie/benchmark/secrets.env.example .archie-bench/secrets.env
# edit .archie-bench/secrets.env: real SUPABASE_URL + service_role key
python3 -m archie.benchmark verify   # auto-loads .archie-bench/secrets.env; checks tables + creds
```

`store.py` reads `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` from the environment.
Without them the harness writes `.archie/benchmark/<name>/results.json` locally
(offline mode). Use the **service_role** key (not anon) so inserts bypass RLS, and
apply `archie/benchmark/schema.sql` in the Supabase SQL Editor once.

## Fairness invariants

- Identical `task_prompt`, `model`, and harness flags on both arms.
- Both branches descend from the same base commit (enforced).
- Deep-scan prep cost is separate (`prep_cost_usd`), never in sample metrics.

-- archie/benchmark/schema.sql
-- Archie benchmark harness — Supabase schema (v1).
-- Run manually against the project (or via CI). Idempotent-ish: uses IF NOT EXISTS.

create table if not exists benchmark_runs (
    id              uuid primary key default gen_random_uuid(),
    name            text not null,
    repo_name       text,                 -- basename only, never a full path
    task_prompt     text,
    model           text,
    judge_model     text,
    repetitions     int,
    git_base_commit text,
    prep_cost_usd   numeric,              -- deep-scan prep cost, separate & best-effort
    archie_version  text,
    created_at      timestamptz not null default now()
);

create table if not exists benchmark_samples (
    id                    uuid primary key default gen_random_uuid(),
    run_id                uuid not null references benchmark_runs(id) on delete cascade,
    arm                   text not null,  -- 'control' | 'treatment'
    repetition            int,
    tool_calls            int,
    tool_breakdown        jsonb,
    input_tokens          int,
    output_tokens         int,
    cache_read_tokens     int,
    cache_creation_tokens int,
    cost_usd              numeric,
    duration_ms           int,
    num_turns             int,
    completed             boolean,
    attempted             boolean,        -- agent produced a non-empty diff
    quality_score         numeric,
    quality_detail        jsonb,
    judge_seed            int,
    created_at            timestamptz not null default now()
);

create index if not exists benchmark_samples_run_id_idx on benchmark_samples(run_id);

-- Per-run, per-arm rollup the website reads (separate spec).
create or replace view benchmark_summary as
select
    r.id            as run_id,
    r.name          as name,
    r.repo_name     as repo_name,
    r.model         as model,
    s.arm           as arm,
    count(*)                          as samples,
    count(*) filter (where s.completed) as completed_samples,
    count(*) filter (where s.attempted) as attempted_samples,
    avg(s.tool_calls)                 as tool_calls_mean,
    avg(s.cost_usd)                   as cost_usd_mean,
    avg(s.duration_ms)                as duration_ms_mean,
    avg(s.input_tokens + s.output_tokens) as total_tokens_mean,
    -- quality only over real attempts (empty-diff runs excluded)
    avg(s.quality_score) filter (where s.attempted) as quality_mean
from benchmark_runs r
join benchmark_samples s on s.run_id = r.id
group by r.id, r.name, r.repo_name, r.model, s.arm;

-- Add `cli` — which coding-agent harness drove the run (claude / codex /
-- unknown). Lets analytics separate Codex CLI runs from Claude Code runs.
-- Nullable: rows inserted before this column existed, and events from older
-- clients that predate the field, carry NULL. Validation (the allow-list)
-- lives in the telemetry-ingest edge function, consistent with the other
-- text columns.

alter table public.telemetry_events
  add column cli text;

create index telemetry_events_cli_idx
  on public.telemetry_events (cli)
  where cli is not null;

comment on column public.telemetry_events.cli is
  'Coding-agent harness that drove the run: claude, codex, or unknown. NULL for rows predating this column. Set by the telemetry-ingest edge function from a validated allow-list.';

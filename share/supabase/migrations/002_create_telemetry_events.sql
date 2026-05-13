-- Anonymous, opt-in usage telemetry from Archie installs.
-- Inserts go through the telemetry-ingest edge function which uses the anon
-- key + RLS — never the service role. Per-row validation (size cap, batch
-- limit, allow-lists, length caps, jsonb sanitization) lives in the function.

create table public.telemetry_events (
  id bigserial primary key,
  received_at timestamptz not null default now(),
  schema_version smallint not null,
  installation_id text,
  archie_version text not null,
  os text,
  arch text,
  command text not null,
  outcome text,
  duration_s int,
  error_class text,
  steps jsonb,
  stack jsonb,
  source text
);

create index telemetry_events_received_at_idx on public.telemetry_events (received_at desc);
create index telemetry_events_command_idx on public.telemetry_events (command);
create index telemetry_events_installation_id_idx on public.telemetry_events (installation_id) where installation_id is not null;

alter table public.telemetry_events enable row level security;

-- anon-key clients (used by the telemetry-ingest edge function) may insert only.
-- WITH CHECK (true) is intentional: validation lives in the edge function.
create policy "anon_insert_only" on public.telemetry_events
  for insert to anon
  with check (true);

-- explicit deny for select/update/delete is the default (no policy, no access).
comment on table public.telemetry_events is 'Anonymous opt-in usage telemetry from Archie installs. No source code, file paths, or repo names. See archie/standalone/telemetry_sync.py and supabase/functions/telemetry-ingest/.';
comment on column public.telemetry_events.installation_id is 'Random UUIDv4 generated once per machine in ~/.archie/config.json. Stripped from payload when telemetry tier == anonymous.';
comment on column public.telemetry_events.stack is 'Detected language/framework/build-tool tuple (e.g. {"languages": ["kotlin"], "frameworks": ["android"], "build_tools": ["gradle"]}). Broad categories only.';

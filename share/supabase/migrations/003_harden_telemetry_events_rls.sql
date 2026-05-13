-- TEL-1 fix: harden the telemetry_events RLS policy so direct PostgREST
-- inserts (using the public anon key embedded in every Archie install)
-- cannot bypass the validation in the telemetry-ingest edge function.
--
-- The previous policy used WITH CHECK (true), which made the edge function's
-- 50KB cap, allow-lists, length caps, and jsonb sanitization purely advisory:
-- an attacker hitting POST /rest/v1/telemetry_events directly with the anon
-- key bypassed all of it. Confirmed reproducible during the audit (HTTP 201
-- returned for a 100k-character `command` field and an out-of-allowlist
-- command value).
--
-- This migration replaces the policy with one whose CHECK clause mirrors the
-- edge function's gates in SQL. The function still runs first (and stays the
-- recommended path because it returns useful 4xx errors instead of opaque
-- PostgREST 400s), but the database is now the actual barrier.

drop policy if exists "anon_insert_only" on public.telemetry_events;

create policy "anon_insert_validated" on public.telemetry_events
  for insert to anon
  with check (
    schema_version = 1
    and command in ('scan', 'deep-scan', 'viewer', 'intent-layer', 'share', 'install')
    and length(command) <= 32
    and length(archie_version) <= 32
    and (outcome is null or (outcome in ('success', 'error', 'aborted', 'unknown') and length(outcome) <= 16))
    and (os is null or os in ('darwin', 'linux', 'win32', 'other'))
    and (arch is null or arch in ('arm64', 'x64', 'ia32', 'other'))
    and (installation_id is null or length(installation_id) <= 64)
    and (error_class is null or length(error_class) <= 200)
    and (source is null or (source in ('live', 'test') and length(source) <= 16))
    and (duration_s is null or (duration_s >= 0 and duration_s <= 86400))
    and (steps is null or octet_length(steps::text) <= 8192)
    and (stack is null or octet_length(stack::text) <= 8192)
  );

comment on policy "anon_insert_validated" on public.telemetry_events is
  'Mirrors the validation in supabase/functions/telemetry-ingest/index.ts. Keep both in sync — the function is the recommended path (better error messages); this policy is the actual security boundary.';

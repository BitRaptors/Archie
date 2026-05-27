// Anonymous, opt-in usage telemetry ingest for Archie.
// Uses the Supabase ANON key + RLS — never the service role key — so a leaked
// or reverse-engineered URL cannot read or modify other rows.
//
// Validation done here (not just in SQL):
//  - 50 KB total payload cap
//  - schema_version === 1
//  - batch ≤ 100 events
//  - command + outcome allow-lists
//  - per-field length caps
//  - any extra fields are dropped (defence-in-depth against schema drift)

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const MAX_PAYLOAD_BYTES = 50 * 1024;
const MAX_BATCH = 100;
const SCHEMA_VERSION = 1;

const ALLOWED_COMMANDS = new Set([
  "scan",
  "deep-scan",
  "viewer",
  "intent-layer",
  "share",
  "install",
]);

const ALLOWED_OUTCOMES = new Set([
  "success",
  "error",
  "aborted",
  "unknown",
]);

const ALLOWED_OS = new Set(["darwin", "linux", "win32", "other"]);
const ALLOWED_ARCH = new Set(["arm64", "x64", "ia32", "other"]);
const ALLOWED_SOURCE = new Set(["live", "test"]);
// Which coding-agent harness drove the run. "unknown" is a legitimate value
// the client sends when it ran outside a detectable harness.
const ALLOWED_CLI = new Set(["claude", "codex", "unknown"]);

const FIELD_LIMITS: Record<string, number> = {
  installation_id: 64,
  archie_version: 32,
  os: 16,
  arch: 16,
  cli: 16,
  command: 32,
  outcome: 16,
  error_class: 200,
  source: 16,
};

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, content-type, apikey",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function jsonResponse(body: unknown, status: number) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...CORS },
  });
}

function clipString(value: unknown, max: number): string | null {
  if (typeof value !== "string") return null;
  if (!value) return null;
  return value.length > max ? value.slice(0, max) : value;
}

function clipInt(value: unknown, min: number, max: number): number | null {
  if (typeof value !== "number") return null;
  if (!Number.isFinite(value)) return null;
  const v = Math.trunc(value);
  if (v < min || v > max) return null;
  return v;
}

// jsonb columns: keep small, reject anything that smells suspicious. We accept
// arrays of strings, and shallow objects whose values are strings, numbers, or
// string arrays (the shape `stack` and `steps` actually use).
function sanitizeStringArray(value: unknown, maxLen: number, maxStringLen: number): string[] {
  if (!Array.isArray(value)) return [];
  const out: string[] = [];
  for (const v of value) {
    if (out.length >= maxLen) break;
    if (typeof v === "string" && v.length > 0 && v.length <= maxStringLen) out.push(v);
  }
  return out;
}

function sanitizeJsonb(value: unknown, maxKeys: number, maxStringLen: number): unknown {
  if (value === null || value === undefined) return null;
  if (Array.isArray(value)) return sanitizeStringArray(value, maxKeys, maxStringLen);
  if (typeof value === "object") {
    const out: Record<string, string | number | string[]> = {};
    let count = 0;
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      if (count >= maxKeys) break;
      if (typeof k !== "string" || k.length === 0 || k.length > 64) continue;
      if (typeof v === "number" && Number.isFinite(v)) {
        out[k] = Math.trunc(v);
        count++;
      } else if (typeof v === "string" && v.length <= maxStringLen) {
        out[k] = v;
        count++;
      } else if (Array.isArray(v)) {
        const arr = sanitizeStringArray(v, maxKeys, maxStringLen);
        if (arr.length > 0) {
          out[k] = arr;
          count++;
        }
      }
    }
    return out;
  }
  return null;
}

function sanitizeEvent(raw: unknown): Record<string, unknown> | null {
  if (!raw || typeof raw !== "object") return null;
  const e = raw as Record<string, unknown>;

  const command = clipString(e.command, FIELD_LIMITS.command);
  if (!command || !ALLOWED_COMMANDS.has(command)) return null;

  const archie_version = clipString(e.archie_version, FIELD_LIMITS.archie_version);
  if (!archie_version) return null;

  const outcome_raw = clipString(e.outcome, FIELD_LIMITS.outcome);
  const outcome = outcome_raw && ALLOWED_OUTCOMES.has(outcome_raw) ? outcome_raw : null;

  const os_raw = clipString(e.os, FIELD_LIMITS.os);
  const os = os_raw && ALLOWED_OS.has(os_raw) ? os_raw : (os_raw ? "other" : null);

  const arch_raw = clipString(e.arch, FIELD_LIMITS.arch);
  const arch = arch_raw && ALLOWED_ARCH.has(arch_raw) ? arch_raw : (arch_raw ? "other" : null);

  // cli is optional: events from clients predating this field arrive without
  // it (→ null). An unrecognised value is also nulled rather than coerced.
  const cli_raw = clipString(e.cli, FIELD_LIMITS.cli);
  const cli = cli_raw && ALLOWED_CLI.has(cli_raw) ? cli_raw : null;

  const source_raw = clipString(e.source, FIELD_LIMITS.source);
  const source = source_raw && ALLOWED_SOURCE.has(source_raw) ? source_raw : "live";

  return {
    schema_version: SCHEMA_VERSION,
    installation_id: clipString(e.installation_id, FIELD_LIMITS.installation_id),
    archie_version,
    os,
    arch,
    cli,
    command,
    outcome,
    duration_s: clipInt(e.duration_s, 0, 24 * 60 * 60),
    error_class: clipString(e.error_class, FIELD_LIMITS.error_class),
    steps: sanitizeJsonb(e.steps, 32, 64),
    stack: sanitizeJsonb(e.stack, 32, 64),
    source,
  };
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
  if (req.method !== "POST") return jsonResponse({ error: "method_not_allowed" }, 405);

  // Read with size cap before parsing (avoid OOM on hostile payloads).
  let body: string;
  try {
    const buf = new Uint8Array(await req.arrayBuffer());
    if (buf.byteLength > MAX_PAYLOAD_BYTES) {
      return jsonResponse({ error: "payload_too_large", limit: MAX_PAYLOAD_BYTES }, 413);
    }
    body = new TextDecoder().decode(buf);
  } catch (_e) {
    return jsonResponse({ error: "body_read_failed" }, 400);
  }

  let parsed: unknown;
  try { parsed = JSON.parse(body); }
  catch (_e) { return jsonResponse({ error: "invalid_json" }, 400); }

  if (!parsed || typeof parsed !== "object") return jsonResponse({ error: "invalid_envelope" }, 400);
  const env = parsed as Record<string, unknown>;
  if (env.schema_version !== SCHEMA_VERSION) {
    return jsonResponse({ error: "unsupported_schema_version", expected: SCHEMA_VERSION }, 400);
  }
  if (!Array.isArray(env.events)) return jsonResponse({ error: "events_not_array" }, 400);
  if (env.events.length === 0) return jsonResponse({ inserted: 0 }, 200);
  if (env.events.length > MAX_BATCH) {
    return jsonResponse({ error: "batch_too_large", limit: MAX_BATCH }, 413);
  }

  const sanitized: Record<string, unknown>[] = [];
  for (const raw of env.events) {
    const e = sanitizeEvent(raw);
    if (e) sanitized.push(e);
  }
  if (sanitized.length === 0) return jsonResponse({ inserted: 0, dropped: env.events.length }, 200);

  // Use ANON key + RLS — deliberately not the service role.
  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY");
  if (!supabaseUrl || !anonKey) return jsonResponse({ error: "server_misconfigured" }, 500);

  const client = createClient(supabaseUrl, anonKey);
  const { error } = await client.from("telemetry_events").insert(sanitized);
  if (error) {
    console.error("insert failed", error);
    return jsonResponse({ error: "insert_failed" }, 500);
  }
  return jsonResponse({ inserted: sanitized.length, dropped: env.events.length - sanitized.length }, 200);
});

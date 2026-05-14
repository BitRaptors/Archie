#!/usr/bin/env python3
"""Anonymous, opt-in telemetry sync to the Archie Supabase backend.

Append-and-push pipeline:

  1. `post-run <project_root> <run-file>` — called at the end of every scan or
     deep-scan. Reads the just-written project-local run JSON, enriches it with
     stack metadata from scan.json, sanitizes, appends one line to the global
     jsonl at ~/.archie/analytics/runs.jsonl, and fire-and-forgets `sync`.
  2. `sync` — reads any unsent lines (cursor at ~/.archie/analytics/.cursor),
     batches up to 100 events, POSTs to the telemetry-ingest edge function
     with --max-time 10, advances cursor only on `inserted > 0` responses.
     Rate-limited to once per 5 minutes via ~/.archie/analytics/.last-sync.

Consent is read from ~/.archie/config.json (managed by config.py). When the
telemetry tier is "off" all operations are no-ops. When the tier is
"anonymous", the installation_id is stripped from each event before upload.

Local jsonl rows always carry the installation_id and an underscore-prefixed
`_project_basename` (kept for the local analytics dashboard, never uploaded).

Zero deps beyond Python 3.9+ stdlib. Failures are silent — telemetry must
never break a scan.

CLI:
  telemetry_sync.py append         <project_root> <run-json>
  telemetry_sync.py post-run       <project_root> <run-json>
  telemetry_sync.py sync           [--force]
  telemetry_sync.py status
  telemetry_sync.py purge
  telemetry_sync.py record-install [--version X.Y.Z]
  telemetry_sync.py record-event   --command X [--outcome O] [--duration N] [--error E] [--project-root P]
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from archie.standalone.config import (
        config_dir,
        get_installation_id,
        get_telemetry_tier,
        load_config,
    )
except ImportError:
    # When invoked as a standalone script from a project's .archie/ directory,
    # the package isn't on sys.path. Fall back to the sibling config.py.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from config import (  # type: ignore[no-redef]
        config_dir,
        get_installation_id,
        get_telemetry_tier,
        load_config,
    )

SCHEMA_VERSION = 1
# Default telemetry-ingest endpoint. ARCHIE_TELEMETRY_ENDPOINT overrides it (via
# _endpoint(), read at call time) — tests point it at a stub so a test run can
# never POST to production. Mirrors gstack's GSTACK_SUPABASE_URL test override.
ENDPOINT_URL = "https://chlmyhkjnirrcrjdsvrc.supabase.co/functions/v1/telemetry-ingest"
ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNobG15aGtqbmlycmNyamRzdnJjIiwicm9sZSI6"
    "ImFub24iLCJpYXQiOjE3NzYwNzk4NTEsImV4cCI6MjA5MTY1NTg1MX0."
    "f6C7vDO0jUWGF_63xhGVPwQlZyKgerw4KdY0HiHmNPw"
)
SYNC_RATE_LIMIT_S = 5 * 60
HTTP_TIMEOUT_S = 10
BATCH_LIMIT = 100

ALLOWED_OS = {"darwin", "linux", "win32", "other"}
ALLOWED_ARCH = {"arm64", "x64", "ia32", "other"}
ALLOWED_OUTCOMES = {"success", "error", "aborted", "unknown"}


# ── Paths ────────────────────────────────────────────────────────────────

def _analytics_dir() -> Path:
    return config_dir() / "analytics"


def _runs_jsonl() -> Path:
    return _analytics_dir() / "runs.jsonl"


def _cursor_path() -> Path:
    return _analytics_dir() / ".cursor"


def _last_sync_path() -> Path:
    return _analytics_dir() / ".last-sync"


# ── Stack + env detection ────────────────────────────────────────────────

def _archie_version() -> str:
    """Read version from npm-package/package.json or pyproject.toml.

    The .archie/ directory does not ship package.json, so we look for a marker
    written at install time. Falls back to "unknown" on miss.
    """
    marker = config_dir() / "version"
    if marker.exists():
        try:
            return marker.read_text(encoding="utf-8").strip()[:32] or "unknown"
        except OSError:
            return "unknown"
    return "unknown"


def _normalized_os() -> str:
    sys_platform = sys.platform.lower()
    if sys_platform.startswith("darwin"):
        return "darwin"
    if sys_platform.startswith("linux"):
        return "linux"
    if sys_platform.startswith("win"):
        return "win32"
    return "other"


def _normalized_arch() -> str:
    machine = platform.machine().lower()
    if machine in {"arm64", "aarch64"}:
        return "arm64"
    if machine in {"x86_64", "amd64"}:
        return "x64"
    if machine in {"i386", "i686", "x86"}:
        return "ia32"
    return "other"


def _detect_stack(project_root: Path) -> dict[str, list[str]]:
    """Read scan.json (if present) and return a broad-category stack tuple.

    Languages: best-effort heuristic from framework_signals keys.
    Frameworks: top-N keys from framework_signals by count.
    Build tools: from monorepo_type + dependency-file heuristics.

    Returns at most 5 entries per category. Lowercased, deduped, sorted.
    """
    scan_path = project_root / ".archie" / "scan.json"
    if not scan_path.exists():
        return {"languages": [], "frameworks": [], "build_tools": []}
    try:
        scan = json.loads(scan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"languages": [], "frameworks": [], "build_tools": []}
    if not isinstance(scan, dict):
        return {"languages": [], "frameworks": [], "build_tools": []}

    # framework_signals is a list of {name, version, evidence} dicts in the
    # current scanner; tolerate the older {name: count} dict shape too.
    raw_signals = scan.get("framework_signals") or []
    framework_names: list[str] = []
    if isinstance(raw_signals, list):
        for entry in raw_signals:
            if isinstance(entry, dict):
                name = entry.get("name")
                if isinstance(name, str) and name:
                    framework_names.append(name.lower())
    elif isinstance(raw_signals, dict):
        framework_names = [str(k).lower() for k in raw_signals.keys() if str(k)]

    # Dedupe while preserving first-seen order, then keep at most 5.
    seen: set[str] = set()
    frameworks: list[str] = []
    for name in framework_names:
        # Some entries are slash-joined like "android/gradle" — split and re-emit
        # each side as its own broad category.
        for piece in name.replace("\\", "/").split("/"):
            piece = piece.strip()
            if piece and piece not in seen:
                seen.add(piece)
                frameworks.append(piece)
                if len(frameworks) >= 5:
                    break
        if len(frameworks) >= 5:
            break

    # Language guess from framework signal names.
    fw_to_lang = {
        "react": "javascript", "vue": "javascript", "angular": "javascript",
        "next": "javascript", "vite": "javascript", "svelte": "javascript",
        "nuxt": "javascript", "express": "javascript", "node": "javascript",
        "django": "python", "fastapi": "python", "flask": "python",
        "rails": "ruby", "sinatra": "ruby",
        "spring": "java",
        "android": "kotlin", "kotlin": "kotlin",
        "ios": "swift", "swift": "swift", "swiftui": "swift",
        "go": "go",
        "rust": "rust", "axum": "rust", "actix": "rust",
        "dotnet": "csharp", "aspnet": "csharp",
        "laravel": "php",
    }
    languages: set[str] = set()
    for fw in frameworks:
        if fw in fw_to_lang:
            languages.add(fw_to_lang[fw])

    # Build tools: monorepo_type signal + dependency files.
    build_tools: set[str] = set()
    subprojects = scan.get("subprojects") or []
    if isinstance(subprojects, list):
        for sub in subprojects:
            if isinstance(sub, dict):
                mt = sub.get("monorepo_type")
                if isinstance(mt, str) and mt:
                    build_tools.add(mt.lower()[:32])
    # Build tools: scan dependencies + framework evidence file paths for known
    # build-tool signatures. Dependency entries shape: {name, version, source}.
    candidate_paths: list[str] = []
    deps = scan.get("dependencies") or []
    if isinstance(deps, list):
        for dep in deps:
            if not isinstance(dep, dict):
                continue
            for key in ("source", "path", "file"):
                v = dep.get(key)
                if isinstance(v, str) and v:
                    candidate_paths.append(v.lower())
    if isinstance(raw_signals, list):
        for entry in raw_signals:
            if not isinstance(entry, dict):
                continue
            ev = entry.get("evidence") or []
            if isinstance(ev, list):
                for item in ev:
                    if isinstance(item, str) and item:
                        candidate_paths.append(item.lower())

    for path_str in candidate_paths:
        if "build.gradle" in path_str or "settings.gradle" in path_str:
            build_tools.add("gradle")
        if "pom.xml" in path_str:
            build_tools.add("maven")
        if "pnpm-lock" in path_str or "pnpm-workspace" in path_str:
            build_tools.add("pnpm")
        elif "yarn.lock" in path_str:
            build_tools.add("yarn")
        elif "package.json" in path_str:
            build_tools.add("npm")
        if "cargo.toml" in path_str:
            build_tools.add("cargo")
        if "pyproject.toml" in path_str or "poetry.lock" in path_str:
            build_tools.add("poetry")
        if "requirements.txt" in path_str:
            build_tools.add("pip")
        if "go.mod" in path_str:
            build_tools.add("go")
        if "podfile" in path_str or "package.swift" in path_str:
            build_tools.add("spm")

    return {
        "languages": sorted(languages)[:5],
        "frameworks": sorted(frameworks)[:5],
        "build_tools": sorted(build_tools)[:5],
    }


# ── Run-file → event ─────────────────────────────────────────────────────

def _summarize_steps(steps: list[dict]) -> dict[str, int]:
    """Reduce a list of step dicts to {short_name: seconds}, capped at 32 keys."""
    out: dict[str, int] = {}
    for s in steps:
        if not isinstance(s, dict):
            continue
        name = str(s.get("name") or "")[:64]
        if not name:
            continue
        seconds = s.get("seconds")
        if not isinstance(seconds, (int, float)):
            seconds = 0
        out[name] = max(0, int(seconds))
        if len(out) >= 32:
            break
    return out


def _outcome_for_run(run: dict) -> str:
    """Heuristic: explicit `outcome` field wins; else `success` if total_seconds > 0."""
    explicit = run.get("outcome")
    if isinstance(explicit, str) and explicit in ALLOWED_OUTCOMES:
        return explicit
    if int(run.get("total_seconds") or 0) > 0:
        return "success"
    return "unknown"


def _build_event(project_root: Path, run: dict, *, source: str = "live") -> dict:
    """Map a project-local run JSON into the wire event shape.

    Adds underscore-prefixed local-only fields that are stripped before upload.
    """
    cfg = load_config()
    stack = _detect_stack(project_root)
    steps = run.get("steps") if isinstance(run.get("steps"), list) else []
    command = str(run.get("command") or "")[:32]
    return {
        "schema_version": SCHEMA_VERSION,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "installation_id": cfg.get("installation_id"),
        "archie_version": _archie_version(),
        "os": _normalized_os(),
        "arch": _normalized_arch(),
        "command": command,
        "outcome": _outcome_for_run(run),
        "duration_s": int(run.get("total_seconds") or 0),
        "error_class": run.get("error_class") if isinstance(run.get("error_class"), str) else None,
        "steps": _summarize_steps(steps),
        "stack": stack,
        "source": source,
        # Local-only — stripped on upload.
        "_project_basename": project_root.name[:64],
    }


# ── Append + sync ────────────────────────────────────────────────────────

def append_event(project_root: Path, run_path: Path, *, source: str = "live") -> bool:
    """Read a run JSON, build an event, append to the global jsonl. Returns success."""
    if get_telemetry_tier() == "off":
        return False
    if not run_path.exists():
        return False
    try:
        run = json.loads(run_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(run, dict):
        return False

    event = _build_event(project_root, run, source=source)
    line = json.dumps(event, separators=(",", ":")) + "\n"

    _analytics_dir().mkdir(parents=True, exist_ok=True)
    try:
        with open(_runs_jsonl(), "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        return False
    return True


def _strip_for_upload(event: dict, tier: str) -> dict:
    """Strip underscore-prefixed local-only fields and the installation_id when anonymous."""
    out = {k: v for k, v in event.items() if not k.startswith("_")}
    if tier == "anonymous":
        out["installation_id"] = None
    return out


def _read_unsent(cursor: int) -> tuple[list[dict], int]:
    """Read events from runs.jsonl starting at line `cursor` (0-indexed). Returns (events, new_cursor)."""
    if not _runs_jsonl().exists():
        return [], cursor
    events: list[dict] = []
    new_cursor = cursor
    with open(_runs_jsonl(), "r", encoding="utf-8") as f:
        for idx, raw in enumerate(f):
            if idx < cursor:
                continue
            new_cursor = idx + 1
            line = raw.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(events) >= BATCH_LIMIT:
                break
    return events, new_cursor


def _read_cursor() -> int:
    if not _cursor_path().exists():
        return 0
    try:
        return int(_cursor_path().read_text(encoding="utf-8").strip() or "0")
    except (OSError, ValueError):
        return 0


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _endpoint() -> str:
    """Resolve the telemetry-ingest URL, honoring the ARCHIE_TELEMETRY_ENDPOINT
    env override. Read at call time (not import) so tests can redirect uploads
    to a stub without re-importing the module."""
    return os.environ.get("ARCHIE_TELEMETRY_ENDPOINT") or ENDPOINT_URL


def _post(payload: dict) -> tuple[int, dict]:
    """POST payload to the telemetry endpoint. Returns (status_code, body_dict)."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        _endpoint(),
        data=body,
        headers={
            "Content-Type": "application/json",
            "apikey": ANON_KEY,
            "Authorization": f"Bearer {ANON_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = {}
            return (resp.status, parsed)
    except urllib.error.HTTPError as e:
        try:
            raw = e.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw) if raw else {}
        except (OSError, json.JSONDecodeError):
            parsed = {}
        return (e.code, parsed)
    except (urllib.error.URLError, TimeoutError, OSError):
        return (0, {})


def sync_now(force: bool = False) -> dict:
    """Send pending events. Returns a status dict (always — never raises)."""
    tier = get_telemetry_tier()
    if tier == "off":
        return {"status": "disabled"}

    if not force:
        last = _last_sync_path()
        if last.exists():
            try:
                if time.time() - last.stat().st_mtime < SYNC_RATE_LIMIT_S:
                    return {"status": "rate_limited"}
            except OSError:
                pass

    cursor = _read_cursor()
    events, new_cursor = _read_unsent(cursor)
    if not events:
        # Touch last-sync so we don't keep re-checking.
        _write_atomic(_last_sync_path(), str(time.time()))
        return {"status": "empty", "cursor": cursor}

    upload_events = [_strip_for_upload(e, tier) for e in events]
    payload = {"schema_version": SCHEMA_VERSION, "events": upload_events}
    status, body = _post(payload)
    _write_atomic(_last_sync_path(), str(time.time()))

    if status == 200:
        # Advance cursor regardless of inserted count — events the server dropped
        # for validation reasons won't pass on retry either.
        _write_atomic(_cursor_path(), str(new_cursor))
        return {
            "status": "ok",
            "sent": len(upload_events),
            "inserted": int(body.get("inserted", 0)),
            "dropped": int(body.get("dropped", 0)),
            "cursor": new_cursor,
        }
    return {"status": "http_error", "code": status, "body": body, "cursor": cursor}


def record_event(
    command: str,
    *,
    outcome: str = "success",
    duration_s: int = 0,
    error_class: str | None = None,
    project_root: Path | None = None,
) -> dict:
    """Append a one-shot event (no project run-file). Used for short commands
    (viewer, share, intent-layer) that don't go through the multi-step
    telemetry.py flow.
    """
    if get_telemetry_tier() == "off":
        return {"appended": False, "reason": "telemetry_off"}
    cfg = load_config()
    stack = _detect_stack(project_root) if project_root else {"languages": [], "frameworks": [], "build_tools": []}
    event = {
        "schema_version": SCHEMA_VERSION,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "installation_id": cfg.get("installation_id"),
        "archie_version": _archie_version(),
        "os": _normalized_os(),
        "arch": _normalized_arch(),
        "command": command[:32],
        "outcome": outcome if outcome in ALLOWED_OUTCOMES else "unknown",
        "duration_s": max(0, int(duration_s or 0)),
        "error_class": error_class[:200] if isinstance(error_class, str) else None,
        "steps": {},
        "stack": stack,
        "source": "live",
    }
    if project_root is not None:
        event["_project_basename"] = project_root.name[:64]
    line = json.dumps(event, separators=(",", ":")) + "\n"
    _analytics_dir().mkdir(parents=True, exist_ok=True)
    try:
        with open(_runs_jsonl(), "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        return {"appended": False, "reason": "write_failed"}
    try:
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "sync"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
    except OSError:
        pass
    return {"appended": True}


def record_install(version: str | None = None) -> dict:
    """Append a one-off `install` event (no project context) and trigger sync."""
    if get_telemetry_tier() == "off":
        return {"appended": False, "reason": "telemetry_off"}
    cfg = load_config()
    event = {
        "schema_version": SCHEMA_VERSION,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "installation_id": cfg.get("installation_id"),
        "archie_version": (version or _archie_version())[:32],
        "os": _normalized_os(),
        "arch": _normalized_arch(),
        "command": "install",
        "outcome": "success",
        "duration_s": 0,
        "error_class": None,
        "steps": {},
        "stack": None,
        "source": "live",
    }
    line = json.dumps(event, separators=(",", ":")) + "\n"
    _analytics_dir().mkdir(parents=True, exist_ok=True)
    try:
        with open(_runs_jsonl(), "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        return {"appended": False, "reason": "write_failed"}
    try:
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "sync", "--force"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
    except OSError:
        pass
    return {"appended": True}


def post_run(project_root: Path, run_path: Path) -> dict:
    """Append the run, then fire-and-forget a background sync."""
    appended = append_event(project_root, run_path)
    if not appended:
        return {"appended": False}

    # Fire-and-forget background sync. Detach from parent so it survives the
    # slash-command process exit. Failures are silent.
    try:
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "sync"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
    except OSError:
        pass
    return {"appended": True}


def status() -> dict:
    cursor = _read_cursor()
    total_lines = 0
    if _runs_jsonl().exists():
        try:
            with open(_runs_jsonl(), "r", encoding="utf-8") as f:
                for _ in f:
                    total_lines += 1
        except OSError:
            pass
    last_sync_iso = None
    if _last_sync_path().exists():
        try:
            ts = _last_sync_path().stat().st_mtime
            last_sync_iso = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except OSError:
            pass
    return {
        "tier": get_telemetry_tier(),
        "installation_id": get_installation_id(),
        "total_local_events": total_lines,
        "cursor": cursor,
        "pending": max(0, total_lines - cursor),
        "last_sync": last_sync_iso,
        "endpoint": _endpoint(),
        "jsonl_path": str(_runs_jsonl()),
    }


def purge() -> dict:
    """Delete the local jsonl + cursor + last-sync. Useful for opt-out cleanup."""
    removed = []
    for p in (_runs_jsonl(), _cursor_path(), _last_sync_path()):
        if p.exists():
            try:
                p.unlink()
                removed.append(p.name)
            except OSError:
                pass
    return {"removed": removed}


# ── CLI ──────────────────────────────────────────────────────────────────

def _usage() -> int:
    sys.stderr.write(
        "Usage:\n"
        "  telemetry_sync.py append         <project_root> <run-json>\n"
        "  telemetry_sync.py post-run       <project_root> <run-json>\n"
        "  telemetry_sync.py sync           [--force]\n"
        "  telemetry_sync.py status\n"
        "  telemetry_sync.py purge\n"
        "  telemetry_sync.py record-install [--version X.Y.Z]\n"
        "  telemetry_sync.py record-event   --command X [--outcome O] "
        "[--duration N] [--error E] [--project-root P]\n"
    )
    return 2


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        return _usage()
    cmd = argv[1]
    if cmd == "append":
        if len(argv) < 4:
            return _usage()
        ok = append_event(Path(argv[2]).resolve(), Path(argv[3]))
        print("appended" if ok else "skipped")
        return 0
    if cmd == "post-run":
        if len(argv) < 4:
            return _usage()
        result = post_run(Path(argv[2]).resolve(), Path(argv[3]))
        print(json.dumps(result))
        return 0
    if cmd == "sync":
        force = "--force" in argv[2:]
        result = sync_now(force=force)
        print(json.dumps(result))
        return 0
    if cmd == "status":
        print(json.dumps(status(), indent=2))
        return 0
    if cmd == "purge":
        print(json.dumps(purge()))
        return 0
    if cmd == "record-install":
        version = None
        if "--version" in argv[2:]:
            try:
                version = argv[argv.index("--version", 2) + 1]
            except (ValueError, IndexError):
                pass
        result = record_install(version=version)
        print(json.dumps(result))
        return 0
    if cmd == "record-event":
        # record-event --command X [--outcome O] [--duration N] [--error E] [--project-root P]
        def _opt(name: str, default: str | None = None) -> str | None:
            if name in argv[2:]:
                try:
                    return argv[argv.index(name, 2) + 1]
                except (ValueError, IndexError):
                    return default
            return default
        command = _opt("--command")
        if not command:
            sys.stderr.write("record-event requires --command\n")
            return 2
        outcome = _opt("--outcome", "success") or "success"
        try:
            duration_s = int(_opt("--duration", "0") or "0")
        except ValueError:
            duration_s = 0
        error_class = _opt("--error")
        project_root_raw = _opt("--project-root")
        project_root = Path(project_root_raw).resolve() if project_root_raw else None
        result = record_event(
            command,
            outcome=outcome,
            duration_s=duration_s,
            error_class=error_class,
            project_root=project_root,
        )
        print(json.dumps(result))
        return 0
    return _usage()


if __name__ == "__main__":
    sys.exit(main(sys.argv))

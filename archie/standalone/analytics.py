#!/usr/bin/env python3
"""Local Archie analytics dashboard — reads ~/.archie/analytics/runs.jsonl.

The jsonl is the source of truth for what's been recorded on this machine
(the Supabase upload is a separate concern handled by telemetry_sync.py).
This script reads it, optionally filters by time window, and prints a
human-friendly summary to the terminal.

Underscore-prefixed fields (e.g. `_project_basename`) are kept locally —
they never get uploaded but DO get displayed here, so you can see which of
your projects have triggered runs.

CLI:
  analytics.py             — last 7 days (default)
  analytics.py 7d          — last 7 days
  analytics.py 30d         — last 30 days
  analytics.py all         — all-time
  analytics.py --json      — emit raw aggregate as JSON

Zero deps beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from archie.standalone.telemetry_sync import _runs_jsonl, status as sync_status
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from telemetry_sync import _runs_jsonl, status as sync_status  # type: ignore[no-redef]


WINDOWS = {"7d": 7, "30d": 30, "all": None}


def _parse_iso(ts: str) -> datetime | None:
    if not isinstance(ts, str) or not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _read_events(window_days: int | None) -> list[dict]:
    path = _runs_jsonl()
    if not path.exists():
        return []
    cutoff = None
    if window_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    out: list[dict] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                if cutoff is not None:
                    ts = _parse_iso(str(event.get("ts") or ""))
                    if ts is None or ts < cutoff:
                        continue
                out.append(event)
    except OSError:
        return []
    return out


def aggregate(events: list[dict]) -> dict[str, Any]:
    by_command: Counter[str] = Counter()
    by_outcome: Counter[str] = Counter()
    duration_by_command: defaultdict[str, list[int]] = defaultdict(list)
    languages: Counter[str] = Counter()
    frameworks: Counter[str] = Counter()
    build_tools: Counter[str] = Counter()
    projects: Counter[str] = Counter()
    last_ts: str | None = None

    for e in events:
        cmd = str(e.get("command") or "unknown")
        out = str(e.get("outcome") or "unknown")
        by_command[cmd] += 1
        by_outcome[out] += 1
        d = e.get("duration_s")
        if isinstance(d, (int, float)) and d > 0:
            duration_by_command[cmd].append(int(d))
        stack = e.get("stack") or {}
        if isinstance(stack, dict):
            for lang in stack.get("languages") or []:
                if isinstance(lang, str):
                    languages[lang] += 1
            for fw in stack.get("frameworks") or []:
                if isinstance(fw, str):
                    frameworks[fw] += 1
            for bt in stack.get("build_tools") or []:
                if isinstance(bt, str):
                    build_tools[bt] += 1
        proj = e.get("_project_basename")
        if isinstance(proj, str) and proj:
            projects[proj] += 1
        ts = e.get("ts")
        if isinstance(ts, str):
            if last_ts is None or ts > last_ts:
                last_ts = ts

    avg_durations = {
        cmd: round(sum(samples) / len(samples), 1)
        for cmd, samples in duration_by_command.items() if samples
    }

    return {
        "total_events": len(events),
        "by_command": dict(by_command.most_common()),
        "by_outcome": dict(by_outcome.most_common()),
        "avg_duration_s": avg_durations,
        "languages": dict(languages.most_common(10)),
        "frameworks": dict(frameworks.most_common(10)),
        "build_tools": dict(build_tools.most_common(10)),
        "projects": dict(projects.most_common(15)),
        "last_event_ts": last_ts,
    }


def _format_counter(d: dict[str, int]) -> str:
    if not d:
        return "  (none)"
    width = max(len(k) for k in d.keys())
    return "\n".join(f"  {k.ljust(width)}  {v}" for k, v in d.items())


def render(window: str, agg: dict[str, Any], sync: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"Archie analytics — window: {window}")
    lines.append(f"Tier: {sync.get('tier', 'off')}    Installation: {sync.get('installation_id', '?')[:8]}…")
    lines.append(f"Local jsonl: {sync.get('jsonl_path', '?')}")
    lines.append(f"Pending upload: {sync.get('pending', 0)}    Last sync: {sync.get('last_sync') or 'never'}")
    lines.append("")
    lines.append(f"Total events in window: {agg['total_events']}")
    if agg["last_event_ts"]:
        lines.append(f"Last event: {agg['last_event_ts']}")
    lines.append("")
    lines.append("By command:")
    lines.append(_format_counter(agg["by_command"]))
    lines.append("")
    lines.append("By outcome:")
    lines.append(_format_counter(agg["by_outcome"]))
    lines.append("")
    lines.append("Avg duration (s):")
    avg = agg["avg_duration_s"]
    if avg:
        width = max(len(k) for k in avg.keys())
        for k, v in sorted(avg.items()):
            lines.append(f"  {k.ljust(width)}  {v}")
    else:
        lines.append("  (none)")
    lines.append("")
    lines.append("Top stacks (by event count):")
    lines.append("  languages:")
    lines.append(_format_counter(agg["languages"]))
    lines.append("  frameworks:")
    lines.append(_format_counter(agg["frameworks"]))
    lines.append("  build_tools:")
    lines.append(_format_counter(agg["build_tools"]))
    lines.append("")
    lines.append("By project (local-only field — not uploaded):")
    lines.append(_format_counter(agg["projects"]))
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    args = argv[1:]
    as_json = "--json" in args
    if as_json:
        args.remove("--json")
    window = args[0] if args else "7d"
    if window not in WINDOWS:
        sys.stderr.write(f"unknown window: {window} (use one of {sorted(WINDOWS.keys())})\n")
        return 2
    days = WINDOWS[window]
    events = _read_events(days)
    agg = aggregate(events)
    if as_json:
        print(json.dumps({"window": window, "aggregate": agg, "sync": sync_status()}, indent=2))
        return 0
    print(render(window, agg, sync_status()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

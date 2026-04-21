#!/usr/bin/env python3
"""Archie telemetry — per-run timing output to .archie/telemetry/.

Assembles step-level timing data and project metadata into a single JSON file
per scan run. Called at the end of each scan or deep-scan command.

The scan/deep-scan prompts call `telemetry.py mark` at the start of every step
to persist the timestamp to disk immediately (`.archie/telemetry/_current_run.json`).
This makes the pipeline safe to /compact mid-run — the final telemetry writer
reads from disk rather than depending on shell variables the orchestrator
carried forward in its conversation context.

Usage (CLI):
  telemetry.py mark     <project_root> <command> <step>   — record step start
  telemetry.py finish   <project_root> <step>             — record completion
  telemetry.py extra    <project_root> <step> key=value…  — attach fields
  telemetry.py read     <project_root>                    — dump _current_run.json
  telemetry.py write    <project_root>                    — consume disk state
                                                             into a final file
  telemetry.py clear    <project_root>                    — delete in-flight state

Legacy (pre-compaction flow, still supported):
  telemetry.py <project_root> --command deep-scan --timing-file /tmp/archie_timing.json

Programmatic:
  from archie.standalone.telemetry import write_telemetry
  write_telemetry("/path/to/project", "scan", steps_list)

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_CURRENT_RUN_FILENAME = "_current_run.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(ts: str) -> datetime | None:
    """Parse an ISO-8601 timestamp, returning None on failure."""
    if not ts:
        return None
    try:
        normalized = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except (ValueError, TypeError):
        return None


def _compute_seconds(started_at: str, completed_at: str) -> int:
    """Compute elapsed seconds between two ISO timestamps. Returns 0 on failure."""
    start = _parse_iso(started_at)
    end = _parse_iso(completed_at)
    if start is None or end is None:
        return 0
    delta = (end - start).total_seconds()
    return max(0, int(delta))


def _read_project_metadata(archie_dir: Path) -> dict:
    """Read project stats from scan.json, returning zeros on failure."""
    defaults = {"source_files": 0, "total_loc": 0, "directories": 0}
    scan_path = archie_dir / "scan.json"
    if not scan_path.exists():
        return defaults
    try:
        data = json.loads(scan_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return defaults
    if not isinstance(data, dict):
        return defaults
    stats = data.get("statistics", {})
    if not isinstance(stats, dict):
        return defaults
    return {
        "source_files": stats.get("source_files", 0) or 0,
        "total_loc": stats.get("total_loc", 0) or 0,
        "directories": stats.get("directories", 0) or 0,
    }


# ── Persisted in-flight state ────────────────────────────────────────────

def _current_run_path(project_root: Path) -> Path:
    return project_root / ".archie" / "telemetry" / _CURRENT_RUN_FILENAME


def _load_current_run(project_root: Path) -> dict:
    """Load _current_run.json, returning an empty shape on failure."""
    path = _current_run_path(project_root)
    if not path.exists():
        return {"command": "", "started_at": "", "steps": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"command": "", "started_at": "", "steps": []}
    if not isinstance(data, dict):
        return {"command": "", "started_at": "", "steps": []}
    data.setdefault("command", "")
    data.setdefault("started_at", "")
    if not isinstance(data.get("steps"), list):
        data["steps"] = []
    return data


def _save_current_run(project_root: Path, state: dict) -> None:
    """Persist the in-flight run state atomically (write + rename)."""
    path = _current_run_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(path)


def mark_step(project_root: str | Path, command: str, step: str) -> None:
    """Record a step's started_at timestamp to disk.

    Idempotent-ish: if a step with the same name is the LAST step and has no
    completed_at, leave it alone (protects against double-mark from /compact +
    --continue). Otherwise append a new entry.

    Also promotes the previous step's missing completed_at to this step's
    started_at (mirrors the existing "next step's start = prior step's end"
    convention in the deep-scan prompt).
    """
    root = Path(project_root)
    now = _now_iso()
    state = _load_current_run(root)

    if command and not state.get("command"):
        state["command"] = command
    if not state.get("started_at"):
        state["started_at"] = now

    steps = state["steps"]
    # Close out the previous step if still open
    if steps:
        last = steps[-1]
        if not last.get("completed_at"):
            last["completed_at"] = now

    # Don't duplicate the same step if already marked and still open at tail
    if steps and steps[-1].get("name") == step and not steps[-1].get("completed_at"):
        # Already the current open step — leave started_at alone
        pass
    else:
        steps.append({"name": step, "started_at": now})

    _save_current_run(root, state)
    print(f"telemetry mark: {step} @ {now}", file=sys.stderr)


def finish_step(project_root: str | Path, step: str | None = None) -> None:
    """Record a step's completed_at timestamp. If step is None, finish the last open step.

    Idempotent: if the target step already has a `completed_at`, this is a
    no-op. That matters because the pipeline calls `finish_step` via
    `complete-step N` auto-finish, and we don't want a later mid-run call to
    overwrite an accurate timestamp with a post-compact one.
    """
    root = Path(project_root)
    now = _now_iso()
    state = _load_current_run(root)
    steps = state["steps"]
    if not steps:
        print("telemetry finish: no steps to finish", file=sys.stderr)
        return

    target = None
    if step is None:
        # Finish whichever step is the newest still-open one.
        for s in reversed(steps):
            if not s.get("completed_at"):
                target = s
                break
        if target is None:
            # All steps already closed; most recent one is the last one.
            target = steps[-1]
    else:
        # Finish the most recent step with this name.
        for s in reversed(steps):
            if s.get("name") == step:
                target = s
                break
    if target is None:
        print(f"telemetry finish: step {step!r} not found", file=sys.stderr)
        return
    if target.get("completed_at"):
        # Already closed — leave the earlier (more accurate) timestamp alone.
        print(f"telemetry finish: {target.get('name')} already closed at {target['completed_at']} (no-op)", file=sys.stderr)
        return
    target["completed_at"] = now
    _save_current_run(root, state)
    print(f"telemetry finish: {target.get('name')} @ {now}", file=sys.stderr)


def attach_extras(project_root: str | Path, step: str, extras: dict) -> None:
    """Merge extra key/values onto the most recent step with this name."""
    root = Path(project_root)
    state = _load_current_run(root)
    steps = state["steps"]
    target = None
    for s in reversed(steps):
        if s.get("name") == step:
            target = s
            break
    if target is None:
        print(f"telemetry extra: step {step!r} not found", file=sys.stderr)
        return
    for k, v in extras.items():
        target[k] = v
    _save_current_run(root, state)
    print(f"telemetry extra: {step} <- {extras}", file=sys.stderr)


def clear_run(project_root: str | Path) -> None:
    """Delete _current_run.json. Call after telemetry write succeeds."""
    path = _current_run_path(Path(project_root))
    if path.exists():
        path.unlink()
        print(f"telemetry clear: removed {path.name}", file=sys.stderr)


def _parse_extras(tokens: list[str]) -> dict:
    """Parse key=value tokens from argv into a dict. Coerces bool/int/float where obvious."""
    out: dict = {}
    for tok in tokens:
        if "=" not in tok:
            continue
        k, _, v = tok.partition("=")
        k = k.strip()
        v = v.strip()
        if not k:
            continue
        if v.lower() in ("true", "false"):
            out[k] = v.lower() == "true"
            continue
        try:
            if "." in v:
                out[k] = float(v)
            else:
                out[k] = int(v)
            continue
        except ValueError:
            pass
        out[k] = v
    return out


# ── Final telemetry file writer ──────────────────────────────────────────

def write_telemetry(project_root: str, command: str, steps: list[dict]) -> Path:
    """Write a telemetry JSON file for one scan run.

    Args:
        project_root: Path to the project root.
        command: The command name ("scan" or "deep-scan").
        steps: List of step dicts, each with at least "name", "started_at",
               "completed_at". Extra fields (e.g. "model", "skipped",
               "folders_processed") are preserved.

    Returns:
        Path to the written telemetry file.
    """
    root = Path(project_root)
    archie_dir = root / ".archie"
    telemetry_dir = archie_dir / "telemetry"
    telemetry_dir.mkdir(parents=True, exist_ok=True)

    project_meta = _read_project_metadata(archie_dir)

    # Enrich each step with computed seconds
    enriched_steps = []
    for step in steps:
        started = step.get("started_at", "")
        completed = step.get("completed_at", "")
        seconds = _compute_seconds(started, completed)
        enriched = {**step, "seconds": seconds}
        enriched_steps.append(enriched)

    # Derive top-level timestamps from first/last step
    started_at = ""
    completed_at = ""
    total_seconds = 0
    if enriched_steps:
        started_at = enriched_steps[0].get("started_at", "")
        for s in reversed(enriched_steps):
            if s.get("completed_at"):
                completed_at = s["completed_at"]
                break
        total_seconds = _compute_seconds(started_at, completed_at)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    filename = f"{command}_{now}.json"

    output = {
        "command": command,
        "started_at": started_at,
        "completed_at": completed_at,
        "total_seconds": total_seconds,
        "project": project_meta,
        "steps": enriched_steps,
    }

    out_path = telemetry_dir / filename
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote telemetry to {out_path.relative_to(root)}", file=sys.stderr)
    return out_path


def write_from_disk(project_root: str | Path) -> Path | None:
    """Consume _current_run.json and emit the final telemetry file.

    Auto-closes any still-open step with `now`. Clears the in-flight file
    on success so the next run starts fresh. Returns the output path, or
    None if there's nothing to write.
    """
    root = Path(project_root)
    state = _load_current_run(root)
    steps = state.get("steps") or []
    if not steps:
        print("telemetry write: no steps recorded", file=sys.stderr)
        return None
    now = _now_iso()
    if steps and not steps[-1].get("completed_at"):
        steps[-1]["completed_at"] = now
    command = state.get("command") or "deep-scan"
    out_path = write_telemetry(str(root), command, steps)
    clear_run(root)
    return out_path


# ── CLI ──────────────────────────────────────────────────────────────────

def _legacy_write(argv: list[str]) -> None:
    """Backwards-compat: telemetry.py <project_root> --command X --timing-file Y."""
    import argparse

    parser = argparse.ArgumentParser(description="Archie telemetry (legacy writer)")
    parser.add_argument("project_root", help="Path to project root")
    parser.add_argument("--command", required=True)
    parser.add_argument("--timing-file", required=True)
    args = parser.parse_args(argv)

    timing_path = Path(args.timing_file)
    if not timing_path.exists():
        print(f"error: timing file not found: {timing_path}", file=sys.stderr)
        sys.exit(1)
    try:
        steps = json.loads(timing_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"error: could not read timing file: {e}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(steps, list):
        print("error: timing file must contain a JSON array", file=sys.stderr)
        sys.exit(1)
    write_telemetry(args.project_root, args.command, steps)


def _usage_and_exit() -> None:
    print(
        "Usage:\n"
        "  telemetry.py mark   <project_root> <command> <step>\n"
        "  telemetry.py finish <project_root> [<step>]\n"
        "  telemetry.py extra  <project_root> <step> key=value [key=value ...]\n"
        "  telemetry.py read   <project_root>\n"
        "  telemetry.py write  <project_root>\n"
        "  telemetry.py clear  <project_root>\n"
        "\n"
        "  (legacy) telemetry.py <project_root> --command <name> --timing-file <path>",
        file=sys.stderr,
    )
    sys.exit(2)


def main():
    argv = sys.argv[1:]
    if not argv:
        _usage_and_exit()

    sub = argv[0]
    KNOWN = {"mark", "finish", "extra", "read", "write", "clear"}

    # Legacy entry point: first arg is a path, plus --command / --timing-file
    if sub not in KNOWN:
        _legacy_write(argv)
        return

    if len(argv) < 2:
        _usage_and_exit()
    root = Path(argv[1]).resolve()

    if sub == "mark":
        if len(argv) < 4:
            _usage_and_exit()
        mark_step(root, argv[2], argv[3])
    elif sub == "finish":
        step = argv[2] if len(argv) >= 3 else None
        finish_step(root, step)
    elif sub == "extra":
        if len(argv) < 4:
            _usage_and_exit()
        attach_extras(root, argv[2], _parse_extras(argv[3:]))
    elif sub == "read":
        state = _load_current_run(root)
        json.dump(state, sys.stdout, indent=2)
        sys.stdout.write("\n")
    elif sub == "write":
        write_from_disk(root)
    elif sub == "clear":
        clear_run(root)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Archie standalone sync — the Living Blueprint change ledger (Phase 1).

PHASE 1 — PRODUCE OUTPUT ONLY. `record` writes a versioned change file under
`.archie/changes/` capturing the diff plus the agent's harvested intent claims, each
classified `eligible` (would fold into the blueprint in Phase 2) or `staged`
(provisional). It writes NOTHING to blueprint.json or any CLAUDE.md — folding is Phase 2.

The intent payload is supplied by the in-session agent (via /archie-sync), which either
PROVIDES context it already holds or BUILDS it from `git diff`. This script is pure,
deterministic glue: it reads the diff, validates + classifies the claims, and records
them. No model calls, zero dependencies beyond Python 3.9+ stdlib.

Usage:
  python3 sync.py record /path/to/repo [--input payload.json] [--agent claude|codex] [--since <ref>]
  python3 sync.py list   /path/to/repo [--json]

Payload (JSON, from --input or stdin) — a list of claims, or {"claims": [...]}:
  { "type": "decision|rule|pitfall|guideline",
    "title": "short title",
    "rationale": "the why",
    "evidence_files": ["path/touched/by/the/change.kt"],
    "confidence": "low|medium|high",
    "reconstructed": false }

Output to stdout: a one-line JSON summary (detect-changes style).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent

# Claim types that map onto canonical blueprint sections.
_VALID_TYPES = {"decision", "rule", "pitfall", "guideline"}
_VALID_CONFIDENCE = {"low", "medium", "high"}
_CHANGES_DIR = "changes"


# ---------------------------------------------------------------------------
# small helpers (mirror existing stack conventions)
# ---------------------------------------------------------------------------

def _now_iso_short() -> str:
    """Match finalize.py's finding timestamp format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M")


def _slugify(value: str) -> str:
    """Mirror intent_layer._slugify."""
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return slug or "claim"


def _git(root: Path, *args: str) -> str:
    """Run a git command in `root`, return stripped stdout ('' on any failure)."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    except Exception:
        return ""


def _ancestors(changed: list[str]) -> list[str]:
    """Every ancestor folder of every changed file (mirrors detect-changes)."""
    folders: set[str] = set()
    for f in changed:
        parts = Path(f).parts
        for i in range(1, len(parts)):
            folders.add(str(Path(*parts[:i])))
    return sorted(folders)


# ---------------------------------------------------------------------------
# diff acquisition — reuse detect-changes; fall back to a direct git diff so the
# command is always testable even before a deep-scan baseline exists.
# ---------------------------------------------------------------------------

def _detect_changes(root: Path) -> dict:
    """Call `intent_layer.py deep-scan-state <root> detect-changes` and parse JSON."""
    intent_layer = _SCRIPT_DIR / "intent_layer.py"
    if not intent_layer.exists():
        return {"mode": "full", "reason": "intent_layer.py not found"}
    try:
        result = subprocess.run(
            [sys.executable, str(intent_layer), "deep-scan-state", str(root), "detect-changes"],
            capture_output=True, text=True, timeout=30,
        )
        return json.loads(result.stdout.strip() or "{}")
    except Exception as e:
        return {"mode": "full", "reason": f"detect-changes failed: {e}"}


def _fallback_diff(root: Path, since: str | None) -> list[str]:
    """Compute changed files directly when there's no deep-scan baseline.

    Precedence: explicit --since, else uncommitted working-tree changes, else the
    last commit (HEAD~1..HEAD). Keeps `record` usable on any repo for review.
    """
    if since:
        out = _git(root, "diff", "--name-only", f"{since}..HEAD")
        return [f for f in out.split("\n") if f]
    # uncommitted (staged + unstaged) vs HEAD
    out = _git(root, "diff", "--name-only", "HEAD")
    changed = [f for f in out.split("\n") if f]
    if changed:
        return changed
    # fall back to the last commit
    out = _git(root, "diff", "--name-only", "HEAD~1..HEAD")
    return [f for f in out.split("\n") if f]


def _resolve_diff(root: Path, since: str | None) -> dict:
    """Return {mode, changed_files, affected_folders, ratio} or {too_large:True,...}.

    Reuses detect-changes for the diff + the too-large guard; when detect-changes
    reports `full` only because no baseline exists, we still compute a diff so the
    user can produce reviewable output.
    """
    dc = _detect_changes(root)
    mode = dc.get("mode")
    reason = dc.get("reason", "")

    # Respect the real "too large" guard — do not record piecemeal.
    if mode == "full" and "exceeds threshold" in reason:
        return {"too_large": True, "reason": reason}

    if mode == "incremental" and dc.get("changed_files") is not None:
        return {
            "mode": "incremental",
            "changed_files": dc.get("changed_files", []),
            "affected_folders": dc.get("affected_folders", []),
            "ratio": dc.get("ratio", 0.0),
        }

    # No baseline (or other non-threshold full): compute the diff ourselves.
    changed = _fallback_diff(root, since)
    return {
        "mode": "incremental",
        "changed_files": changed,
        "affected_folders": _ancestors(changed),
        "ratio": 0.0,
    }


# ---------------------------------------------------------------------------
# claim validation + classification
# ---------------------------------------------------------------------------

def _read_payload(input_file: str | None) -> list[dict]:
    raw = Path(input_file).read_text() if input_file else sys.stdin.read()
    raw = raw.strip()
    if not raw:
        return []
    data = json.loads(raw)
    if isinstance(data, list):
        claims = data
    elif isinstance(data, dict):
        claims = data.get("claims") or data.get("intent_updates") or []
    else:
        raise ValueError("payload must be a JSON list or object")
    if not isinstance(claims, list):
        raise ValueError("`claims` must be a list")
    return claims


def _validate_claim(claim: object, idx: int) -> dict:
    if not isinstance(claim, dict):
        raise ValueError(f"claim #{idx} is not an object")
    ctype = claim.get("type") or claim.get("section")
    if ctype not in _VALID_TYPES:
        raise ValueError(f"claim #{idx}: type must be one of {sorted(_VALID_TYPES)}, got {ctype!r}")
    title = (claim.get("title") or "").strip()
    if not title:
        raise ValueError(f"claim #{idx}: missing title")
    confidence = claim.get("confidence", "low")
    if confidence not in _VALID_CONFIDENCE:
        raise ValueError(f"claim #{idx}: confidence must be one of {sorted(_VALID_CONFIDENCE)}")
    evidence = claim.get("evidence_files", [])
    if not isinstance(evidence, list):
        raise ValueError(f"claim #{idx}: evidence_files must be a list")
    return {
        "type": ctype,
        "title": title,
        "rationale": (claim.get("rationale") or "").strip(),
        "evidence_files": [str(e) for e in evidence],
        "confidence": confidence,
        "reconstructed": bool(claim.get("reconstructed", False)),
    }


def _evidence_in_diff(evidence_files: list[str], changed_files: list[str], affected: list[str]) -> bool:
    changed_set = set(changed_files)
    for ev in evidence_files:
        if ev in changed_set:
            return True
        if any(ev == f or ev.startswith(f + "/") for f in affected):
            return True
    return False


def _classify(claim: dict, changed_files: list[str], affected: list[str]) -> str:
    """eligible = confident + non-reconstructed + evidenced inside the diff; else staged."""
    if claim["reconstructed"]:
        return "staged"
    if claim["confidence"] not in ("medium", "high"):
        return "staged"
    if not _evidence_in_diff(claim["evidence_files"], changed_files, affected):
        return "staged"
    return "eligible"


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------

def _changes_dir(root: Path) -> Path:
    return root / ".archie" / _CHANGES_DIR


def _next_version(changes_dir: Path) -> int:
    if not changes_dir.is_dir():
        return 1
    existing = [f for f in changes_dir.iterdir()
                if f.name.startswith("change_") and f.name.endswith(".json")]
    return len(existing) + 1


def _unique_change_path(changes_dir: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base = changes_dir / f"change_{ts}.json"
    if not base.exists():
        return base
    i = 2
    while True:
        candidate = changes_dir / f"change_{ts}_{i}.json"
        if not candidate.exists():
            return candidate
        i += 1


def cmd_record(root: Path, input_file: str | None, agent: str, since: str | None) -> int:
    # 1. Read + validate the payload BEFORE touching disk (reject malformed wholesale).
    try:
        raw_claims = _read_payload(input_file)
        claims = [_validate_claim(c, i) for i, c in enumerate(raw_claims)]
    except (ValueError, json.JSONDecodeError, OSError) as e:
        print(json.dumps({"ok": False, "error": f"invalid payload: {e}"}))
        return 1

    # 2. Resolve the diff (reuse detect-changes; respect the too-large guard).
    diff = _resolve_diff(root, since)
    if diff.get("too_large"):
        print(json.dumps({
            "ok": False, "mode": "full",
            "reason": f"delta too large — run /archie-deep-scan ({diff['reason']})",
        }))
        return 0

    changed_files = diff["changed_files"]
    affected = diff["affected_folders"]

    # 3. Classify each claim (Phase 1: classify only, never fold).
    out_claims = []
    for c in claims:
        status = _classify(c, changed_files, affected)
        out_claims.append({
            "id": f"{c['type']}:{_slugify(c['title'])}",
            "section": c["type"],
            "status": status,
            "title": c["title"],
            "rationale": c["rationale"],
            "evidence_files": c["evidence_files"],
            "confidence": c["confidence"],
            "reconstructed": c["reconstructed"],
        })

    # 4. Provenance (reuse the save-baseline git pattern).
    sha = _git(root, "rev-parse", "HEAD")
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    record = {
        "version": None,  # filled below
        "id": f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{sha[:7] or 'nogit'}",
        "folded": False,  # Phase 1 never folds
        "provenance": {
            "created_at": _now_iso_short(),
            "git_head": sha,
            "branch": branch,
            "agent": agent,
            "reconstructed": any(c["reconstructed"] for c in claims),
        },
        "diff": {
            "mode": diff["mode"],
            "changed_files": changed_files,
            "affected_folders": affected,
            "ratio": diff["ratio"],
        },
        "claims": out_claims,
    }

    # 5. Write the versioned change file + latest.json (mirror drift._save_snapshot).
    changes_dir = _changes_dir(root)
    changes_dir.mkdir(parents=True, exist_ok=True)
    record["version"] = _next_version(changes_dir)
    path = _unique_change_path(changes_dir)
    path.write_text(json.dumps(record, indent=2))
    (changes_dir / "latest.json").write_text(json.dumps(record, indent=2))

    eligible = sum(1 for c in out_claims if c["status"] == "eligible")
    staged = sum(1 for c in out_claims if c["status"] == "staged")
    print(json.dumps({
        "ok": True,
        "id": record["id"],
        "version": record["version"],
        "branch": branch,
        "folded": False,
        "eligible": eligible,
        "staged": staged,
        "changed_count": len(changed_files),
        "path": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
    }))
    return 0


def cmd_list(root: Path, as_json: bool) -> int:
    changes_dir = _changes_dir(root)
    if not changes_dir.is_dir():
        print("No change ledger found (.archie/changes/).", file=sys.stderr)
        if as_json:
            print(json.dumps([]))
        return 0
    files = sorted(
        [f for f in changes_dir.iterdir()
         if f.name.startswith("change_") and f.name.endswith(".json")],
        key=lambda f: f.name,
    )
    entries = []
    for f in files:
        try:
            data = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        claims = data.get("claims", [])
        entries.append({
            "file": f.name,
            "version": data.get("version"),
            "created_at": data.get("provenance", {}).get("created_at", ""),
            "branch": data.get("provenance", {}).get("branch", ""),
            "folded": data.get("folded", False),
            "eligible": sum(1 for c in claims if c.get("status") == "eligible"),
            "staged": sum(1 for c in claims if c.get("status") == "staged"),
            "id": data.get("id", ""),
        })

    if not entries:
        print("No change records yet.", file=sys.stderr)
    else:
        print(f"\nChange ledger ({len(entries)} records):\n", file=sys.stderr)
        for e in entries:
            print(
                f"  v{e['version']:<3} {e['created_at']:<16} {e['branch']:<24} "
                f"eligible={e['eligible']} staged={e['staged']}  {e['file']}",
                file=sys.stderr,
            )
        print("", file=sys.stderr)
    print(json.dumps(entries, indent=2))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _usage() -> None:
    print("Usage:", file=sys.stderr)
    print("  python3 sync.py record /path/to/repo [--input payload.json] [--agent claude|codex] [--since <ref>]", file=sys.stderr)
    print("  python3 sync.py list   /path/to/repo [--json]", file=sys.stderr)


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        _usage()
        return 1
    cmd = argv[1]
    root = Path(argv[2]).resolve()
    rest = argv[3:]

    if cmd == "record":
        input_file = None
        agent = "unknown"
        since = None
        i = 0
        while i < len(rest):
            if rest[i] == "--input" and i + 1 < len(rest):
                input_file = rest[i + 1]; i += 2
            elif rest[i] == "--agent" and i + 1 < len(rest):
                agent = rest[i + 1]; i += 2
            elif rest[i] == "--since" and i + 1 < len(rest):
                since = rest[i + 1]; i += 2
            else:
                i += 1
        return cmd_record(root, input_file, agent, since)

    if cmd == "list":
        return cmd_list(root, "--json" in rest)

    _usage()
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

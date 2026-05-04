#!/usr/bin/env python3
"""Apply Haiku verifier verdicts to `.archie/findings.json` with cross-run
hysteresis.

Pipeline position:
    synthesis → finalize.py (initial merge) → verify_findings.py (verdicts.json)
                                                              → apply_verdicts.py (this script)

Reads:
    - .archie/findings.json   — the findings store, with per-entry status
    - .archie/verdicts.json   — verifier output: [{id, verdict, confidence, reason}]

Writes:
    - .archie/findings.json   — updated in place: status transitions applied,
                                verdict_history accumulated, drop/demote
                                routing applied.

Hysteresis rules — the system gains precision from the verifier without
trading temporal stability:

    promote (demoted → active):   needs 2 consecutive `keep` verdicts
                                  OR a git-diff anchor (a file in the
                                  finding's triggering_call_site has been
                                  changed in the last 5 commits)

    demote  (active → demoted):   needs 2 consecutive `demote` verdicts
                                  OR a git-diff anchor

    drop    (any → dropped):      immediate (high-confidence "premise
                                  unsound" verdict — re-emergence with new
                                  evidence reactivates)

    re-emerge (dropped → active): a single `keep` verdict reactivates
                                  (something changed in the corpus)

Single-scan flips that have no material code change behind them stay in
the prior status — kills LLM-noise flicker while letting real signal
through immediately when the diff confirms it.

Usage:
    python3 apply_verdicts.py /path/to/project
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

VERDICT_HISTORY_DEPTH = 3
GIT_DIFF_DEPTH = 5  # number of commits to scan for material-change anchor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso_short() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M")


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _git_recently_changed_files(project_root: Path, depth: int = GIT_DIFF_DEPTH) -> set[str]:
    """Files changed in the last N commits. Used as the material-change anchor
    that lets a finding transition state on a single scan instead of waiting
    for two consecutive matching verdicts."""
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", f"HEAD~{depth}..HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(project_root),
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return set()
    if proc.returncode != 0:
        return set()
    return {line.strip() for line in proc.stdout.splitlines() if line.strip()}


def _has_material_change(finding: dict, recent_files: set[str]) -> bool:
    """Does this finding cite a file that was changed in the recent diff window?

    The material-change anchor lets us promote/demote on a single verdict
    when there's an obvious code-level reason for the transition (vs.
    LLM-flake-driven noise on unchanged code).
    """
    if not recent_files:
        return False
    tcs = finding.get("triggering_call_site") or ""
    # First line of triggering_call_site is conventionally `<path>:<line>`.
    first_line = tcs.split("\n", 1)[0].strip()
    file_part = first_line.split(":")[0].strip()
    if file_part and file_part in recent_files:
        return True
    for at in finding.get("applies_to") or []:
        if isinstance(at, str) and at.strip() in recent_files:
            return True
    return False


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

def _two_consecutive(history: list[str], wanted: str) -> bool:
    return len(history) >= 2 and history[0] == wanted and history[1] == wanted


def _apply_one(finding: dict, verdict: dict, recent_files: set[str], now: str) -> dict:
    """Apply one verdict + hysteresis to one finding entry. Returns the
    updated entry (does not mutate the input).

    Schema additions populated here:
      - verdict_history: list[str] (newest first, max length 3)
      - last_verdict_reason: str
      - last_verdict_confidence: float
      - status: extended values "demoted" and "dropped" beyond existing
                "active"/"resolved"
      - demoted_at / dropped_at: timestamps when those transitions fire
      - pending_demotion / pending_promotion: bool flags set when a single
                verdict pushed toward the transition but hysteresis held
                it back; cleared once the transition completes or reverses
    """
    out = dict(finding)
    v = verdict.get("verdict", "keep")

    # Accumulate verdict_history (newest first, capped).
    prior_history = finding.get("verdict_history") or []
    history = ([v] + list(prior_history))[:VERDICT_HISTORY_DEPTH]
    out["verdict_history"] = history
    out["last_verdict_reason"] = verdict.get("reason") or ""
    out["last_verdict_confidence"] = verdict.get("confidence", 0.0)

    prior_status = finding.get("status") or "active"

    # Drop is fast-path: no hysteresis. The verifier said the finding's
    # premise is unsound for this codebase. Re-emerge later by re-emitting
    # with new evidence (which lands as a fresh `keep` and flips back
    # below).
    if v == "drop":
        if prior_status != "dropped":
            out["status"] = "dropped"
            out["dropped_at"] = now
            out.pop("pending_demotion", None)
            out.pop("pending_promotion", None)
        return out

    # Re-emergence: a previously-dropped finding that the verifier now
    # confirms is real. Reactivate.
    if prior_status == "dropped" and v == "keep":
        out["status"] = "active"
        out.pop("dropped_at", None)
        return out

    # Resolved is sticky unless the verifier says the failure mode is
    # firing again (keep), in which case treat as re-emergence.
    if prior_status == "resolved":
        if v == "keep":
            out["status"] = "active"
        return out

    material = _has_material_change(out, recent_files)

    if prior_status == "active":
        if v == "demote":
            # Promote demotion only on hysteresis or material change. A
            # single demote verdict on unchanged code is suspect (LLM
            # flake) — record it in history but don't transition.
            if material or _two_consecutive(history, "demote"):
                out["status"] = "demoted"
                out["demoted_at"] = now
                out.pop("pending_demotion", None)
            else:
                out["status"] = "active"
                out["pending_demotion"] = True
        else:
            # keep — clear any pending demotion flag, stay active.
            out["status"] = "active"
            out.pop("pending_demotion", None)
        return out

    if prior_status == "demoted":
        if v == "keep":
            if material or _two_consecutive(history, "keep"):
                out["status"] = "active"
                out.pop("demoted_at", None)
                out.pop("pending_promotion", None)
            else:
                out["status"] = "demoted"
                out["pending_promotion"] = True
        else:
            # demote again — confirm demotion, clear any pending flag.
            out["status"] = "demoted"
            out.pop("pending_promotion", None)
        return out

    # Unknown prior status: default to active treatment.
    out["status"] = "active"
    return out


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def apply_verdicts(archie_dir: Path) -> dict:
    """Read findings.json + verdicts.json, apply hysteresis, write
    findings.json in place. Returns a summary dict for logging."""
    findings_path = archie_dir / "findings.json"
    verdicts_path = archie_dir / "verdicts.json"

    if not findings_path.exists():
        return {"status": "skipped", "reason": "no findings.json"}
    if not verdicts_path.exists():
        return {"status": "skipped", "reason": "no verdicts.json — verifier hasn't run"}

    findings_store = _read_json(findings_path)
    verdicts_store = _read_json(verdicts_path)

    findings = findings_store.get("findings") or []
    verdicts_list = verdicts_store.get("verdicts") or []
    by_id: dict[str, dict] = {
        v["id"]: v for v in verdicts_list
        if isinstance(v, dict) and v.get("id")
    }

    if not by_id:
        return {"status": "skipped", "reason": "no verdicts to apply"}

    project_root = archie_dir.parent
    recent_files = _git_recently_changed_files(project_root)
    now = _now_iso_short()

    # Counters for the run summary.
    counts = {
        "applied": 0,
        "no_verdict": 0,
        "kept_active": 0,
        "kept_demoted": 0,
        "promoted": 0,
        "demoted": 0,
        "dropped": 0,
        "re_emerged": 0,
        "pending_demotion": 0,
        "pending_promotion": 0,
    }

    updated: list[dict] = []
    for f in findings:
        if not isinstance(f, dict):
            updated.append(f)
            continue
        fid = f.get("id")
        verdict = by_id.get(fid) if fid else None
        if not verdict:
            updated.append(f)
            counts["no_verdict"] += 1
            continue

        prior_status = f.get("status") or "active"
        new_state = _apply_one(f, verdict, recent_files, now)
        new_status = new_state.get("status") or "active"
        updated.append(new_state)
        counts["applied"] += 1

        # Classify the transition for the summary.
        if new_state.get("dropped_at") and prior_status != "dropped":
            counts["dropped"] += 1
        elif prior_status == "dropped" and new_status == "active":
            counts["re_emerged"] += 1
        elif prior_status == "active" and new_status == "demoted":
            counts["demoted"] += 1
        elif prior_status == "demoted" and new_status == "active":
            counts["promoted"] += 1
        elif new_status == "active":
            counts["kept_active"] += 1
            if new_state.get("pending_demotion"):
                counts["pending_demotion"] += 1
        elif new_status == "demoted":
            counts["kept_demoted"] += 1
            if new_state.get("pending_promotion"):
                counts["pending_promotion"] += 1

    findings_store["findings"] = updated
    findings_store["verdicts_applied_at"] = now
    findings_path.write_text(json.dumps(findings_store, indent=2))

    return {"status": "applied", "summary": counts}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply verify_findings.py verdicts to .archie/findings.json with cross-run hysteresis."
    )
    parser.add_argument("project_root", type=Path,
                        help="Project root (parent of .archie/).")
    args = parser.parse_args()

    archie_dir = args.project_root / ".archie"
    if not archie_dir.is_dir():
        print(f"apply_verdicts: {archie_dir} does not exist; nothing to do.", file=sys.stderr)
        return 1

    result = apply_verdicts(archie_dir)
    if result.get("status") == "skipped":
        print(f"apply_verdicts: skipped — {result.get('reason')}")
        return 0

    summary = result.get("summary") or {}
    print(f"apply_verdicts: applied {summary.get('applied', 0)} verdict(s) "
          f"({summary.get('no_verdict', 0)} unmatched).")
    print("  transitions:")
    for k in ("kept_active", "kept_demoted", "promoted", "demoted", "dropped",
              "re_emerged", "pending_demotion", "pending_promotion"):
        if summary.get(k):
            print(f"    {k:<22} {summary[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

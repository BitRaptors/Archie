"""Diff basis: pick the base ref and list branch-introduced files.

Mirrors the well-known local ladder: --base -> gh pr view -> git remote HEAD ->
main. `run` is injectable so the ladder is unit-testable without git.
"""
from __future__ import annotations
import subprocess
from pathlib import Path

def _out(run, argv):
    try:
        r = run(argv, capture_output=True, text=True)
        return (r.stdout or "").strip(), r.returncode
    except Exception:
        return "", 1

def detect_base(root: Path, explicit: str | None = None, run=subprocess.run) -> str:
    if explicit:
        return explicit
    out, code = _out(run, ["gh", "pr", "view", "--json", "baseRefName", "-q", ".baseRefName"])
    if code == 0 and out:
        return out
    out, code = _out(run, ["git", "-C", str(root), "symbolic-ref", "refs/remotes/origin/HEAD"])
    if code == 0 and out:
        return out.rsplit("/", 1)[-1]
    return "main"

def changed_files(root: Path, base: str, run=subprocess.run) -> list[str]:
    mb, code = _out(run, ["git", "-C", str(root), "merge-base", "HEAD", base])
    ref = mb if code == 0 and mb else base
    out, code = _out(run, ["git", "-C", str(root), "diff", "--name-only", ref])
    return [ln for ln in out.splitlines() if ln.strip()]

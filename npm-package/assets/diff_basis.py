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

def _is_safe_ref(ref: str) -> bool:
    """Return True iff `ref` is a non-empty string that does not start with '-'.

    Git CLI parses bare arguments starting with '-' as options, so passing such
    a value as a positional ref is an argument-injection vector.
    """
    return bool(ref) and not ref.startswith("-")

def detect_base(root: Path, explicit: str | None = None, run=subprocess.run) -> str:
    if explicit:
        # Reject any explicit base that looks like a CLI option to prevent
        # argument injection (e.g. "--output=/tmp/x" would be parsed by git).
        if not _is_safe_ref(explicit):
            pass  # fall through to auto-detection
        else:
            return explicit
    out, code = _out(run, ["gh", "pr", "view", "--json", "baseRefName", "-q", ".baseRefName"])
    if code == 0 and out and _is_safe_ref(out):
        return out
    out, code = _out(run, ["git", "-C", str(root), "symbolic-ref", "refs/remotes/origin/HEAD"])
    if code == 0 and out:
        branch = out.rsplit("/", 1)[-1]
        if _is_safe_ref(branch):
            return branch
    return "main"


def changed_files_result(root: Path, base: str, run=subprocess.run) -> dict:
    """List files changed relative to `base`, with a structured result.

    Returns a dict:
      {
        "files": [...],          # list of changed file paths (may be empty)
        "ok": bool,              # False if git failed or ref was invalid
        "reason": str,           # "ok" | "git_error" | "invalid_ref"
      }

    `base` is validated with `_is_safe_ref` before use to prevent argument
    injection. If the ref starts with '-', the call is refused immediately.
    """
    if not _is_safe_ref(base):
        return {"files": [], "ok": False, "reason": "invalid_ref"}

    # Validate the base ref with git rev-parse before using it in merge-base
    # (merge-base has no '--' separator for refs, so we must validate first).
    _, parse_code = _out(run, ["git", "-C", str(root), "rev-parse", "--verify", "--quiet", base])

    mb_ref: str
    if parse_code == 0:
        mb, mb_code = _out(run, ["git", "-C", str(root), "merge-base", "HEAD", base])
        if mb_code == 0 and mb and _is_safe_ref(mb):
            mb_ref = mb
        else:
            mb_ref = base
    else:
        # base ref doesn't validate — still try using it directly, but track error
        mb, mb_code = _out(run, ["git", "-C", str(root), "merge-base", "HEAD", base])
        if mb_code == 0 and mb and _is_safe_ref(mb):
            mb_ref = mb
        else:
            # Neither base nor merge-base resolved — git error
            return {"files": [], "ok": False, "reason": "git_error"}

    # Pass '--' after the ref so git treats it as an end-of-options marker,
    # preventing the ref from being parsed as an option.
    out, diff_code = _out(run, ["git", "-C", str(root), "diff", "--name-only", mb_ref, "--"])
    if diff_code != 0:
        return {"files": [], "ok": False, "reason": "git_error"}

    files = [ln for ln in out.splitlines() if ln.strip()]
    return {"files": files, "ok": True, "reason": "ok"}


def changed_files(root: Path, base: str, run=subprocess.run) -> list[str]:
    """Return list of files changed relative to `base` (back-compat wrapper).

    Returns an empty list both when there are no changes AND when git fails.
    Use `changed_files_result` to distinguish the two cases.
    """
    return changed_files_result(root, base, run=run)["files"]

"""Diff basis: pick the base ref and list branch-introduced files.

Mirrors the well-known local ladder: --base -> gh pr view -> git remote HEAD ->
main. `run` is injectable so the ladder is unit-testable without git.
"""
from __future__ import annotations
import re
import subprocess
from pathlib import Path

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

# Generated/managed artifacts that are not source code. Excluded from the reviewed
# diff so the code reviewer anchors findings to real source, not Archie's own snapshot
# files (blueprint.json, per-folder CLAUDE.md, change records, hooks, settings).
_REVIEW_EXCLUDE = [
    ":(exclude).archie",
    ":(exclude).claude",
    ":(exclude,glob)**/CLAUDE.md",
    ":(exclude)AGENTS.md",
]


def review_pathspec() -> list[str]:
    """Pathspec args (placed after '--') restricting a diff to reviewable source:
    the whole tree minus generated Archie/agent artifacts."""
    return [".", *_REVIEW_EXCLUDE]


def parse_hunk_added_lines(diff_text: str) -> dict:
    """Parse a `git diff -U0` (or any unified diff) into added-line numbers.

    Returns dict[str, set[int]] mapping each changed file path to the set of
    line numbers added on the `+` side. Pure — no I/O — so it's unit-testable
    without git. Handles multiple hunks/files; tolerates a malformed diff by
    skipping lines it can't parse.

    We track the current file from the `+++ b/<path>` header and, for each
    `@@ ... +c,d @@` hunk, walk the body counting only added ('+') lines to
    assign real line numbers (a `+c,d` hunk header alone gives the start, but
    context/deletions inside a -U0 diff are absent, so counting `+` lines is
    exact for -U0 and best-effort otherwise).
    """
    result: dict = {}
    current: str | None = None
    cur_line = 0
    in_hunk = False
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            # Strip a leading "b/" (git prefix); "/dev/null" means a deletion.
            if path.startswith("b/"):
                path = path[2:]
            current = None if path == "/dev/null" else path
            in_hunk = False
            continue
        m = _HUNK_RE.match(line)
        if m:
            cur_line = int(m.group(1))
            in_hunk = True
            continue
        if not in_hunk or current is None:
            continue
        if line.startswith("+"):
            result.setdefault(current, set()).add(cur_line)
            cur_line += 1
        elif line.startswith("-"):
            # deletion — does not advance the +side line counter
            continue
        elif line.startswith(" "):
            # context line — advances the +side counter (rare under -U0)
            cur_line += 1
        else:
            # diff metadata (index/--- lines etc.) — leave hunk state as-is
            continue
    return result


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
    out, diff_code = _out(run, ["git", "-C", str(root), "diff", "--name-only", mb_ref, "--",
                                *review_pathspec()])
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

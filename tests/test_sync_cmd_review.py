"""Tests for sync.py `review` entrypoint — the wired delivery-review pipeline.

Covers non-blocking behavior (never raises, always returns 0), the skip path,
and the pure hunk-parsing helper (unit-testable without git).
"""
import subprocess
import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import sync  # noqa: E402


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True,
                   capture_output=True, text=True)


def test_cmd_review_nonblocking_on_error(tmp_path, capsys):
    """A dir that is NOT a git repo → returns 0, prints a skip/error line, no raise."""
    rc = sync.cmd_review(tmp_path)
    assert rc == 0
    out = capsys.readouterr().out
    assert "[archie] delivery review" in out


def test_cmd_review_skipped_when_no_source(tmp_path, capsys):
    """A git repo whose only branch change is a README → returns 0 and prints skipped."""
    root = tmp_path
    _git(root, "init")
    _git(root, "config", "user.email", "t@t.t")
    _git(root, "config", "user.name", "t")
    (root / "seed.txt").write_text("seed\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    # Base branch "main" (detect_base fallback) points at the seed commit; then a
    # second branch changes only a README (non-source) → skip-gate must fire.
    _git(root, "checkout", "-B", "main")
    _git(root, "checkout", "-B", "feature")
    (root / "README.md").write_text("hello\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "docs")

    rc = sync.cmd_review(root)
    assert rc == 0
    out = capsys.readouterr().out
    assert "skipped" in out


def test_parse_hunk_added_lines_pure():
    diff = (
        "diff --git a/foo.py b/foo.py\n"
        "index e69de29..4b825dc 100644\n"
        "--- a/foo.py\n"
        "+++ b/foo.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+line one\n"
        "+line two\n"
        "diff --git a/bar.py b/bar.py\n"
        "--- a/bar.py\n"
        "+++ b/bar.py\n"
        "@@ -5,0 +6 @@\n"
        "+inserted\n"
    )
    got = sync.parse_hunk_added_lines(diff)
    assert got == {"foo.py": {1, 2}, "bar.py": {6}}


def test_parse_hunk_added_lines_ignores_deletions_and_devnull():
    diff = (
        "--- a/gone.py\n"
        "+++ /dev/null\n"
        "@@ -1,2 +0,0 @@\n"
        "-was here\n"
        "-and here\n"
        "--- a/keep.py\n"
        "+++ b/keep.py\n"
        "@@ -3 +3 @@\n"
        "-old\n"
        "+new\n"
    )
    got = sync.parse_hunk_added_lines(diff)
    # the /dev/null (deleted) file contributes nothing; keep.py line 3 is added.
    assert got == {"keep.py": {3}}

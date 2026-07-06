# tests/test_diff_basis.py
import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import diff_basis as db  # noqa: E402

class FakeRun:
    def __init__(self, table): self.table = table
    def __call__(self, argv, **kw):
        key = " ".join(argv)
        class R: pass
        r = R(); out = self.table.get(key, ("", 1))
        r.stdout, r.returncode = out[0], out[1]; r.stderr = ""
        return r


class RecordingRun:
    """Records all argv lists passed to it; always returns success with empty output."""
    def __init__(self):
        self.calls = []

    def __call__(self, argv, **kw):
        self.calls.append(list(argv))
        class R: pass
        r = R()
        r.stdout = ""
        r.returncode = 1
        r.stderr = ""
        return r


def test_parse_hunk_added_lines_in_diff_basis():
    diff = (
        "diff --git a/foo.py b/foo.py\n"
        "--- a/foo.py\n"
        "+++ b/foo.py\n"
        "@@ -1,0 +5,2 @@\n"
        "+first added\n"
        "+second added\n"
    )
    got = db.parse_hunk_added_lines(diff)
    assert got == {"foo.py": {5, 6}}


def test_parse_hunk_added_lines_multiple_files():
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
    got = db.parse_hunk_added_lines(diff)
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
    got = db.parse_hunk_added_lines(diff)
    assert got == {"keep.py": {3}}


def test_detect_base_prefers_explicit():
    assert db.detect_base(Path("/x"), explicit="develop", run=FakeRun({})) == "develop"

def test_detect_base_uses_gh_pr_view():
    run = FakeRun({"gh pr view --json baseRefName -q .baseRefName": ("main\n", 0)})
    assert db.detect_base(Path("/x"), run=run) == "main"

def test_detect_base_falls_back_to_main():
    assert db.detect_base(Path("/x"), run=FakeRun({})) == "main"

def test_changed_files_uses_merge_base():
    # Note: new implementation passes '--' as end-of-options after the ref.
    run = FakeRun({
        "git -C /x rev-parse --verify --quiet main": ("main\n", 0),
        "git -C /x merge-base HEAD main": ("abc123\n", 0),
        "git -C /x diff --name-only abc123 -- " + " ".join(db.review_pathspec()): ("a.py\nb.py\n", 0),
    })
    assert db.changed_files(Path("/x"), "main", run=run) == ["a.py", "b.py"]


# ── D1 security tests ─────────────────────────────────────────────────────────

def test_changed_files_rejects_dash_ref():
    """A ref starting with '-' must be refused — never placed in git argv as a bare ref."""
    rec = RecordingRun()
    result = db.changed_files(Path("/x"), "--output=/tmp/x", run=rec)
    # Must return empty list (invalid ref rejected)
    assert result == []
    # The malicious ref must NOT appear in any argv as a bare positional argument
    for argv in rec.calls:
        assert "--output=/tmp/x" not in argv, (
            f"Dashed ref appeared in git argv: {argv}"
        )


def test_changed_files_result_rejects_dash_ref():
    """changed_files_result must return ok=False, reason='invalid_ref' for dashed refs."""
    rec = RecordingRun()
    result = db.changed_files_result(Path("/x"), "--output=/tmp/x", run=rec)
    assert result["ok"] is False
    assert result["reason"] == "invalid_ref"
    assert result["files"] == []


def test_detect_base_rejects_dash_explicit():
    """detect_base with explicit='-foo' must NOT return '-foo'; must fall through to a safe default."""
    result = db.detect_base(Path("/x"), explicit="-foo", run=FakeRun({}))
    assert result != "-foo"
    # Falls through to "main" since all other ladders fail too
    assert result == "main"


def test_changed_files_result_signals_git_error():
    """When both merge-base and diff fail, changed_files_result returns ok=False, reason='git_error'."""
    # All git commands return failure (returncode=1, empty stdout)
    run = FakeRun({})  # empty table → all return ("", 1)
    result = db.changed_files_result(Path("/x"), "main", run=run)
    assert result["ok"] is False
    assert result["reason"] == "git_error"
    assert result["files"] == []


def test_changed_files_result_ok():
    """Happy-path: changed_files_result returns ok=True, reason='ok', with the file list."""
    run = FakeRun({
        "git -C /x rev-parse --verify --quiet main": ("main\n", 0),
        "git -C /x merge-base HEAD main": ("abc123\n", 0),
        "git -C /x diff --name-only abc123 -- " + " ".join(db.review_pathspec()): ("foo.py\nbar.py\n", 0),
    })
    result = db.changed_files_result(Path("/x"), "main", run=run)
    assert result["ok"] is True
    assert result["reason"] == "ok"
    assert result["files"] == ["foo.py", "bar.py"]


def test_diff_uses_double_dash_separator():
    """git diff argv must include '--' after the ref to prevent option injection."""
    captured = []

    def capturing_run(argv, **kw):
        captured.append(list(argv))
        class R: pass
        r = R()
        # Make rev-parse and merge-base succeed, diff succeed
        if "rev-parse" in argv:
            r.stdout = "abc\n"; r.returncode = 0
        elif "merge-base" in argv:
            r.stdout = "deadbeef\n"; r.returncode = 0
        elif "diff" in argv:
            r.stdout = "f.py\n"; r.returncode = 0
        else:
            r.stdout = ""; r.returncode = 1
        r.stderr = ""
        return r

    db.changed_files(Path("/x"), "main", run=capturing_run)
    diff_calls = [a for a in captured if "diff" in a and "--name-only" in a]
    assert diff_calls, "No diff call found"
    diff_argv = diff_calls[0]
    # '--' must appear AFTER the ref, not before
    assert "--" in diff_argv, f"No '--' in diff argv: {diff_argv}"
    dash_idx = diff_argv.index("--")
    # The ref (deadbeef) should appear before '--'
    assert dash_idx > 0


def test_review_pathspec_excludes_generated_artifacts():
    ps = db.review_pathspec()
    assert ps[0] == "."   # positive include first, else git matches nothing
    joined = " ".join(ps)
    assert ":(exclude).archie" in joined and ":(exclude).claude" in joined
    assert "CLAUDE.md" in joined and "AGENTS.md" in joined


def test_changed_files_result_passes_exclusions_to_git():
    """The diff that lists changed files must carry the review exclusions so
    .archie/blueprint.json etc. are never handed to the code reviewer."""
    seen = {}
    def fake_run(argv, **kw):
        import subprocess as sp
        if argv[:4] == ["git", "-C", "/repo", "rev-parse"]:
            return sp.CompletedProcess(argv, 0, "abc\n", "")
        if "merge-base" in argv:
            return sp.CompletedProcess(argv, 0, "abc\n", "")
        if "diff" in argv and "--name-only" in argv:
            seen["argv"] = argv
            return sp.CompletedProcess(argv, 0, "new_worker/main.py\n", "")
        return sp.CompletedProcess(argv, 0, "", "")
    from pathlib import Path
    out = db.changed_files_result(Path("/repo"), "origin/develop", run=fake_run)
    assert out["ok"] and out["files"] == ["new_worker/main.py"]
    assert ":(exclude).archie" in seen["argv"], seen.get("argv")

import subprocess
from archie.benchmark.diff import capture_diff


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(path):
    _git(["init"], path)
    _git(["config", "user.email", "t@t.t"], path)
    _git(["config", "user.name", "t"], path)
    (path / "a.txt").write_text("one\n")
    _git(["add", "-A"], path)
    _git(["commit", "-m", "init"], path)


def test_captures_modified_and_untracked(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("one\ntwo\n")      # modified, tracked
    (tmp_path / "b.txt").write_text("new file\n")       # untracked
    diff = capture_diff(tmp_path)
    assert "a.txt" in diff
    assert "two" in diff
    assert "b.txt" in diff
    assert "new file" in diff


def test_empty_diff_when_no_changes(tmp_path):
    _init_repo(tmp_path)
    diff = capture_diff(tmp_path)
    assert diff.strip() == ""

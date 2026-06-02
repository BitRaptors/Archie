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


def test_excludes_build_and_cache_noise(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "calc.py").write_text("def f():\n    return 1\n")   # real change
    # universal build/cache noise (no .gitignore in this repo):
    pyc_dir = tmp_path / "__pycache__"
    pyc_dir.mkdir()
    (pyc_dir / "calc.cpython-311.pyc").write_text("BYTECODE")
    (tmp_path / ".DS_Store").write_text("junk")
    nm = tmp_path / "node_modules" / "left-pad"
    nm.mkdir(parents=True)
    (nm / "index.js").write_text("module.exports = 1\n")

    diff = capture_diff(tmp_path)
    # real source change is present
    assert "calc.py" in diff
    # noise is excluded
    assert "__pycache__" not in diff
    assert "calc.cpython-311.pyc" not in diff
    assert ".DS_Store" not in diff
    assert "node_modules" not in diff


def test_still_includes_plain_untracked(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "b.txt").write_text("new file\n")
    diff = capture_diff(tmp_path)
    assert "b.txt" in diff

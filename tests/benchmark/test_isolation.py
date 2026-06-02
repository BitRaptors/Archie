# tests/benchmark/test_isolation.py
import subprocess
from pathlib import Path
from archie.benchmark.isolation import worktree, prune


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(path):
    _git(["init"], path)
    _git(["config", "user.email", "t@t.t"], path)
    _git(["config", "user.name", "t"], path)
    (path / "a.txt").write_text("one\n")
    _git(["add", "-A"], path)
    _git(["commit", "-m", "init"], path)
    _git(["branch", "feature"], path)


def test_worktree_created_and_removed(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    dest = tmp_path / "wt"
    with worktree(repo, "feature", dest) as wt:
        assert Path(wt).exists()
        assert (Path(wt) / "a.txt").exists()
    assert not Path(dest).exists()


def test_worktree_removed_on_exception(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    dest = tmp_path / "wt"
    try:
        with worktree(repo, "feature", dest):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert not Path(dest).exists()


def test_prune_runs_without_error(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    prune(repo)  # must not raise

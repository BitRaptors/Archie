# archie/benchmark/isolation.py
import subprocess
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def worktree(repo_path, branch, dest):
    """Create a git worktree for `branch` at `dest`, always removed on exit."""
    dest = Path(dest)
    subprocess.run(["git", "worktree", "add", "--force", str(dest), branch],
                   cwd=str(repo_path), check=True, capture_output=True, text=True)
    try:
        yield dest
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(dest)],
                       cwd=str(repo_path), capture_output=True, text=True)


def prune(repo_path):
    subprocess.run(["git", "worktree", "prune"],
                   cwd=str(repo_path), capture_output=True, text=True)

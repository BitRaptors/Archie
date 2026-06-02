import subprocess


def capture_diff(worktree_path):
    """Stage everything (so untracked files show) and return the cached diff text."""
    subprocess.run(["git", "add", "-A"], cwd=str(worktree_path),
                   check=True, capture_output=True, text=True)
    result = subprocess.run(["git", "diff", "--cached"], cwd=str(worktree_path),
                            check=True, capture_output=True, text=True)
    return result.stdout

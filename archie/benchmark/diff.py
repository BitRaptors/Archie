import subprocess

# Build/cache artifacts that are never meaningful for code review. These are
# excluded from the captured diff so the judge scores only real source changes,
# even when the target repo lacks a .gitignore for them (the agent may create
# them as a side effect of running tests). Patterns use git pathspec wildcards
# (`*` matches across `/`), so `*X*` catches X at any depth.
_NOISE_GLOBS = [
    "*__pycache__*",
    "*.pyc",
    "*.pyo",
    "*.DS_Store",
    "*node_modules*",
    "*.pytest_cache*",
    "*.mypy_cache*",
    "*.ruff_cache*",
]


def capture_diff(worktree_path):
    """Stage everything (so untracked files show) and return the cached diff text,
    excluding universal build/cache artifacts (see _NOISE_GLOBS)."""
    subprocess.run(["git", "add", "-A"], cwd=str(worktree_path),
                   check=True, capture_output=True, text=True)
    excludes = [f":(exclude){glob}" for glob in _NOISE_GLOBS]
    result = subprocess.run(
        ["git", "diff", "--cached", "--", ".", *excludes],
        cwd=str(worktree_path), check=True, capture_output=True, text=True)
    return result.stdout

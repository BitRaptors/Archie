"""detect-changes must honor .archieignore.

`git diff --name-only` lists tracked files even when .archieignore'd (git only
knows .gitignore), so without filtering, vendored/generated paths would both
inflate the incremental threshold and get fed to the Risk agent's recency
sweep, which reads every listed file. The retired drift step filtered its
git-log list through the ignore system (filter-ignored); detect-changes is the
replacement source and must apply the same semantics.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

INTENT = str(
    Path(__file__).resolve().parent.parent / "archie" / "standalone" / "intent_layer.py"
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), "-c", "commit.gpgsign=false", *args],
        check=True,
        capture_output=True,
    )


def test_detect_changes_filters_archieignored_paths(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@test.invalid")
    _git(tmp_path, "config", "user.name", "test")

    (tmp_path / "src").mkdir()
    (tmp_path / "vendor").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('v1')\n")
    (tmp_path / "vendor" / "lib.py").write_text("print('v1')\n")
    (tmp_path / ".archieignore").write_text("vendor/\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "baseline")
    sha = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    archie = tmp_path / ".archie"
    archie.mkdir()
    (archie / "last_deep_scan.json").write_text(json.dumps({"commit_sha": sha}))
    (archie / "scan.json").write_text(
        json.dumps({"file_tree": [{"path": f"f{i}.py"} for i in range(50)]})
    )

    (tmp_path / "src" / "app.py").write_text("print('v2')\n")
    (tmp_path / "vendor" / "lib.py").write_text("print('v2')\n")
    # add only the source dirs — .archie/ tool state stays untracked, as in a
    # default install (the generated .gitignore excludes tool internals)
    _git(tmp_path, "add", "src", "vendor")
    _git(tmp_path, "commit", "-q", "-m", "changes")

    out = subprocess.run(
        [sys.executable, INTENT, "deep-scan-state", str(tmp_path), "detect-changes"],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    assert data["mode"] == "incremental"
    # vendor/lib.py changed too, but it's .archieignore'd — only src/app.py
    # may reach the changed list (and thus the recency sweep).
    assert data["changed_files"] == ["src/app.py"]

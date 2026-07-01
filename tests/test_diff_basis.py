# tests/test_diff_basis.py
from pathlib import Path
import archie.standalone.diff_basis as db

class FakeRun:
    def __init__(self, table): self.table = table
    def __call__(self, argv, **kw):
        key = " ".join(argv)
        class R: pass
        r = R(); out = self.table.get(key, ("", 1))
        r.stdout, r.returncode = out[0], out[1]; r.stderr = ""
        return r

def test_detect_base_prefers_explicit():
    assert db.detect_base(Path("/x"), explicit="develop", run=FakeRun({})) == "develop"

def test_detect_base_uses_gh_pr_view():
    run = FakeRun({"gh pr view --json baseRefName -q .baseRefName": ("main\n", 0)})
    assert db.detect_base(Path("/x"), run=run) == "main"

def test_detect_base_falls_back_to_main():
    assert db.detect_base(Path("/x"), run=FakeRun({})) == "main"

def test_changed_files_uses_merge_base():
    run = FakeRun({
        "git -C /x merge-base HEAD main": ("abc123\n", 0),
        "git -C /x diff --name-only abc123": ("a.py\nb.py\n", 0),
    })
    assert db.changed_files(Path("/x"), "main", run=run) == ["a.py", "b.py"]

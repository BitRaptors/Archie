import subprocess, sys, json
from pathlib import Path


def test_check_rules_skips_ignored_files(tmp_path):
    # An ignored vendored file that would otherwise trip a rule must not be walked.
    # Use a dir name NOT already in SKIP_DIRS so the test exercises IgnoreMatcher,
    # not the built-in skip list.
    (tmp_path / ".archieignore").write_text("thirdparty/\n")
    (tmp_path / "thirdparty").mkdir()
    (tmp_path / "thirdparty" / "huge.py").write_text("x = 1\n")
    (tmp_path / "app.py").write_text("y = 2\n")
    from importlib import import_module
    sys.path.insert(0, "archie/standalone")
    cr = import_module("check_rules")
    walked = {rel for rel, _ in cr._walk_source_files(tmp_path)}
    assert "app.py" in walked
    assert "thirdparty/huge.py" not in walked

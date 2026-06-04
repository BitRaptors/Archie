"""Tests for scanner comprehensive depth (archie/standalone/scanner.py).

Targets the zero-dependency standalone scanner (NOT archie.engine.scanner).
Imported via sys.path so no pydantic/click is required.
"""
import sys
from importlib import import_module

sys.path.insert(0, "archie/standalone")
scanner = import_module("scanner")


def test_run_scan_accepts_comprehensive_param():
    """The comprehensive kwarg must exist on run_scan (guards the API)."""
    import inspect
    sig = inspect.signature(scanner.run_scan)
    assert "comprehensive" in sig.parameters


def test_comprehensive_reads_bulk_and_full_depth(tmp_path):
    # A bulk-tagged generated file present and deep nesting.
    (tmp_path / "a/b/c/d").mkdir(parents=True)
    (tmp_path / "a/b/c/d/deep.py").write_text("import os\n")
    (tmp_path / "gen").mkdir()
    (tmp_path / "gen" / "x.min.js").write_text("var a=1")
    (tmp_path / ".archiebulk").write_text("**/*.min.js  generated  bundler\n")

    default_scan = scanner.run_scan(str(tmp_path))
    comp_scan = scanner.run_scan(str(tmp_path), comprehensive=True)

    # The bulk file is always TAGGED in file_tree (classification runs in both
    # depths for ratios); the behavioral difference is whether it is READ.
    # file_hashes is built from readable_files, so it is the observable signal:
    #   default      -> bulk file gated out, not hashed
    #   comprehensive -> bulk read-ban lifted, file is hashed
    assert "gen/x.min.js" not in default_scan["file_hashes"]
    assert "gen/x.min.js" in comp_scan["file_hashes"]

    # The deeply-nested file is read in both depths (it is not bulk), but it
    # confirms the deep tree is reachable regardless of the dep-depth cap.
    assert "a/b/c/d/deep.py" in default_scan["file_hashes"]
    assert "a/b/c/d/deep.py" in comp_scan["file_hashes"]

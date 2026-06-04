def test_current_hashes_skips_ignored(tmp_path):
    import sys
    # Use a dir NOT in refresh's hardcoded SKIP_DIRS, so the test genuinely
    # exercises the ignore system (vendor/ is already in SKIP_DIRS → false pass).
    (tmp_path / ".archieignore").write_text("thirdparty/\n")
    (tmp_path / "thirdparty").mkdir()
    (tmp_path / "thirdparty" / "lib.py").write_text("a = 1\n")
    (tmp_path / "app.py").write_text("b = 2\n")
    sys.path.insert(0, "archie/standalone")
    from importlib import import_module
    refresh = import_module("refresh")
    hashes = refresh.current_hashes(tmp_path)
    assert "app.py" in hashes
    assert "thirdparty/lib.py" not in hashes

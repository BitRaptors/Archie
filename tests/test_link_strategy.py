import importlib.util
import sys
from pathlib import Path

import pytest

_SPEC = Path(__file__).resolve().parents[1] / "archie" / "standalone" / "link_strategy.py"
_loader = importlib.util.spec_from_file_location("link_strategy", _SPEC)
ls = importlib.util.module_from_spec(_loader)
_loader.loader.exec_module(ls)


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX symlink semantics")
def test_strategy_for_posix():
    assert ls.strategy_for("dir") == "symlink"
    assert ls.strategy_for("file") == "symlink"


def test_create_symlink_dir(tmp_path):
    target = tmp_path / "store" / "artifacts"
    target.mkdir(parents=True)
    (target / "hello.txt").write_text("hi")
    link = tmp_path / "repo" / ".archie"
    used = ls.create_link(target, link, "dir")
    assert used in {"symlink", "junction"}
    assert (link / "hello.txt").read_text() == "hi"


def test_copy_strategy_materializes_file(tmp_path):
    target = tmp_path / "store" / "a.md"
    target.parent.mkdir(parents=True)
    target.write_text("body")
    link = tmp_path / "repo" / "src" / "a.md"
    used = ls.create_link(target, link, "file_copy")
    assert used == "copy"
    assert link.read_text() == "body"
    assert not link.is_symlink()


def test_remove_managed_refuses_real_file(tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    real = tmp_path / "repo" / "important.md"
    real.parent.mkdir(parents=True)
    real.write_text("DO NOT DELETE")
    removed = ls.remove_managed(real, store, "symlink")
    assert removed is False
    assert real.read_text() == "DO NOT DELETE"


def test_remove_managed_removes_real_symlink(tmp_path):
    store = tmp_path / "store" / "artifacts"
    store.mkdir(parents=True)
    (store / "x").write_text("x")
    link = tmp_path / "repo" / ".archie"
    ls.create_link(store, link, "dir")
    removed = ls.remove_managed(link, tmp_path / "store", "symlink")
    assert removed is True
    assert not link.exists()
    assert (store / "x").read_text() == "x"

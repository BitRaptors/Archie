"""Viewer exposure control-plane helpers (detached mode).

Loads standalone modules directly so the suite runs on Python 3.9.
"""
import importlib.util
from pathlib import Path

_BASE = Path(__file__).resolve().parents[1] / "archie" / "standalone"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _BASE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


viewer = _load("viewer")
linker = _load("linker")
link_store = _load("link_store")


def _detached_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHIE_HOME", str(tmp_path / "home"))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "CLAUDE.md").write_text("# r\n")
    linker.bind(repo)
    return repo


def test_collect_exposure_detached(tmp_path, monkeypatch):
    repo = _detached_repo(tmp_path, monkeypatch)
    data = viewer._collect_exposure_data(repo)
    assert data["mode"] == "detached"
    assert data["categories"]["rules"] is True
    assert any(p["path"] == ".claude/rules" for p in data["placements"])


def test_collect_exposure_repo_mode(tmp_path):
    repo = tmp_path / "plain"
    repo.mkdir()
    data = viewer._collect_exposure_data(repo)
    assert data["mode"] == "repo"
    assert data["placements"] == []


def test_apply_exposure_toggles_category(tmp_path, monkeypatch):
    repo = _detached_repo(tmp_path, monkeypatch)
    out = viewer._apply_exposure_action(
        repo, {"target": "category", "key": "rules", "value": False})
    assert out["categories"]["rules"] is False
    pid = link_store.read_link_file(repo)["project_id"]
    store = link_store.project_store(pid)
    assert link_store.read_exposure(store)["categories"]["rules"] is False
    # reconcile removed the rules link from the tree
    assert not (repo / ".claude" / "rules").exists()


def test_apply_exposure_rejects_bad_target(tmp_path, monkeypatch):
    repo = _detached_repo(tmp_path, monkeypatch)
    import pytest
    with pytest.raises(ValueError):
        viewer._apply_exposure_action(repo, {"target": "nope", "key": "x", "value": True})

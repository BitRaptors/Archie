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


def test_collect_exposure_detached_excludes_infrastructure(tmp_path, monkeypatch):
    repo = _detached_repo(tmp_path, monkeypatch)
    # add a blueprint doc + an intent-layer file
    (repo / ".claude" / "rules").mkdir(parents=True)
    (repo / ".claude" / "rules" / "tech.md").write_text("# tech\n")
    linker.externalize_tree(repo, ".claude/rules")
    (repo / "src").mkdir()
    (repo / "src" / "CLAUDE.md").write_text("# src\n")
    linker.externalize_folder_file(repo, "src/CLAUDE.md")

    data = viewer._collect_exposure_data(repo)
    assert data["mode"] == "detached"
    assert data["categories"]["intent_layer"] is True
    assert data["categories"]["blueprint"] is True
    paths = {p["path"]: p["category"] for p in data["placements"]}
    assert paths[".claude/rules/tech.md"] == "blueprint"
    assert paths["src/CLAUDE.md"] == "intent_layer"
    assert ".archie" not in paths  # infrastructure never listed


def test_collect_exposure_repo_mode(tmp_path):
    repo = tmp_path / "plain"
    repo.mkdir()
    data = viewer._collect_exposure_data(repo)
    assert data["mode"] == "repo"
    assert data["placements"] == []


def test_apply_exposure_hides_single_blueprint_file(tmp_path, monkeypatch):
    repo = _detached_repo(tmp_path, monkeypatch)
    (repo / ".claude" / "rules").mkdir(parents=True)
    (repo / ".claude" / "rules" / "tech.md").write_text("# tech\n")
    linker.externalize_tree(repo, ".claude/rules")

    out = viewer._apply_exposure_action(
        repo, {"target": "path", "key": ".claude/rules/tech.md", "value": False})
    assert out["overrides"][".claude/rules/tech.md"] is False
    # reconcile removed just that file from the tree; store keeps it
    assert not (repo / ".claude" / "rules" / "tech.md").exists()
    store = link_store.project_store(link_store.read_link_file(repo)["project_id"])
    assert (store / "artifacts" / ".claude" / "rules" / "tech.md").exists()


def test_apply_exposure_rejects_bad_target(tmp_path, monkeypatch):
    repo = _detached_repo(tmp_path, monkeypatch)
    import pytest
    with pytest.raises(ValueError):
        viewer._apply_exposure_action(repo, {"target": "nope", "key": "x", "value": True})

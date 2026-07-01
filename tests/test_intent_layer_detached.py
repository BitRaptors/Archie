"""Detached-mode externalize wiring for intent_layer.cmd_merge.

Loads the standalone modules directly (no `archie` package import) so the
suite runs on Python 3.9 — the engine package requires tomllib (3.11+).
"""
import importlib.util
import json
from pathlib import Path

_BASE = Path(__file__).resolve().parents[1] / "archie" / "standalone"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _BASE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_cmd_merge_externalizes_in_detached_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHIE_HOME", str(tmp_path / "home"))
    intent_layer = _load("intent_layer")
    linker = _load("linker")
    link_store = _load("link_store")

    repo = tmp_path / "repo"
    (repo / "src" / "api").mkdir(parents=True)
    (repo / "CLAUDE.md").write_text("# root\n")
    linker.bind(repo)

    enrich_dir = repo / ".archie" / "enrichments"
    enrich_dir.mkdir(parents=True, exist_ok=True)
    (enrich_dir / "src_api.json").write_text(
        json.dumps({"src/api": {"purpose": "HTTP layer"}})
    )

    intent_layer.cmd_merge(repo)

    pid = link_store.read_link_file(repo)["project_id"]
    store = link_store.project_store(pid)
    assert (store / "tree" / "src" / "api" / "CLAUDE.md").exists()
    # in-tree file still readable (through the managed link)
    assert (repo / "src" / "api" / "CLAUDE.md").exists()


def test_cmd_merge_repo_mode_writes_in_tree(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHIE_HOME", str(tmp_path / "home"))
    intent_layer = _load("intent_layer")

    repo = tmp_path / "repo"
    (repo / "src" / "api").mkdir(parents=True)
    enrich_dir = repo / ".archie" / "enrichments"
    enrich_dir.mkdir(parents=True, exist_ok=True)
    (enrich_dir / "src_api.json").write_text(
        json.dumps({"src/api": {"purpose": "HTTP layer"}})
    )

    intent_layer.cmd_merge(repo)

    # repo mode: real file in the tree, no external store created.
    assert (repo / "src" / "api" / "CLAUDE.md").is_file()
    assert not (repo / "src" / "api" / "CLAUDE.md").is_symlink()

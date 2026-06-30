"""End-to-end detached-mode lifecycle guard.

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


linker = _load("linker")
link_store = _load("link_store")


def test_detached_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHIE_HOME", str(tmp_path / "home"))
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "CLAUDE.md").write_text("# proj\nhand guidance\n")

    # bind
    linker.bind(repo)

    # pipeline writes land in the store via write-through
    (repo / ".archie" / "blueprint.json").write_text('{"meta":{}}')
    (repo / ".claude" / "rules").mkdir(parents=True, exist_ok=True)
    (repo / ".claude" / "rules" / "placement.md").write_text("rule body")
    pid = link_store.read_link_file(repo)["project_id"]
    store = link_store.project_store(pid)
    assert (store / "artifacts" / ".archie" / "blueprint.json").exists()
    assert (store / "artifacts" / ".claude" / "rules" / "placement.md").exists()

    # per-folder externalize
    (repo / "src" / "CLAUDE.md").write_text("# src\n")
    linker.externalize_folder_file(repo, "src/CLAUDE.md")
    assert (store / "tree" / "src" / "CLAUDE.md").exists()

    # committed footprint is minimal + hand content preserved
    assert (repo / ".archie-link.json").exists()
    assert "hand guidance" in (repo / "CLAUDE.md").read_text()

    # hide the agent-facing categories; .archie stays (infrastructure)
    exp = link_store.read_exposure(store)
    exp["categories"]["rules"] = False
    exp["categories"]["folder_context"] = False
    link_store.write_exposure(store, exp)
    linker.reconcile(repo)
    assert not (repo / ".claude" / "rules").exists()
    assert not (repo / "src" / "CLAUDE.md").exists()
    assert (repo / ".archie").exists()  # infrastructure never hidden
    # content survives in the store
    assert (store / "artifacts" / ".claude" / "rules" / "placement.md").exists()

    # detach restores real files and cleans the committed footprint
    linker.detach(repo)
    assert link_store.read_link_file(repo) is None
    assert not (repo / ".archie").is_symlink()
    assert (repo / ".archie" / "blueprint.json").read_text() == '{"meta":{}}'
    # rules + folder context were hidden at detach time, but the real content
    # is copied back out of the store so nothing is lost.
    assert (repo / ".claude" / "rules" / "placement.md").read_text() == "rule body"
    assert (repo / "src" / "CLAUDE.md").read_text() == "# src\n"

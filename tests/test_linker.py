import importlib.util
from pathlib import Path

import pytest

_BASE = Path(__file__).resolve().parents[1] / "archie" / "standalone"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _BASE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


linker = _load("linker")
link_store = _load("link_store")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHIE_HOME", str(tmp_path / "home"))
    r = tmp_path / "repo"
    r.mkdir()
    (r / "CLAUDE.md").write_text("# My Project\n\nHand-written guidance.\n")
    (r / ".gitignore").write_text("node_modules/\n")
    return r


# --- bind -----------------------------------------------------------------
def test_bind_creates_link_file_and_store(repo):
    info = linker.bind(repo)
    assert info["mode"] == "detached"
    pid = info["project_id"]
    link = link_store.read_link_file(repo)
    assert link["project_id"] == pid
    store = link_store.project_store(pid)
    assert (store / "artifacts" / ".archie").is_dir()
    assert (store / "artifacts" / ".claude" / "rules").is_dir()


def test_bind_lays_directory_links(repo):
    linker.bind(repo)
    assert (repo / ".archie").is_symlink() or (repo / ".archie").exists()
    (repo / ".archie" / "probe.json").write_text("{}")
    pid = link_store.read_link_file(repo)["project_id"]
    store = link_store.project_store(pid)
    assert (store / "artifacts" / ".archie" / "probe.json").read_text() == "{}"


def test_bind_preserves_handwritten_claude_md_and_adds_pointer(repo):
    linker.bind(repo)
    text = (repo / "CLAUDE.md").read_text()
    assert "Hand-written guidance." in text
    assert "archie:detached" in text


def test_bind_adds_gitignore_entries(repo):
    linker.bind(repo)
    gi = (repo / ".gitignore").read_text()
    assert "/.archie" in gi
    assert "/.claude/rules" in gi
    assert "node_modules/" in gi


def test_bind_records_placements(repo):
    linker.bind(repo)
    pid = link_store.read_link_file(repo)["project_id"]
    placements = link_store.read_placements(link_store.project_store(pid))
    paths = {p["path"] for p in placements}
    assert ".archie" in paths
    assert ".claude/rules" in paths


# --- externalize ----------------------------------------------------------
def test_externalize_moves_file_to_store_and_links(repo):
    linker.bind(repo)
    folder = repo / "src" / "a"
    folder.mkdir(parents=True)
    (folder / "CLAUDE.md").write_text("# a\nfolder context\n")

    strategy = linker.externalize_folder_file(repo, "src/a/CLAUDE.md")
    assert strategy in {"symlink", "copy"}

    pid = link_store.read_link_file(repo)["project_id"]
    store = link_store.project_store(pid)
    assert (store / "tree" / "src" / "a" / "CLAUDE.md").read_text() == "# a\nfolder context\n"
    assert (repo / "src" / "a" / "CLAUDE.md").read_text() == "# a\nfolder context\n"

    placements = link_store.read_placements(store)
    assert any(p["path"] == "src/a/CLAUDE.md" and p["kind"] == "file" for p in placements)


def test_externalize_noop_when_not_detached(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHIE_HOME", str(tmp_path / "home"))
    plain = tmp_path / "plain"
    (plain / "src").mkdir(parents=True)
    (plain / "src" / "CLAUDE.md").write_text("x")
    assert linker.externalize_folder_file(plain, "src/CLAUDE.md") is None


# --- reconcile ------------------------------------------------------------
def test_reconcile_hides_and_restores_folder_context(repo):
    linker.bind(repo)
    (repo / "src" / "a").mkdir(parents=True)
    (repo / "src" / "a" / "CLAUDE.md").write_text("# a\n")
    linker.externalize_folder_file(repo, "src/a/CLAUDE.md")

    pid = link_store.read_link_file(repo)["project_id"]
    store = link_store.project_store(pid)

    exp = link_store.read_exposure(store)
    exp["categories"]["folder_context"] = False
    link_store.write_exposure(store, exp)
    result = linker.reconcile(repo)
    assert not (repo / "src" / "a" / "CLAUDE.md").exists()
    assert (store / "tree" / "src" / "a" / "CLAUDE.md").exists()
    assert "src/a/CLAUDE.md" in result["hidden"]

    exp["categories"]["folder_context"] = True
    link_store.write_exposure(store, exp)
    linker.reconcile(repo)
    assert (repo / "src" / "a" / "CLAUDE.md").read_text() == "# a\n"


def test_reconcile_per_path_override_beats_category(repo):
    linker.bind(repo)
    (repo / "src" / "a").mkdir(parents=True)
    (repo / "src" / "a" / "CLAUDE.md").write_text("# a\n")
    linker.externalize_folder_file(repo, "src/a/CLAUDE.md")
    pid = link_store.read_link_file(repo)["project_id"]
    store = link_store.project_store(pid)

    exp = link_store.read_exposure(store)
    exp["categories"]["folder_context"] = True
    exp["overrides"]["src/a/CLAUDE.md"] = False
    link_store.write_exposure(store, exp)
    linker.reconcile(repo)
    assert not (repo / "src" / "a" / "CLAUDE.md").exists()


# --- status / detach ------------------------------------------------------
def test_detach_restores_real_files_and_clean_repo(repo):
    linker.bind(repo)
    (repo / ".archie" / "blueprint.json").write_text('{"x":1}')
    (repo / ".claude" / "rules").mkdir(parents=True, exist_ok=True)
    (repo / ".claude" / "rules" / "r.md").write_text("rule")
    (repo / "src" / "a").mkdir(parents=True)
    (repo / "src" / "a" / "CLAUDE.md").write_text("# a\n")
    linker.externalize_folder_file(repo, "src/a/CLAUDE.md")

    linker.detach(repo)

    assert link_store.read_link_file(repo) is None
    assert not (repo / ".archie").is_symlink()
    assert (repo / ".archie" / "blueprint.json").read_text() == '{"x":1}'
    assert (repo / ".claude" / "rules" / "r.md").read_text() == "rule"
    assert (repo / "src" / "a" / "CLAUDE.md").read_text() == "# a\n"
    gi = (repo / ".gitignore").read_text()
    assert linker.GITIGNORE_BEGIN not in gi
    assert "archie:detached" not in (repo / "CLAUDE.md").read_text()


def test_status_reports_placements(repo):
    linker.bind(repo)
    st = linker.status(repo)
    assert st["mode"] == "detached"
    assert any(p["path"] == ".archie" for p in st["placements"])


def test_attach_round_trips_existing_artifacts(repo):
    # Start in repo mode with real artifacts, then attach.
    (repo / ".archie").mkdir()
    (repo / ".archie" / "blueprint.json").write_text('{"k":2}')
    (repo / ".claude" / "rules").mkdir(parents=True)
    (repo / ".claude" / "rules" / "r.md").write_text("body")
    (repo / "pkg").mkdir()
    (repo / "pkg" / "CLAUDE.md").write_text("# pkg\n")

    linker.attach(repo)

    assert link_store.read_link_file(repo)["mode"] == "detached"
    assert (repo / ".archie" / "blueprint.json").read_text() == '{"k":2}'
    assert (repo / "pkg" / "CLAUDE.md").read_text() == "# pkg\n"

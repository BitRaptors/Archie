import importlib.util
import subprocess
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


def _store(repo):
    return link_store.project_store(link_store.read_link_file(repo)["project_id"])


# --- bind -----------------------------------------------------------------
def test_bind_creates_link_file_and_store(repo):
    info = linker.bind(repo)
    assert info["mode"] == "detached"
    store = _store(repo)
    assert (store / "artifacts" / ".archie").is_dir()
    assert (store / "artifacts" / ".claude" / "rules").is_dir()


def test_bind_lays_archie_infra_symlink_writethrough(repo):
    linker.bind(repo)
    assert (repo / ".archie").is_symlink() or (repo / ".archie").exists()
    (repo / ".archie" / "probe.json").write_text("{}")
    assert (_store(repo) / "artifacts" / ".archie" / "probe.json").read_text() == "{}"


def test_bind_only_infra_placement_initially(repo):
    linker.bind(repo)
    placements = link_store.read_placements(_store(repo))
    assert [p["path"] for p in placements] == [".archie"]
    assert placements[0]["category"] == "infrastructure"


def test_bind_does_not_touch_claude_md(repo):
    before = (repo / "CLAUDE.md").read_text()
    linker.bind(repo)
    after = (repo / "CLAUDE.md").read_text()
    assert after == before  # no inert @import pointer appended
    assert "Hand-written guidance." in after


def test_rebind_preserves_placements(repo):
    linker.bind(repo)
    (repo / ".claude" / "rules").mkdir(parents=True)
    (repo / ".claude" / "rules" / "tech.md").write_text("# tech\n")
    linker.externalize_tree(repo, ".claude/rules")
    (repo / "src").mkdir()
    (repo / "src" / "CLAUDE.md").write_text("# src\n")
    linker.externalize_folder_file(repo, "src/CLAUDE.md")

    before = {p["path"] for p in link_store.read_placements(_store(repo))}
    assert {".archie", ".claude/rules/tech.md", "src/CLAUDE.md"} <= before

    # Re-bind (what `npx --detached` does on reinstall) must NOT orphan links.
    linker.bind(repo)
    after = {p["path"] for p in link_store.read_placements(_store(repo))}
    assert before == after
    # and the links are still managed/toggleable
    st = linker.status(repo)
    assert any(p["path"] == "src/CLAUDE.md" for p in st["placements"])


def test_prune_blueprint_removes_stale_keeps_produced(repo):
    linker.bind(repo)
    rules = repo / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "keep.md").write_text("# keep\n")
    (rules / "stale.md").write_text("# stale\n")
    linker.externalize_tree(repo, ".claude/rules")
    store = _store(repo)

    # A later render produces only keep.md; cleanup removed the stale tree link.
    (rules / "stale.md").unlink()
    removed = linker.prune_blueprint(repo, [".claude/rules/keep.md"])
    assert removed == [".claude/rules/stale.md"]

    # stale gone from store + placements; a reconcile cannot resurrect it
    assert not (store / "artifacts" / ".claude" / "rules" / "stale.md").exists()
    paths = {p["path"] for p in link_store.read_placements(store)}
    assert ".claude/rules/stale.md" not in paths
    assert ".claude/rules/keep.md" in paths
    linker.reconcile(repo)
    assert not (repo / ".claude" / "rules" / "stale.md").exists()


def test_prune_keeps_hidden_file_still_in_render_set(repo):
    linker.bind(repo)
    rules = repo / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "tech.md").write_text("# tech\n")
    linker.externalize_tree(repo, ".claude/rules")
    store = _store(repo)

    # User hides it (tree link gone) but the renderer STILL produces it.
    exp = link_store.read_exposure(store)
    exp["overrides"][".claude/rules/tech.md"] = False
    link_store.write_exposure(store, exp)
    linker.reconcile(repo)
    assert not (repo / ".claude" / "rules" / "tech.md").exists()

    # prune with it still in the render set must NOT remove it.
    linker.prune_blueprint(repo, [".claude/rules/tech.md"])
    assert (store / "artifacts" / ".claude" / "rules" / "tech.md").exists()
    paths = {p["path"] for p in link_store.read_placements(store)}
    assert ".claude/rules/tech.md" in paths


def test_reconcile_tolerates_old_shape_placement(repo):
    linker.bind(repo)
    store = _store(repo)
    (store / "artifacts" / ".claude" / "rules" / "legacy.md").write_text("# legacy\n")
    # Simulate a placement written by an older build (no "target" field).
    placements = link_store.read_placements(store)
    placements.append({"path": ".claude/rules/legacy.md", "kind": "file",
                       "strategy": "symlink", "category": "blueprint"})
    link_store.write_placements(store, placements)
    # Must not raise KeyError on the missing "target".
    result = linker.reconcile(repo)
    assert ".claude/rules/legacy.md" in result["exposed"]
    assert (repo / ".claude" / "rules" / "legacy.md").read_text() == "# legacy\n"


def test_bind_adds_gitignore_entries(repo):
    linker.bind(repo)
    gi = (repo / ".gitignore").read_text()
    assert "/.archie" in gi
    assert "/.claude/rules" in gi
    assert "node_modules/" in gi


def test_bind_absorbs_existing_archie_tooling(repo):
    (repo / ".archie").mkdir()
    (repo / ".archie" / "linker.py").write_text("# tooling")
    (repo / ".archie" / "platform_rules.json").write_text("{}")
    linker.bind(repo)
    assert (repo / ".archie" / "linker.py").read_text() == "# tooling"
    assert (_store(repo) / "artifacts" / ".archie" / "linker.py").read_text() == "# tooling"


# --- externalize: intent-layer per-folder CLAUDE.md -----------------------
def test_externalize_intent_layer_file(repo):
    linker.bind(repo)
    (repo / "src" / "a").mkdir(parents=True)
    (repo / "src" / "a" / "CLAUDE.md").write_text("# a\nfolder context\n")
    strat = linker.externalize_folder_file(repo, "src/a/CLAUDE.md")
    assert strat in {"symlink", "copy"}
    store = _store(repo)
    assert (store / "tree" / "src" / "a" / "CLAUDE.md").read_text() == "# a\nfolder context\n"
    assert (repo / "src" / "a" / "CLAUDE.md").read_text() == "# a\nfolder context\n"
    p = [p for p in link_store.read_placements(store) if p["path"] == "src/a/CLAUDE.md"][0]
    assert p["kind"] == "file" and p["category"] == "intent_layer"


# --- externalize: blueprint .claude/rules/*.md (per file) -----------------
def test_externalize_blueprint_rules_per_file(repo):
    linker.bind(repo)
    rules = repo / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "technology.md").write_text("# tech\n")
    (rules / "data-models.md").write_text("# data\n")
    done = linker.externalize_tree(repo, ".claude/rules")
    assert set(done) == {".claude/rules/technology.md", ".claude/rules/data-models.md"}
    store = _store(repo)
    assert (store / "artifacts" / ".claude" / "rules" / "technology.md").exists()
    cats = {p["path"]: p["category"] for p in link_store.read_placements(store)
            if p["path"].startswith(".claude/rules/")}
    assert all(c == "blueprint" for c in cats.values())
    # reachable through the per-file link
    assert (repo / ".claude" / "rules" / "technology.md").read_text() == "# tech\n"


def test_externalize_skips_git_tracked_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHIE_HOME", str(tmp_path / "home"))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "CLAUDE.md").write_text("# root\n")

    def git(*a):
        subprocess.run(["git", "-C", str(repo), *a], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    git("init")
    git("config", "user.email", "t@t.t")
    git("config", "user.name", "t")
    (repo / "pkg").mkdir()
    (repo / "pkg" / "CLAUDE.md").write_text("# hand-written, committed\n")
    git("add", "-A")
    git("commit", "-m", "init")

    linker.bind(repo)
    # The committed per-folder file must NOT be externalized into a symlink.
    assert linker.externalize_folder_file(repo, "pkg/CLAUDE.md") is None
    assert not (repo / "pkg" / "CLAUDE.md").is_symlink()
    assert (repo / "pkg" / "CLAUDE.md").read_text() == "# hand-written, committed\n"
    # untracked generated file still externalizes
    (repo / "gen").mkdir()
    (repo / "gen" / "CLAUDE.md").write_text("# generated\n")
    assert linker.externalize_folder_file(repo, "gen/CLAUDE.md") is not None
    assert (repo / "gen" / "CLAUDE.md").is_symlink()


def test_externalize_noop_when_not_detached(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHIE_HOME", str(tmp_path / "home"))
    plain = tmp_path / "plain"
    (plain / "src").mkdir(parents=True)
    (plain / "src" / "CLAUDE.md").write_text("x")
    assert linker.externalize_folder_file(plain, "src/CLAUDE.md") is None


# --- reconcile: per-file gating both groups -------------------------------
def test_reconcile_hides_and_restores_intent_layer(repo):
    linker.bind(repo)
    (repo / "src" / "a").mkdir(parents=True)
    (repo / "src" / "a" / "CLAUDE.md").write_text("# a\n")
    linker.externalize_folder_file(repo, "src/a/CLAUDE.md")
    store = _store(repo)

    exp = link_store.read_exposure(store)
    exp["categories"]["intent_layer"] = False
    link_store.write_exposure(store, exp)
    result = linker.reconcile(repo)
    assert not (repo / "src" / "a" / "CLAUDE.md").exists()
    assert (store / "tree" / "src" / "a" / "CLAUDE.md").exists()
    assert "src/a/CLAUDE.md" in result["hidden"]

    exp["categories"]["intent_layer"] = True
    link_store.write_exposure(store, exp)
    linker.reconcile(repo)
    assert (repo / "src" / "a" / "CLAUDE.md").read_text() == "# a\n"


def test_reconcile_hides_blueprint_doc_per_file(repo):
    linker.bind(repo)
    rules = repo / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "technology.md").write_text("# tech\n")
    (rules / "data-models.md").write_text("# data\n")
    linker.externalize_tree(repo, ".claude/rules")
    store = _store(repo)

    # Hide a single blueprint file via per-path override; the other stays.
    exp = link_store.read_exposure(store)
    exp["overrides"][".claude/rules/technology.md"] = False
    link_store.write_exposure(store, exp)
    linker.reconcile(repo)
    assert not (repo / ".claude" / "rules" / "technology.md").exists()
    assert (repo / ".claude" / "rules" / "data-models.md").exists()
    # store keeps both
    assert (store / "artifacts" / ".claude" / "rules" / "technology.md").exists()


def test_infrastructure_always_exposed(repo):
    linker.bind(repo)
    store = _store(repo)
    exp = link_store.read_exposure(store)
    # even a malicious override can't hide .archie
    exp["overrides"][".archie"] = False
    link_store.write_exposure(store, exp)
    linker.reconcile(repo)
    assert (repo / ".archie").exists()


# --- status / detach / attach ---------------------------------------------
def test_status_reports_placements_with_category(repo):
    linker.bind(repo)
    st = linker.status(repo)
    assert st["mode"] == "detached"
    infra = [p for p in st["placements"] if p["path"] == ".archie"][0]
    assert infra["category"] == "infrastructure" and infra["exposed"] is True


def test_detach_restores_real_files_and_clean_repo(repo):
    linker.bind(repo)
    (repo / ".archie" / "blueprint.json").write_text('{"x":1}')
    (repo / ".claude" / "rules").mkdir(parents=True, exist_ok=True)
    (repo / ".claude" / "rules" / "r.md").write_text("rule")
    linker.externalize_tree(repo, ".claude/rules")
    (repo / "src" / "a").mkdir(parents=True)
    (repo / "src" / "a" / "CLAUDE.md").write_text("# a\n")
    linker.externalize_folder_file(repo, "src/a/CLAUDE.md")

    linker.detach(repo)

    assert link_store.read_link_file(repo) is None
    assert not (repo / ".archie").is_symlink()
    assert (repo / ".archie" / "blueprint.json").read_text() == '{"x":1}'
    assert (repo / ".claude" / "rules" / "r.md").read_text() == "rule"
    assert not (repo / ".claude" / "rules" / "r.md").is_symlink()
    assert (repo / "src" / "a" / "CLAUDE.md").read_text() == "# a\n"
    gi = (repo / ".gitignore").read_text()
    assert linker.GITIGNORE_BEGIN not in gi
    assert "archie:detached" not in (repo / "CLAUDE.md").read_text()


def test_attach_round_trips_existing_artifacts(repo):
    (repo / ".archie").mkdir()
    (repo / ".archie" / "blueprint.json").write_text('{"k":2}')
    (repo / ".claude" / "rules").mkdir(parents=True)
    (repo / ".claude" / "rules" / "tech.md").write_text("body")
    (repo / "pkg").mkdir()
    (repo / "pkg" / "CLAUDE.md").write_text("# pkg\n")

    linker.attach(repo)

    assert link_store.read_link_file(repo)["mode"] == "detached"
    assert (repo / ".archie" / "blueprint.json").read_text() == '{"k":2}'
    assert (repo / ".claude" / "rules" / "tech.md").read_text() == "body"
    assert (repo / "pkg" / "CLAUDE.md").read_text() == "# pkg\n"
    cats = {p["category"] for p in link_store.read_placements(_store(repo))}
    assert {"infrastructure", "blueprint", "intent_layer"} <= cats

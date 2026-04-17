"""End-to-end tests for the wiki build pipeline."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
FIXTURE = Path(__file__).parent / "fixtures" / "wiki_fixture_blueprint.json"


def _setup_project(tmp_path: Path) -> Path:
    """Create a temp project with .archie/blueprint.json from the fixture."""
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    shutil.copy(FIXTURE, archie_dir / "blueprint.json")
    return tmp_path


def test_wiki_builder_cli_produces_expected_pages(tmp_path):
    project = _setup_project(tmp_path)
    result = subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr

    wiki = project / ".archie" / "wiki"
    assert (wiki / "index.md").exists()
    assert (wiki / "decisions" / "postgresql-as-primary-store.md").exists()
    assert (wiki / "decisions" / "jwt-over-sessions.md").exists()
    assert (wiki / "components" / "user-service.md").exists()
    assert (wiki / "components" / "user-repository.md").exists()
    assert (wiki / "components" / "auth-controller.md").exists()
    assert (wiki / "patterns" / "repository.md").exists()
    assert (wiki / "pitfalls" / "password-storage.md").exists()


def test_wiki_builder_forward_links_resolve(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    wiki = project / ".archie" / "wiki"
    us = (wiki / "components" / "user-service.md").read_text()
    assert "[UserRepository](../components/user-repository.md)" in us
    pitfall = (wiki / "pitfalls" / "password-storage.md").read_text()
    assert "[PostgreSQL as primary store](../decisions/postgresql-as-primary-store.md)" in pitfall


def test_wiki_builder_emits_backlinks_and_provenance(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    wiki = project / ".archie" / "wiki"
    backlinks = json.loads((wiki / "_meta" / "backlinks.json").read_text())
    # UserRepository is referenced by UserService (depends_on).
    assert any(
        ref["path"] == "components/user-service.md"
        for ref in backlinks.get("components/user-repository.md", [])
    )
    # Referenced by is appended to user-repository.
    ur = (wiki / "components" / "user-repository.md").read_text()
    assert "## Referenced by" in ur
    assert "[UserService](../components/user-service.md)" in ur
    # Provenance has SHA256 for all pages.
    prov = json.loads((wiki / "_meta" / "provenance.json").read_text())
    assert "index.md" in prov
    assert len(prov["index.md"]["sha256"]) == 64


def test_wiki_builder_is_idempotent(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    first = (project / ".archie" / "wiki" / "components" / "user-repository.md").read_text()
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    second = (project / ".archie" / "wiki" / "components" / "user-repository.md").read_text()
    assert first == second

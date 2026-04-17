"""End-to-end tests for the wiki build pipeline."""

import json
import os
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


def test_wiki_builder_skips_when_flag_off(tmp_path, monkeypatch):
    project = _setup_project(tmp_path)
    env = os.environ.copy()
    env["ARCHIE_WIKI_ENABLED"] = "false"
    result = subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        capture_output=True, text=True, check=False, env=env,
    )
    assert result.returncode == 0
    # Nothing should be written under .archie/wiki/
    assert not (project / ".archie" / "wiki").exists()
    assert "skipped" in result.stdout.lower() or "disabled" in result.stdout.lower()


def test_wiki_builder_respects_archie_json_flag(tmp_path):
    project = _setup_project(tmp_path)
    (project / ".archie" / "archie.json").write_text(
        json.dumps({"wiki_enabled": False}), encoding="utf-8"
    )
    # No ARCHIE_WIKI_ENABLED env var in the subprocess environment
    env = {k: v for k, v in os.environ.items() if k != "ARCHIE_WIKI_ENABLED"}
    result = subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        capture_output=True, text=True, check=False, env=env,
    )
    assert result.returncode == 0
    assert not (project / ".archie" / "wiki").exists()
    assert "skipped" in result.stdout.lower() or "disabled" in result.stdout.lower()


def test_wiki_builder_emits_capability_page(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    cap = project / ".archie" / "wiki" / "capabilities" / "user-authentication.md"
    assert cap.exists()
    text = cap.read_text()
    assert "# User Authentication" in text
    assert "[UserService](../components/user-service.md)" in text
    assert "[JWT over sessions](../decisions/jwt-over-sessions.md)" in text
    assert "[Password storage](../pitfalls/password-storage.md)" in text


def test_wiki_builder_persists_capability_evidence_in_provenance(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    prov = json.loads(
        (project / ".archie" / "wiki" / "_meta" / "provenance.json").read_text()
    )
    # From the fixture, the User Authentication capability has evidence globs.
    cap_prov = prov.get("capabilities/user-authentication.md")
    assert cap_prov is not None
    assert "evidence" in cap_prov
    assert len(cap_prov["evidence"]) > 0
    # And component pages do NOT have evidence (they depend on blueprint structure).
    comp_prov = prov.get("components/user-service.md")
    assert comp_prov is not None
    assert "evidence" not in comp_prov


def test_capability_backlinks_appear_on_components(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    us = (project / ".archie" / "wiki" / "components" / "user-service.md").read_text()
    # UserService is used by the User Authentication capability, so its
    # "Referenced by" section must include it.
    assert "[User Authentication](../capabilities/user-authentication.md)" in us

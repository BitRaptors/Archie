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


def test_wiki_builder_handles_components_in_dict(tmp_path):
    """Real Archie blueprints wrap components in a dict; wiki should still render them."""
    archie = tmp_path / ".archie"
    archie.mkdir()
    (archie / "blueprint.json").write_text(json.dumps({
        "meta": {},
        "decisions": {"key_decisions": []},
        "components": {
            "structure_type": "layered",
            "components": [
                {"name": "Alpha", "purpose": "First"},
                {"name": "Beta", "purpose": "Second", "depends_on": ["Alpha"]},
            ],
        },
        "communication": {"patterns": []},
        "pitfalls": [],
    }))
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(tmp_path)],
        check=True, capture_output=True,
    )
    wiki = tmp_path / ".archie" / "wiki"
    assert (wiki / "components" / "alpha.md").exists()
    assert (wiki / "components" / "beta.md").exists()
    beta = (wiki / "components" / "beta.md").read_text()
    assert "[Alpha](../components/alpha.md)" in beta
    # Index falls back to directory name since meta.project_name is absent.
    idx = (wiki / "index.md").read_text()
    assert f"# {tmp_path.name} Wiki" in idx


def test_wiki_builder_emits_guideline_pages(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    wiki = project / ".archie" / "wiki"
    assert (wiki / "guidelines" / "how-to-add-a-new-auth-protected-endpoint.md").exists()
    assert (wiki / "guidelines" / "how-to-hash-a-new-password.md").exists()
    g = (wiki / "guidelines" / "how-to-add-a-new-auth-protected-endpoint.md").read_text()
    assert "# How to add a new auth-protected endpoint" in g
    assert "## Libraries" in g
    assert "- express" in g
    assert "requireAuth middleware" in g


def test_wiki_builder_emits_rules_architecture(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    wiki = project / ".archie" / "wiki"
    assert (wiki / "rules" / "architecture.md").exists()
    text = (wiki / "rules" / "architecture.md").read_text()
    assert "# Architecture rules" in text
    assert "## File placement" in text
    assert "| HTTP controllers |" in text
    assert "## Naming conventions" in text
    assert "| Controller classes |" in text


def test_wiki_builder_survives_malformed_blueprint(tmp_path):
    """If the blueprint has a list where a dict was expected (or vice versa),
    the builder must not crash — it should produce an empty wiki instead."""
    archie = tmp_path / ".archie"
    archie.mkdir()
    # `decisions` as a LIST instead of a dict (real Wave-2 failure mode).
    # Every other required key is also present-but-malformed.
    (archie / "blueprint.json").write_text(json.dumps({
        "meta": ["not", "a", "dict"],
        "decisions": ["this", "should", "be", "a", "dict"],
        "components": "not a list",
        "communication": 123,
        "pitfalls": None,
        "capabilities": {"not": "a list"},
    }))
    result = subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(tmp_path)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, f"exit {result.returncode}: {result.stderr}"
    # Index.md exists even though there is no data.
    assert (tmp_path / ".archie" / "wiki" / "index.md").exists()


def test_wiki_builder_emits_rules_development(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    wiki = project / ".archie" / "wiki"
    assert (wiki / "rules" / "development.md").exists()
    text = (wiki / "rules" / "development.md").read_text()
    assert "# Development rules" in text
    assert "## Security" in text
    assert "Never log passwords" in text
    assert "`features/auth/**`" in text  # applies_to code-formatted


def test_wiki_builder_emits_technology(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    wiki = project / ".archie" / "wiki"
    assert (wiki / "technology.md").exists()
    text = (wiki / "technology.md").read_text()
    assert "# Technology" in text
    assert "## Stack" in text
    assert "| TypeScript |" in text
    assert "## External integrations" in text
    assert "PostgreSQL" in text
    assert "## Run commands" in text
    assert "npm run dev" in text


def test_wiki_builder_emits_quick_reference(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    wiki = project / ".archie" / "wiki"
    assert (wiki / "quick-reference.md").exists()
    text = (wiki / "quick-reference.md").read_text()
    assert "# Quick reference" in text
    assert "## Which pattern should I use?" in text
    assert "## Error handling" in text
    assert "401" in text


def test_wiki_builder_emits_frontend(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    wiki = project / ".archie" / "wiki"
    assert (wiki / "frontend.md").exists()
    text = (wiki / "frontend.md").read_text()
    assert "# Frontend" in text
    assert "**Framework:**" in text
    assert "Next.js 15" in text
    assert "## Conventions" in text


def test_wiki_builder_emits_architecture(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    wiki = project / ".archie" / "wiki"
    assert (wiki / "architecture.md").exists()
    text = (wiki / "architecture.md").read_text()
    assert "# Architecture" in text
    assert "```mermaid" in text
    assert "AuthController" in text or "graph" in text


def test_wiki_builder_component_enrichment_end_to_end(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    wiki = project / ".archie" / "wiki"
    us = (wiki / "components" / "user-service.md").read_text()
    assert "## Responsibility" in us
    assert "## Public interface" in us
    assert "`async login(email: string, password: string): Promise<Result<Session, AuthError>>`" in us
    assert "## Key files" in us
    assert "features/auth/UserService.ts" in us
    assert "**Platform:** backend" in us
    assert "**Location:** `features/auth/UserService.ts`" in us


def test_wiki_builder_pitfall_applies_to_end_to_end(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    wiki = project / ".archie" / "wiki"
    pitfall_md = (wiki / "pitfalls" / "password-storage.md").read_text()
    assert "## Applies to" in pitfall_md
    assert "features/auth/UserRepository.ts" in pitfall_md
    assert "features/auth/PasswordHelper.ts" in pitfall_md


def test_wiki_builder_emits_decisions_index(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    wiki = project / ".archie" / "wiki"
    di = wiki / "decisions" / "index.md"
    assert di.exists()
    text = di.read_text()
    assert "# Architectural decisions" in text
    assert "## Architectural style" in text
    assert "Layered MVC" in text
    assert "## Trade-offs accepted" in text
    assert "Token revocation" in text
    assert "## Explicitly out of scope" in text
    assert "OAuth social login" in text
    assert "## All decisions" in text
    assert "[PostgreSQL as primary store](./postgresql-as-primary-store.md)" in text
    # Top-level index is not this file
    top = (wiki / "index.md").read_text()
    assert "# TestProject Wiki" in top


def test_wiki_builder_index_system_overview_end_to_end(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    idx = (project / ".archie" / "wiki" / "index.md").read_text()
    assert "## System overview" in idx
    assert "TestProject is a small test-scope application" in idx
    assert "### Architecture style" in idx
    assert "Layered MVC with repository pattern" in idx
    # Browse by type has new entries
    assert "Guidelines (" in idx
    assert "Rules (" in idx
    assert "Technology" in idx
    assert "Quick reference" in idx
    # Decisions section has the overview pointer
    assert "[Decisions overview](./decisions/index.md)" in idx
    # Order: System overview before Before-you-implement
    sys_idx = idx.index("## System overview")
    before_idx = idx.index("## Before you implement anything")
    assert sys_idx < before_idx


def test_wiki_builder_emits_data_model_pages(tmp_path):
    """Data models from blueprint produce data-models/*.md pages with all expected sections."""
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    wiki = project / ".archie" / "wiki"
    assert (wiki / "data-models" / "user.md").exists()
    assert (wiki / "data-models" / "session.md").exists()
    user = (wiki / "data-models" / "user.md").read_text()
    assert "# User" in user
    assert "| `email` | `string` | no |" in user
    assert "[UserService](../components/user-service.md)" in user
    # Verify evidence appears in provenance
    prov = json.loads((wiki / "_meta" / "provenance.json").read_text())
    assert "data-models/user.md" in prov
    assert "data-models/session.md" in prov
    assert prov["data-models/user.md"].get("evidence") == ["features/auth/User.ts"]
    assert prov["data-models/session.md"].get("evidence") == ["features/auth/Session.ts"]


def test_wiki_builder_plan5a_all_page_types(tmp_path):
    """Single end-to-end test: fixture -> full wiki build -> every Plan 5a page type exists."""
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    wiki = project / ".archie" / "wiki"

    # New page types from Plan 5a
    assert (wiki / "guidelines" / "how-to-add-a-new-auth-protected-endpoint.md").exists()
    assert (wiki / "guidelines" / "how-to-hash-a-new-password.md").exists()
    assert (wiki / "rules" / "architecture.md").exists()
    assert (wiki / "rules" / "development.md").exists()
    assert (wiki / "technology.md").exists()
    assert (wiki / "quick-reference.md").exists()
    assert (wiki / "frontend.md").exists()
    assert (wiki / "architecture.md").exists()
    assert (wiki / "decisions" / "index.md").exists()

    # Enriched existing pages
    us = (wiki / "components" / "user-service.md").read_text()
    assert "## Responsibility" in us
    assert "## Public interface" in us
    assert "## Key files" in us
    assert "**Platform:** backend" in us
    assert "**Location:** `features/auth/UserService.ts`" in us

    pitfall = (wiki / "pitfalls" / "password-storage.md").read_text()
    assert "## Applies to" in pitfall
    assert "features/auth/UserRepository.ts" in pitfall

    # Top-level index overhaul
    idx = (wiki / "index.md").read_text()
    assert "## System overview" in idx
    assert "## Browse by type" in idx
    # System overview appears before the Before-you-implement section
    assert idx.index("## System overview") < idx.index("## Before you implement anything")
    # New browse entries present
    assert "Guidelines (" in idx
    assert "Rules (" in idx
    assert "Technology" in idx
    assert "Quick reference" in idx
    assert "Architecture" in idx

    # Wiki lint shows zero findings on a clean fixture-derived wiki
    lint_result = subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_index.py"),
         "--wiki", str(wiki), "--fs-root", str(project), "--lint", "--json"],
        capture_output=True, text=True, check=True,
    )
    findings = json.loads(lint_result.stdout)
    # Filter out stale_evidence — capability evidence globs reference files that don't exist in the synthetic fixture project.
    # Filter out orphan — Plan 5a pages may not all be indexed in top-level index yet.
    # All other kinds should be clean.
    non_stale = [f for f in findings if f["kind"] not in ("stale_evidence", "orphan")]
    assert non_stale == [], f"Unexpected lint findings: {non_stale}"


def test_component_pages_show_data_models_section(tmp_path):
    """Component pages list data models that point at them via used_by_components."""
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    wiki = project / ".archie" / "wiki"

    # UserService is referenced by both User and Session.
    us = (wiki / "components" / "user-service.md").read_text()
    assert "## Data models" in us
    assert "[User](../data-models/user.md)" in us
    assert "[Session](../data-models/session.md)" in us

    # AuthController is referenced by Session only.
    ac = (wiki / "components" / "auth-controller.md").read_text()
    assert "## Data models" in ac
    assert "[Session](../data-models/session.md)" in ac
    assert "[User](../data-models/user.md)" not in ac

    # UserRepository is referenced by User only.
    ur = (wiki / "components" / "user-repository.md").read_text()
    assert "## Data models" in ur
    assert "[User](../data-models/user.md)" in ur
    assert "[Session](../data-models/session.md)" not in ur


def test_wiki_data_models_end_to_end(tmp_path):
    """Single end-to-end check that data-model pages, component backlinks, and the
    index entry are all emitted in one builder run."""
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )

    wiki = project / ".archie" / "wiki"

    # 1. data-models pages exist
    user_md = wiki / "data-models" / "user.md"
    session_md = wiki / "data-models" / "session.md"
    assert user_md.exists()
    assert session_md.exists()

    # 2. component pages show the Data models section
    user_service_md = (wiki / "components" / "user-service.md").read_text()
    assert "## Data models" in user_service_md
    assert "[User](../data-models/user.md)" in user_service_md
    assert "[Session](../data-models/session.md)" in user_service_md

    # 3. index has the browse-by-type bullet AND the dedicated section
    index_md = (wiki / "index.md").read_text()
    assert "**Data models (2)** — entities moving through the system" in index_md
    assert "## Data models" in index_md
    assert "- [User](./data-models/user.md)" in index_md
    assert "- [Session](./data-models/session.md)" in index_md


def test_data_model_pages_show_related_models_from_field_types(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True,
        capture_output=True,
    )
    user_md = (project / ".archie" / "wiki" / "data-models" / "user.md").read_text()
    session_md = (project / ".archie" / "wiki" / "data-models" / "session.md").read_text()
    assert "## Related models" in user_md
    assert "[Session](./session.md)" in user_md
    assert "## Related models" in session_md
    assert "[User](./user.md)" in session_md


def test_wiki_builder_emits_utilities_page_from_scan(tmp_path):
    """End-to-end: scanner produces symbols on sample_sources, wiki_builder
    renders utilities.md with at least one categorized section."""
    project = _setup_project(tmp_path)

    # Drop sample_sources into the project so scanner has something to extract from
    fixture_root = Path(__file__).parent / "fixtures" / "sample_sources"
    for src in fixture_root.iterdir():
        if src.is_dir():
            shutil.copytree(src, project / src.name)

    # Run scanner so .archie/scan.json gets symbols[]
    scanner_path = STANDALONE / "scanner.py"
    subprocess.run(
        [sys.executable, str(scanner_path), str(project)],
        check=True,
        capture_output=True,
    )

    # Run wiki_builder
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True,
        capture_output=True,
    )

    utilities_md = (project / ".archie" / "wiki" / "utilities.md").read_text()
    assert "# Utilities catalog" in utilities_md
    # At least one of the sample functions should appear
    assert (
        "formatLocalizedDate" in utilities_md
        or "format_time" in utilities_md
        or "formatDate" in utilities_md
    )

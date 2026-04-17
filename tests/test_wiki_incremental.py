"""Tests for wiki_builder --incremental."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))

import wiki_builder  # noqa: E402

STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
FIXTURE_BP = Path(__file__).parent / "fixtures" / "wiki_fixture_blueprint.json"


def test_diff_scans_added_modified_deleted(tmp_path):
    old = {"files": [{"path": "a.py", "hash": "1"}, {"path": "b.py", "hash": "2"}]}
    new = {"files": [{"path": "b.py", "hash": "22"}, {"path": "c.py", "hash": "3"}]}
    diff = wiki_builder.diff_scans(old, new)
    assert sorted(diff["added"]) == ["c.py"]
    assert sorted(diff["modified"]) == ["b.py"]
    assert sorted(diff["deleted"]) == ["a.py"]


def test_diff_scans_empty_old_returns_all_added():
    old = {"files": []}
    new = {"files": [{"path": "a.py", "hash": "1"}, {"path": "b.py", "hash": "2"}]}
    diff = wiki_builder.diff_scans(old, new)
    assert sorted(diff["added"]) == ["a.py", "b.py"]
    assert diff["modified"] == []
    assert diff["deleted"] == []


import fnmatch


def test_affected_pages_matches_globs():
    provenance = {
        "capabilities/auth-flow.md": {
            "sha256": "x", "source": "wiki_builder",
            "evidence": ["features/auth/**"],
        },
        "capabilities/payment.md": {
            "sha256": "y", "source": "wiki_builder",
            "evidence": ["features/payment/**"],
        },
        "index.md": {"sha256": "z", "source": "wiki_builder"},  # no evidence field
    }
    changed = ["features/auth/AuthService.ts", "README.md"]
    affected = wiki_builder.affected_pages(provenance, changed)
    assert sorted(affected) == ["capabilities/auth-flow.md"]


def test_affected_pages_handles_no_evidence_gracefully():
    provenance = {"index.md": {"sha256": "z", "source": "wiki_builder"}}
    affected = wiki_builder.affected_pages(provenance, ["anything.py"])
    assert affected == []


import hashlib


def test_write_if_changed_skips_identical_content(tmp_path):
    page = tmp_path / "page.md"
    page.write_text("same content\n")
    original_mtime = page.stat().st_mtime_ns
    changed = wiki_builder.write_if_changed(page, "same content\n")
    assert changed is False
    # File not rewritten; mtime unchanged.
    assert page.stat().st_mtime_ns == original_mtime


def test_write_if_changed_writes_new_content(tmp_path):
    page = tmp_path / "page.md"
    page.write_text("old\n")
    changed = wiki_builder.write_if_changed(page, "new\n")
    assert changed is True
    assert page.read_text() == "new\n"


def test_write_if_changed_creates_parent_dir(tmp_path):
    page = tmp_path / "sub" / "dir" / "page.md"
    changed = wiki_builder.write_if_changed(page, "hello\n")
    assert changed is True
    assert page.read_text() == "hello\n"


def _setup_project_with_previous_wiki(tmp_path):
    """Build a wiki once (simulating a prior deep-scan), then prepare an
    incremental scenario where one evidence file has changed."""
    archie = tmp_path / ".archie"
    archie.mkdir()
    shutil.copy(FIXTURE_BP, archie / "blueprint.json")
    # First: build full wiki.
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(tmp_path)],
        check=True, capture_output=True,
    )
    # Write a previous scan snapshot showing the evidence files that existed.
    old_scan = {
        "files": [
            {"path": "features/auth/AuthController.ts", "hash": "h1"},
            {"path": "features/auth/AuthService.ts", "hash": "h2"},
            {"path": "routes/api/auth.py", "hash": "h3"},
        ]
    }
    (archie / "scan.json").write_text(json.dumps(old_scan))
    return tmp_path


def test_incremental_rewrites_only_affected_pages(tmp_path):
    project = _setup_project_with_previous_wiki(tmp_path)
    wiki = project / ".archie" / "wiki"
    # Capture current file mtimes.
    before = {p: p.stat().st_mtime_ns for p in wiki.rglob("*.md")}

    # Simulate: one evidence file for "User Authentication" has changed.
    new_scan = {
        "files": [
            {"path": "features/auth/AuthController.ts", "hash": "h1-modified"},
            {"path": "features/auth/AuthService.ts", "hash": "h2"},
            {"path": "routes/api/auth.py", "hash": "h3"},
        ]
    }
    prev_scan = json.loads((project / ".archie" / "scan.json").read_text())
    (project / ".archie" / "scan.json").write_text(json.dumps(new_scan))

    # Run incremental.
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project),
         "--incremental", "--previous-scan", json.dumps(prev_scan)],
        check=True, capture_output=True,
    )

    after = {p: p.stat().st_mtime_ns for p in wiki.rglob("*.md")}
    # Capability page MAY have been rewritten (evidence matched). Other pages
    # must NOT have changed on disk.
    unchanged_pages = [
        wiki / "components" / "user-repository.md",
        wiki / "decisions" / "postgresql-as-primary-store.md",
        wiki / "patterns" / "repository.md",
    ]
    for p in unchanged_pages:
        assert after[p] == before[p], f"{p} should not have been rewritten"

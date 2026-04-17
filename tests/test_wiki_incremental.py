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

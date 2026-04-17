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

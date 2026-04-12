"""Tests for finalize.py --normalize-only flag."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

FINALIZE_SCRIPT = Path(__file__).resolve().parent.parent / "archie" / "standalone" / "finalize.py"


def _run_normalize(project_root: Path):
    """Run finalize.py --normalize-only and return CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(FINALIZE_SCRIPT), str(project_root), "--normalize-only"],
        capture_output=True,
        text=True,
    )


class TestNormalizeOnly:
    def test_wraps_plain_list_components(self, tmp_path):
        """Plain list components should be wrapped into {"components": [...]}."""
        archie_dir = tmp_path / ".archie"
        archie_dir.mkdir()
        bp = {
            "meta": {"architecture_style": "test"},
            "components": [
                {"name": "Foo", "type": "module"},
                {"name": "Bar", "type": "module"},
            ],
        }
        (archie_dir / "blueprint.json").write_text(json.dumps(bp))

        result = _run_normalize(tmp_path)
        assert result.returncode == 0

        normalized = json.loads((archie_dir / "blueprint.json").read_text())
        assert isinstance(normalized["components"], dict)
        assert isinstance(normalized["components"]["components"], list)
        assert len(normalized["components"]["components"]) == 2
        assert "Normalized blueprint.json (2 components)" in result.stderr

    def test_idempotent(self, tmp_path):
        """Running normalize 3 times produces the same result."""
        archie_dir = tmp_path / ".archie"
        archie_dir.mkdir()
        bp = {
            "meta": {"architecture_style": "layered"},
            "components": [{"name": "A", "type": "service"}],
            "pitfalls": "not a list",
        }
        (archie_dir / "blueprint.json").write_text(json.dumps(bp))

        # Run 3 times
        for _ in range(3):
            result = _run_normalize(tmp_path)
            assert result.returncode == 0

        after_third = (archie_dir / "blueprint.json").read_text()

        # Run once more and compare
        _run_normalize(tmp_path)
        after_fourth = (archie_dir / "blueprint.json").read_text()

        assert after_third == after_fourth

    def test_exit_code_1_if_missing(self, tmp_path):
        """Should exit with code 1 if blueprint.json doesn't exist."""
        archie_dir = tmp_path / ".archie"
        archie_dir.mkdir()
        # No blueprint.json created

        result = _run_normalize(tmp_path)
        assert result.returncode == 1
        assert "blueprint.json not found" in result.stderr

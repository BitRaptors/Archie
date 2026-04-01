"""Tests for `archie status` dashboard."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from click.testing import CliRunner

from archie.cli.main import cli


def _write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def test_status_no_blueprint() -> None:
    """Empty dir with no blueprint shows guidance message."""
    with tempfile.TemporaryDirectory() as tmp:
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--path", tmp])
        assert result.exit_code == 0, result.output
        assert "No blueprint found" in result.output


def test_status_with_blueprint() -> None:
    """Minimal blueprint + scan + rules shows freshness and rule stats."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        archie_dir = tmp_path / ".archie"

        # Blueprint with file_tree
        _write_json(archie_dir / "blueprint.json", {
            "meta": {"analyzed_at": "2026-03-20T14:32:01"},
            "file_tree": {
                "src/main.py": {"hash": "aaa"},
                "src/utils.py": {"hash": "bbb"},
            },
        })

        # Scan with one new file and one modified, plus token counts
        _write_json(archie_dir / "scan.json", {
            "file_tree": {
                "src/main.py": {"hash": "aaa"},
                "src/utils.py": {"hash": "ccc"},  # modified
                "src/new.py": {"hash": "ddd"},     # new
            },
            "token_counts": {
                "src/main.py": 500_000,
                "src/utils.py": 300_000,
                "src/new.py": 200_000,
            },
        })

        # Create subagent prompt files
        (archie_dir / "subagent_0_prompt.md").write_text("prompt0")
        (archie_dir / "subagent_1_prompt.md").write_text("prompt1")

        # Rules
        _write_json(archie_dir / "rules.json", {
            "rules": [
                {"id": "r1", "severity": "warn", "description": "test"},
                {"id": "r2", "severity": "error", "description": "test"},
                {"id": "r3", "severity": "warn", "description": "test"},
            ],
        })

        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--path", tmp])
        assert result.exit_code == 0, result.output
        assert "2026-03-20T14:32:01" in result.output
        assert "Files in blueprint:  2" in result.output
        assert "Files on disk:       3" in result.output
        assert "New files:           1" in result.output
        assert "Modified files:      1" in result.output
        assert "Total:    3" in result.output
        assert "Warn:     2" in result.output
        assert "Error:    1" in result.output

        # Token tracking
        assert "Tokens" in result.output
        assert "Total scanned:     1,000,000" in result.output
        assert "Subagent groups:   2" in result.output
        assert "Avg per group:     500,000" in result.output


def test_status_with_stats() -> None:
    """stats.jsonl entries are counted and displayed."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        archie_dir = tmp_path / ".archie"

        _write_json(archie_dir / "blueprint.json", {
            "meta": {"analyzed_at": "2026-01-01T00:00:00"},
        })

        stats_path = archie_dir / "stats.jsonl"
        lines = [
            json.dumps({"rule_id": "r1", "result": "pass"}),
            json.dumps({"rule_id": "r2", "result": "warn"}),
            json.dumps({"rule_id": "r3", "result": "warn"}),
            json.dumps({"rule_id": "r4", "result": "block"}),
        ]
        stats_path.write_text("\n".join(lines) + "\n")

        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--path", tmp])
        assert result.exit_code == 0, result.output
        assert "Checks run:        4" in result.output
        assert "Warnings:          2" in result.output
        assert "Blocks:            1" in result.output


def test_status_never_crashes() -> None:
    """Corrupt/missing files still exit 0."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        archie_dir = tmp_path / ".archie"
        archie_dir.mkdir()

        # Write corrupt blueprint
        (archie_dir / "blueprint.json").write_text("{invalid json!!!")
        # Write corrupt scan
        (archie_dir / "scan.json").write_text("not json")
        # Write corrupt rules
        (archie_dir / "rules.json").write_text("{{{")
        # Write corrupt stats
        (archie_dir / "stats.jsonl").write_text("not json\nalso bad\n")

        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--path", tmp])
        assert result.exit_code == 0, result.output

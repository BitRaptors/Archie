"""Tests for `archie check` command."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from click.testing import CliRunner

from archie.cli.main import cli


def _write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def _make_rules(*rule_defs: dict) -> dict:
    return {"rules": list(rule_defs)}


def test_check_all_pass() -> None:
    """Files that match all rules produce exit 0 and 'pass' output."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _write_json(tmp_path / ".archie" / "rules.json", _make_rules(
            {
                "id": "naming-1",
                "check": "naming",
                "severity": "warn",
                "pattern": r"^[a-z_]+\.py$",
                "description": "snake_case Python files",
            },
        ))

        runner = CliRunner()
        result = runner.invoke(cli, [
            "check",
            "--path", tmp,
            "-f", "src/hello_world.py",
            "-f", "src/my_module.py",
        ])
        assert result.exit_code == 0, result.output
        assert "pass" in result.output
        assert "2 pass" in result.output
        assert "0 warning" in result.output
        assert "0 error" in result.output


def test_check_with_warning() -> None:
    """File violating a warn-level rule produces exit 0 (warnings don't fail)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _write_json(tmp_path / ".archie" / "rules.json", _make_rules(
            {
                "id": "naming-1",
                "check": "naming",
                "severity": "warn",
                "pattern": r"^[a-z_]+\.py$",
                "description": "snake_case expected",
            },
        ))

        runner = CliRunner()
        result = runner.invoke(cli, [
            "check",
            "--path", tmp,
            "-f", "src/MyBadName.py",
        ])
        assert result.exit_code == 0, result.output
        assert "warning" in result.output.lower()
        assert "0 error" in result.output


def test_check_with_error() -> None:
    """File violating an error-level rule produces exit 1."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _write_json(tmp_path / ".archie" / "rules.json", _make_rules(
            {
                "id": "placement-1",
                "check": "file_placement",
                "severity": "error",
                "allowed_dirs": ["src/api/"],
                "description": "direct DB import in API layer",
            },
        ))

        runner = CliRunner()
        result = runner.invoke(cli, [
            "check",
            "--path", tmp,
            "-f", "lib/payments.py",
        ])
        # SystemExit(1) is caught by CliRunner
        assert result.exit_code == 1, result.output
        assert "error" in result.output.lower()
        assert "1 error" in result.output


def test_check_no_rules() -> None:
    """No rules.json means nothing to check — exit 0."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / ".archie").mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, [
            "check",
            "--path", tmp,
            "-f", "src/foo.py",
        ])
        assert result.exit_code == 0, result.output
        assert "No rules" in result.output


def test_check_specific_files() -> None:
    """Only files passed via --files are checked."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _write_json(tmp_path / ".archie" / "rules.json", _make_rules(
            {
                "id": "naming-1",
                "check": "naming",
                "severity": "warn",
                "pattern": r"^[a-z_]+\.py$",
                "description": "snake_case expected",
            },
        ))

        runner = CliRunner()
        # Only check one file, not two — output should mention exactly 1 file
        result = runner.invoke(cli, [
            "check",
            "--path", tmp,
            "-f", "src/good_file.py",
        ])
        assert result.exit_code == 0, result.output
        assert "Checking 1 files" in result.output
        assert "1 pass" in result.output


def test_check_no_blueprint() -> None:
    """No .archie/ directory at all — appropriate message, exit 0."""
    with tempfile.TemporaryDirectory() as tmp:
        runner = CliRunner()
        result = runner.invoke(cli, [
            "check",
            "--path", tmp,
            "-f", "src/foo.py",
        ])
        assert result.exit_code == 0, result.output
        assert "No .archie/" in result.output

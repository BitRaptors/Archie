"""Tests for `archie refresh` via CLI."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from click.testing import CliRunner

from archie.cli.main import cli


def _make_repo(tmp: Path) -> None:
    """Create a minimal repo."""
    src = tmp / "src"
    src.mkdir()
    (src / "main.py").write_text("print('hello')\n")
    (tmp / "requirements.txt").write_text("fastapi>=0.100\n")


def _run_init(runner: CliRunner, tmp_path: Path) -> None:
    """Run archie init to establish a baseline scan."""
    result = runner.invoke(cli, ["init", str(tmp_path), "--local-only"])
    assert result.exit_code == 0, result.output


def test_refresh_updates_scan() -> None:
    """After adding a file, refresh updates scan.json to include it."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_repo(tmp_path)

        runner = CliRunner()
        _run_init(runner, tmp_path)

        # Add a new file
        (tmp_path / "src" / "new_module.py").write_text("y = 2\n")

        result = runner.invoke(cli, ["refresh", str(tmp_path)])
        assert result.exit_code == 0, result.output

        scan_file = tmp_path / ".archie" / "scan.json"
        assert scan_file.exists()

        data = json.loads(scan_file.read_text())
        paths = [e["path"] for e in data["file_tree"]]
        assert "src/new_module.py" in paths


def test_refresh_reports_changes() -> None:
    """After adding a file, refresh output mentions new files."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_repo(tmp_path)

        runner = CliRunner()
        _run_init(runner, tmp_path)

        # Add a new file
        (tmp_path / "src" / "extra.py").write_text("z = 3\n")

        result = runner.invoke(cli, ["refresh", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert "new files" in result.output.lower(), (
            f"Expected 'new files' in output, got:\n{result.output}"
        )


def test_refresh_no_blueprint() -> None:
    """Refresh without a prior init still works (creates baseline scan)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_repo(tmp_path)

        runner = CliRunner()
        # Run refresh directly — no init
        result = runner.invoke(cli, ["refresh", str(tmp_path)])
        assert result.exit_code == 0, result.output

        scan_file = tmp_path / ".archie" / "scan.json"
        assert scan_file.exists()


def test_refresh_deep_creates_prompt() -> None:
    """Running refresh --deep creates .archie/refresh_prompt.md."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_repo(tmp_path)

        runner = CliRunner()
        _run_init(runner, tmp_path)

        # Add a new file so there are changes to analyze
        (tmp_path / "src" / "deep_module.py").write_text("a = 1\n")

        result = runner.invoke(cli, ["refresh", str(tmp_path), "--deep"])
        assert result.exit_code == 0, result.output

        prompt_file = tmp_path / ".archie" / "refresh_prompt.md"
        assert prompt_file.exists(), (
            f"refresh_prompt.md missing; output:\n{result.output}"
        )
        content = prompt_file.read_text()
        assert "refresh" in content.lower()

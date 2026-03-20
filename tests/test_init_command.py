"""Tests for `archie init` end-to-end via CLI."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from click.testing import CliRunner

from archie.cli.main import cli


def _make_repo(tmp: Path) -> None:
    """Create a minimal repo with enough files for scan to detect something."""
    src = tmp / "src"
    src.mkdir()
    (src / "main.py").write_text("print('hello')\n")
    (src / "utils.py").write_text("x = 1\n")
    (tmp / "requirements.txt").write_text("fastapi>=0.100\nuvicorn\n")
    (tmp / "package.json").write_text(
        json.dumps({"dependencies": {"react": "^18.0.0"}})
    )


def test_init_creates_archie_dir() -> None:
    """Running `archie init <path> --local-only` creates .archie/scan.json."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_repo(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["init", str(tmp_path), "--local-only"])
        assert result.exit_code == 0, result.output

        scan_file = tmp_path / ".archie" / "scan.json"
        assert scan_file.exists(), f"scan.json missing; output:\n{result.output}"

        data = json.loads(scan_file.read_text())
        assert "file_tree" in data


def test_init_creates_hooks() -> None:
    """Running `archie init` installs hook scripts under .claude/hooks/."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_repo(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["init", str(tmp_path), "--local-only"])
        assert result.exit_code == 0, result.output

        hooks_dir = tmp_path / ".claude" / "hooks"
        assert (hooks_dir / "inject-context.sh").exists()
        assert (hooks_dir / "pre-validate.sh").exists()

        settings = tmp_path / ".claude" / "settings.local.json"
        assert settings.exists()


def test_init_creates_rules_json() -> None:
    """Running `archie init` creates .archie/rules.json (empty if no blueprint)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_repo(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["init", str(tmp_path), "--local-only"])
        assert result.exit_code == 0, result.output

        rules_file = tmp_path / ".archie" / "rules.json"
        assert rules_file.exists(), f"rules.json missing; output:\n{result.output}"

        data = json.loads(rules_file.read_text())
        assert "rules" in data


def test_init_outputs_coordinator_prompt() -> None:
    """The coordinator prompt file is created and mentions detected frameworks."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_repo(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["init", str(tmp_path), "--local-only"])
        assert result.exit_code == 0, result.output

        coord = tmp_path / ".archie" / "coordinator_prompt.md"
        assert coord.exists(), f"coordinator_prompt.md missing; output:\n{result.output}"

        content = coord.read_text()
        # The repo has fastapi in requirements.txt and react in package.json
        # At least one framework should appear in the prompt
        assert "fastapi" in content.lower() or "react" in content.lower(), (
            f"Expected framework name in coordinator prompt, got:\n{content[:500]}"
        )

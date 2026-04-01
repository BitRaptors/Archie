"""End-to-end tests for `archie refresh` with file change detection."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from click.testing import CliRunner

from archie.cli.main import cli


def _make_repo(tmp: Path, file_count: int = 2) -> None:
    """Create a minimal repo with *file_count* source files."""
    src = tmp / "src"
    src.mkdir()
    (src / "main.py").write_text("print('hello')\n")
    if file_count >= 2:
        (src / "utils.py").write_text("x = 1\n")
    if file_count >= 3:
        (src / "helpers.py").write_text("y = 2\n")
    (tmp / "requirements.txt").write_text("fastapi>=0.100\n")


def _run_init(runner: CliRunner, tmp_path: Path) -> None:
    """Run archie init --local-only to establish a baseline scan."""
    result = runner.invoke(cli, ["init", str(tmp_path), "--local-only"])
    assert result.exit_code == 0, f"init failed:\n{result.output}"


def _get_scan_hashes(tmp_path: Path) -> dict[str, str]:
    """Read file_hashes from the current scan.json."""
    scan_file = tmp_path / ".archie" / "scan.json"
    data = json.loads(scan_file.read_text())
    return data.get("file_hashes", {})


def _write_blueprint_with_hashes(tmp_path: Path, file_hashes: dict[str, str]) -> None:
    """Write a fake blueprint.json containing only file_hashes."""
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir(parents=True, exist_ok=True)
    bp = {"file_hashes": file_hashes}
    (archie_dir / "blueprint.json").write_text(json.dumps(bp), encoding="utf-8")


# --------------------------------------------------------------------------- #
# 1. Detect new file
# --------------------------------------------------------------------------- #


def test_refresh_detects_new_file() -> None:
    """After adding a 3rd file, refresh reports new files."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_repo(tmp_path, file_count=2)

        runner = CliRunner()
        _run_init(runner, tmp_path)

        # Add a 3rd source file
        (tmp_path / "src" / "new_module.py").write_text("z = 42\n")

        result = runner.invoke(cli, ["refresh", str(tmp_path)])
        assert result.exit_code == 0, result.output
        out = result.output.lower()
        assert "new files" in out, (
            f"Expected 'new files' in output, got:\n{result.output}"
        )


# --------------------------------------------------------------------------- #
# 2. Detect modified file
# --------------------------------------------------------------------------- #


def test_refresh_detects_modified_file() -> None:
    """After modifying a file, refresh reports modified/changed files."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_repo(tmp_path, file_count=2)

        runner = CliRunner()
        _run_init(runner, tmp_path)

        # Grab hashes from the scan, write them into blueprint.json
        old_hashes = _get_scan_hashes(tmp_path)
        _write_blueprint_with_hashes(tmp_path, old_hashes)

        # Modify an existing file
        (tmp_path / "src" / "utils.py").write_text("x = 999  # changed\n")

        result = runner.invoke(cli, ["refresh", str(tmp_path)])
        assert result.exit_code == 0, result.output
        out = result.output.lower()
        assert "modified files" in out, (
            f"Expected 'modified files' in output, got:\n{result.output}"
        )


# --------------------------------------------------------------------------- #
# 3. Detect deleted file
# --------------------------------------------------------------------------- #


def test_refresh_detects_deleted_file() -> None:
    """After deleting a file, refresh reports deleted files."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_repo(tmp_path, file_count=3)

        runner = CliRunner()
        _run_init(runner, tmp_path)

        # Grab hashes from the scan, write them into blueprint.json
        old_hashes = _get_scan_hashes(tmp_path)
        _write_blueprint_with_hashes(tmp_path, old_hashes)

        # Delete one file
        (tmp_path / "src" / "helpers.py").unlink()

        result = runner.invoke(cli, ["refresh", str(tmp_path)])
        assert result.exit_code == 0, result.output
        out = result.output.lower()
        assert "deleted files" in out, (
            f"Expected 'deleted files' in output, got:\n{result.output}"
        )


# --------------------------------------------------------------------------- #
# 4. Deep refresh generates prompt
# --------------------------------------------------------------------------- #


def test_refresh_deep_generates_prompt() -> None:
    """Running refresh --deep with changes creates .archie/refresh_prompt.md."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_repo(tmp_path, file_count=2)

        runner = CliRunner()
        _run_init(runner, tmp_path)

        # Write old hashes from scan into blueprint
        old_hashes = _get_scan_hashes(tmp_path)
        _write_blueprint_with_hashes(tmp_path, old_hashes)

        # Add a new file to trigger changes
        (tmp_path / "src" / "deep_target.py").write_text("deep = True\n")

        result = runner.invoke(cli, ["refresh", str(tmp_path), "--deep"])
        assert result.exit_code == 0, result.output

        prompt_file = tmp_path / ".archie" / "refresh_prompt.md"
        assert prompt_file.exists(), (
            f"refresh_prompt.md missing; output:\n{result.output}"
        )
        content = prompt_file.read_text()
        # Should mention the refresh context
        assert "refresh" in content.lower()
        # Should reference the new file
        assert "deep_target.py" in content


# --------------------------------------------------------------------------- #
# 5. No changes
# --------------------------------------------------------------------------- #


def test_refresh_no_changes() -> None:
    """When nothing changed, refresh says no changes."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_repo(tmp_path, file_count=2)

        runner = CliRunner()
        _run_init(runner, tmp_path)

        # Run refresh immediately — no file changes
        result = runner.invoke(cli, ["refresh", str(tmp_path)])
        assert result.exit_code == 0, result.output
        out = result.output.lower()
        assert "no changes" in out, (
            f"Expected 'no changes' in output, got:\n{result.output}"
        )

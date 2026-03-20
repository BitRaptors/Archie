"""Tests for archie.coordinator.runner — subagent spawning."""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from archie.coordinator.planner import SubagentAssignment
from archie.coordinator.runner import check_claude_cli, run_subagents, _extract_json
from archie.engine.models import RawScan, FileEntry


def _minimal_scan() -> RawScan:
    """Create a minimal RawScan for testing."""
    return RawScan(
        file_tree=[FileEntry(path="src/main.py", size=100, language="python")],
        dependencies=[],
        framework_signals=[],
        entry_points=[],
        config_files=[],
        token_counts={"src/main.py": 50},
        import_graph={},
    )


def _minimal_group() -> SubagentAssignment:
    """Create a minimal SubagentAssignment for testing."""
    return SubagentAssignment(
        files=["src/main.py"],
        token_total=50,
        sections=["components", "technology"],
        module_hint="src",
    )


def test_check_claude_cli() -> None:
    """check_claude_cli returns a bool."""
    result = check_claude_cli()
    assert isinstance(result, bool)


def test_run_subagents_handles_missing_cli() -> None:
    """When claude CLI is not found, subagent is skipped gracefully."""
    with tempfile.TemporaryDirectory() as tmp:
        scan = _minimal_scan()
        groups = [_minimal_group()]

        with patch("archie.coordinator.runner.subprocess.run", side_effect=FileNotFoundError("claude not found")):
            results = run_subagents(Path(tmp), scan, groups)

        assert results == []


def test_run_subagents_parses_json_response() -> None:
    """When claude returns valid JSON, the blueprint sections are parsed."""
    blueprint_sections = {"components": {"structure_type": "layered", "components": []}}
    claude_response = {
        "type": "result",
        "result": json.dumps(blueprint_sections),
        "cost_usd": 0.01,
    }

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = json.dumps(claude_response)
    mock_proc.stderr = ""

    with tempfile.TemporaryDirectory() as tmp:
        scan = _minimal_scan()
        groups = [_minimal_group()]

        with patch("archie.coordinator.runner.subprocess.run", return_value=mock_proc):
            results = run_subagents(Path(tmp), scan, groups)

        assert len(results) == 1
        assert results[0] == blueprint_sections


def test_run_subagents_handles_timeout() -> None:
    """When a subagent times out, it is skipped gracefully."""
    with tempfile.TemporaryDirectory() as tmp:
        scan = _minimal_scan()
        groups = [_minimal_group()]

        with patch(
            "archie.coordinator.runner.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=600),
        ):
            results = run_subagents(Path(tmp), scan, groups)

        assert results == []


def test_run_subagents_handles_nonzero_exit() -> None:
    """When claude returns a non-zero exit code, subagent is skipped."""
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stdout = ""
    mock_proc.stderr = "some error"

    with tempfile.TemporaryDirectory() as tmp:
        scan = _minimal_scan()
        groups = [_minimal_group()]

        with patch("archie.coordinator.runner.subprocess.run", return_value=mock_proc):
            results = run_subagents(Path(tmp), scan, groups)

        assert results == []


def test_run_subagents_handles_invalid_json() -> None:
    """When claude returns invalid JSON in the result field, subagent is skipped."""
    claude_response = {
        "type": "result",
        "result": "This is not JSON at all, just text",
        "cost_usd": 0.01,
    }

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = json.dumps(claude_response)
    mock_proc.stderr = ""

    with tempfile.TemporaryDirectory() as tmp:
        scan = _minimal_scan()
        groups = [_minimal_group()]

        with patch("archie.coordinator.runner.subprocess.run", return_value=mock_proc):
            results = run_subagents(Path(tmp), scan, groups)

        assert results == []


def test_extract_json_from_code_block() -> None:
    """_extract_json can parse JSON inside markdown code blocks."""
    text = 'Here is the result:\n```json\n{"components": {}}\n```'
    result = _extract_json(text)
    assert result == {"components": {}}


def test_extract_json_direct() -> None:
    """_extract_json can parse a plain JSON string."""
    result = _extract_json('{"technology": {"languages": ["python"]}}')
    assert result == {"technology": {"languages": ["python"]}}


def test_run_subagents_multiple_groups() -> None:
    """Multiple groups produce multiple results."""
    blueprint_1 = {"components": {"structure_type": "layered", "components": []}}
    blueprint_2 = {"technology": {"languages": ["python"]}}

    responses = [
        {"type": "result", "result": json.dumps(blueprint_1), "cost_usd": 0.01},
        {"type": "result", "result": json.dumps(blueprint_2), "cost_usd": 0.02},
    ]

    mock_procs = []
    for resp in responses:
        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = json.dumps(resp)
        proc.stderr = ""
        mock_procs.append(proc)

    with tempfile.TemporaryDirectory() as tmp:
        scan = _minimal_scan()
        groups = [_minimal_group(), _minimal_group()]

        with patch("archie.coordinator.runner.subprocess.run", side_effect=mock_procs):
            results = run_subagents(Path(tmp), scan, groups)

        assert len(results) == 2
        assert results[0] == blueprint_1
        assert results[1] == blueprint_2

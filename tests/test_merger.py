"""Tests for archie.coordinator.merger."""
from __future__ import annotations

from pathlib import Path

from archie.coordinator.merger import (
    load_blueprint,
    merge_subagent_outputs,
    save_blueprint,
)
from archie.engine.models import FrameworkSignal, RawScan


def _empty_scan() -> RawScan:
    return RawScan()


def test_merge_single_output():
    """A single subagent output passes through correctly."""
    output = {
        "components": {
            "structure_type": "layered",
            "components": [{"name": "API", "location": "src/api"}],
        },
        "architecture_diagram": "graph TD\n  A-->B",
    }
    result = merge_subagent_outputs([output], _empty_scan(), repo_name="test-repo")

    assert result["components"]["structure_type"] == "layered"
    assert len(result["components"]["components"]) == 1
    assert result["components"]["components"][0]["name"] == "API"
    assert result["architecture_diagram"] == "graph TD\n  A-->B"


def test_merge_multiple_outputs():
    """Two outputs with different sections merge into one."""
    output_a = {
        "components": {
            "structure_type": "layered",
            "components": [{"name": "API", "location": "src/api"}],
        },
    }
    output_b = {
        "technology": {
            "stack": [{"category": "runtime", "name": "Python", "version": "3.12"}],
            "project_structure": "src/\n  api/",
        },
    }
    result = merge_subagent_outputs([output_a, output_b], _empty_scan())

    assert result["components"]["structure_type"] == "layered"
    assert result["technology"]["stack"][0]["name"] == "Python"
    assert result["technology"]["project_structure"] == "src/\n  api/"


def test_merge_lists_concatenated():
    """developer_recipes from two outputs are combined and deduplicated."""
    output_a = {
        "developer_recipes": [
            {"task": "Add endpoint", "files": ["routes.py"], "steps": ["Create route"]},
        ],
    }
    output_b = {
        "developer_recipes": [
            {"task": "Add model", "files": ["models.py"], "steps": ["Define model"]},
            {"task": "Add endpoint", "files": ["routes.py", "views.py"], "steps": ["Create route v2"]},
        ],
    }
    result = merge_subagent_outputs([output_a, output_b], _empty_scan())

    tasks = [r["task"] for r in result["developer_recipes"]]
    # "Add endpoint" appears twice in input but should be deduplicated (last wins)
    assert tasks.count("Add endpoint") == 1
    assert "Add model" in tasks
    assert len(result["developer_recipes"]) == 2


def test_merge_fills_meta():
    """Meta section has analyzed_at and schema_version filled from scan data."""
    scan = RawScan(
        framework_signals=[
            FrameworkSignal(name="FastAPI", version="0.100", confidence=1.0),
        ],
    )
    result = merge_subagent_outputs([], scan, repo_name="my-repo")

    assert result["meta"]["schema_version"] == "2.0.0"
    assert result["meta"]["analyzed_at"]  # non-empty ISO timestamp
    assert result["meta"]["repository"] == "my-repo"
    assert "backend" in result["meta"]["platforms"]


def test_save_and_load_blueprint(tmp_path: Path):
    """Round-trip through .archie/blueprint.json."""
    blueprint = merge_subagent_outputs(
        [{"components": {"structure_type": "flat"}}],
        _empty_scan(),
        repo_name="round-trip",
    )

    save_blueprint(tmp_path, blueprint)
    loaded = load_blueprint(tmp_path)

    assert loaded is not None
    assert loaded["meta"]["repository"] == "round-trip"
    assert loaded["components"]["structure_type"] == "flat"

    # Missing file returns None
    assert load_blueprint(tmp_path / "nonexistent") is None

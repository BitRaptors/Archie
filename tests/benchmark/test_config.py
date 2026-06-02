# tests/benchmark/test_config.py
import json
import pytest
from pathlib import Path
from archie.benchmark.config import parse_config, load_config, BenchmarkConfig


def _valid():
    return {
        "name": "demo",
        "repo": "/tmp/repo",
        "task_prompt": "Add a feature",
        "model": "claude-sonnet-4-6",
    }


def test_parse_minimal_applies_defaults():
    cfg = parse_config(_valid())
    assert isinstance(cfg, BenchmarkConfig)
    assert cfg.repetitions == 3
    assert cfg.timeout_seconds == 3600
    assert cfg.branches == {"treatment": "archie-bench/with-archie", "control": "archie-bench/no-archie"}
    assert cfg.judge.model == "claude-opus-4-8"
    assert "correctness" in cfg.judge.rubric
    assert isinstance(cfg.repo, Path)


def test_parse_overrides():
    data = _valid()
    data.update({
        "repetitions": 5,
        "timeout_seconds": 1200,
        "branches": {"treatment": "t", "control": "c"},
        "judge": {"model": "m", "rubric": ["x"]},
    })
    cfg = parse_config(data)
    assert cfg.repetitions == 5
    assert cfg.timeout_seconds == 1200
    assert cfg.branches == {"treatment": "t", "control": "c"}
    assert cfg.judge.model == "m"
    assert cfg.judge.rubric == ["x"]


@pytest.mark.parametrize("missing", ["name", "repo", "task_prompt", "model"])
def test_missing_required_raises(missing):
    data = _valid()
    del data[missing]
    with pytest.raises(ValueError, match="required"):
        parse_config(data)


def test_repetitions_must_be_positive():
    data = _valid()
    data["repetitions"] = 0
    with pytest.raises(ValueError, match="repetitions"):
        parse_config(data)


def test_branches_missing_arm_raises():
    data = _valid()
    data["branches"] = {"treatment": "t"}
    with pytest.raises(ValueError, match="control"):
        parse_config(data)


def test_load_config_reads_file(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps(_valid()))
    cfg = load_config(p)
    assert cfg.name == "demo"

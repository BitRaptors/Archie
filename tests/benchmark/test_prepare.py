# tests/benchmark/test_prepare.py
import subprocess
import pytest
from archie.benchmark.config import BenchmarkConfig, JudgeConfig
from archie.benchmark import orchestrator as orch


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _repo(tmp_path, with_archie):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init"], repo)
    _git(["config", "user.email", "t@t.t"], repo)
    _git(["config", "user.name", "t"], repo)
    (repo / "src.py").write_text("print('hi')\n")
    if with_archie:
        (repo / "CLAUDE.md").write_text("# context\n")
        (repo / ".claude").mkdir()
        (repo / ".claude" / "settings.json").write_text("{}\n")
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "init"], repo)
    return repo


def _cfg(repo):
    return BenchmarkConfig(name="d", repo=repo, task_prompt="x", model="m",
                           branches={"treatment": "archie-bench/with-archie",
                                     "control": "archie-bench/no-archie"},
                           repetitions=1, judge=JudgeConfig(), timeout_seconds=60)


def test_clean_tree_required(tmp_path):
    repo = _repo(tmp_path, with_archie=True)
    (repo / "dirty.txt").write_text("uncommitted\n")
    with pytest.raises(ValueError, match="clean"):
        orch.prepare_branches(_cfg(repo))


def test_control_branch_strips_archie_files(tmp_path):
    repo = _repo(tmp_path, with_archie=True)
    status = orch.prepare_branches(_cfg(repo))
    # control branch checked out: Archie files gone
    _git(["checkout", "archie-bench/no-archie"], repo)
    assert not (repo / "CLAUDE.md").exists()
    assert not (repo / ".claude").exists()
    assert (repo / "src.py").exists()
    assert status["archie_present"] is True
    assert status["needs_deep_scan"] is False


def test_treatment_keeps_archie_files(tmp_path):
    repo = _repo(tmp_path, with_archie=True)
    orch.prepare_branches(_cfg(repo))
    _git(["checkout", "archie-bench/with-archie"], repo)
    assert (repo / "CLAUDE.md").exists()


def test_no_archie_flags_deep_scan_needed(tmp_path):
    repo = _repo(tmp_path, with_archie=False)
    status = orch.prepare_branches(_cfg(repo))
    assert status["archie_present"] is False
    assert status["needs_deep_scan"] is True


def test_cli_run_invokes_benchmark(tmp_path, monkeypatch):
    import json
    from archie.benchmark import cli
    repo = _repo(tmp_path, with_archie=True)
    cfg_file = tmp_path / "c.json"
    cfg_file.write_text(json.dumps({
        "name": "d", "repo": str(repo), "task_prompt": "x", "model": "m",
        "branches": {"treatment": "archie-bench/with-archie", "control": "archie-bench/no-archie"},
    }))
    called = {}
    monkeypatch.setattr(cli, "run_benchmark",
                        lambda cfg: called.update(ran=True) or {
                            "aggregate": {"treatment": {"n": 0, "completed_n": 0,
                                "attempted_n": 0,
                                "cost_usd_mean": None, "tool_calls_mean": None,
                                "duration_ms_mean": None, "quality_mean": None},
                                "control": {"n": 0, "completed_n": 0, "attempted_n": 0,
                                "cost_usd_mean": None,
                                "tool_calls_mean": None, "duration_ms_mean": None,
                                "quality_mean": None},
                                "savings": {"cost_pct": None, "tool_calls_pct": None,
                                "duration_pct": None}},
                            "store": {"mode": "offline"}})
    cli.main(["run", str(cfg_file)])
    assert called["ran"] is True

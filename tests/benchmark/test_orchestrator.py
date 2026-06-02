# tests/benchmark/test_orchestrator.py
import pytest
from archie.benchmark.config import BenchmarkConfig, JudgeConfig
from archie.benchmark.metrics import SampleMetrics
from archie.benchmark import orchestrator


def _cfg(tmp_path, reps=2):
    return BenchmarkConfig(
        name="demo", repo=tmp_path, task_prompt="do it",
        model="m", branches={"treatment": "treatment", "control": "control"},
        repetitions=reps, judge=JudgeConfig(model="jm", rubric=["correctness"]),
        timeout_seconds=60,
    )


def _fake_run(metrics_by_branch):
    seen = {"calls": []}

    def run_fn(prompt, model, cwd, timeout):
        # branch name is encoded in the worktree path by the orchestrator
        branch = "treatment" if "treatment" in str(cwd) else "control"
        seen["calls"].append((branch, prompt, model))
        return metrics_by_branch[branch], "raw"

    return run_fn, seen


def test_run_benchmark_builds_matrix_and_aggregates(tmp_path, monkeypatch):
    # neutralize real worktree/diff/base-commit side effects
    monkeypatch.setattr(orchestrator, "_base_commit", lambda repo: "abc123")
    monkeypatch.setattr(orchestrator, "_branch_base", lambda repo, b: "abc123")

    import contextlib
    @contextlib.contextmanager
    def fake_worktree(repo, branch, dest):
        yield tmp_path / ("wt-" + branch)
    monkeypatch.setattr(orchestrator, "worktree", fake_worktree)
    monkeypatch.setattr(orchestrator, "prune", lambda repo: None)

    t_metrics = SampleMetrics(tool_calls=5, cost_usd=1.0, duration_ms=100,
                              input_tokens=10, output_tokens=20, completed=True)
    c_metrics = SampleMetrics(tool_calls=12, cost_usd=3.0, duration_ms=300,
                              input_tokens=30, output_tokens=40, completed=True)
    run_fn, seen = _fake_run({"treatment": t_metrics, "control": c_metrics})

    judged = {"calls": 0}
    def judge_fn(task, t_diff, c_diff, rubric, model, seed):
        judged["calls"] += 1
        return {"treatment": {"overall": 9.0}, "control": {"overall": 5.0}, "seed": seed}

    stored = {}
    def store_fn(run_row, sample_rows, offline_path):
        stored["run"] = run_row
        stored["samples"] = sample_rows
        return {"mode": "offline", "path": str(offline_path)}

    result = orchestrator.run_benchmark(
        _cfg(tmp_path, reps=2),
        run_fn=run_fn, judge_fn=judge_fn, store_fn=store_fn,
        diff_fn=lambda wt: f"diff:{wt}",
    )

    # 2 reps x 2 arms = 4 runs; 2 reps = 2 pairwise judge calls
    assert len(seen["calls"]) == 4
    assert judged["calls"] == 2
    assert len(stored["samples"]) == 4
    # quality assigned per arm
    t_samples = [s for s in stored["samples"] if s["arm"] == "treatment"]
    assert all(s["quality_score"] == 9.0 for s in t_samples)
    # aggregate shows treatment cheaper
    assert result["aggregate"]["savings"]["cost_pct"] > 0
    # prompt identical across all runs
    assert len({c[1] for c in seen["calls"]}) == 1


def test_fairness_guard_rejects_divergent_base(tmp_path, monkeypatch):
    monkeypatch.setattr(orchestrator, "_branch_base",
                        lambda repo, b: "AAA" if b == "treatment" else "BBB")
    with pytest.raises(ValueError, match="base commit"):
        orchestrator.run_benchmark(_cfg(tmp_path), run_fn=lambda *a: None,
                                   judge_fn=lambda *a, **k: None,
                                   store_fn=lambda *a: None, diff_fn=lambda w: "")


def test_failed_sample_does_not_sink_run(tmp_path, monkeypatch):
    monkeypatch.setattr(orchestrator, "_branch_base", lambda repo, b: "same")
    monkeypatch.setattr(orchestrator, "_base_commit", lambda repo: "base")
    import contextlib
    @contextlib.contextmanager
    def fake_worktree(repo, branch, dest):
        yield tmp_path / ("wt-" + branch)
    monkeypatch.setattr(orchestrator, "worktree", fake_worktree)
    monkeypatch.setattr(orchestrator, "prune", lambda repo: None)

    def run_fn(prompt, model, cwd, timeout):
        if "treatment" in str(cwd):
            raise RuntimeError("treatment crashed")
        return SampleMetrics(completed=True, cost_usd=2.0), "raw"

    stored = {}
    result = orchestrator.run_benchmark(
        _cfg(tmp_path, reps=1),
        run_fn=run_fn,
        judge_fn=lambda *a, **k: {"treatment": {"overall": 0}, "control": {"overall": 5}, "seed": 0},
        store_fn=lambda r, s, p: stored.update(samples=s) or {"mode": "offline"},
        diff_fn=lambda wt: "",
    )
    # treatment sample recorded as not-completed; control still present
    arms = {s["arm"]: s for s in stored["samples"]}
    assert arms["treatment"]["completed"] is False
    assert arms["control"]["completed"] is True

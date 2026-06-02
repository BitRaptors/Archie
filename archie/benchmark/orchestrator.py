# archie/benchmark/orchestrator.py
import subprocess
import hashlib
from pathlib import Path

from .isolation import worktree, prune
from .diff import capture_diff
from .runner import run_claude
from .judge import run_judge
from .store import store_results
from .aggregate import aggregate_samples
from .metrics import SampleMetrics


def _git_out(args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), check=True,
                          capture_output=True, text=True).stdout.strip()


def _base_commit(repo):
    return _git_out(["rev-parse", "HEAD"], repo)


def _branch_base(repo, branch):
    """The commit the branch resolves to (used to verify both arms share a base)."""
    return _git_out(["rev-parse", branch], repo)


def _seed(name, repetition):
    h = hashlib.sha256(f"{name}:{repetition}".encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _worktrees_root(repo):
    root = Path(repo) / ".archie" / "benchmark" / "worktrees"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _run_one(cfg, branch, repetition, run_fn, diff_fn):
    """Run a single (branch, repetition) sample; return (metrics, diff)."""
    root = _worktrees_root(cfg.repo)
    dest = root / f"{branch.replace('/', '_')}-{repetition}"
    with worktree(cfg.repo, branch, dest) as wt:
        try:
            metrics, _raw = run_fn(cfg.task_prompt, cfg.model, wt, cfg.timeout_seconds)
        except Exception:
            return SampleMetrics(completed=False), ""
        diff = diff_fn(wt)
        return metrics, diff


def _sample_row(arm, repetition, metrics, quality_score, quality_detail, seed):
    return {
        "arm": arm,
        "repetition": repetition,
        "tool_calls": metrics.tool_calls,
        "tool_breakdown": metrics.tool_breakdown,
        "input_tokens": metrics.input_tokens,
        "output_tokens": metrics.output_tokens,
        "cache_read_tokens": metrics.cache_read_tokens,
        "cache_creation_tokens": metrics.cache_creation_tokens,
        "cost_usd": metrics.cost_usd,
        "duration_ms": metrics.duration_ms,
        "num_turns": metrics.num_turns,
        "completed": metrics.completed,
        "quality_score": quality_score,
        "quality_detail": quality_detail,
        "judge_seed": seed,
    }


def run_benchmark(cfg, run_fn=run_claude, judge_fn=run_judge,
                  store_fn=store_results, diff_fn=capture_diff):
    # Fairness guard: both arms must descend from the same base commit.
    t_base = _branch_base(cfg.repo, cfg.branches["treatment"])
    c_base = _branch_base(cfg.repo, cfg.branches["control"])
    if t_base != c_base:
        raise ValueError(
            f"arms have divergent base commit (treatment={t_base}, control={c_base}); "
            "both benchmark branches must branch from the same commit")

    prune(cfg.repo)
    samples = []
    for rep in range(cfg.repetitions):
        t_metrics, t_diff = _run_one(cfg, cfg.branches["treatment"], rep, run_fn, diff_fn)
        c_metrics, c_diff = _run_one(cfg, cfg.branches["control"], rep, run_fn, diff_fn)

        seed = _seed(cfg.name, rep)
        verdict = judge_fn(cfg.task_prompt, t_diff, c_diff, cfg.judge.rubric,
                           cfg.judge.model, seed)
        t_q = verdict["treatment"]
        c_q = verdict["control"]
        samples.append(_sample_row("treatment", rep, t_metrics,
                                    t_q.get("overall"), t_q, seed))
        samples.append(_sample_row("control", rep, c_metrics,
                                    c_q.get("overall"), c_q, seed))
    prune(cfg.repo)

    agg = aggregate_samples(samples)
    run_row = {
        "name": cfg.name,
        "repo_name": Path(cfg.repo).name,
        "task_prompt": cfg.task_prompt,
        "model": cfg.model,
        "judge_model": cfg.judge.model,
        "repetitions": cfg.repetitions,
        "git_base_commit": _base_commit(cfg.repo),
        "prep_cost_usd": None,
        "archie_version": _archie_version(),
    }
    offline_path = Path(cfg.repo) / ".archie" / "benchmark" / cfg.name / "results.json"
    store_result = store_fn(run_row, samples, offline_path)
    return {"aggregate": agg, "samples": samples, "store": store_result, "run": run_row}


def _archie_version():
    try:
        from archie import __version__
        return __version__
    except Exception:
        return "unknown"

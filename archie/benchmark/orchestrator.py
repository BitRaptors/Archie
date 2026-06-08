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


def _merge_base(repo, a, b):
    """The common-ancestor commit of two branches.

    Used to verify both arms descend from the same base. We compare the
    merge-base (not branch tips): prep intentionally adds a strip/deep-scan
    commit to an arm, so the tips legitimately differ while the shared base
    does not.
    """
    return _git_out(["merge-base", a, b], repo)


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


def _sample_row(arm, repetition, metrics, quality_score, quality_detail, seed, attempted):
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
        "attempted": attempted,
        "quality_score": quality_score,
        "quality_detail": quality_detail,
        "judge_seed": seed,
    }


def run_benchmark(cfg, run_fn=run_claude, judge_fn=run_judge,
                  store_fn=store_results, diff_fn=capture_diff):
    # Fairness guard: both arms must descend from the same base commit. We
    # compare the merge-base, not branch tips — prep adds a strip/deep-scan
    # commit to an arm, so tips differ while the common base must not.
    try:
        base = _merge_base(cfg.repo, cfg.branches["treatment"], cfg.branches["control"])
    except subprocess.CalledProcessError:
        base = ""
    if not base:
        raise ValueError(
            "benchmark arms have no common ancestor base commit; both branches "
            "must branch from the same commit")

    prune(cfg.repo)
    samples = []
    for rep in range(cfg.repetitions):
        t_metrics, t_diff = _run_one(cfg, cfg.branches["treatment"], rep, run_fn, diff_fn)
        c_metrics, c_diff = _run_one(cfg, cfg.branches["control"], rep, run_fn, diff_fn)

        # "Attempted" = the agent actually produced a code change. An empty
        # diff means the task was not attempted, regardless of how the judge
        # scores it — tracked so it can be excluded from quality means.
        t_attempted = bool((t_diff or "").strip())
        c_attempted = bool((c_diff or "").strip())

        seed = _seed(cfg.name, rep)
        try:
            verdict = judge_fn(cfg.task_prompt, t_diff, c_diff, cfg.judge.rubric,
                               cfg.judge.model, seed)
            t_q = verdict["treatment"]
            c_q = verdict["control"]
        except Exception:
            # A judge failure must not discard the (expensive) completed runs;
            # record the samples without a quality score instead of aborting.
            t_q = c_q = None
        samples.append(_sample_row("treatment", rep, t_metrics,
                                    t_q.get("overall") if t_q else None, t_q, seed,
                                    t_attempted))
        samples.append(_sample_row("control", rep, c_metrics,
                                    c_q.get("overall") if c_q else None, c_q, seed,
                                    c_attempted))
    prune(cfg.repo)

    agg = aggregate_samples(samples)
    run_row = {
        "name": cfg.name,
        "repo_name": Path(cfg.repo).name,
        "task_prompt": cfg.task_prompt,
        "model": cfg.model,
        "judge_model": cfg.judge.model,
        "repetitions": cfg.repetitions,
        "git_base_commit": base,
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


ARCHIE_PATHS = ["CLAUDE.md", "AGENTS.md", ".claude", ".archie"]


def _is_clean(repo):
    out = _git_out(["status", "--porcelain"], repo)
    return out == ""


def _archie_present(repo):
    return any((Path(repo) / p).exists() for p in ARCHIE_PATHS)


def _branch_exists(repo, branch):
    res = subprocess.run(["git", "rev-parse", "--verify", branch],
                         cwd=str(repo), capture_output=True, text=True)
    return res.returncode == 0


def _create_branch(repo, branch, base):
    if _branch_exists(repo, branch):
        subprocess.run(["git", "branch", "-D", branch], cwd=str(repo),
                       capture_output=True, text=True)
    _git_out(["branch", branch, base], repo)


def _strip_archie_on_branch(repo, branch):
    """Check out branch, remove Archie artifacts (incl. per-folder CLAUDE.md), commit."""
    current = _git_out(["rev-parse", "--abbrev-ref", "HEAD"], repo)
    _git_out(["checkout", branch], repo)
    try:
        # remove root-level + nested CLAUDE.md and known Archie dirs/files
        subprocess.run(["git", "rm", "-r", "--quiet", "--ignore-unmatch",
                        *ARCHIE_PATHS], cwd=str(repo), capture_output=True, text=True)
        # nested per-folder CLAUDE.md files. Use -z (NUL-delimited) so paths
        # containing spaces (e.g. Xcode "Button icons/") are not fragmented —
        # splitting on whitespace would break them and git rm would skip them,
        # leaking Archie context onto the control arm.
        out = subprocess.run(["git", "ls-files", "-z", "*/CLAUDE.md"], cwd=str(repo),
                             capture_output=True, text=True).stdout
        nested = [p for p in out.split("\0") if p]
        if nested:
            subprocess.run(["git", "rm", "--quiet", "--ignore-unmatch", *nested],
                           cwd=str(repo), capture_output=True, text=True)
        if not _is_clean(repo):
            _git_out(["commit", "-m", "benchmark: strip Archie artifacts (control arm)"], repo)
    finally:
        _git_out(["checkout", current], repo)


def prepare_branches(cfg):
    """Create control (no Archie) and treatment (with Archie) branches from current HEAD.

    Returns a status dict; if Archie is absent, `needs_deep_scan` is True and the
    caller (cli) must run the interactive deep-scan on the treatment branch.
    """
    repo = cfg.repo
    if not _is_clean(repo):
        raise ValueError("working tree is not clean; commit or stash before benchmarking")

    base = _base_commit(repo)
    archie_present = _archie_present(repo)

    _create_branch(repo, cfg.branches["treatment"], base)
    _create_branch(repo, cfg.branches["control"], base)

    if archie_present:
        _strip_archie_on_branch(repo, cfg.branches["control"])
    # if absent, control already has no Archie files; treatment will be populated
    # by the interactive deep-scan (cli handles the pause).

    return {
        "archie_present": archie_present,
        "needs_deep_scan": not archie_present,
        "base": base,
        "branches": cfg.branches,
    }

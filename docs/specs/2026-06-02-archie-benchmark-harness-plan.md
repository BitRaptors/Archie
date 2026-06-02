# Archie Benchmark Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an internal Python tool that runs an identical headless Claude Code task on a control branch (no Archie) and a treatment branch (full Archie docs+hooks), captures tool calls / tokens / cost / time + a blind judge-Claude quality score, and stores results in Supabase.

**Architecture:** Zero-dep stdlib Python package `archie/benchmark/`. Each module has one responsibility: config parsing, git-worktree isolation, headless `claude -p` execution, stream-json metric extraction, diff capture, blind judge scoring, Supabase write, and an orchestrator that runs the (arm × repetition) matrix. External side effects (the `claude` CLI, git, Supabase HTTP) are isolated behind functions that accept injectable dependencies so tests mock them.

**Tech Stack:** Python 3.9+ (stdlib only — `json`, `subprocess`, `urllib`, `dataclasses`, `pathlib`, `contextlib`, `hashlib`, `argparse`), pytest, Claude Code CLI (`claude -p`), Supabase PostgREST.

**Spec:** `docs/specs/2026-06-02-archie-benchmark-harness-design.md`

---

## File Structure

```
archie/benchmark/
  __init__.py        # package marker, exports
  config.py          # BenchmarkConfig + JudgeConfig dataclasses, load/parse/validate
  metrics.py         # SampleMetrics dataclass + parse_stream(lines)
  diff.py            # capture_diff(worktree_path) -> str
  isolation.py       # worktree() contextmanager + prune()
  runner.py          # run_claude(...) -> (SampleMetrics, raw_stdout)
  judge.py           # run_judge(...) -> per-arm rubric scores (blind, seeded A/B)
  store.py           # store_results(...) -> Supabase write or offline fallback
  aggregate.py       # aggregate_samples(samples) -> per-arm means/spread
  orchestrator.py    # run_benchmark(config, deps...) + prepare_branches(...)
  cli.py             # argparse entry: run / auto / prep
  schema.sql         # versioned Supabase DDL (tables + summary view)
tests/benchmark/
  __init__.py
  test_config.py
  test_metrics.py
  test_diff.py
  test_isolation.py
  test_runner.py
  test_judge.py
  test_store.py
  test_aggregate.py
  test_orchestrator.py
```

**Conventions to follow (from existing `archie/standalone/`):** zero third-party imports, `subprocess.run(..., capture_output=True, text=True)`, defensive `.get()` on parsed JSON, no secrets in logs.

---

## Shared Type Contracts (defined once, used everywhere)

These exact shapes are used across tasks — keep names identical.

- `BenchmarkConfig`: `name:str, repo:Path, task_prompt:str, model:str, branches:dict{"treatment":str,"control":str}, repetitions:int, judge:JudgeConfig, timeout_seconds:int`
- `JudgeConfig`: `model:str, rubric:list[str]`
- `SampleMetrics`: `tool_calls:int, tool_breakdown:dict[str,int], input_tokens:int, output_tokens:int, cache_read_tokens:int, cache_creation_tokens:int, cost_usd:float, duration_ms:int, num_turns:int, completed:bool`
- Judge result dict: `{"treatment": {<axis>:int,..,"overall":float,"justification":str}, "control": {...}, "seed": int}`
- Sample row dict (for store): `{arm, repetition, tool_calls, tool_breakdown, input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens, cost_usd, duration_ms, num_turns, completed, quality_score, quality_detail, judge_seed}`

---

### Task 1: Package scaffold + config

**Files:**
- Create: `archie/benchmark/__init__.py`
- Create: `archie/benchmark/config.py`
- Create: `tests/benchmark/__init__.py`
- Test: `tests/benchmark/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/benchmark/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'archie.benchmark.config'`

- [ ] **Step 3: Write minimal implementation**

```python
# archie/benchmark/__init__.py
"""Internal Archie effectiveness benchmark harness (not shipped via npm)."""
```

```python
# archie/benchmark/config.py
import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_JUDGE_MODEL = "claude-opus-4-8"
DEFAULT_RUBRIC = ["correctness", "completeness", "follows_conventions", "no_regressions"]
DEFAULT_BRANCHES = {"treatment": "archie-bench/with-archie", "control": "archie-bench/no-archie"}
DEFAULT_TIMEOUT = 3600
DEFAULT_REPETITIONS = 3
REQUIRED = ("name", "repo", "task_prompt", "model")


@dataclass
class JudgeConfig:
    model: str = DEFAULT_JUDGE_MODEL
    rubric: list = field(default_factory=lambda: list(DEFAULT_RUBRIC))


@dataclass
class BenchmarkConfig:
    name: str
    repo: Path
    task_prompt: str
    model: str
    branches: dict = field(default_factory=lambda: dict(DEFAULT_BRANCHES))
    repetitions: int = DEFAULT_REPETITIONS
    judge: JudgeConfig = field(default_factory=JudgeConfig)
    timeout_seconds: int = DEFAULT_TIMEOUT


def parse_config(data):
    missing = [k for k in REQUIRED if k not in data or data[k] in (None, "")]
    if missing:
        raise ValueError(f"config missing required fields: {', '.join(missing)}")

    branches = data.get("branches", dict(DEFAULT_BRANCHES))
    for arm in ("treatment", "control"):
        if arm not in branches or not branches[arm]:
            raise ValueError(f"config.branches missing '{arm}'")

    reps = int(data.get("repetitions", DEFAULT_REPETITIONS))
    if reps < 1:
        raise ValueError("repetitions must be >= 1")

    jd = data.get("judge", {}) or {}
    judge = JudgeConfig(
        model=jd.get("model") or DEFAULT_JUDGE_MODEL,
        rubric=jd.get("rubric") or list(DEFAULT_RUBRIC),
    )

    return BenchmarkConfig(
        name=data["name"],
        repo=Path(data["repo"]).expanduser(),
        task_prompt=data["task_prompt"],
        model=data["model"],
        branches={"treatment": branches["treatment"], "control": branches["control"]},
        repetitions=reps,
        judge=judge,
        timeout_seconds=int(data.get("timeout_seconds", DEFAULT_TIMEOUT)),
    )


def load_config(path):
    return parse_config(json.loads(Path(path).read_text()))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/benchmark/test_config.py -v`
Expected: PASS (all 9 cases)

- [ ] **Step 5: Commit**

```bash
git add archie/benchmark/__init__.py archie/benchmark/config.py tests/benchmark/__init__.py tests/benchmark/test_config.py
git commit -m "feat(benchmark): config dataclasses + JSON parsing/validation"
```

---

### Task 2: Stream-json metric extraction

**Files:**
- Create: `archie/benchmark/metrics.py`
- Test: `tests/benchmark/test_metrics.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/benchmark/test_metrics.py
import json
from archie.benchmark.metrics import parse_stream, SampleMetrics


def _assistant(blocks):
    return json.dumps({"type": "assistant", "message": {"content": blocks}})


def _tool_use(name):
    return {"type": "tool_use", "name": name, "id": "x", "input": {}}


def _result(subtype="success"):
    return json.dumps({
        "type": "result",
        "subtype": subtype,
        "total_cost_usd": 0.1234,
        "duration_ms": 5000,
        "num_turns": 7,
        "usage": {
            "input_tokens": 100,
            "output_tokens": 200,
            "cache_read_input_tokens": 50,
            "cache_creation_input_tokens": 25,
        },
    })


def test_counts_tools_and_breakdown():
    lines = [
        json.dumps({"type": "system", "subtype": "init"}),
        _assistant([{"type": "text", "text": "hi"}, _tool_use("Read")]),
        _assistant([_tool_use("Edit"), _tool_use("Edit")]),
        _result(),
    ]
    m = parse_stream(lines)
    assert m.tool_calls == 3
    assert m.tool_breakdown == {"Read": 1, "Edit": 2}


def test_extracts_result_fields():
    m = parse_stream([_result()])
    assert m.input_tokens == 100
    assert m.output_tokens == 200
    assert m.cache_read_tokens == 50
    assert m.cache_creation_tokens == 25
    assert m.cost_usd == 0.1234
    assert m.duration_ms == 5000
    assert m.num_turns == 7
    assert m.completed is True


def test_error_result_not_completed():
    m = parse_stream([_result(subtype="error_max_turns")])
    assert m.completed is False


def test_zero_tool_run():
    m = parse_stream([_assistant([{"type": "text", "text": "done"}]), _result()])
    assert m.tool_calls == 0
    assert m.tool_breakdown == {}


def test_ignores_blank_and_malformed_lines():
    m = parse_stream(["", "  ", "not json", _result()])
    assert m.completed is True


def test_no_result_event_defaults():
    m = parse_stream([_assistant([_tool_use("Bash")])])
    assert m.tool_calls == 1
    assert m.completed is False
    assert m.cost_usd == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/benchmark/test_metrics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'archie.benchmark.metrics'`

- [ ] **Step 3: Write minimal implementation**

```python
# archie/benchmark/metrics.py
import json
from dataclasses import dataclass, field


@dataclass
class SampleMetrics:
    tool_calls: int = 0
    tool_breakdown: dict = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    num_turns: int = 0
    completed: bool = False


def parse_stream(lines):
    m = SampleMetrics()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        etype = ev.get("type")
        if etype == "assistant":
            for block in ev.get("message", {}).get("content", []) or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    m.tool_calls += 1
                    name = block.get("name", "unknown")
                    m.tool_breakdown[name] = m.tool_breakdown.get(name, 0) + 1
        elif etype == "result":
            usage = ev.get("usage", {}) or {}
            m.input_tokens = usage.get("input_tokens", 0)
            m.output_tokens = usage.get("output_tokens", 0)
            m.cache_read_tokens = usage.get("cache_read_input_tokens", 0)
            m.cache_creation_tokens = usage.get("cache_creation_input_tokens", 0)
            m.cost_usd = ev.get("total_cost_usd", 0.0)
            m.duration_ms = ev.get("duration_ms", 0)
            m.num_turns = ev.get("num_turns", 0)
            m.completed = ev.get("subtype") == "success"
    return m
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/benchmark/test_metrics.py -v`
Expected: PASS (6 cases)

- [ ] **Step 5: Commit**

```bash
git add archie/benchmark/metrics.py tests/benchmark/test_metrics.py
git commit -m "feat(benchmark): stream-json metric extraction (tools, tokens, cost, completed)"
```

---

### Task 3: Diff capture

**Files:**
- Create: `archie/benchmark/diff.py`
- Test: `tests/benchmark/test_diff.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/benchmark/test_diff.py
import subprocess
from archie.benchmark.diff import capture_diff


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(path):
    _git(["init"], path)
    _git(["config", "user.email", "t@t.t"], path)
    _git(["config", "user.name", "t"], path)
    (path / "a.txt").write_text("one\n")
    _git(["add", "-A"], path)
    _git(["commit", "-m", "init"], path)


def test_captures_modified_and_untracked(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("one\ntwo\n")      # modified, tracked
    (tmp_path / "b.txt").write_text("new file\n")       # untracked
    diff = capture_diff(tmp_path)
    assert "a.txt" in diff
    assert "two" in diff
    assert "b.txt" in diff
    assert "new file" in diff


def test_empty_diff_when_no_changes(tmp_path):
    _init_repo(tmp_path)
    diff = capture_diff(tmp_path)
    assert diff.strip() == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/benchmark/test_diff.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'archie.benchmark.diff'`

- [ ] **Step 3: Write minimal implementation**

```python
# archie/benchmark/diff.py
import subprocess


def capture_diff(worktree_path):
    """Stage everything (so untracked files show) and return the cached diff text."""
    subprocess.run(["git", "add", "-A"], cwd=str(worktree_path),
                   check=True, capture_output=True, text=True)
    result = subprocess.run(["git", "diff", "--cached"], cwd=str(worktree_path),
                            check=True, capture_output=True, text=True)
    return result.stdout
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/benchmark/test_diff.py -v`
Expected: PASS (2 cases)

- [ ] **Step 5: Commit**

```bash
git add archie/benchmark/diff.py tests/benchmark/test_diff.py
git commit -m "feat(benchmark): capture full diff (modified + untracked) from a worktree"
```

---

### Task 4: Git worktree isolation

**Files:**
- Create: `archie/benchmark/isolation.py`
- Test: `tests/benchmark/test_isolation.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/benchmark/test_isolation.py
import subprocess
from pathlib import Path
from archie.benchmark.isolation import worktree, prune


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(path):
    _git(["init"], path)
    _git(["config", "user.email", "t@t.t"], path)
    _git(["config", "user.name", "t"], path)
    (path / "a.txt").write_text("one\n")
    _git(["add", "-A"], path)
    _git(["commit", "-m", "init"], path)
    _git(["branch", "feature"], path)


def test_worktree_created_and_removed(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    dest = tmp_path / "wt"
    with worktree(repo, "feature", dest) as wt:
        assert Path(wt).exists()
        assert (Path(wt) / "a.txt").exists()
    assert not Path(dest).exists()


def test_worktree_removed_on_exception(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    dest = tmp_path / "wt"
    try:
        with worktree(repo, "feature", dest):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert not Path(dest).exists()


def test_prune_runs_without_error(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    prune(repo)  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/benchmark/test_isolation.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'archie.benchmark.isolation'`

- [ ] **Step 3: Write minimal implementation**

```python
# archie/benchmark/isolation.py
import subprocess
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def worktree(repo_path, branch, dest):
    """Create a git worktree for `branch` at `dest`, always removed on exit."""
    dest = Path(dest)
    subprocess.run(["git", "worktree", "add", "--force", str(dest), branch],
                   cwd=str(repo_path), check=True, capture_output=True, text=True)
    try:
        yield dest
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(dest)],
                       cwd=str(repo_path), capture_output=True, text=True)


def prune(repo_path):
    subprocess.run(["git", "worktree", "prune"],
                   cwd=str(repo_path), capture_output=True, text=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/benchmark/test_isolation.py -v`
Expected: PASS (3 cases)

- [ ] **Step 5: Commit**

```bash
git add archie/benchmark/isolation.py tests/benchmark/test_isolation.py
git commit -m "feat(benchmark): git worktree contextmanager with guaranteed cleanup"
```

---

### Task 5: Headless claude runner

**Files:**
- Create: `archie/benchmark/runner.py`
- Test: `tests/benchmark/test_runner.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/benchmark/test_runner.py
import json
import subprocess
import pytest
from archie.benchmark import runner


def _stream():
    return "\n".join([
        json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Edit"}]}}),
        json.dumps({"type": "result", "subtype": "success", "total_cost_usd": 0.5,
                    "duration_ms": 1000, "num_turns": 2,
                    "usage": {"input_tokens": 10, "output_tokens": 20}}),
    ])


def test_run_claude_parses_metrics(monkeypatch):
    captured = {}

    def fake_run(cmd, cwd=None, capture_output=None, text=None, timeout=None):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        return subprocess.CompletedProcess(cmd, 0, stdout=_stream(), stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    metrics, raw = runner.run_claude("do it", "claude-sonnet-4-6", "/tmp/wt", 60)

    assert metrics.tool_calls == 1
    assert metrics.cost_usd == 0.5
    assert metrics.completed is True
    assert captured["cwd"] == "/tmp/wt"
    # identical, fair harness flags must always be present
    assert captured["cmd"][:2] == ["claude", "-p"]
    assert "--permission-mode" in captured["cmd"]
    assert "acceptEdits" in captured["cmd"]
    assert "stream-json" in captured["cmd"]
    assert "--model" in captured["cmd"] and "claude-sonnet-4-6" in captured["cmd"]


def test_timeout_marks_incomplete(monkeypatch):
    def fake_run(cmd, cwd=None, capture_output=None, text=None, timeout=None):
        raise subprocess.TimeoutExpired(cmd, timeout, output=_stream())

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    metrics, raw = runner.run_claude("do it", "m", "/tmp/wt", 1)
    assert metrics.completed is False
    assert metrics.tool_calls == 1  # partial stdout still parsed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/benchmark/test_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'archie.benchmark.runner'`

- [ ] **Step 3: Write minimal implementation**

```python
# archie/benchmark/runner.py
import subprocess
from .metrics import parse_stream


def run_claude(prompt, model, cwd, timeout_seconds):
    """Run a headless Claude Code session in `cwd`; return (SampleMetrics, raw_stdout).

    Both benchmark arms must call this with identical flags — the only difference
    between arms is the on-disk files (CLAUDE.md / .claude hooks), never the flags.
    """
    cmd = [
        "claude", "-p", prompt,
        "--model", model,
        "--output-format", "stream-json", "--verbose",
        "--permission-mode", "acceptEdits",
    ]
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True,
                              text=True, timeout=timeout_seconds)
        metrics = parse_stream(proc.stdout.splitlines())
        return metrics, proc.stdout
    except subprocess.TimeoutExpired as e:
        partial = e.output or ""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", "replace")
        metrics = parse_stream(partial.splitlines())
        metrics.completed = False
        return metrics, partial
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/benchmark/test_runner.py -v`
Expected: PASS (2 cases)

- [ ] **Step 5: Commit**

```bash
git add archie/benchmark/runner.py tests/benchmark/test_runner.py
git commit -m "feat(benchmark): headless claude -p runner with timeout handling"
```

---

### Task 6: Blind judge

**Files:**
- Create: `archie/benchmark/judge.py`
- Test: `tests/benchmark/test_judge.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/benchmark/test_judge.py
import json
import pytest
from archie.benchmark import judge


def test_assign_order_is_seed_deterministic():
    assert judge.assign_order(0) == ("a", "b")
    assert judge.assign_order(2) == ("a", "b")
    assert judge.assign_order(1) == ("b", "a")
    assert judge.assign_order(3) == ("b", "a")


def test_parse_judge_output_extracts_embedded_json():
    text = 'Here is my verdict:\n{"variant_a": {"overall": 8}, "variant_b": {"overall": 5}}\nThanks'
    parsed = judge.parse_judge_output(text)
    assert parsed["variant_a"]["overall"] == 8


def test_parse_judge_output_raises_without_json():
    with pytest.raises(ValueError, match="JSON"):
        judge.parse_judge_output("no json here")


def test_run_judge_maps_variants_to_arms_seed_even():
    # seed even -> treatment is variant_a
    payload = json.dumps({"variant_a": {"overall": 9}, "variant_b": {"overall": 4}})
    calls = []

    def fake_runner(prompt, model, timeout):
        calls.append((prompt, model))
        return payload

    result = judge.run_judge("task", "TREAT_DIFF", "CTRL_DIFF",
                             rubric=["correctness"], model="m", seed=0,
                             _runner=fake_runner)
    assert result["treatment"]["overall"] == 9
    assert result["control"]["overall"] == 4
    assert result["seed"] == 0
    # variant A diff (shown first) must be the treatment diff for an even seed
    assert calls[0][0].index("TREAT_DIFF") < calls[0][0].index("CTRL_DIFF")


def test_run_judge_maps_variants_to_arms_seed_odd():
    # seed odd -> treatment is variant_b
    payload = json.dumps({"variant_a": {"overall": 3}, "variant_b": {"overall": 7}})
    result = judge.run_judge("task", "TREAT_DIFF", "CTRL_DIFF",
                             rubric=["correctness"], model="m", seed=1,
                             _runner=lambda p, m, t: payload)
    assert result["treatment"]["overall"] == 7
    assert result["control"]["overall"] == 3


def test_run_judge_retries_once_on_bad_json():
    outputs = ["garbage", json.dumps({"variant_a": {"overall": 6}, "variant_b": {"overall": 6}})]

    def flaky(prompt, model, timeout):
        return outputs.pop(0)

    result = judge.run_judge("task", "A", "B", rubric=["c"], model="m", seed=0, _runner=flaky)
    assert result["treatment"]["overall"] == 6
    assert outputs == []  # both outputs consumed -> retried exactly once


def test_run_judge_raises_after_two_failures():
    with pytest.raises(ValueError):
        judge.run_judge("task", "A", "B", rubric=["c"], model="m", seed=0,
                        _runner=lambda p, m, t: "still garbage")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/benchmark/test_judge.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'archie.benchmark.judge'`

- [ ] **Step 3: Write minimal implementation**

```python
# archie/benchmark/judge.py
import json
import subprocess


def assign_order(seed):
    """Return (treatment_variant, control_variant) — blind A/B label assignment."""
    return ("a", "b") if seed % 2 == 0 else ("b", "a")


def build_judge_prompt(task_prompt, diff_a, diff_b, rubric):
    axes = ", ".join(rubric)
    schema = ('{"variant_a": {' + ", ".join(f'"{a}": int' for a in rubric)
              + ', "overall": number, "justification": string}, "variant_b": {... same keys ...}}')
    return (
        "You are an impartial senior code reviewer. Two AI agents independently "
        "attempted the SAME task. You are shown each agent's diff as an anonymous "
        "variant. Judge purely on the code; you do not know anything about how each "
        "was produced.\n\n"
        f"TASK GIVEN TO BOTH AGENTS:\n{task_prompt}\n\n"
        f"Score each variant on these axes (each 1-10): {axes}. Also give an "
        "'overall' score (0-10) and a one-sentence 'justification'.\n\n"
        f"Respond with ONLY a JSON object of this exact shape:\n{schema}\n\n"
        f"=== VARIANT A DIFF ===\n{diff_a}\n\n"
        f"=== VARIANT B DIFF ===\n{diff_b}\n"
    )


def parse_judge_output(text):
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found in judge output")
    return json.loads(text[start:end + 1])


def _default_runner(prompt, model, timeout):
    proc = subprocess.run(
        ["claude", "-p", prompt, "--model", model, "--output-format", "text"],
        capture_output=True, text=True, timeout=timeout,
    )
    return proc.stdout


def run_judge(task_prompt, treatment_diff, control_diff, rubric, model, seed,
              timeout_seconds=600, _runner=None):
    t_variant, c_variant = assign_order(seed)
    diff_a = treatment_diff if t_variant == "a" else control_diff
    diff_b = treatment_diff if t_variant == "b" else control_diff
    prompt = build_judge_prompt(task_prompt, diff_a, diff_b, rubric)

    runner = _runner or _default_runner
    parsed = None
    last_err = None
    for _ in range(2):
        try:
            parsed = parse_judge_output(runner(prompt, model, timeout_seconds))
            break
        except (ValueError, json.JSONDecodeError) as e:
            last_err = e
    if parsed is None:
        raise ValueError(f"judge returned unparseable output twice: {last_err}")

    return {
        "treatment": parsed["variant_a"] if t_variant == "a" else parsed["variant_b"],
        "control": parsed["variant_a"] if c_variant == "a" else parsed["variant_b"],
        "seed": seed,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/benchmark/test_judge.py -v`
Expected: PASS (7 cases)

- [ ] **Step 5: Commit**

```bash
git add archie/benchmark/judge.py tests/benchmark/test_judge.py
git commit -m "feat(benchmark): blind seeded judge with A/B randomization + retry"
```

---

### Task 7: Aggregation

**Files:**
- Create: `archie/benchmark/aggregate.py`
- Test: `tests/benchmark/test_aggregate.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/benchmark/test_aggregate.py
from archie.benchmark.aggregate import aggregate_samples


def _s(arm, cost, tools, quality, completed=True):
    return {"arm": arm, "cost_usd": cost, "tool_calls": tools,
            "duration_ms": 1000, "input_tokens": 10, "output_tokens": 20,
            "quality_score": quality, "completed": completed}


def test_per_arm_means():
    samples = [
        _s("treatment", 1.0, 10, 8.0),
        _s("treatment", 3.0, 20, 9.0),
        _s("control", 2.0, 30, 6.0),
        _s("control", 4.0, 40, 7.0),
    ]
    agg = aggregate_samples(samples)
    assert agg["treatment"]["cost_usd_mean"] == 2.0
    assert agg["treatment"]["tool_calls_mean"] == 15.0
    assert agg["treatment"]["quality_mean"] == 8.5
    assert agg["control"]["cost_usd_mean"] == 3.0
    assert agg["treatment"]["n"] == 2
    assert agg["treatment"]["completed_n"] == 2


def test_savings_percentages():
    samples = [_s("treatment", 1.0, 10, 8.0), _s("control", 2.0, 20, 8.0)]
    agg = aggregate_samples(samples)
    # treatment cost is 50% lower than control
    assert agg["savings"]["cost_pct"] == 50.0
    assert agg["savings"]["tool_calls_pct"] == 50.0


def test_quality_ignores_none_scores():
    samples = [
        _s("treatment", 1.0, 10, None, completed=False),
        _s("treatment", 1.0, 10, 8.0),
        _s("control", 1.0, 10, 6.0),
    ]
    agg = aggregate_samples(samples)
    assert agg["treatment"]["quality_mean"] == 8.0  # None excluded
    assert agg["treatment"]["completed_n"] == 1


def test_handles_empty_arm():
    samples = [_s("treatment", 1.0, 10, 8.0)]
    agg = aggregate_samples(samples)
    assert agg["control"]["n"] == 0
    assert agg["control"]["cost_usd_mean"] is None
    assert agg["savings"]["cost_pct"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/benchmark/test_aggregate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'archie.benchmark.aggregate'`

- [ ] **Step 3: Write minimal implementation**

```python
# archie/benchmark/aggregate.py
NUMERIC_FIELDS = ["cost_usd", "tool_calls", "duration_ms", "input_tokens", "output_tokens"]


def _mean(values):
    return sum(values) / len(values) if values else None


def _arm_stats(samples):
    stats = {"n": len(samples), "completed_n": sum(1 for s in samples if s.get("completed"))}
    for f in NUMERIC_FIELDS:
        vals = [s[f] for s in samples if s.get(f) is not None]
        stats[f + "_mean"] = _mean(vals)
    qvals = [s["quality_score"] for s in samples if s.get("quality_score") is not None]
    stats["quality_mean"] = _mean(qvals)
    return stats


def _pct_lower(treatment, control):
    """Percent reduction of treatment relative to control (positive = treatment cheaper)."""
    if treatment is None or control is None or control == 0:
        return None
    return round((control - treatment) / control * 100, 1)


def aggregate_samples(samples):
    treatment = [s for s in samples if s.get("arm") == "treatment"]
    control = [s for s in samples if s.get("arm") == "control"]
    t_stats = _arm_stats(treatment)
    c_stats = _arm_stats(control)
    return {
        "treatment": t_stats,
        "control": c_stats,
        "savings": {
            "cost_pct": _pct_lower(t_stats["cost_usd_mean"], c_stats["cost_usd_mean"]),
            "tool_calls_pct": _pct_lower(t_stats["tool_calls_mean"], c_stats["tool_calls_mean"]),
            "duration_pct": _pct_lower(t_stats["duration_ms_mean"], c_stats["duration_ms_mean"]),
        },
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/benchmark/test_aggregate.py -v`
Expected: PASS (4 cases)

- [ ] **Step 5: Commit**

```bash
git add archie/benchmark/aggregate.py tests/benchmark/test_aggregate.py
git commit -m "feat(benchmark): per-arm aggregation + savings percentages"
```

---

### Task 8: Supabase store + offline fallback

**Files:**
- Create: `archie/benchmark/store.py`
- Test: `tests/benchmark/test_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/benchmark/test_store.py
import json
from archie.benchmark import store


def test_offline_fallback_when_env_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    out = tmp_path / "nested" / "results.json"
    res = store.store_results({"name": "x"}, [{"arm": "treatment"}], out)
    assert res["mode"] == "offline"
    saved = json.loads(out.read_text())
    assert saved["run"]["name"] == "x"
    assert saved["samples"][0]["arm"] == "treatment"


def test_online_write_posts_run_then_samples(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "secret")
    calls = []

    def fake_poster(url, key, table, rows):
        calls.append((table, rows))
        if table == "benchmark_runs":
            return [{"id": "run-123"}]
        return rows

    res = store.store_results({"name": "x"}, [{"arm": "treatment"}, {"arm": "control"}],
                              tmp_path / "r.json", _poster=fake_poster)
    assert res["mode"] == "online"
    assert res["run_id"] == "run-123"
    assert calls[0][0] == "benchmark_runs"
    assert calls[1][0] == "benchmark_samples"
    # run_id stamped onto every sample row
    assert all(r["run_id"] == "run-123" for r in calls[1][1])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/benchmark/test_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'archie.benchmark.store'`

- [ ] **Step 3: Write minimal implementation**

```python
# archie/benchmark/store.py
import json
import os
import urllib.request
from pathlib import Path


def _env():
    return os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY")


def _post(url, key, table, rows):
    data = json.dumps(rows).encode("utf-8")
    req = urllib.request.Request(
        f"{url}/rest/v1/{table}",
        data=data,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def store_results(run_row, sample_rows, offline_path, _poster=None):
    url, key = _env()
    if not url or not key:
        path = Path(offline_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"run": run_row, "samples": sample_rows}, indent=2))
        return {"mode": "offline", "path": str(path)}

    poster = _poster or _post
    created = poster(url, key, "benchmark_runs", [run_row])
    run_id = created[0]["id"]
    for r in sample_rows:
        r["run_id"] = run_id
    poster(url, key, "benchmark_samples", sample_rows)
    return {"mode": "online", "run_id": run_id}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/benchmark/test_store.py -v`
Expected: PASS (2 cases)

- [ ] **Step 5: Commit**

```bash
git add archie/benchmark/store.py tests/benchmark/test_store.py
git commit -m "feat(benchmark): Supabase PostgREST write with offline fallback"
```

---

### Task 9: Supabase schema DDL

**Files:**
- Create: `archie/benchmark/schema.sql`
- Test: `tests/benchmark/test_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/benchmark/test_schema.py
from pathlib import Path

SQL = Path(__file__).parent.parent.parent / "archie" / "benchmark" / "schema.sql"


def test_schema_defines_both_tables_and_view():
    text = SQL.read_text()
    assert "create table" in text.lower()
    assert "benchmark_runs" in text
    assert "benchmark_samples" in text
    assert "benchmark_summary" in text
    # key sample columns referenced by store.py / aggregate.py exist
    for col in ["tool_calls", "tool_breakdown", "cost_usd", "quality_score",
                "cache_read_tokens", "judge_seed", "completed", "arm"]:
        assert col in text
    # prep cost lives on the run, separate from measured samples
    assert "prep_cost_usd" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/benchmark/test_schema.py -v`
Expected: FAIL with `FileNotFoundError` (schema.sql does not exist)

- [ ] **Step 3: Write minimal implementation**

```sql
-- archie/benchmark/schema.sql
-- Archie benchmark harness — Supabase schema (v1).
-- Run manually against the project (or via CI). Idempotent-ish: uses IF NOT EXISTS.

create table if not exists benchmark_runs (
    id              uuid primary key default gen_random_uuid(),
    name            text not null,
    repo_name       text,                 -- basename only, never a full path
    task_prompt     text,
    model           text,
    judge_model     text,
    repetitions     int,
    git_base_commit text,
    prep_cost_usd   numeric,              -- deep-scan prep cost, separate & best-effort
    archie_version  text,
    created_at      timestamptz not null default now()
);

create table if not exists benchmark_samples (
    id                    uuid primary key default gen_random_uuid(),
    run_id                uuid not null references benchmark_runs(id) on delete cascade,
    arm                   text not null,  -- 'control' | 'treatment'
    repetition            int,
    tool_calls            int,
    tool_breakdown        jsonb,
    input_tokens          int,
    output_tokens         int,
    cache_read_tokens     int,
    cache_creation_tokens int,
    cost_usd              numeric,
    duration_ms           int,
    num_turns             int,
    completed             boolean,
    quality_score         numeric,
    quality_detail        jsonb,
    judge_seed            int,
    created_at            timestamptz not null default now()
);

create index if not exists benchmark_samples_run_id_idx on benchmark_samples(run_id);

-- Per-run, per-arm rollup the website reads (separate spec).
create or replace view benchmark_summary as
select
    r.id            as run_id,
    r.name          as name,
    r.repo_name     as repo_name,
    r.model         as model,
    s.arm           as arm,
    count(*)                          as samples,
    count(*) filter (where s.completed) as completed_samples,
    avg(s.tool_calls)                 as tool_calls_mean,
    avg(s.cost_usd)                   as cost_usd_mean,
    avg(s.duration_ms)                as duration_ms_mean,
    avg(s.input_tokens + s.output_tokens) as total_tokens_mean,
    avg(s.quality_score)              as quality_mean
from benchmark_runs r
join benchmark_samples s on s.run_id = r.id
group by r.id, r.name, r.repo_name, r.model, s.arm;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/benchmark/test_schema.py -v`
Expected: PASS (1 case)

- [ ] **Step 5: Commit**

```bash
git add archie/benchmark/schema.sql tests/benchmark/test_schema.py
git commit -m "feat(benchmark): Supabase schema (runs + samples tables, summary view)"
```

---

### Task 10: Orchestrator — measurement matrix + fairness guards

**Files:**
- Create: `archie/benchmark/orchestrator.py`
- Test: `tests/benchmark/test_orchestrator.py`

This task assumes both branches already exist (the `run` command). Branch prep (`auto`) is Task 11. The orchestrator accepts injectable `run_fn`, `judge_fn`, `store_fn`, and `diff_fn` so the matrix is testable without invoking real claude/git/Supabase.

- [ ] **Step 1: Write the failing test**

```python
# tests/benchmark/test_orchestrator.py
import pytest
from archie.benchmark.config import BenchmarkConfig, JudgeConfig
from archie.benchmark.metrics import SampleMetrics
from archie.benchmark import orchestrator


def _cfg(tmp_path, reps=2):
    return BenchmarkConfig(
        name="demo", repo=tmp_path, task_prompt="do it",
        model="m", branches={"treatment": "t", "control": "c"},
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
                        lambda repo, b: "AAA" if b == "t" else "BBB")
    with pytest.raises(ValueError, match="base commit"):
        orchestrator.run_benchmark(_cfg(tmp_path), run_fn=lambda *a: None,
                                   judge_fn=lambda *a, **k: None,
                                   store_fn=lambda *a: None, diff_fn=lambda w: "")


def test_failed_sample_does_not_sink_run(tmp_path, monkeypatch):
    monkeypatch.setattr(orchestrator, "_branch_base", lambda repo, b: "same")
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/benchmark/test_orchestrator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'archie.benchmark.orchestrator'`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

> **Note on test `test_failed_sample_does_not_sink_run`:** `_run_one` catches the runner exception and returns `SampleMetrics(completed=False)`, so the control arm still runs and the run completes. The fairness-guard test patches `_branch_base` to return equal values via the same-string lambda; the divergent test returns different strings.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/benchmark/test_orchestrator.py -v`
Expected: PASS (3 cases)

- [ ] **Step 5: Commit**

```bash
git add archie/benchmark/orchestrator.py tests/benchmark/test_orchestrator.py
git commit -m "feat(benchmark): orchestrator matrix, fairness guard, per-sample rows"
```

---

### Task 11: Branch prep + CLI

**Files:**
- Modify: `archie/benchmark/orchestrator.py` (add `prepare_branches`)
- Create: `archie/benchmark/cli.py`
- Test: `tests/benchmark/test_prepare.py`

`prepare_branches` does the pure, testable git work: verify clean tree, create control branch (stripping Archie files), create treatment branch. The interactive deep-scan pause lives in `cli.py` (calls `input()`), kept thin and out of unit tests.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/benchmark/test_prepare.py -v`
Expected: FAIL with `AttributeError: module 'archie.benchmark.orchestrator' has no attribute 'prepare_branches'`

- [ ] **Step 3: Write minimal implementation**

Append to `archie/benchmark/orchestrator.py`:

```python
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
        # nested per-folder CLAUDE.md files
        nested = subprocess.run(["git", "ls-files", "*/CLAUDE.md"], cwd=str(repo),
                                capture_output=True, text=True).stdout.split()
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/benchmark/test_prepare.py -v`
Expected: PASS (4 cases)

- [ ] **Step 5: Write the CLI**

```python
# archie/benchmark/cli.py
import argparse
import sys
from pathlib import Path

from .config import load_config, parse_config
from .orchestrator import run_benchmark, prepare_branches


def _print_summary(result):
    agg = result["aggregate"]
    print("\n=== Benchmark summary ===")
    for arm in ("treatment", "control"):
        a = agg[arm]
        print(f"[{arm}] n={a['n']} completed={a['completed_n']} "
              f"cost=${_fmt(a['cost_usd_mean'])} tools={_fmt(a['tool_calls_mean'])} "
              f"dur={_fmt(a['duration_ms_mean'])}ms quality={_fmt(a['quality_mean'])}")
    s = agg["savings"]
    print(f"[savings] cost={_fmt(s['cost_pct'])}%  tools={_fmt(s['tool_calls_pct'])}%  "
          f"time={_fmt(s['duration_pct'])}%")
    print(f"[store] {result['store']}")


def _fmt(v):
    return "n/a" if v is None else (f"{v:.2f}" if isinstance(v, float) else str(v))


def _cmd_run(args):
    cfg = load_config(args.config)
    result = run_benchmark(cfg)
    _print_summary(result)


def _cmd_prep(args):
    cfg = load_config(args.config)
    status = prepare_branches(cfg)
    if status["needs_deep_scan"]:
        _interactive_deep_scan(cfg)
    print(f"Branches ready: {cfg.branches}")


def _cmd_auto(args):
    if args.config:
        cfg = load_config(args.config)
    else:
        cfg = parse_config({"name": Path(args.repo).name, "repo": args.repo,
                            "task_prompt": args.prompt, "model": args.model})
    status = prepare_branches(cfg)
    if status["needs_deep_scan"]:
        _interactive_deep_scan(cfg)
    result = run_benchmark(cfg)
    _print_summary(result)


def _interactive_deep_scan(cfg):
    treatment = cfg.branches["treatment"]
    print("\n" + "=" * 70)
    print("Archie not found in this repo. Semi-automatic prep:")
    print(f"  1. In a terminal: git checkout {treatment}")
    print(f"  2. Install Archie:  npx @bitraptors/archie {cfg.repo}")
    print("  3. In Claude Code on that branch, run:  /archie-deep-scan")
    print("  4. Commit the generated files.")
    print("This deep-scan is NOT counted in the benchmark metrics.")
    print("=" * 70)
    input("Press Enter once the treatment branch has committed Archie files... ")
    # verify
    from .orchestrator import _git_out, _archie_present  # local import to avoid cycle noise
    current = _git_out(["rev-parse", "--abbrev-ref", "HEAD"], cfg.repo)
    _git_out(["checkout", treatment], cfg.repo)
    present = _archie_present(cfg.repo)
    _git_out(["checkout", current], cfg.repo)
    if not present:
        print("ERROR: no Archie files found on the treatment branch. Aborting.", file=sys.stderr)
        sys.exit(1)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="archie-benchmark",
                                     description="Measure Archie effectiveness (control vs treatment).")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run benchmark on existing branches")
    p_run.add_argument("config", help="path to benchmark config JSON")
    p_run.set_defaults(func=_cmd_run)

    p_prep = sub.add_parser("prep", help="create/refresh benchmark branches only")
    p_prep.add_argument("config", help="path to benchmark config JSON")
    p_prep.set_defaults(func=_cmd_prep)

    p_auto = sub.add_parser("auto", help="prep branches then run, from a plain repo")
    p_auto.add_argument("repo", nargs="?", help="repo path (when no --config)")
    p_auto.add_argument("--config", help="path to benchmark config JSON")
    p_auto.add_argument("--prompt", help="task prompt (when no --config)")
    p_auto.add_argument("--model", default="claude-sonnet-4-6")
    p_auto.set_defaults(func=_cmd_auto)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Add a CLI smoke test**

```python
# append to tests/benchmark/test_prepare.py
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
                        lambda cfg: called.setdefault("ran", True) or {
                            "aggregate": {"treatment": {"n": 0, "completed_n": 0,
                                "cost_usd_mean": None, "tool_calls_mean": None,
                                "duration_ms_mean": None, "quality_mean": None},
                                "control": {"n": 0, "completed_n": 0, "cost_usd_mean": None,
                                "tool_calls_mean": None, "duration_ms_mean": None,
                                "quality_mean": None},
                                "savings": {"cost_pct": None, "tool_calls_pct": None,
                                "duration_pct": None}},
                            "store": {"mode": "offline"}})
    cli.main(["run", str(cfg_file)])
    assert called["ran"] is True
```

- [ ] **Step 7: Run all benchmark tests**

Run: `python -m pytest tests/benchmark/ -v`
Expected: PASS (all tasks' tests green)

- [ ] **Step 8: Commit**

```bash
git add archie/benchmark/orchestrator.py archie/benchmark/cli.py tests/benchmark/test_prepare.py
git commit -m "feat(benchmark): branch prep (strip Archie for control) + CLI (run/prep/auto)"
```

---

### Task 12: Docs + full suite

**Files:**
- Create: `archie/benchmark/README.md`
- Modify: `CLAUDE.md` (add a short "Benchmark Harness" section under Commands)

- [ ] **Step 1: Write `archie/benchmark/README.md`**

```markdown
# Archie Benchmark Harness (internal)

Measures Archie's effectiveness: runs the **same** task headlessly on a control
branch (no Archie) and a treatment branch (full Archie docs + hooks), capturing
tool calls / tokens / cost / time + a blind judge-Claude quality score, and writes
results to Supabase. **Not** shipped via npm.

## Usage

```bash
# 1. Author a config (see example below) — JSON, zero-dep.
# 2. From a plain repo, prep branches then run:
python3 -m archie.benchmark auto /path/to/repo --prompt "Add a sleep timer feature"

# Or with a config file:
python3 -m archie.benchmark run config.json     # branches must already exist
python3 -m archie.benchmark prep config.json    # only create/refresh branches
```

If the repo has no Archie files yet, `auto`/`prep` create the branches, then pause
so you can run `/archie-deep-scan` interactively on the treatment branch. That
deep-scan is **never** counted in the measured metrics.

## Config

```json
{
  "name": "bedtime-add-sleep-timer",
  "repo": "/Users/you/DEV/BedtimeApp",
  "task_prompt": "Add a sleep timer feature ...",
  "model": "claude-sonnet-4-6",
  "repetitions": 3,
  "branches": {"treatment": "archie-bench/with-archie", "control": "archie-bench/no-archie"},
  "judge": {"model": "claude-opus-4-8", "rubric": ["correctness", "completeness", "follows_conventions", "no_regressions"]},
  "timeout_seconds": 3600
}
```

## Supabase

Set `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` in the environment. Without them the
harness writes `.archie/benchmark/<name>/results.json` locally (offline mode).
Apply `archie/benchmark/schema.sql` to the project once.

## Fairness invariants

- Identical `task_prompt`, `model`, and harness flags on both arms.
- Both branches descend from the same base commit (enforced).
- Deep-scan prep cost is separate (`prep_cost_usd`), never in sample metrics.
```

- [ ] **Step 2: Add a section to `CLAUDE.md`** (under "Commands", after "Tests")

```markdown
### Benchmark Harness (internal)
```bash
# Measure Archie effectiveness: same task, control (no Archie) vs treatment (full Archie)
python3 -m archie.benchmark auto /path/to/repo --prompt "..."   # prep + run from a plain repo
python3 -m archie.benchmark run config.json                     # run on existing branches
```
Internal-only (not shipped via npm). Captures tool calls / tokens / cost / time +
blind judge-Claude quality, writes to Supabase (`benchmark_runs`, `benchmark_samples`).
See `archie/benchmark/README.md`.
```

- [ ] **Step 3: Run the full project test suite**

Run: `python -m pytest tests/ -v`
Expected: PASS (existing tests + all `tests/benchmark/` tests)

- [ ] **Step 4: Run the sync checker** (benchmark is internal, so it must NOT trip sync)

Run: `python3 scripts/verify_sync.py`
Expected: PASS — confirms no accidental npm-package coupling

- [ ] **Step 5: Commit**

```bash
git add archie/benchmark/README.md CLAUDE.md
git commit -m "docs(benchmark): README + CLAUDE.md usage section"
```

---

## Self-Review Notes (completed by plan author)

- **Spec coverage:** §1 purpose → Tasks 5/6/7/10; §4 config → Task 1; §5 data flow → Tasks 2/3/4/5/10; §6 auto/prep → Task 11; §7 judge → Task 6; §8 schema/store → Tasks 8/9; §9 error/fairness/cleanup → Tasks 4/10/11; §10 testing → every task is TDD. All covered.
- **Type consistency:** `SampleMetrics` fields, judge result dict keys (`treatment`/`control`/`overall`), and sample-row keys match across `metrics.py`, `judge.py`, `orchestrator._sample_row`, `aggregate.py`, `store.py`, and `schema.sql`.
- **Out of scope (per spec §11):** website display, end-user shipped mode, headless deep-scan, Agent SDK — none included.
- **Open implementation note:** `prep_cost_usd` stays `None` in v1 (best-effort per spec); a follow-up can read `.archie/telemetry/` after the interactive deep-scan to populate it.
```

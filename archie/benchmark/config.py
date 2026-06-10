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

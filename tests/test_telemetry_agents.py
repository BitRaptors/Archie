"""Tests for parallel sub-agent timing (telemetry.py agent-start/finish/collect)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))
import telemetry  # noqa: E402


def _step(root: Path):
    state = telemetry._load_current_run(root)
    return next((s for s in state.get("steps", []) if s.get("name") == "wave2_synthesis"), None)


def test_collect_agents_folds_durations(tmp_path):
    (tmp_path / ".archie").mkdir()
    telemetry.mark_step(tmp_path, "deep-scan", "wave2_synthesis")
    for a in ("design", "risk", "overview"):
        telemetry.agent_start(tmp_path, "wave2_synthesis", a)
        telemetry.agent_finish(tmp_path, "wave2_synthesis", a)
    telemetry.collect_agents(tmp_path, "wave2_synthesis")

    step = _step(tmp_path)
    assert step is not None
    names = {a["name"] for a in step["agents"]}
    assert names == {"design", "risk", "overview"}
    assert all(a["seconds"] is not None for a in step["agents"])
    # temp per-agent files consumed
    assert not list((tmp_path / ".archie" / "telemetry" / "agents").glob("*.json"))


def test_collect_agents_incomplete_is_graceful(tmp_path):
    (tmp_path / ".archie").mkdir()
    telemetry.mark_step(tmp_path, "deep-scan", "wave2_synthesis")
    telemetry.agent_start(tmp_path, "wave2_synthesis", "risk")  # never finishes
    telemetry.collect_agents(tmp_path, "wave2_synthesis")
    step = _step(tmp_path)
    risk = next(a for a in step["agents"] if a["name"] == "risk")
    assert risk["seconds"] is None  # no completed_at → graceful, not a crash


def test_collect_agents_noop_when_nothing(tmp_path):
    (tmp_path / ".archie").mkdir()
    telemetry.mark_step(tmp_path, "deep-scan", "wave2_synthesis")
    telemetry.collect_agents(tmp_path, "wave2_synthesis")  # no agent files
    step = _step(tmp_path)
    assert "agents" not in step

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


# --- build_summary (canonical structured output) ---------------------------

def test_build_summary_structure_and_total():
    steps = [
        {"name": "scan", "seconds": 7},
        {"name": "wave2_synthesis", "seconds": 61,
         "agents": [{"name": "design", "seconds": 30}, {"name": "risk", "seconds": 163}]},
        {"name": "drift", "seconds": 570},
    ]
    out = telemetry.build_summary(steps)
    assert [s["step"] for s in out["steps"]] == [1, 2, 3]          # numbered in order
    assert out["steps"][0]["key"] == "scan" and out["steps"][0]["name"] == "Scanner"
    w2 = out["steps"][1]
    assert w2["key"] == "wave2_synthesis" and w2["name"] == "Wave 2 — reasoning"
    assert {a["key"] for a in w2["sub_agents"]} == {"design", "risk"}
    assert w2["seconds"] == 163                                    # timing fix: parent >= slowest child
    assert out["total_seconds"] == 7 + 163 + 570                  # uses fixed step seconds


def test_build_summary_renests_leaked_top_level_agents():
    # design/risk/overview recorded as TOP-LEVEL steps must be folded under wave2.
    steps = [
        {"name": "wave2_synthesis", "seconds": 61},
        {"name": "design", "seconds": 30},
        {"name": "risk", "seconds": 163},
        {"name": "overview", "seconds": 37},
    ]
    out = telemetry.build_summary(steps)
    assert len(out["steps"]) == 1                                  # only wave2 remains top-level
    w2 = out["steps"][0]
    assert {a["key"] for a in w2["sub_agents"]} == {"design", "risk", "overview"}
    assert w2["seconds"] == 163


def test_build_summary_friendly_name_fallback():
    out = telemetry.build_summary([{"name": "some_custom_step", "seconds": 5}])
    assert out["steps"][0]["key"] == "some_custom_step"
    assert out["steps"][0]["name"] == "Some custom step"          # derived fallback

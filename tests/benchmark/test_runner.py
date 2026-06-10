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


def test_prompt_wraps_task_with_autonomy_framing(monkeypatch):
    # Headless `claude -p` has no human to approve/answer. Without an explicit
    # autonomy directive the agent obeys global "describe approach and wait for
    # approval / ask clarifying questions" rules and stops without editing —
    # producing an empty diff on both arms. The wrapper must override that.
    captured = {}

    def fake_run(cmd, cwd=None, capture_output=None, text=None, timeout=None):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=_stream(), stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    runner.run_claude("Add a sleep timer feature", "m", "/tmp/wt", 60)

    sent = captured["cmd"][2]
    assert "Add a sleep timer feature" in sent  # original task preserved verbatim
    low = sent.lower()
    assert "autonomous" in low                  # framed as autonomous
    assert "do not ask" in low                  # overrides clarifying-questions rule
    assert "do not stop" in low                 # overrides wait-for-approval rule


def test_timeout_marks_incomplete(monkeypatch):
    def fake_run(cmd, cwd=None, capture_output=None, text=None, timeout=None):
        raise subprocess.TimeoutExpired(cmd, timeout, output=_stream())

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    metrics, raw = runner.run_claude("do it", "m", "/tmp/wt", 1)
    assert metrics.completed is False
    assert metrics.tool_calls == 1  # partial stdout still parsed

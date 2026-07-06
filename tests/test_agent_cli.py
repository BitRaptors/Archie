"""Tests for `agent_cli` — the runtime per-CLI adapter.

agent_cli is the single home for headless coding-agent CLI invocation: harness
detection plus the actual `claude` / `codex` shell-outs. Pipeline scripts
(verify_findings.py) call `detect_verifier` / `run_verifier` and stay
CLI-agnostic; all per-CLI knowledge is concentrated here.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))

import agent_cli  # noqa: E402


# ---------------------------------------------------------------------------
# detect_verifier — picks the harness from the environment
# ---------------------------------------------------------------------------

def test_detect_verifier_claude_when_claudecode_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDECODE", "1")
    assert agent_cli.detect_verifier() == "claude"


def test_detect_verifier_codex_when_not_claude_and_codex_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.setattr(agent_cli.shutil, "which",
                        lambda name: "/usr/bin/codex" if name == "codex" else None)
    assert agent_cli.detect_verifier() == "codex"


def test_detect_verifier_falls_back_to_claude(monkeypatch: pytest.MonkeyPatch) -> None:
    """No CLAUDECODE and no codex on PATH → fall back to claude (which itself
    no-ops gracefully if that CLI is also absent)."""
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.setattr(agent_cli.shutil, "which", lambda name: None)
    assert agent_cli.detect_verifier() == "claude"


# ---------------------------------------------------------------------------
# detect_cli — harness identity for telemetry attribution
# ---------------------------------------------------------------------------

def test_detect_cli_claude_when_claudecode_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDECODE", "1")
    assert agent_cli.detect_cli() == "claude"


def test_detect_cli_codex_when_not_claude_and_codex_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.setattr(agent_cli.shutil, "which",
                        lambda name: "/usr/bin/codex" if name == "codex" else None)
    assert agent_cli.detect_cli() == "codex"


def test_detect_cli_unknown_when_no_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unlike detect_verifier, telemetry detection reports "unknown" rather than
    guessing — an honest value beats a wrong one in the analytics."""
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.setattr(agent_cli.shutil, "which", lambda name: None)
    assert agent_cli.detect_cli() == "unknown"


def test_detect_verifier_shares_detection_with_detect_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """detect_verifier must agree with detect_cli except for the indeterminate
    case, where it falls back to claude so the verifier always has a CLI."""
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.setattr(agent_cli.shutil, "which", lambda name: None)
    assert agent_cli.detect_cli() == "unknown"
    assert agent_cli.detect_verifier() == "claude"


# ---------------------------------------------------------------------------
# run_verifier — dispatch to the right CLI
# ---------------------------------------------------------------------------

def test_run_verifier_dispatches_to_codex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """verifier='codex' must route through the Codex path, not the Claude one."""
    calls: list[str] = []
    seen_model: dict[str, str] = {}
    monkeypatch.setattr(
        agent_cli, "_run_codex",
        lambda prompt, root, timeout: calls.append("codex") or "codex-out",
    )
    monkeypatch.setattr(
        agent_cli, "_run_claude",
        lambda prompt, root, timeout, model="haiku": (calls.append("claude"),
                                                      seen_model.__setitem__("m", model), "claude-out")[-1],
    )
    # Make both CLIs appear available on PATH so run_verifier routes by verifier arg.
    monkeypatch.setattr(
        agent_cli.shutil, "which",
        lambda name: f"/usr/local/bin/{name}" if name in ("codex", "claude") else None,
    )

    assert agent_cli.run_verifier("p", tmp_path, "codex") == "codex-out"
    assert agent_cli.run_verifier("p", tmp_path, "claude") == "claude-out"
    assert calls == ["codex", "claude"]
    # model alias must thread through run_verifier -> _run_claude (§6.6a tracer/challenger).
    assert agent_cli.run_verifier("p", tmp_path, "claude", model="opus") == "claude-out"
    assert seen_model["m"] == "opus"


# ---------------------------------------------------------------------------
# _run_codex — invocation shape
# ---------------------------------------------------------------------------

def test_run_codex_uses_stdin_and_output_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def _fake_run(args, input, capture_output, text, cwd, timeout, env=None):
        seen["args"] = args
        seen["input"] = input
        seen["cwd"] = cwd
        seen["env"] = env
        out_idx = args.index("--output-last-message") + 1
        Path(args[out_idx]).write_text('{"id":"f","verdict":"keep","confidence":1.0,"reason":"ok"}')
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(agent_cli.subprocess, "run", _fake_run)
    result = agent_cli._run_codex("PROMPT BODY", tmp_path, 90)

    assert '"verdict":"keep"' in result
    assert seen["input"] == "PROMPT BODY"
    assert seen["cwd"] == str(tmp_path)
    assert seen["args"][-1] == "-"
    assert "--output-last-message" in seen["args"]
    # Internal spawn must carry the marker so it can't pollute the intent log.
    assert seen["env"] is not None and seen["env"].get("ARCHIE_INTERNAL") == "1"


def test_codex_cleans_temp_on_nonzero_return(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Temp file must be deleted even when codex exits with a non-zero returncode."""
    created_tmp: list[str] = []
    real_mkstemp = tempfile.mkstemp

    def _tracking_mkstemp(**kwargs):
        fd, name = real_mkstemp(**kwargs)
        created_tmp.append(name)
        return fd, name

    # mkstemp is called as tempfile.mkstemp inside agent_cli, so patch the module
    monkeypatch.setattr(agent_cli.tempfile, "mkstemp", _tracking_mkstemp)

    def _fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr="")

    monkeypatch.setattr(agent_cli.subprocess, "run", _fake_run)

    result = agent_cli._run_codex("prompt", tmp_path, 30)

    assert result == ""
    assert len(created_tmp) == 1, "expected exactly one temp file to be created"
    assert not Path(created_tmp[0]).exists(), "temp file was NOT cleaned up on non-zero returncode"


def test_codex_cleans_temp_on_missing_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Temp file must be deleted when the codex CLI is not found (FileNotFoundError)."""
    created_tmp: list[str] = []
    real_mkstemp = tempfile.mkstemp

    def _tracking_mkstemp(**kwargs):
        fd, name = real_mkstemp(**kwargs)
        created_tmp.append(name)
        return fd, name

    monkeypatch.setattr(agent_cli.tempfile, "mkstemp", _tracking_mkstemp)

    def _fake_run(args, **kwargs):
        raise FileNotFoundError("codex not found")

    monkeypatch.setattr(agent_cli.subprocess, "run", _fake_run)

    result = agent_cli._run_codex("prompt", tmp_path, 30)

    assert result == ""
    assert len(created_tmp) == 1, "expected exactly one temp file to be created"
    assert not Path(created_tmp[0]).exists(), "temp file was NOT cleaned up on FileNotFoundError"

"""Tests for the direct Anthropic API fallback in agent_cli.run_verifier.

When no coding-agent CLI (claude/codex) is on PATH but ANTHROPIC_API_KEY is set,
run_verifier must call _run_api instead of returning "". When neither is available,
it must return "". When the claude CLI IS available, it must use _run_claude.
"""
from __future__ import annotations

import io
import json
import sys
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock

import pytest


_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))

import agent_cli  # noqa: E402


# ---------------------------------------------------------------------------
# Helper — build a fake urllib response that returns a valid Anthropic body
# ---------------------------------------------------------------------------

def _fake_urlopen(api_text: str):
    """Return a context-manager mock that yields a response with `api_text`."""
    body = json.dumps({
        "id": "msg_test",
        "type": "message",
        "content": [{"type": "text", "text": api_text}],
        "model": agent_cli.API_MODEL,
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }).encode()

    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)

    class _CM:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return resp
        def __exit__(self, *a): return False

    return _CM


# ---------------------------------------------------------------------------
# run_verifier → API fallback (no CLI, key present)
# ---------------------------------------------------------------------------

def test_run_verifier_uses_api_when_no_cli_and_key_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no CLI available but ANTHROPIC_API_KEY set, run_verifier returns API text."""
    monkeypatch.setattr(agent_cli.shutil, "which", lambda name: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")
    monkeypatch.setattr(
        agent_cli.urllib.request, "urlopen", _fake_urlopen("api-response-text")
    )

    result = agent_cli.run_verifier("hello prompt", tmp_path, "claude")
    assert result == "api-response-text"


def test_run_verifier_returns_empty_when_no_cli_and_no_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no CLI and no ANTHROPIC_API_KEY, run_verifier returns ''."""
    monkeypatch.setattr(agent_cli.shutil, "which", lambda name: None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    result = agent_cli.run_verifier("hello prompt", tmp_path, "claude")
    assert result == ""


def test_run_verifier_prefers_claude_cli_over_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the claude CLI is available, run_verifier must use _run_claude, not the API."""
    monkeypatch.setattr(agent_cli.shutil, "which",
                        lambda name: "/usr/local/bin/claude" if name == "claude" else None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")

    claude_called: list[str] = []
    monkeypatch.setattr(
        agent_cli, "_run_claude",
        lambda prompt, root, timeout: claude_called.append("called") or "claude-sentinel",
    )
    api_called: list[str] = []
    monkeypatch.setattr(
        agent_cli, "_run_api",
        lambda prompt, key, timeout: api_called.append("called") or "api-sentinel",
    )

    result = agent_cli.run_verifier("p", tmp_path, "claude")
    assert result == "claude-sentinel"
    assert claude_called == ["called"]
    assert api_called == []


def test_run_verifier_prefers_codex_cli_when_verifier_is_codex(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When verifier='codex' and codex is on PATH, _run_codex must be used."""
    monkeypatch.setattr(agent_cli.shutil, "which",
                        lambda name: "/usr/local/bin/codex" if name == "codex" else None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")

    codex_called: list[str] = []
    monkeypatch.setattr(
        agent_cli, "_run_codex",
        lambda prompt, root, timeout: codex_called.append("called") or "codex-sentinel",
    )
    api_called: list[str] = []
    monkeypatch.setattr(
        agent_cli, "_run_api",
        lambda prompt, key, timeout: api_called.append("called") or "api-sentinel",
    )

    result = agent_cli.run_verifier("p", tmp_path, "codex")
    assert result == "codex-sentinel"
    assert codex_called == ["called"]
    assert api_called == []


# ---------------------------------------------------------------------------
# _run_api — unit tests for the API function itself
# ---------------------------------------------------------------------------

def test_run_api_returns_text_from_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_run_api extracts the text from a well-formed Anthropic response."""
    monkeypatch.setattr(
        agent_cli.urllib.request, "urlopen", _fake_urlopen("extracted text")
    )
    result = agent_cli._run_api("prompt", "sk-test", timeout=10)
    assert result == "extracted text"


def test_run_api_returns_empty_on_network_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_run_api returns '' on any exception (network, timeout, JSON decode, etc.)."""
    def _raise(*a, **kw):
        raise OSError("connection refused")

    monkeypatch.setattr(agent_cli.urllib.request, "urlopen", _raise)
    result = agent_cli._run_api("prompt", "sk-test", timeout=10)
    assert result == ""


def test_run_api_sends_correct_headers_and_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_run_api builds a Request with the right URL, model, and headers."""
    captured: list[urllib.request.Request] = []

    def _fake_open(req, timeout=None):
        captured.append(req)
        body = json.dumps({
            "content": [{"type": "text", "text": "ok"}]
        }).encode()
        resp = MagicMock()
        resp.read.return_value = body
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    monkeypatch.setattr(agent_cli.urllib.request, "urlopen", _fake_open)
    agent_cli._run_api("my prompt", "my-api-key", timeout=5)

    assert len(captured) == 1
    req = captured[0]
    assert req.full_url == agent_cli.ANTHROPIC_URL
    assert req.get_header("X-api-key") == "my-api-key"
    assert req.get_header("Anthropic-version") == "2023-06-01"

    sent_body = json.loads(req.data.decode())
    assert sent_body["model"] == agent_cli.API_MODEL
    assert sent_body["messages"][0]["content"] == "my prompt"

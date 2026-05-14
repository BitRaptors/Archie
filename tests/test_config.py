"""Tests for archie.standalone.config — machine-level config + telemetry gate.

Loaded by path (config.py is pure stdlib). Every test redirects HOME to a
tmp dir so the real ~/.archie/config.json is never touched.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "_archie_config",
    Path(__file__).resolve().parent.parent / "archie" / "standalone" / "config.py",
)
_config = importlib.util.module_from_spec(_SPEC)
sys.modules["_archie_config"] = _config
_SPEC.loader.exec_module(_config)


def test_should_prompt_fresh_config_prints_prompt(tmp_path, monkeypatch, capsys):
    """A fresh machine has telemetry_prompted=false -> 'prompt' on stdout, exit 0.

    The token-on-stdout contract (not exit-code-only) lets the installer tell a
    real 'skip' apart from a config.py crash.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    rc = _config.main(["config.py", "should-prompt"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "prompt"


def test_apply_prompt_result_then_should_prompt_says_skip(tmp_path, monkeypatch, capsys):
    """After apply-prompt-result, should-prompt prints 'skip' and the tier sticks."""
    monkeypatch.setenv("HOME", str(tmp_path))
    assert _config.main(["config.py", "apply-prompt-result", "community"]) == 0
    capsys.readouterr()  # discard

    rc = _config.main(["config.py", "should-prompt"])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "skip"
    assert _config.get_telemetry_tier() == "community"

    cfg = json.loads((tmp_path / ".archie" / "config.json").read_text())
    assert cfg["telemetry_prompted"] is True
    assert cfg["telemetry"] == "community"


def test_apply_prompt_result_rejects_bad_tier(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert _config.main(["config.py", "apply-prompt-result", "bogus"]) == 2


def test_telemetry_prompted_is_not_user_settable(tmp_path, monkeypatch):
    """Internal state must not be writable via `config.py set` (exits 2)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(SystemExit) as exc:
        _config.main(["config.py", "set", "telemetry_prompted", "true"])
    assert exc.value.code == 2

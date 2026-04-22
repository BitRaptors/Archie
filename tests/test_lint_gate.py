"""Tests for archie.standalone.lint_gate — the opt-in external-tooling gate."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


# Load lint_gate.py directly (it's a standalone script, not a package module).
_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location(
    "lint_gate",
    _HERE.parent / "archie" / "standalone" / "lint_gate.py",
)
lint_gate = importlib.util.module_from_spec(_SPEC)  # type: ignore[arg-type]
_SPEC.loader.exec_module(lint_gate)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


def test_load_config_missing_returns_none(tmp_path):
    assert lint_gate.load_config(tmp_path) is None


def test_load_config_disabled_returns_none(tmp_path):
    archie = tmp_path / ".archie"
    archie.mkdir()
    (archie / "enforcement.json").write_text(json.dumps({"enabled": False}))
    assert lint_gate.load_config(tmp_path) is None


def test_load_config_enabled_returns_dict(tmp_path):
    archie = tmp_path / ".archie"
    archie.mkdir()
    (archie / "enforcement.json").write_text(
        json.dumps({"enabled": True, "severity": "warn"})
    )
    cfg = lint_gate.load_config(tmp_path)
    assert cfg == {"enabled": True, "severity": "warn"}


def test_load_config_malformed_json_returns_none(tmp_path):
    archie = tmp_path / ".archie"
    archie.mkdir()
    (archie / "enforcement.json").write_text("not json {{{")
    assert lint_gate.load_config(tmp_path) is None


# ---------------------------------------------------------------------------
# detect_linter — config override path (doesn't need real linters installed)
# ---------------------------------------------------------------------------


def test_detect_linter_uses_config_override_for_python(tmp_path):
    cfg = {
        "enabled": True,
        "linters": {"python": {"command": "my-custom-ruff"}},
    }
    result = lint_gate.detect_linter(
        tmp_path / "foo.py", tmp_path, cfg
    )
    assert result == {
        "kind": "python",
        "command": "my-custom-ruff",
        "target": "file",
    }


def test_detect_linter_uses_config_override_for_js(tmp_path):
    cfg = {
        "enabled": True,
        "linters": {"js": {"command": "eslint-wrapper"}},
    }
    for ext in (".js", ".jsx", ".ts", ".tsx"):
        result = lint_gate.detect_linter(
            tmp_path / f"foo{ext}", tmp_path, cfg
        )
        assert result == {
            "kind": "js",
            "command": "eslint-wrapper",
            "target": "file",
        }, ext


def test_detect_linter_uses_config_override_for_go(tmp_path):
    """Go override defaults to target=parent since golangci-lint is package-aware."""
    cfg = {
        "enabled": True,
        "linters": {"go": {"command": "golangci-lint run"}},
    }
    result = lint_gate.detect_linter(
        tmp_path / "main.go", tmp_path, cfg
    )
    assert result == {
        "kind": "go",
        "command": "golangci-lint run",
        "target": "parent",
    }


def test_detect_linter_go_override_can_pin_target_file(tmp_path):
    """Advanced users can override target=file if their Go tool handles single files."""
    cfg = {
        "enabled": True,
        "linters": {"go": {"command": "gofmt -l", "target": "file"}},
    }
    result = lint_gate.detect_linter(
        tmp_path / "main.go", tmp_path, cfg
    )
    assert result["target"] == "file"


def test_detect_linter_go_autodetect_without_golangci_config(tmp_path, monkeypatch):
    """Without a .golangci.yaml, auto-detect returns None even if golangci-lint
    is on PATH — we only fire the gate when the project opts in via config."""
    monkeypatch.setattr(lint_gate.shutil, "which", lambda cmd: "/usr/bin/golangci-lint" if cmd == "golangci-lint" else None)
    cfg = {"enabled": True}
    result = lint_gate.detect_linter(
        tmp_path / "main.go", tmp_path, cfg
    )
    assert result is None


def test_detect_linter_go_autodetect_with_golangci_yaml(tmp_path, monkeypatch):
    """With .golangci.yaml and golangci-lint on PATH, detection returns the
    expected command + parent target."""
    (tmp_path / ".golangci.yaml").write_text("linters:\n  enable: [govet]\n")
    monkeypatch.setattr(
        lint_gate.shutil,
        "which",
        lambda cmd: "/usr/bin/golangci-lint" if cmd == "golangci-lint" else None,
    )
    cfg = {"enabled": True}
    result = lint_gate.detect_linter(
        tmp_path / "main.go", tmp_path, cfg
    )
    assert result == {
        "kind": "go",
        "command": "golangci-lint run --fast",
        "target": "parent",
    }


def test_detect_linter_unknown_extension_returns_none(tmp_path):
    cfg = {"enabled": True, "linters": {"python": {"command": "ruff"}}}
    result = lint_gate.detect_linter(
        tmp_path / "README.md", tmp_path, cfg
    )
    assert result is None


def test_detect_linter_no_override_no_autodetect_returns_none(tmp_path):
    """Without config override and without project-level linter config files
    present, detection should yield None (fail open)."""
    cfg = {"enabled": True}
    # pyproject.toml exists but has no [tool.ruff] section.
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    result = lint_gate.detect_linter(
        tmp_path / "foo.py", tmp_path, cfg
    )
    # Could be None OR could match semgrep if the machine happens to have one
    # checked in — but tmp_path is fresh, so None.
    assert result is None


# ---------------------------------------------------------------------------
# run_linter — uses real shell commands with stub exit codes
# ---------------------------------------------------------------------------


def test_run_linter_success_returns_zero(tmp_path):
    target = tmp_path / "foo.txt"
    target.write_text("hello")
    code, output = lint_gate.run_linter("true", target, tmp_path)
    assert code == 0


def test_run_linter_failure_returns_nonzero_with_output(tmp_path):
    target = tmp_path / "foo.txt"
    target.write_text("hello")
    # `sh -c 'echo ISSUE; exit 1'` simulates a linter that fails.
    code, output = lint_gate.run_linter(
        "sh -c 'echo ISSUE; exit 1' --",
        target,
        tmp_path,
    )
    assert code != 0
    assert "ISSUE" in output


def test_run_linter_missing_command_fails_open(tmp_path):
    target = tmp_path / "foo.txt"
    target.write_text("x")
    code, output = lint_gate.run_linter(
        "this-definitely-does-not-exist-xyz123",
        target,
        tmp_path,
    )
    # Shell returns 127 for "command not found" — that's still a lint
    # "failure" from the hook's perspective. The fail-open behavior is
    # elsewhere (detect_linter won't return a command when the binary is
    # absent), so we just verify run_linter doesn't crash.
    assert isinstance(code, int)
    assert isinstance(output, str)


# ---------------------------------------------------------------------------
# gate — end-to-end top-level entrypoint
# ---------------------------------------------------------------------------


def _write_config(root: Path, cfg: dict) -> None:
    archie = root / ".archie"
    archie.mkdir(exist_ok=True)
    (archie / "enforcement.json").write_text(json.dumps(cfg))


def test_gate_disabled_returns_zero(tmp_path):
    """No config → no-op."""
    target = tmp_path / "foo.py"
    target.write_text("print('hi')\n")
    code, msg = lint_gate.gate(tmp_path, target)
    assert code == 0
    assert msg == ""


def test_gate_passes_when_linter_exits_zero(tmp_path):
    _write_config(
        tmp_path,
        {
            "enabled": True,
            "severity": "error",
            "linters": {"python": {"command": "true"}},
        },
    )
    target = tmp_path / "foo.py"
    target.write_text("print('hi')\n")
    code, msg = lint_gate.gate(tmp_path, target)
    assert code == 0
    assert msg == ""


def test_gate_blocks_when_linter_fails_and_severity_error(tmp_path):
    _write_config(
        tmp_path,
        {
            "enabled": True,
            "severity": "error",
            "linters": {
                "python": {"command": "sh -c 'echo LINT-ERROR; exit 1' --"},
            },
        },
    )
    target = tmp_path / "bad.py"
    target.write_text("bad")
    code, msg = lint_gate.gate(tmp_path, target)
    assert code == 2
    assert "BLOCKED" in msg
    assert "LINT-ERROR" in msg
    assert "bad.py" in msg


def test_gate_warns_when_linter_fails_and_severity_warn(tmp_path):
    _write_config(
        tmp_path,
        {
            "enabled": True,
            "severity": "warn",
            "linters": {
                "python": {"command": "sh -c 'echo LINT-WARN; exit 1' --"},
            },
        },
    )
    target = tmp_path / "bad.py"
    target.write_text("bad")
    code, msg = lint_gate.gate(tmp_path, target)
    assert code == 0
    assert "WARNING" in msg
    assert "LINT-WARN" in msg


def test_gate_ignores_unknown_file_types(tmp_path):
    """A .md file with no linter config → gate is a no-op even when enabled."""
    _write_config(
        tmp_path,
        {
            "enabled": True,
            "severity": "error",
            "linters": {"python": {"command": "false"}},
        },
    )
    target = tmp_path / "README.md"
    target.write_text("# hi")
    code, msg = lint_gate.gate(tmp_path, target)
    assert code == 0
    assert msg == ""


def test_gate_go_dispatches_to_parent_dir(tmp_path):
    """Target=parent means the linter command gets the containing directory,
    not the file path. Uses a stub that echoes its arg so we can verify."""
    _write_config(
        tmp_path,
        {
            "enabled": True,
            "severity": "error",
            "linters": {
                "go": {
                    "command": "sh -c 'echo GOT-ARG:$1; exit 1' --",
                    # target defaults to "parent" for kind=go
                },
            },
        },
    )
    pkg_dir = tmp_path / "cmd" / "server"
    pkg_dir.mkdir(parents=True)
    target = pkg_dir / "main.go"
    target.write_text("package main\nfunc main() {}\n")

    code, msg = lint_gate.gate(tmp_path, target)
    assert code == 2
    # Stub received the parent dir, not the single file.
    assert "GOT-ARG:" in msg
    assert "cmd/server" in msg
    # Must NOT have received the file path itself as the arg.
    assert "main.go" not in msg.split("GOT-ARG:")[1].splitlines()[0]

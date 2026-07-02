"""Tests that pre-validate.sh preserves the enforcement exit code after the
intent-capture block was appended.

CRITICAL regression guard: a prior change appended an intent-capture `if` block
AFTER the enforcement heredoc, causing the script to exit 0 even when the
engine emitted sys.exit(2).  These tests prove the fix is in place.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "archie"
    / "assets"
    / "hook_scripts"
    / "pre-validate.sh"
)


# ---------------------------------------------------------------------------
# Structural tests (fast, no subprocess) — always run
# ---------------------------------------------------------------------------


def _script_text() -> str:
    return SCRIPT.read_text()


def test_script_captures_rc_immediately_after_pyeof():
    """_rc=$? must appear on the line immediately after the PYEOF line that
    closes the enforcement heredoc."""
    text = _script_text()
    lines = text.splitlines()
    pyeof_idx = None
    for i, line in enumerate(lines):
        # The closing PYEOF of the enforcement heredoc (starts at column 0).
        if line.strip() == "PYEOF" and pyeof_idx is None:
            pyeof_idx = i
    assert pyeof_idx is not None, "Could not find closing PYEOF in pre-validate.sh"
    # The very next non-empty line must capture _rc.
    next_line = lines[pyeof_idx + 1].strip()
    assert next_line == "_rc=$?", (
        f"Expected '_rc=$?' immediately after PYEOF but got: {next_line!r}"
    )


def test_script_ends_with_exit_rc():
    """The script's final meaningful line must be 'exit $_rc' so the
    enforcement exit code is re-emitted after the intent-capture block."""
    text = _script_text()
    # Strip trailing whitespace/blank lines and get the last non-empty line.
    meaningful_lines = [l.rstrip() for l in text.splitlines() if l.strip()]
    last_line = meaningful_lines[-1]
    assert last_line == "exit $_rc", (
        f"Expected script to end with 'exit $_rc' but last line is: {last_line!r}"
    )


def test_intent_capture_block_is_best_effort():
    """The intent-capture invocation must include '|| true' so it can never
    block a passing edit."""
    text = _script_text()
    assert "intent_capture.py edit" in text, "intent_capture.py call missing"
    # The line that calls intent_capture.py must end with || true
    for line in text.splitlines():
        if "intent_capture.py edit" in line:
            assert "|| true" in line, (
                f"intent_capture.py line is not best-effort (missing '|| true'): {line!r}"
            )
            break


def test_rc_captured_before_intent_block():
    """_rc=$? must appear BEFORE the intent-capture if-block, not after."""
    text = _script_text()
    lines = text.splitlines()
    rc_idx = next(
        (i for i, l in enumerate(lines) if l.strip() == "_rc=$?"), None
    )
    intent_idx = next(
        (i for i, l in enumerate(lines) if "intent_capture.py" in l), None
    )
    assert rc_idx is not None, "_rc=$? not found"
    assert intent_idx is not None, "intent_capture.py call not found"
    assert rc_idx < intent_idx, (
        "_rc=$? must appear before the intent_capture.py block"
    )


# ---------------------------------------------------------------------------
# Real execution tests — run the actual shell script via subprocess
# ---------------------------------------------------------------------------


def _make_tmp_repo() -> Path:
    """Create a minimal git repo in a temp dir and return its Path."""
    d = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init", str(d)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(d), "config", "user.email", "test@test.com"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(d), "config", "user.name", "Test"],
        check=True, capture_output=True,
    )
    return d


def _write_rules(archie_dir: Path, rules: list) -> None:
    archie_dir.mkdir(exist_ok=True)
    (archie_dir / "rules.json").write_text(json.dumps({"rules": rules}))


def _run_script(repo: Path, payload: dict) -> int:
    """Run pre-validate.sh inside repo with payload as stdin; return exit code."""
    env = {**os.environ, "HOME": os.environ.get("HOME", str(Path.home()))}
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(repo),
        env=env,
    )
    return result.returncode


@pytest.fixture()
def tmp_repo(tmp_path):
    """A temp git repo with no rules yet."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "t@t.com"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "T"],
        check=True, capture_output=True,
    )
    return repo


def test_passing_edit_exits_0(tmp_repo):
    """A Write that does NOT violate any rule must exit 0."""
    archie_dir = tmp_repo / ".archie"
    _write_rules(
        archie_dir,
        [
            {
                "id": "no-eval",
                "check": "forbidden_content",
                "severity_class": "decision_violation",
                "forbidden_patterns": [r"\beval\b"],
                "description": "No eval()",
            }
        ],
    )
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(tmp_repo / "src" / "clean.py"),
            "content": "x = 1 + 1",
        },
    }
    rc = _run_script(tmp_repo, payload)
    assert rc == 0, f"Expected exit 0 for a clean edit, got {rc}"


def test_blocking_rule_exits_2(tmp_repo):
    """A Write that violates a decision_violation rule must exit 2 (BLOCKED),
    even when the intent-capture block follows the enforcement heredoc."""
    archie_dir = tmp_repo / ".archie"
    _write_rules(
        archie_dir,
        [
            {
                "id": "no-eval",
                "check": "forbidden_content",
                "severity_class": "decision_violation",
                "forbidden_patterns": [r"\beval\b"],
                "description": "No eval() — architectural constraint",
            }
        ],
    )
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(tmp_repo / "src" / "bad.py"),
            "content": "result = eval(user_input)",
        },
    }
    rc = _run_script(tmp_repo, payload)
    assert rc == 2, (
        f"Expected exit 2 for a blocking rule violation, got {rc}. "
        "This is the critical regression: if you get 0 here the intent-capture "
        "block is swallowing the enforcement exit code."
    )


def test_mechanical_violation_exits_2(tmp_repo):
    """mechanical_violation severity also blocks (exit 2)."""
    archie_dir = tmp_repo / ".archie"
    _write_rules(
        archie_dir,
        [
            {
                "id": "no-todo",
                "check": "forbidden_content",
                "severity_class": "mechanical_violation",
                "forbidden_patterns": [r"TODO"],
                "description": "No TODO comments in production code",
            }
        ],
    )
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(tmp_repo / "app.py"),
            "content": "# TODO: fix this later\npass",
        },
    }
    rc = _run_script(tmp_repo, payload)
    assert rc == 2, f"mechanical_violation should exit 2, got {rc}"


def test_warn_rule_exits_0(tmp_repo):
    """A tradeoff_undermined (warn) rule must exit 0 — it warns but does not block."""
    archie_dir = tmp_repo / ".archie"
    _write_rules(
        archie_dir,
        [
            {
                "id": "prefer-async",
                "check": "forbidden_content",
                "severity_class": "tradeoff_undermined",
                "forbidden_patterns": [r"time\.sleep"],
                "description": "Prefer async sleep",
            }
        ],
    )
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(tmp_repo / "worker.py"),
            "content": "import time\ntime.sleep(1)",
        },
    }
    rc = _run_script(tmp_repo, payload)
    assert rc == 0, f"Warn rule should exit 0, got {rc}"


def test_no_rules_exits_0(tmp_repo):
    """When no rules.json exists the script exits 0 (fail open)."""
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(tmp_repo / "foo.py"),
            "content": "x = 1",
        },
    }
    rc = _run_script(tmp_repo, payload)
    assert rc == 0, f"No-rules case should exit 0, got {rc}"


def test_intent_capture_failure_does_not_affect_exit_code(tmp_repo, monkeypatch):
    """Even if a buggy intent_capture.py would exit non-zero, the enforcement
    exit code must be preserved (best-effort '|| true' contract)."""
    archie_dir = tmp_repo / ".archie"
    _write_rules(
        archie_dir,
        [
            {
                "id": "no-eval",
                "check": "forbidden_content",
                "severity_class": "decision_violation",
                "forbidden_patterns": [r"\beval\b"],
                "description": "No eval()",
            }
        ],
    )
    # Drop a deliberately crashing intent_capture.py so '|| true' must save us.
    (archie_dir / "intent_capture.py").write_text("import sys; sys.exit(99)\n")

    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(tmp_repo / "bad.py"),
            "content": "eval('x')",
        },
    }
    rc = _run_script(tmp_repo, payload)
    assert rc == 2, (
        f"Blocking rule must still exit 2 even when intent_capture.py crashes, got {rc}"
    )

    # Also check a passing edit still exits 0 when intent_capture.py crashes.
    payload2 = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(tmp_repo / "clean.py"),
            "content": "x = 1",
        },
    }
    rc2 = _run_script(tmp_repo, payload2)
    assert rc2 == 0, (
        f"Passing edit must still exit 0 even when intent_capture.py crashes, got {rc2}"
    )

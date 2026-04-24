"""Tests for the `deep-scan-state save-run-context` subcommand.

These tests enforce a specific privacy + portability property: the run
context state file must NEVER contain machine-specific absolute paths. The
`project_root` field was removed from the persisted shape because its
presence caused `.archie/deep_scan_state.json` to embed paths like
`/Users/<name>/DEV/<project>`, which leaks user info and breaks portability
for any user who commits `.archie/` or shares it between machines.

The Resume Prelude now rehydrates `PROJECT_ROOT="$PWD"` directly.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


INTENT_LAYER = Path(__file__).resolve().parent.parent / "archie" / "standalone" / "intent_layer.py"


def _run_save_run_context(root: Path, extra_flags: list[str], stdin: str = "") -> tuple[int, str, str]:
    args = [
        sys.executable,
        str(INTENT_LAYER),
        "deep-scan-state",
        str(root),
        "save-run-context",
        *extra_flags,
    ]
    proc = subprocess.run(args, input=stdin, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def test_save_run_context_does_not_persist_project_root(tmp_path):
    """Even if the caller passes --project-root, the field must not land in the file.
    This is the core privacy guarantee."""
    rc, _, stderr = _run_save_run_context(
        tmp_path,
        [
            "--scope", "whole",
            "--intent-layer", "yes",
            "--scan-mode", "full",
            "--project-root", "/Users/someone/DEV/secret-project",
            "--monorepo-type", "bun-workspaces",
            "--start-step", "1",
        ],
    )
    assert rc == 0, f"stderr: {stderr}"

    state_path = tmp_path / ".archie" / "deep_scan_state.json"
    assert state_path.exists()
    raw = state_path.read_text()
    state = json.loads(raw)

    # Hard guarantee: no `project_root` in the persisted run context
    assert "project_root" not in state.get("run_context", {}), \
        f"project_root leaked into state: {state}"

    # Hard guarantee: the machine path does not appear anywhere in the file
    assert "/Users/someone" not in raw, \
        f"machine path leaked into state file bytes: {raw}"


def test_save_run_context_persists_expected_fields(tmp_path):
    """The fields we DO keep — scope, intent_layer, scan_mode, monorepo_type,
    start_step, workspaces — must still round-trip correctly."""
    rc, _, stderr = _run_save_run_context(
        tmp_path,
        [
            "--scope", "hybrid",
            "--intent-layer", "no",
            "--scan-mode", "incremental",
            "--monorepo-type", "npm-workspaces",
            "--start-step", "7",
            "--workspaces-from-stdin",
        ],
        stdin="apps/web\nservices/api\n",
    )
    assert rc == 0, f"stderr: {stderr}"

    state = json.loads((tmp_path / ".archie" / "deep_scan_state.json").read_text())
    ctx = state["run_context"]
    assert ctx["scope"] == "hybrid"
    assert ctx["intent_layer"] == "no"
    assert ctx["scan_mode"] == "incremental"
    assert ctx["monorepo_type"] == "npm-workspaces"
    assert ctx["start_step"] == 7
    assert ctx["workspaces"] == ["apps/web", "services/api"]


def test_save_run_context_scrubs_legacy_project_root_from_existing_state(tmp_path):
    """A pre-existing state file (e.g. written by an older Archie version) might
    already contain a stale project_root. Calling save-run-context must scrub
    it — otherwise the leak persists forever in long-lived projects."""
    legacy = {
        "last_completed": 3,
        "run_context": {
            "scope": "whole",
            "project_root": "/Users/legacy-user/DEV/openmeter",  # leaked value
        },
    }
    state_path = tmp_path / ".archie" / "deep_scan_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(legacy))

    rc, _, stderr = _run_save_run_context(
        tmp_path,
        ["--scope", "whole"],  # arbitrary call, no project_root passed
    )
    assert rc == 0, f"stderr: {stderr}"

    cleaned = json.loads(state_path.read_text())
    assert "project_root" not in cleaned["run_context"], \
        "legacy project_root was not scrubbed"
    # Other legacy fields outside run_context still survive
    assert cleaned["last_completed"] == 3


def test_save_run_context_accepts_project_root_without_failing(tmp_path):
    """Backward-compat: the flag is still accepted (older slash-command prose
    may still pass it). Must not raise 'unknown flag' — must silently discard."""
    rc, _, stderr = _run_save_run_context(
        tmp_path,
        [
            "--project-root", "/whatever/path",
            "--scope", "whole",
        ],
    )
    assert rc == 0, f"save-run-context rejected --project-root: {stderr}"


def test_save_run_context_does_not_leak_any_machine_path(tmp_path):
    """Defense-in-depth: scan the written file for any string resembling a
    machine-specific absolute path, regardless of which field it ended up in."""
    LEAK_PREFIXES = ("/Users/", "/home/", "/root/", "/var/folders/", "C:\\Users\\")
    # Try to smuggle leaky values through multiple fields
    rc, _, stderr = _run_save_run_context(
        tmp_path,
        [
            "--scope", "whole",
            "--intent-layer", "yes",
            "--scan-mode", "full",
            "--monorepo-type", "none",
            "--start-step", "1",
            "--project-root", "/Users/should-not-leak/project",
            "--workspaces-from-stdin",
        ],
        stdin="openmeter\n",
    )
    assert rc == 0, f"stderr: {stderr}"

    raw = (tmp_path / ".archie" / "deep_scan_state.json").read_text()
    for prefix in LEAK_PREFIXES:
        assert prefix not in raw, f"machine-specific prefix {prefix!r} leaked into state: {raw!r}"

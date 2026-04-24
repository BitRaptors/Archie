"""Regression guard for `suggest-batches` stdin support.

Historically the only way to pass ready folders to `suggest-batches` was as
positional argv. At ~100+ folders this breaks silently on shell word-split /
unquoted-expansion failures — the command received zero folders, output `[]`,
and the downstream reader couldn't parse it. Real-world failure on a 474-folder
DAG on a 632-folder project.

Fix: accept a JSON array on stdin when argv is empty. The slash-command
orchestrator now pipes `next-ready | suggest-batches` directly.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


INTENT_LAYER = Path(__file__).resolve().parent.parent / "archie" / "standalone" / "intent_layer.py"


def _prepare_fake_plan(tmp_path: Path) -> Path:
    """suggest-batches reads .archie/enrich_batches.json for folder sizes.
    Create a minimal valid one so the command has something to lookup."""
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir(parents=True, exist_ok=True)
    (archie_dir / "enrich_batches.json").write_text(json.dumps({"folders": {}}))
    return tmp_path


def _run(root: Path, stdin_json: str | None, argv_folders: list[str] | None = None) -> tuple[int, str, str]:
    args = [sys.executable, str(INTENT_LAYER), "suggest-batches", str(root)]
    if argv_folders:
        args.extend(argv_folders)
    proc = subprocess.run(
        args,
        input=stdin_json if stdin_json is not None else "",
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_suggest_batches_reads_folders_from_stdin(tmp_path):
    """JSON array on stdin → batched output."""
    root = _prepare_fake_plan(tmp_path)
    folders = ["a/b", "a/c", "a/d", "x/y", "x/z", "foo"]
    rc, stdout, stderr = _run(root, json.dumps(folders))
    assert rc == 0, f"stderr: {stderr}"
    batches = json.loads(stdout)
    total = sum(len(b["folders"]) for b in batches)
    assert total == len(folders)
    # Each batch has a stable 'id' field — w0, w1, ...
    for i, b in enumerate(batches):
        assert b["id"] == f"w{i}"


def test_suggest_batches_stdin_handles_hundreds_of_folders(tmp_path):
    """The real-world failure mode: 474 ready folders. Must not drop any."""
    root = _prepare_fake_plan(tmp_path)
    # Mimic the openmeter failure — nested paths, 500-ish leaves
    folders = [f"pkg{i // 10}/leaf{i}" for i in range(500)]
    rc, stdout, stderr = _run(root, json.dumps(folders))
    assert rc == 0, f"stderr: {stderr}"
    batches = json.loads(stdout)
    total = sum(len(b["folders"]) for b in batches)
    assert total == 500, f"lost folders: expected 500, got {total}"


def test_suggest_batches_argv_still_works_for_small_inputs(tmp_path):
    """Backward compat: small test cases that pass folders via argv must still work."""
    root = _prepare_fake_plan(tmp_path)
    rc, stdout, stderr = _run(root, stdin_json=None, argv_folders=["a/b", "a/c"])
    assert rc == 0, f"stderr: {stderr}"
    batches = json.loads(stdout)
    total = sum(len(b["folders"]) for b in batches)
    assert total == 2


def test_suggest_batches_empty_stdin_produces_empty_batches(tmp_path):
    """Nothing to batch → empty array, exit 0 (not an error)."""
    root = _prepare_fake_plan(tmp_path)
    rc, stdout, stderr = _run(root, "")
    assert rc == 0, f"stderr: {stderr}"
    assert json.loads(stdout) == []


def test_suggest_batches_malformed_stdin_exits_nonzero(tmp_path):
    """Bad input gets a clear error — no silent zero-batches."""
    root = _prepare_fake_plan(tmp_path)
    rc, stdout, stderr = _run(root, "not json at all {{")
    assert rc != 0
    assert "not valid JSON" in stderr


def test_suggest_batches_non_array_stdin_exits_nonzero(tmp_path):
    """stdin must be a JSON array, not an object/string/number."""
    root = _prepare_fake_plan(tmp_path)
    rc, stdout, stderr = _run(root, json.dumps({"folders": ["a", "b"]}))
    assert rc != 0
    assert "must be an array" in stderr


def test_suggest_batches_pipe_from_next_ready_equivalent(tmp_path):
    """The canonical production pattern: next-ready's output format
    (JSON array of strings) must feed suggest-batches via stdin.

    We simulate by writing a canonical next-ready output and piping it in.
    """
    root = _prepare_fake_plan(tmp_path)
    next_ready_output = json.dumps(["src/api", "src/db", "src/web"])
    rc, stdout, stderr = _run(root, next_ready_output)
    assert rc == 0
    batches = json.loads(stdout)
    assert sum(len(b["folders"]) for b in batches) == 3

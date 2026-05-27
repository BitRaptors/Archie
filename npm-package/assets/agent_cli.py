#!/usr/bin/env python3
"""Runtime per-CLI adapter — headless invocation of the user's coding-agent CLI.

Archie's standalone pipeline scripts are CLI-agnostic. A few of them, though,
must spawn an AI model mid-pipeline (the finding backward-check). They cannot
reach the connector layer — connectors are install-time objects, gone by the
time a scan runs. This module is the runtime counterpart:

    connector  = install-time per-CLI adapter (translates the manifest, renders
                 the workflow into per-CLI install artifacts)
    agent_cli  = runtime per-CLI adapter (turns "run this prompt through the
                 user's coding agent" into the right headless CLI call)

All per-CLI invocation knowledge lives here, in ONE place. A pipeline script
that needs an AI call imports `detect_verifier` / `run_verifier` and stays
fully CLI-agnostic itself.

Like the rest of `archie/standalone/`, this shells out to a CLI rather than
importing a vendor SDK — keeps the zero-dependency invariant and inherits the
user's existing auth.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

CLAUDE_CLI = "claude"
CODEX_CLI = "codex"
DEFAULT_TIMEOUT = 90  # seconds


def detect_cli() -> str:
    """Identify the coding-agent harness driving this run: "claude", "codex",
    or "unknown".

    A pipeline script only ever runs from inside a harness-driven scan, so the
    orchestrating harness IS the signal. Claude Code exports CLAUDECODE=1 to
    every process it spawns; inside a harness-driven run its absence means the
    Codex harness, confirmed by the PATH check. "unknown" is returned only when
    neither signal is present — a unit test or a direct script invocation
    outside any harness — so telemetry records an honest value rather than a
    guess.
    """
    if os.environ.get("CLAUDECODE"):
        return "claude"
    if shutil.which(CODEX_CLI):
        return "codex"
    return "unknown"


def detect_verifier() -> str:
    """Pick the CLI for the headless finding-verifier subagent.

    Shares harness detection with `detect_cli`, but the verifier must always
    have a runnable CLI to shell out to — so an indeterminate environment
    falls back to "claude" (which itself no-ops gracefully if that CLI is
    absent), rather than the "unknown" that `detect_cli` reports for telemetry.
    """
    cli = detect_cli()
    return cli if cli != "unknown" else "claude"


def run_verifier(prompt: str, project_root: Path, verifier: str,
                 timeout: int = DEFAULT_TIMEOUT) -> str:
    """Run `prompt` through the selected coding-agent CLI; return its text or ""."""
    if verifier == "codex":
        return _run_codex(prompt, project_root, timeout)
    return _run_claude(prompt, project_root, timeout)


def _run_claude(prompt: str, project_root: Path, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Spawn `claude -p --model haiku` synchronously. Returns result text or ""."""
    try:
        proc = subprocess.run(
            [
                CLAUDE_CLI,
                "-p",
                "--model", "haiku",
                "--output-format", "json",
                "--permission-mode", "bypassPermissions",
                "--allowedTools", "Read,Grep,Glob",
            ],
            input=prompt,
            capture_output=True,
            text=True,
            cwd=str(project_root),
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return ""
    return envelope.get("result", "") or ""


def _run_codex(prompt: str, project_root: Path, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Spawn `codex exec` synchronously. Returns the model's final text or "".

    `codex exec` runs the prompt non-interactively in a read-only sandbox and
    persists the agent's last message to a file. Send the prompt on stdin
    instead of argv so large cited-file bundles do not hit shell/exec length
    limits.
    """
    tmp_file: str | None = None
    try:
        with tempfile.NamedTemporaryFile("r+", encoding="utf-8", delete=False) as fh:
            tmp_file = fh.name
        proc = subprocess.run(
            [
                CODEX_CLI,
                "exec",
                "--sandbox", "read-only",
                "--skip-git-repo-check",
                "--output-last-message", tmp_file,
                "-",
            ],
            input=prompt,
            capture_output=True,
            text=True,
            cwd=str(project_root),
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    if not tmp_file:
        return ""
    try:
        return Path(tmp_file).read_text()
    except OSError:
        return ""
    finally:
        if tmp_file:
            Path(tmp_file).unlink(missing_ok=True)

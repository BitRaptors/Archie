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
import urllib.error
import urllib.request
from pathlib import Path

CLAUDE_CLI = "claude"
CODEX_CLI = "codex"
DEFAULT_TIMEOUT = 90  # seconds

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
API_MODEL = "claude-haiku-4-5"


def _run_api(prompt: str, api_key: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Direct Anthropic Messages API call — used in CI where no coding-agent CLI exists.
    Returns the text response or '' on any error."""
    body = json.dumps({
        "model": API_MODEL,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        ANTHROPIC_URL, data=body, method="POST",
        headers={"content-type": "application/json", "x-api-key": api_key,
                 "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        parts = data.get("content") or []
        return "".join(p.get("text", "") for p in parts if p.get("type") == "text")
    except Exception:
        return ""


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
    """Run `prompt` through the selected coding-agent CLI; return its text or "".

    Priority:
    1. Requested codex CLI (if verifier=='codex' and codex is on PATH).
    2. claude CLI (if available on PATH).
    3. Direct Anthropic API (if ANTHROPIC_API_KEY is set) — CI fallback where
       no coding-agent CLI is installed.
    4. Empty string — nothing available.
    """
    if verifier == "codex" and shutil.which("codex"):
        return _run_codex(prompt, project_root, timeout)
    if shutil.which("claude"):
        return _run_claude(prompt, project_root, timeout)
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return _run_api(prompt, key, timeout)
    return ""


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
        fd, tmp_file = tempfile.mkstemp(suffix=".codex-out.txt")
        os.close(fd)
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
        if proc.returncode != 0:
            return ""
        try:
            return Path(tmp_file).read_text().strip()
        except OSError:
            return ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    finally:
        if tmp_file:
            Path(tmp_file).unlink(missing_ok=True)

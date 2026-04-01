"""Subagent runner -- spawns Claude Code CLI processes to analyze code."""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

import click

from archie.coordinator.planner import SubagentAssignment
from archie.coordinator.prompts import build_subagent_prompt
from archie.engine.models import RawScan

logger = logging.getLogger(__name__)

CLAUDE_CLI = "claude"


def check_claude_cli() -> bool:
    """Check if the ``claude`` binary exists in PATH.

    Returns True if found, False otherwise.
    """
    return shutil.which(CLAUDE_CLI) is not None


def run_subagents(
    project_root: Path,
    scan: RawScan,
    groups: list[SubagentAssignment],
) -> list[dict]:
    """Run Claude Code subagents sequentially and collect their blueprint outputs.

    For each :class:`SubagentAssignment`, builds a prompt via
    :func:`build_subagent_prompt`, spawns ``claude -p`` as a subprocess,
    parses the JSON response, and extracts the blueprint sections.

    Parameters
    ----------
    project_root:
        Absolute path to the repository root (used as cwd for subagents).
    scan:
        The :class:`RawScan` from the local analysis engine.
    groups:
        List of :class:`SubagentAssignment` objects from the planner.

    Returns
    -------
    List of parsed blueprint dicts (one per successful subagent).
    """
    results: list[dict] = []
    total = len(groups)

    for idx, group in enumerate(groups, 1):
        label = group.module_hint or "general"
        click.echo(f"Running subagent {idx}/{total} ({label} module)...")

        prompt = build_subagent_prompt(group, scan)

        try:
            proc = subprocess.run(
                [
                    CLAUDE_CLI,
                    "-p",
                    "--model", "sonnet",
                    "--output-format", "json",
                    "--permission-mode", "bypassPermissions",
                    "--allowedTools", "Read,Grep,Glob,WebSearch,WebFetch",
                ],
                input=prompt,
                capture_output=True,
                text=True,
                cwd=str(project_root),
                timeout=600,
            )
        except FileNotFoundError:
            click.echo(f"  Error: claude CLI not found, skipping subagent {idx}")
            logger.warning("claude CLI not found")
            continue
        except subprocess.TimeoutExpired:
            click.echo(f"  Error: subagent {idx} timed out, skipping")
            logger.warning("Subagent %d timed out", idx)
            continue

        if proc.returncode != 0:
            click.echo(f"  Error: subagent {idx} failed (exit {proc.returncode}), skipping")
            logger.warning(
                "Subagent %d failed with exit code %d: %s",
                idx, proc.returncode, proc.stderr[:500],
            )
            continue

        # Parse the outer JSON envelope from claude --output-format json
        try:
            envelope = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            click.echo(f"  Error: could not parse subagent {idx} JSON envelope, skipping")
            logger.warning("JSON envelope parse error for subagent %d: %s", idx, exc)
            continue

        # Extract the result text which contains the blueprint JSON
        result_text = envelope.get("result", "")
        if not result_text:
            click.echo(f"  Warning: subagent {idx} returned empty result, skipping")
            continue

        # The result text may contain the JSON inside a code block
        blueprint_json = _extract_json(result_text)
        if blueprint_json is None:
            click.echo(f"  Error: could not extract blueprint JSON from subagent {idx}, skipping")
            logger.warning("Could not extract JSON from subagent %d result", idx)
            continue

        click.echo(f"  Subagent {idx} completed successfully")
        results.append(blueprint_json)

    return results


def _extract_json(text: str) -> dict | None:
    """Extract a JSON dict from text that may contain markdown code fences."""
    # Try direct parse first
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # Try extracting from ```json ... ``` code block
    import re
    pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    # Try finding the first { ... } block
    start = text.find("{")
    if start >= 0:
        # Find the matching closing brace
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(text[start:i + 1])
                        if isinstance(data, dict):
                            return data
                    except json.JSONDecodeError:
                        pass
                    break

    return None

"""Canonical types defining what Archie ships across all CLIs.

Manifest entries are CLI-agnostic. Each Connector reads them and emits the
appropriate per-CLI artifact (slash command / skill, hook config,
config patch). See docs/plans/2026-05-18-multi-agent-connector-architecture.md
for the full design.
"""
from dataclasses import dataclass
from typing import Literal, Optional

HookEvent = Literal[
    "pre-tool-use",
    "post-tool-use",
    "user-prompt-submit",
    "stop",
    "pre-commit",
]


@dataclass(frozen=True)
class CommandDef:
    name: str
    description: str
    body_path: str


@dataclass(frozen=True)
class HookDef:
    event: HookEvent
    tool_match: Optional[str]
    script_path: str
    blocking: bool


@dataclass(frozen=True)
class ConfigPatch:
    cli: str
    key: str
    value: object

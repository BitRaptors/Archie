"""Connector registry.

Per-CLI connectors are added to ALL_CONNECTORS as they're implemented.
See docs/plans/2026-05-18-multi-agent-connector-architecture.md §18
for ownership per connector:

    Stage 2 — Claude agent: ClaudeConnector
    Stage 3 — Codex agent:  CodexConnector
    Stage 4-5 — Pi agent:   PiConnector
"""
from .base import Connector

# Populated as connectors land. Each entry must be an instance of Connector.
ALL_CONNECTORS: list[Connector] = []

"""Contract tests — every Connector's declared capabilities must work end-to-end.

The interface promise: if a connector lists `"hooks:X"` in capabilities,
its install_hook must not raise on a HookDef whose event is X. Same for
`"commands"`, `"agents"`, `"config-patch"`. Catches "I claimed support but
my method errors" drift between manifest and connector code.

Run: python -m pytest tests/test_connector_contract.py -v

Precondition: pydantic must be importable (archie/__init__.py eagerly imports
archie.engine which uses pydantic). Install via `pip install pydantic` or run
inside the project's venv.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

# Make the project root importable when running from tests/ directly.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from archie.connectors import ALL_CONNECTORS  # noqa: E402
from archie.manifest import AgentDef, CommandDef, ConfigPatch, HookDef  # noqa: E402
from archie.manifest_data import AGENTS, COMMANDS, CONFIG_PATCHES, HOOKS  # noqa: E402


SAMPLE_CMD = CommandDef("archie-test", "Test command.", ".archie/prompts/skill_test.md")
SAMPLE_AGENT = AgentDef("archie-test-agent", "Test agent.", ".archie/prompts/test.md")


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """A throwaway project root with .archie/hooks/ already populated.

    The connector's install_hook references archie/assets/hook_scripts/<name>.sh
    — those are committed under archie/assets/, so the connectors find them.
    """
    return tmp_path


@pytest.mark.parametrize("connector", ALL_CONNECTORS, ids=lambda c: c.name)
def test_connector_has_required_attrs(connector):
    assert connector.name
    assert isinstance(connector.capabilities, frozenset)
    assert "commands" in connector.capabilities, "every connector must support commands"


@pytest.mark.parametrize("connector", ALL_CONNECTORS, ids=lambda c: c.name)
def test_install_command_creates_file(connector, tmp_project: Path):
    connector.install_command(tmp_project, SAMPLE_CMD)
    # Each connector writes to its own native location; we just assert that
    # ONE of the expected paths exists. Walking the project root is sufficient.
    artifacts = list(tmp_project.rglob("archie-test*"))
    assert artifacts, f"{connector.name}.install_command produced no files"


@pytest.mark.parametrize("connector", ALL_CONNECTORS, ids=lambda c: c.name)
def test_install_hook_honors_capabilities(connector, tmp_project: Path):
    for hook in HOOKS:
        if hook.event == "pre-commit":
            continue  # handled by universal git hook, not per-connector
        if connector.supports_event(hook.event):
            # Must not raise; declared capabilities are a contract.
            connector.install_hook(tmp_project, hook)
        # If unsupported, we don't call it — that's the install loop's job.
    connector.finalize(tmp_project)


@pytest.mark.parametrize("connector", ALL_CONNECTORS, ids=lambda c: c.name)
def test_install_agent_when_capable(connector, tmp_project: Path):
    if "agents" not in connector.capabilities:
        # Non-capable connectors get a no-op default; calling shouldn't raise.
        connector.install_agent(tmp_project, SAMPLE_AGENT)
        return
    connector.install_agent(tmp_project, SAMPLE_AGENT)
    toml_files = list(tmp_project.rglob(f"{SAMPLE_AGENT.name}.toml"))
    assert toml_files, "agent capability claimed but no TOML written"


@pytest.mark.parametrize("connector", ALL_CONNECTORS, ids=lambda c: c.name)
def test_patch_config_idempotent_when_capable(connector, tmp_project: Path, monkeypatch):
    if "config-patch" not in connector.capabilities:
        connector.patch_config([ConfigPatch(connector.name, "k", "v")])  # default no-op
        return
    # Redirect home so the test doesn't touch real ~/.codex/config.toml
    fake_home = tmp_project / "fake_home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    patches = [p for p in CONFIG_PATCHES if p.cli == connector.name]
    connector.patch_config(patches)
    first = (fake_home / f".{connector.name}" / "config.toml").read_text()
    connector.patch_config(patches)
    second = (fake_home / f".{connector.name}" / "config.toml").read_text()
    assert first == second, f"{connector.name}.patch_config is not idempotent"


def test_every_hook_event_has_at_least_one_connector():
    """If we declare a HookDef with event X, at least one connector must claim hooks:X.
    Otherwise the manifest entry is dead weight."""
    declared_events = {h.event for h in HOOKS}
    capable_events: set[str] = set()
    for c in ALL_CONNECTORS:
        for cap in c.capabilities:
            if cap.startswith("hooks:"):
                capable_events.add(cap.split(":", 1)[1])
    # pre-commit is universal — handled outside per-connector path
    declared_events.discard("pre-commit")
    orphans = declared_events - capable_events
    assert not orphans, f"HookDef events with no connector support: {orphans}"


def test_registry_is_non_empty():
    assert len(ALL_CONNECTORS) >= 1
    names = {c.name for c in ALL_CONNECTORS}
    assert names == {"claude", "codex"}, f"Unexpected registry: {names}"

"""Contract tests — every Connector's declared capabilities must work end-to-end.

The interface promise: if a connector lists `"hooks:X"` in capabilities,
its install_hook must not raise on a HookDef whose event is X. Same for
`"commands"`, `"config-patch"`. Catches "I claimed support but
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
import re

import pytest

# Make the project root importable when running from tests/ directly.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from archie.connectors import ALL_CONNECTORS  # noqa: E402
from archie.manifest import CommandDef, ConfigPatch, HookDef  # noqa: E402
from archie.manifest_data import COMMANDS, CONFIG_PATCHES, HOOKS  # noqa: E402


SAMPLE_CMD = CommandDef("archie-test", "Test command.", ".archie/prompts/skill_test.md")


@pytest.fixture
def tmp_project(tmp_path: Path, monkeypatch) -> Path:
    """A throwaway project root with .archie/hooks/ already populated.

    The connector's install_hook references archie/assets/hook_scripts/<name>.sh
    — those are committed under archie/assets/, so the connectors find them.

    Redirects `Path.home()` to a fake home dir under tmp_path so any connector
    that writes to `~/.codex/config.toml` during the test (CodexConnector.finalize
    writes [agents] + [projects."<abs>"] trust_level there) does not pollute
    the developer's real config file. Without this every test run would leave
    a [projects."<pytest-tmp>"] entry behind permanently.
    """
    fake_home = tmp_path / "_fake_home"
    fake_home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
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


# ---------------------------------------------------------------------------
# Render-map contract — every connector must declare the locked slot set
# ---------------------------------------------------------------------------

_REQUIRED_TOKENS = {
    "ANALYSIS_MODEL", "REASONING_MODEL", "VERIFY_MODEL", "WORKFLOW_ROOT",
    "COMMAND_PREFIX",
}
_REQUIRED_PARTIALS = {
    "dispatch_parallel", "dispatch_workspace_parallel", "dispatch_single",
    "output_contract", "ask_user",
}


@pytest.mark.parametrize("connector", ALL_CONNECTORS, ids=lambda c: c.name)
def test_connector_declares_all_render_tokens(connector):
    missing = _REQUIRED_TOKENS - set(connector.render_tokens)
    assert not missing, f"{connector.name} render_tokens missing: {missing}"
    for key, val in connector.render_tokens.items():
        assert isinstance(val, str), f"{connector.name} token {key} is not a string"


@pytest.mark.parametrize("connector", ALL_CONNECTORS, ids=lambda c: c.name)
def test_connector_declares_all_render_partials(connector):
    missing = _REQUIRED_PARTIALS - set(connector.render_partials)
    assert not missing, f"{connector.name} render_partials missing: {missing}"


@pytest.mark.parametrize("connector", ALL_CONNECTORS, ids=lambda c: c.name)
def test_connector_workflow_root_is_namespaced(connector):
    """{{WORKFLOW_ROOT}} must point at the connector's own .archie/workflow/<cli>
    subtree so Claude and Codex can be installed side by side."""
    root = connector.render_tokens["WORKFLOW_ROOT"]
    assert root == f".archie/workflow/{connector.name}"


def test_codex_render_partials_only_reference_supported_runtime_tools():
    codex = next(c for c in ALL_CONNECTORS if c.name == "codex")
    rendered = "\n".join(codex.render_partials.values())
    for forbidden in (
        "spawn_agent",
        "wait_agent",
        "request_user_input",
        "exec_command",
        "spawn_agents_on_csv",
        "report_agent_job_result",
    ):
        assert re.search(rf"`{re.escape(forbidden)}`|\b{re.escape(forbidden)}\b(?!_)", rendered) is None
    assert "apply_patch" in rendered
    assert "native subagent workflow" in rendered


def test_codex_finalize_installs_native_subagent_config(tmp_path: Path, monkeypatch):
    """finalize() drops the project-scoped archie_analysis custom agent
    definition. The `[agents]` global block (max_threads, max_depth) lives in
    `~/.codex/config.toml` per the Codex docs and is patched via patch_config(),
    not finalize() — verified separately in
    test_codex_patch_config_writes_agents_section."""
    codex = next(c for c in ALL_CONNECTORS if c.name == "codex")
    codex.finalize(tmp_path)

    # Project-scoped `.codex/config.toml` is NOT written by finalize anymore —
    # the [agents] keys live in user-home, written via patch_config.
    assert not (tmp_path / ".codex" / "config.toml").exists()

    agent = tmp_path / ".codex" / "agents" / "archie-analysis.toml"
    assert agent.is_file()
    text = agent.read_text()
    assert 'name = "archie_analysis"' in text
    assert "developer_instructions" in text


def test_codex_patch_config_writes_agents_section(tmp_path: Path, monkeypatch):
    """The [agents] section (max_threads, max_depth) is written to
    `~/.codex/config.toml` by patch_config() via CONFIG_PATCHES — that's where
    the Codex docs document those keys living. Project-scoped writes are
    deliberately not done."""
    codex = next(c for c in ALL_CONNECTORS if c.name == "codex")
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    patches = [p for p in CONFIG_PATCHES if p.cli == codex.name]
    codex.patch_config(patches)

    cfg = (fake_home / ".codex" / "config.toml").read_text()
    assert "[agents]" in cfg
    assert "max_threads = 6" in cfg
    assert "max_depth = 2" in cfg
    # And the existing top-level keys are still written too.
    assert "project_doc_max_bytes = 131072" in cfg
    assert 'project_doc_fallback_filenames' in cfg


def test_codex_patch_config_respects_user_agents_values(tmp_path: Path, monkeypatch):
    """[agents] defaults must be set-if-absent — if the user has customised
    `max_threads` (rate-limited account, larger workload) or `max_depth`
    (other tooling using deeper recursion), our install must not overwrite
    those choices. Top-level project-doc keys still get overwritten because
    they're Archie requirements, not user preferences."""
    codex = next(c for c in ALL_CONNECTORS if c.name == "codex")
    fake_home = tmp_path / "fake_home"
    (fake_home / ".codex").mkdir(parents=True)
    # Pre-existing user config: max_threads bumped up, max_depth bumped up,
    # plus an unrelated [agents] knob Archie doesn't touch.
    (fake_home / ".codex" / "config.toml").write_text(
        "[agents]\n"
        "max_threads = 10\n"
        "max_depth = 4\n"
        "custom_user_knob = true\n"
    )
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    patches = [p for p in CONFIG_PATCHES if p.cli == codex.name]
    codex.patch_config(patches)

    cfg = (fake_home / ".codex" / "config.toml").read_text()
    # User's [agents] values preserved.
    assert "max_threads = 10" in cfg
    assert "max_depth = 4" in cfg
    assert "custom_user_knob = true" in cfg
    # Top-level Archie requirements still written (overwrite policy).
    assert "project_doc_max_bytes = 131072" in cfg
    assert "project_doc_fallback_filenames" in cfg


def test_codex_patch_config_fills_in_missing_agents_keys(tmp_path: Path, monkeypatch):
    """If only ONE of the [agents] defaults is user-set, the install fills in
    the missing key (set-if-absent doesn't mean skip-if-section-exists)."""
    codex = next(c for c in ALL_CONNECTORS if c.name == "codex")
    fake_home = tmp_path / "fake_home"
    (fake_home / ".codex").mkdir(parents=True)
    # User set only max_threads — max_depth is missing.
    (fake_home / ".codex" / "config.toml").write_text(
        "[agents]\n"
        "max_threads = 12\n"
    )
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    patches = [p for p in CONFIG_PATCHES if p.cli == codex.name]
    codex.patch_config(patches)

    cfg = (fake_home / ".codex" / "config.toml").read_text()
    assert "max_threads = 12" in cfg  # user's value preserved
    assert "max_depth = 2" in cfg     # missing key filled in


# ---------------------------------------------------------------------------
# Codex execpolicy Rules file — pre-approves the deep-scan command surface
# ---------------------------------------------------------------------------

def test_codex_finalize_writes_archie_rules_file(tmp_path: Path, monkeypatch):
    """finalize() drops .codex/rules/archie.rules with one prefix_rule per
    standalone script + one per COMMAND_RULES entry. This is the documented
    Codex mechanism for pre-approving shell commands at install time
    (developers.openai.com/codex/rules)."""
    codex = next(c for c in ALL_CONNECTORS if c.name == "codex")
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    codex.finalize(tmp_path)

    rules_file = tmp_path / ".codex" / "rules" / "archie.rules"
    assert rules_file.is_file()
    content = rules_file.read_text()
    # Header references the docs source so the next contributor knows where
    # the schema lives.
    assert "developers.openai.com/codex/rules" in content
    # All prefix_rules carry decision = "allow" — the Rules file is purely
    # additive (no "prompt" or "forbidden" entries Archie ships).
    assert 'decision = "allow"' in content
    assert 'decision = "prompt"' not in content
    assert 'decision = "forbidden"' not in content
    # Every Archie Python script has its own prefix_rule by script name.
    from archie.install import _STANDALONE_SCRIPTS
    for script in _STANDALONE_SCRIPTS:
        if not script.endswith(".py"):
            continue
        expected = f'"python3", ".archie/{script}"'
        assert expected in content, f"archie.rules missing prefix_rule for {script}"
    # Catalogue-driven shell utility entries land too — pick a representative.
    assert '"mkdir"' in content
    assert '"rm", "-f", ".archie/health.json"' in content
    assert '"git", "log"' in content
    # Inline Python (`python3 -c …`) is its own entry.
    assert '"python3", "-c"' in content


def test_codex_finalize_marks_project_trusted(tmp_path: Path, monkeypatch):
    """The Codex Rules file (and our .codex/agents/, .codex/hooks.json) only
    load when the project is marked trusted in ~/.codex/config.toml. The
    install writes that trust marker — set-if-absent, so a manual
    "untrusted" choice is respected."""
    codex = next(c for c in ALL_CONNECTORS if c.name == "codex")
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    codex.finalize(tmp_path)

    cfg = (fake_home / ".codex" / "config.toml").read_text()
    # Section header uses the documented quoted-key TOML form with the
    # project's RESOLVED absolute path (symlinks collapsed).
    abs_path = str(tmp_path.resolve())
    assert f'[projects."{abs_path}"]' in cfg
    assert 'trust_level = "trusted"' in cfg


def test_codex_finalize_respects_user_untrusted_project_marker(tmp_path: Path, monkeypatch):
    """A user who deliberately marked their project "untrusted" (knowing it
    skips the project-scoped .codex/ layer) is respected — install does not
    overwrite that choice."""
    codex = next(c for c in ALL_CONNECTORS if c.name == "codex")
    fake_home = tmp_path / "fake_home"
    (fake_home / ".codex").mkdir(parents=True)
    abs_path = str(tmp_path.resolve())
    (fake_home / ".codex" / "config.toml").write_text(
        f'[projects."{abs_path}"]\n'
        'trust_level = "untrusted"\n'
    )
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    codex.finalize(tmp_path)

    cfg = (fake_home / ".codex" / "config.toml").read_text()
    assert 'trust_level = "untrusted"' in cfg
    assert 'trust_level = "trusted"' not in cfg


def test_codex_finalize_idempotent_trust_marker(tmp_path: Path, monkeypatch):
    """Running finalize() twice produces no further changes — the trust
    marker write is idempotent on subsequent installs."""
    codex = next(c for c in ALL_CONNECTORS if c.name == "codex")
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    codex.finalize(tmp_path)
    first = (fake_home / ".codex" / "config.toml").read_text()
    codex.finalize(tmp_path)
    second = (fake_home / ".codex" / "config.toml").read_text()
    assert first == second, "trust-level write is not idempotent"


def test_command_catalogue_parity_with_claude(tmp_path: Path):
    """Every COMMAND_RULES entry must declare both a Codex prefix pattern
    and a Claude bash-glob string. If a new utility is added to one CLI
    without the other, this test catches the drift."""
    from archie.manifest_data import COMMAND_RULES
    for rule in COMMAND_RULES:
        assert rule.codex_pattern, f"{rule.name}: empty codex_pattern"
        assert rule.claude_glob, f"{rule.name}: empty claude_glob"
        assert rule.claude_glob.startswith("Bash("), (
            f"{rule.name}: claude_glob must be a Bash(...) entry, got {rule.claude_glob!r}"
        )
        # First codex_pattern token reflects the same shell command as
        # claude_glob — basic semantic parity.
        first_token = rule.codex_pattern[0]
        assert first_token in rule.claude_glob, (
            f"{rule.name}: codex_pattern[0]={first_token!r} does not appear in "
            f"claude_glob={rule.claude_glob!r}"
        )

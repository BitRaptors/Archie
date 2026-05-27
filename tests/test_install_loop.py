"""Tests for the connector-driven install loop."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from archie.install import install, render_template  # noqa: E402
from archie.connectors import ALL_CONNECTORS  # noqa: E402
from archie.manifest_data import COMMANDS  # noqa: E402


_COMMAND_DIRS = [c.body_path.split("/", 1)[0] for c in COMMANDS]


def test_claude_install_preserves_main_assets(tmp_path: Path) -> None:
    install(tmp_path, ["claude"])

    assert (tmp_path / ".claude" / "commands" / "archie-deep-scan.md").exists()
    # The deep-scan step tree is now rendered into .archie/workflow/<cli>/.
    assert (tmp_path / ".archie" / "workflow" / "claude" / "deep-scan" / "SKILL.md").exists()
    assert (
        tmp_path / ".archie" / "workflow" / "claude" / "deep-scan" / "steps" / "step-1-scanner.md"
    ).exists()
    assert (tmp_path / ".claude" / "hooks" / "pre-validate.sh").exists()
    assert (tmp_path / ".archie" / "platform_rules.json").exists()
    assert (tmp_path / ".archie" / "viewer" / "package.json").exists()
    assert (tmp_path / ".archieignore").exists()
    assert (tmp_path / ".archiebulk").exists()


def test_claude_install_writes_settings_local_json(tmp_path: Path) -> None:
    install(tmp_path, ["claude"])

    settings_path = tmp_path / ".claude" / "settings.local.json"
    assert settings_path.exists()

    settings = json.loads(settings_path.read_text())
    assert "hooks" in settings
    assert "PreToolUse" in settings["hooks"]
    assert any(
        entry.get("matcher") == "Edit|Write|MultiEdit"
        for entry in settings["hooks"]["PreToolUse"]
    )


def test_install_removes_legacy_layout(tmp_path: Path) -> None:
    """An upgrade over an old-layout install drops the superseded trees so the
    user is not left with a dead skill registration or a stale workflow body."""
    legacy_skill = tmp_path / ".claude" / "skills" / "archie-deep-scan" / "steps"
    legacy_skill.mkdir(parents=True)
    (legacy_skill / "step-1-scanner.md").write_text("OLD")
    legacy_prompts = tmp_path / ".archie" / "prompts"
    legacy_prompts.mkdir(parents=True)
    (legacy_prompts / "skill_archie_scan.md").write_text("OLD")
    legacy_shared = tmp_path / ".claude" / "commands" / "_shared"
    legacy_shared.mkdir(parents=True)
    (legacy_shared / "scope_resolution.md").write_text("OLD")

    install(tmp_path, ["claude"])

    assert not (tmp_path / ".claude" / "skills" / "archie-deep-scan").exists()
    assert not (tmp_path / ".archie" / "prompts").exists()
    assert not (legacy_shared / "scope_resolution.md").exists()
    # ...and the current layout is in place.
    assert (
        tmp_path / ".archie" / "workflow" / "claude" / "deep-scan" / "SKILL.md"
    ).exists()


def test_install_sweeps_stale_command_shims_from_prior_version(tmp_path: Path) -> None:
    """Upgrading from a prior version that shipped a now-removed command
    (e.g. /archie-scan, dropped in the connector branch's merge with main)
    must remove the leftover per-CLI shim — otherwise the agent still
    discovers the dead command from .agents/skills/archie-X/ or
    .claude/commands/archie-X.md and tries to invoke a workflow body that
    no longer exists."""
    # Seed a prior install with shims for a since-removed command.
    stale_claude_shim = tmp_path / ".claude" / "commands" / "archie-scan.md"
    stale_claude_shim.parent.mkdir(parents=True)
    stale_claude_shim.write_text("---\nname: archie-scan\n---\nPRIOR VERSION\n")
    stale_codex_skill = tmp_path / ".agents" / "skills" / "archie-scan"
    stale_codex_skill.mkdir(parents=True)
    (stale_codex_skill / "SKILL.md").write_text(
        "---\nname: archie-scan\n---\nPRIOR VERSION\n"
    )

    install(tmp_path, ["claude", "codex"])

    # Both shims for the removed command are gone.
    assert not stale_claude_shim.exists()
    assert not stale_codex_skill.exists()
    # Current command shims are intact.
    assert (tmp_path / ".claude" / "commands" / "archie-deep-scan.md").exists()
    assert (tmp_path / ".agents" / "skills" / "archie-deep-scan" / "SKILL.md").exists()


# ---------------------------------------------------------------------------
# Render-infrastructure contract
# ---------------------------------------------------------------------------

def test_render_template_fails_loud_on_unknown_token() -> None:
    with pytest.raises(ValueError):
        render_template("hello {{MISSING}}", {}, {})


def test_render_template_fails_loud_on_unknown_partial() -> None:
    with pytest.raises(ValueError):
        render_template("hello {{>missing}}", {}, {})


def test_render_template_fails_loud_on_leftover_brace() -> None:
    # A token rendered to a value containing {{ would still be caught.
    with pytest.raises(ValueError):
        render_template("a {{X}} b", {"X": "{{still here}}"}, {})


def test_render_template_substitutes_tokens_and_partials() -> None:
    out = render_template(
        "model={{M}} how={{>do_it}}",
        {"M": "gpt-5"},
        {"do_it": "spawn it"},
    )
    assert out == "model=gpt-5 how=spawn it"
    assert "{{" not in out


@pytest.mark.parametrize("connector", ALL_CONNECTORS, ids=lambda c: c.name)
def test_rendered_workflow_has_no_unresolved_slots(connector, tmp_path: Path) -> None:
    """Every rendered workflow file must be fully concrete — no {{ }} left."""
    install(tmp_path, [connector.name])
    workflow_root = tmp_path / ".archie" / "workflow" / connector.name
    assert workflow_root.is_dir()
    md_files = list(workflow_root.rglob("*.md"))
    assert md_files, f"no rendered workflow files for {connector.name}"
    for f in md_files:
        assert "{{" not in f.read_text(), f"unresolved slot in {f}"


@pytest.mark.parametrize("connector", ALL_CONNECTORS, ids=lambda c: c.name)
def test_every_command_has_a_rendered_skill(connector, tmp_path: Path) -> None:
    install(tmp_path, [connector.name])
    workflow_root = tmp_path / ".archie" / "workflow" / connector.name
    for cmd_dir in _COMMAND_DIRS:
        skill = workflow_root / cmd_dir / "SKILL.md"
        assert skill.is_file(), f"{connector.name}: missing rendered {cmd_dir}/SKILL.md"


def test_codex_rendered_tree_has_no_claude_workflow_paths(tmp_path: Path) -> None:
    """The Codex rendered tree must not reference .claude/-hardcoded workflow
    paths. Deterministic-renderer output paths (.claude/rules/) are allowed —
    renderer.py writes there for both CLIs — so the check targets the
    .claude/skills + .claude/commands workflow locations specifically."""
    install(tmp_path, ["codex"])
    workflow_root = tmp_path / ".archie" / "workflow" / "codex"
    bad = re.compile(r"\.claude/(skills|commands)/")
    for f in workflow_root.rglob("*.md"):
        m = bad.search(f.read_text())
        assert not m, f"Codex tree references a Claude workflow path in {f}: {m.group(0)}"


def test_codex_rendered_tree_has_no_session_only_helper_tool_names(tmp_path: Path) -> None:
    install(tmp_path, ["codex"])
    workflow_root = tmp_path / ".archie" / "workflow" / "codex"
    forbidden = (
        "spawn_agent",
        "wait_agent",
        "request_user_input",
        "exec_command",
        "spawn_agents_on_csv",
        "report_agent_job_result",
    )
    for f in workflow_root.rglob("*.md"):
        text = f.read_text()
        for needle in forbidden:
            leaked = re.search(rf"`{re.escape(needle)}`|\b{re.escape(needle)}\b(?!_)", text)
            assert leaked is None, f"{f} leaked non-Codex helper name: {needle}"


def test_codex_rendered_tree_has_no_claude_tool_name_leaks(tmp_path: Path) -> None:
    """Tool-name leaks from Claude's tool vocabulary into the canonical
    workflow show up as wrong instructions on Codex. The connector's
    output_contract / dispatch_* partials own per-CLI write/spawn mechanics —
    canonical prose must not bypass them."""
    install(tmp_path, ["codex"])
    workflow_root = tmp_path / ".archie" / "workflow" / "codex"
    forbidden = (
        "Use the Write tool",
        "Use the Read tool",
        "background Agent",
        "background agent",
        "blocking batch",
        "dispatch primitive",
    )
    for f in workflow_root.rglob("*.md"):
        text = f.read_text()
        for needle in forbidden:
            assert needle not in text, f"{f} leaks Claude-tool / hidden-batch wording: {needle!r}"


def test_codex_rendered_tree_uses_codex_command_prefix_not_slash(tmp_path: Path) -> None:
    """Every reference to an Archie slash command in canonical prose must go
    through {{COMMAND_PREFIX}} so Codex renders `$archie-X`, not literal
    `/archie-X` (which Codex's harness does not recognise)."""
    install(tmp_path, ["codex"])
    workflow_root = tmp_path / ".archie" / "workflow" / "codex"
    # Match `/archie-NAME` only when not preceded by a letter/digit/`$`/`/` —
    # that filters out incidental occurrences inside ARN/URL/identifier strings
    # (e.g. `acme-archie-shares`, `https://archie-viewer.vercel.app`) and
    # excludes the Codex-rendered `$archie-X`.
    leak_re = re.compile(r"(?:^|[^A-Za-z0-9$/])/archie-[a-z]")
    for f in workflow_root.rglob("*.md"):
        text = f.read_text()
        m = leak_re.search(text)
        assert m is None, f"{f} leaks literal /archie- prefix: {text[m.start():m.start()+40]!r}"


def test_codex_rendered_tree_writes_artifacts_to_workspace_relative_tmp(tmp_path: Path) -> None:
    """The disk-artifact contract uses `.archie/tmp/archie_*` so Codex's
    default workspace-write sandbox covers writes natively. Bare `/tmp/archie_`
    (outside the workspace) would force a sandbox escalation."""
    install(tmp_path, ["codex"])
    workflow_root = tmp_path / ".archie" / "workflow" / "codex"
    # Bare /tmp/archie_ — preceded by anything except `e` (which would mean
    # `.archie/tmp/archie_` — the correct workspace-relative form).
    bare_tmp = re.compile(r"(?:^|[^e])/tmp/archie_")
    for f in workflow_root.rglob("*.md"):
        text = f.read_text()
        m = bare_tmp.search(text)
        assert m is None, f"{f} writes to bare /tmp (not workspace-relative): {text[m.start():m.start()+50]!r}"


def test_codex_rendered_step3_assigns_output_paths_before_dispatch(tmp_path: Path) -> None:
    """Step 3 must give Wave 1 sub-agents their output path and the output
    contract at dispatch time. If the table + contract appear AFTER the
    {{>dispatch_parallel}} slot, the sub-agents never see them — the
    handoff's Gap 1."""
    install(tmp_path, ["codex"])
    step3 = (tmp_path / ".archie" / "workflow" / "codex" / "deep-scan"
             / "steps" / "step-3-wave1" / "orchestration.md").read_text()
    full_table_idx = step3.rfind("archie_sub1_")
    dispatch_idx = step3.find("from the same orchestration step")  # Codex dispatch_parallel marker
    assert full_table_idx > 0, "Step 3 missing the Wave 1 output-path table"
    assert dispatch_idx > 0, "Step 3 missing the rendered dispatch_parallel marker"
    assert full_table_idx < dispatch_idx, (
        "Wave 1 output paths must be declared BEFORE the dispatch slot — "
        "otherwise sub-agents never see their assigned output path"
    )
    # All four Wave 1 output paths must be present, workspace-relative.
    for sub in ("archie_sub1_", "archie_sub2_", "archie_sub3_", "archie_sub4_"):
        assert f".archie/tmp/{sub}" in step3, f"Step 3 missing output path: .archie/tmp/{sub}*"


def test_codex_rendered_step4_is_consumer_only(tmp_path: Path) -> None:
    """Step 4 must be a pure consumer of Wave 1 outputs — no more 'append
    this block to each Wave 1 agent's prompt before spawning' wording."""
    install(tmp_path, ["codex"])
    step4 = (tmp_path / ".archie" / "workflow" / "codex" / "deep-scan"
             / "steps" / "step-4-merge.md").read_text()
    assert "append this block to each Wave 1 agent" not in step4
    assert "Append this block to each Wave 1 agent" not in step4
    # Positive: Step 4 still does the merge.
    assert "merge.py" in step4


def test_codex_rendered_scope_resolution_uses_native_subagent_fanout(tmp_path: Path) -> None:
    """The shared scope-resolution must dispatch per-package / hybrid parallel
    workspace runs via {{>dispatch_workspace_parallel}}, which on Codex
    renders the native-subagent call using the archie_analysis custom agent."""
    install(tmp_path, ["codex"])
    scope = (tmp_path / ".archie" / "workflow" / "codex"
             / "_shared" / "scope_resolution.md").read_text()
    assert "archie_analysis" in scope
    assert "native Codex subagent" in scope
    assert "background Agent" not in scope


def test_install_drops_self_ignoring_archie_tmp_gitignore(tmp_path: Path) -> None:
    """.archie/tmp/ holds transient run artifacts (Wave 1 outputs, rules,
    enrichments). A self-ignoring `.gitignore` lives there so the user can
    never accidentally commit those artifacts even if their repo's root
    .gitignore does not cover .archie/tmp/ explicitly."""
    install(tmp_path, ["codex"])
    gi = tmp_path / ".archie" / "tmp" / ".gitignore"
    assert gi.is_file(), ".archie/tmp/.gitignore was not created"
    assert gi.read_text().strip() == "*"


def test_codex_install_does_not_write_project_scoped_config_toml(tmp_path: Path) -> None:
    """[agents] keys (max_threads, max_depth) live in ~/.codex/config.toml
    per Codex docs — written by patch_config() via CONFIG_PATCHES. The
    project-scoped <project>/.codex/config.toml is deliberately not written
    so there is exactly one source of truth for those settings."""
    install(tmp_path, ["codex"])
    assert not (tmp_path / ".codex" / "config.toml").exists()
    # The custom-agent definition (project-scoped per docs) still goes here.
    assert (tmp_path / ".codex" / "agents" / "archie-analysis.toml").is_file()


def test_all_target_renders_both_trees_differing_only_in_slots(tmp_path: Path) -> None:
    """--target=all must produce a claude tree and a codex tree whose files
    differ ONLY on lines carrying a slotted value. Lines with no slot must be
    byte-identical between the two."""
    install(tmp_path, ["all"])
    claude_root = tmp_path / ".archie" / "workflow" / "claude"
    codex_root = tmp_path / ".archie" / "workflow" / "codex"
    assert claude_root.is_dir() and codex_root.is_dir()

    claude_files = sorted(p.relative_to(claude_root).as_posix() for p in claude_root.rglob("*.md"))
    codex_files = sorted(p.relative_to(codex_root).as_posix() for p in codex_root.rglob("*.md"))
    assert claude_files == codex_files, "claude and codex workflow trees have different file sets"

    # Recover the universe of token/partial values for both connectors so we
    # can recognise a "slotted line": a line that changed must contain at
    # least one connector-specific rendered value.
    connectors = {c.name: c for c in ALL_CONNECTORS}
    claude = connectors["claude"]
    codex = connectors["codex"]
    claude_values = set(claude.render_tokens.values()) | set(claude.render_partials.values())
    codex_values = set(codex.render_tokens.values()) | set(codex.render_partials.values())
    # Multi-line partials: also collect their individual lines.
    slot_fragments: set[str] = set()
    for v in claude_values | codex_values:
        for line in v.splitlines():
            line = line.strip()
            if line:
                slot_fragments.add(line)

    differing = 0
    for rel in claude_files:
        a = (claude_root / rel).read_text().splitlines()
        b = (codex_root / rel).read_text().splitlines()
        # Same line count: every diff is a same-position substitution.
        assert len(a) == len(b), f"{rel}: line count differs between trees"
        for la, lb in zip(a, b):
            if la == lb:
                continue
            differing += 1
            # The changed line must carry a slotted fragment from one side.
            touched = any(frag in la or frag in lb for frag in slot_fragments)
            assert touched, f"{rel}: non-slot line differs:\n  claude: {la}\n  codex:  {lb}"
    assert differing > 0, "expected at least some slotted lines to differ"

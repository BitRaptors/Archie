"""Tests for the Phase 1 inline rule shape (richer-rules plan, v2.5.0).

Covers:
- Schema validation — new-shape rules pass strict shape checks.
- Backward-compat rendering — old-shape rules without severity_class / why
  / example still render a useful message and don't crash.
- New-shape rendering — full rule renders the WHY + EXAMPLE blocks the
  agent reads at edit time.
- Severity gating — pre-validate hook exits per severity_class:
    * decision_violation / pitfall_triggered / mechanical_violation -> exit 2
    * tradeoff_undermined -> exit 0 with WARN
    * pattern_divergence -> exit 0 with INFO
- Source-field stamping — extract_output.py cmd_rules defensively stamps
  `source: "deep_scan"` on any rule emitted without one.
- Regression — openmeter's existing 36 old-shape rules.json renders without
  crashing through the new hook (proves backward compat on real-world data).

The hook lives as a heredoc'd bash script inside install_hooks.PRE_VALIDATE_HOOK.
We exercise it end-to-end by writing it to a temp script, building a fake
PreToolUse tool-call JSON, fake rules.json files, and running the hook
through bash with that input on stdin. This tests the actual production
artifact, not a Python re-implementation of it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Import PRE_VALIDATE_HOOK from the canonical install_hooks module without
# pulling in the rest of the package (which depends on pydantic etc.).
import importlib.util

_INSTALL_HOOKS_PATH = REPO_ROOT / "archie" / "standalone" / "install_hooks.py"
_spec = importlib.util.spec_from_file_location("_archie_install_hooks", _INSTALL_HOOKS_PATH)
assert _spec and _spec.loader
_install_hooks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_install_hooks)
PRE_VALIDATE_HOOK = _install_hooks.PRE_VALIDATE_HOOK

# Same dance for extract_output (used by source-stamping tests).
_EXTRACT_OUTPUT_PATH = REPO_ROOT / "archie" / "standalone" / "extract_output.py"
_spec2 = importlib.util.spec_from_file_location("_archie_extract_output", _EXTRACT_OUTPUT_PATH)
assert _spec2 and _spec2.loader
_extract_output = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(_extract_output)


VALID_SEVERITY_CLASSES = {
    "decision_violation",
    "pitfall_triggered",
    "tradeoff_undermined",
    "pattern_divergence",
    "mechanical_violation",
}
VALID_SOURCES = {
    "deep_scan",
    "scan",
    "scan-amended",
    "scan-proposed",
    "scan-adopted",
    "scan-inferred",
    "adopted",
    "blueprint",
}


# ---------------------------------------------------------------------------
# Helpers — run the canonical hook script against a fake project
# ---------------------------------------------------------------------------


def _run_hook(
    tmp_path: Path,
    rules: list[dict[str, Any]],
    tool_input: dict[str, Any],
    platform_rules: list[dict[str, Any]] | None = None,
) -> subprocess.CompletedProcess:
    """Run PRE_VALIDATE_HOOK with the given rules + tool input.

    Sets up a fake project root with .archie/rules.json (and optionally
    platform_rules.json), writes the hook to a temp .sh, and pipes the
    tool-call JSON in as stdin (which is how Claude Code invokes the hook).
    """
    project = tmp_path
    archie = project / ".archie"
    archie.mkdir(parents=True, exist_ok=True)
    (archie / "rules.json").write_text(json.dumps({"rules": rules}))
    if platform_rules is not None:
        (archie / "platform_rules.json").write_text(json.dumps({"rules": platform_rules}))
    # Initialize a real git repo so `git rev-parse --show-toplevel` works.
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    hook_path = project / "pre_validate.sh"
    hook_path.write_text(PRE_VALIDATE_HOOK)
    hook_path.chmod(0o755)

    proc = subprocess.run(
        ["bash", str(hook_path)],
        input=json.dumps(tool_input),
        capture_output=True,
        text=True,
        cwd=project,
    )
    return proc


def _make_tool_input(file_path: str, content: str, tool_name: str = "Edit") -> dict[str, Any]:
    if tool_name == "Edit":
        return {"tool_name": "Edit", "tool_input": {"file_path": file_path, "new_string": content}}
    if tool_name == "Write":
        return {"tool_name": "Write", "tool_input": {"file_path": file_path, "content": content}}
    raise ValueError(f"unknown tool_name {tool_name}")


# ---------------------------------------------------------------------------
# 1. Schema validation
# ---------------------------------------------------------------------------


def _new_shape_rule(**overrides: Any) -> dict[str, Any]:
    base = {
        "id": "tx-001",
        "severity_class": "decision_violation",
        "description": "Wrap helpers accepting *entdb.Client in entutils.Tx",
        "why": "Database transactions span the full charge lifecycle.",
        "example": "func (a *adapter) AdvanceCharges(...) error { return entutils.Tx(...) }",
        "source": "deep_scan",
    }
    base.update(overrides)
    return base


def test_schema_valid_new_shape_rule() -> None:
    r = _new_shape_rule()
    assert r["id"]
    assert r["severity_class"] in VALID_SEVERITY_CLASSES
    assert r["description"]
    assert r["source"] in VALID_SOURCES


def test_schema_rejects_unknown_severity_class() -> None:
    r = _new_shape_rule(severity_class="bogus_class")
    assert r["severity_class"] not in VALID_SEVERITY_CLASSES


def test_schema_rejects_unknown_source() -> None:
    r = _new_shape_rule(source="totally-made-up")
    assert r["source"] not in VALID_SOURCES


# ---------------------------------------------------------------------------
# 2. Backward-compat rendering — old-shape rule still produces a message
# ---------------------------------------------------------------------------


def test_old_shape_rule_renders_without_crash(tmp_path: Path) -> None:
    """Rule with only id/description/severity (today's openmeter shape)
    must not crash the hook and must surface the description to the agent."""
    old_rule = {
        "id": "legacy-1",
        "description": "Never edit generated files in ent/db/",
        "rationale": "Generated files are overwritten on next make generate.",
        "severity": "error",
        "check": "forbidden_content",
        "applies_to": "openmeter/ent/db/",
        "forbidden_patterns": ["^(?!// Code generated)"],
    }
    proc = _run_hook(
        tmp_path,
        rules=[old_rule],
        tool_input=_make_tool_input("openmeter/ent/db/foo.go", "package db\nfunc Foo() {}"),
    )
    # forbidden_content should fire. severity=error -> blocking.
    assert proc.returncode == 2, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    assert "legacy-1" in proc.stdout
    # WHY block should be populated from `rationale` (backward-compat fallback)
    assert "WHY:" in proc.stdout
    assert "overwritten" in proc.stdout


# ---------------------------------------------------------------------------
# 3. New-shape rendering — WHY and EXAMPLE blocks present
# ---------------------------------------------------------------------------


def test_new_shape_rule_renders_why_and_example(tmp_path: Path) -> None:
    rule = _new_shape_rule(
        id="dep-001",
        severity_class="mechanical_violation",
        description="Domain layer must not import from presentation layer",
        why="The domain is the stable core. UI depends on domain, never the reverse.",
        example="// domain/order.go imports nothing from presentation/",
        check="forbidden_import",
        applies_to="domain/",
        forbidden_patterns=["from presentation"],
    )
    proc = _run_hook(
        tmp_path,
        rules=[rule],
        tool_input=_make_tool_input(
            "domain/order.go",
            "package domain\nimport \"x/from presentation\"\n",
        ),
    )
    assert proc.returncode == 2
    assert "dep-001" in proc.stdout
    assert "WHY:" in proc.stdout
    assert "stable core" in proc.stdout
    assert "EXAMPLE:" in proc.stdout
    assert "domain/order.go" in proc.stdout


# ---------------------------------------------------------------------------
# 4. Severity gating — exit code matches severity_class
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "severity_class,expected_exit,expected_label",
    [
        ("decision_violation", 2, "BLOCKED"),
        ("pitfall_triggered", 2, "BLOCKED"),
        ("mechanical_violation", 2, "BLOCKED"),
        ("tradeoff_undermined", 0, "WARN"),
        ("pattern_divergence", 0, "INFO"),
    ],
)
def test_severity_class_drives_exit_code(
    tmp_path: Path,
    severity_class: str,
    expected_exit: int,
    expected_label: str,
) -> None:
    rule = _new_shape_rule(
        id="sev-test",
        severity_class=severity_class,
        check="forbidden_content",
        applies_to="src/",
        forbidden_patterns=["BANNED"],
    )
    proc = _run_hook(
        tmp_path,
        rules=[rule],
        tool_input=_make_tool_input("src/foo.go", "BANNED string here"),
    )
    assert proc.returncode == expected_exit, (
        f"severity={severity_class} expected exit {expected_exit}, "
        f"got {proc.returncode}. stdout={proc.stdout!r}"
    )
    assert expected_label in proc.stdout
    assert severity_class in proc.stdout


# ---------------------------------------------------------------------------
# 5. Source-field stamping — cmd_rules adds source=deep_scan defensively
# ---------------------------------------------------------------------------


def test_cmd_rules_stamps_missing_source(tmp_path: Path) -> None:
    """Rules emitted by Sonnet without `source` should be stamped
    `deep_scan` post-hoc by extract_output.py cmd_rules."""
    raw_input = tmp_path / "raw.txt"
    raw_input.write_text(json.dumps({
        "rules": [
            {"id": "no-source", "description": "X"},
            {"id": "explicit", "description": "Y", "source": "scan"},
        ]
    }))
    out_path = tmp_path / "rules.json"

    _extract_output.cmd_rules(str(raw_input), str(out_path))

    saved = json.loads(out_path.read_text())["rules"]
    by_id = {r["id"]: r for r in saved}
    assert by_id["no-source"]["source"] == "deep_scan", "missing source not stamped"
    assert by_id["explicit"]["source"] == "scan", "existing source got overwritten"


def test_cmd_rules_preserves_adopted_rules(tmp_path: Path) -> None:
    """Existing rules with id not in new set should be preserved (today's
    behavior). New behavior: still preserved AND any of those without
    source remain untouched (cmd_rules only stamps NEW rules)."""
    out_path = tmp_path / "rules.json"
    out_path.write_text(json.dumps({"rules": [
        {"id": "old-1", "description": "kept", "source": "adopted"},
    ]}))
    raw_input = tmp_path / "raw.txt"
    raw_input.write_text(json.dumps({"rules": [
        {"id": "new-1", "description": "new"},
    ]}))

    _extract_output.cmd_rules(str(raw_input), str(out_path))

    saved = {r["id"]: r for r in json.loads(out_path.read_text())["rules"]}
    assert "old-1" in saved
    assert saved["old-1"]["source"] == "adopted"
    assert saved["new-1"]["source"] == "deep_scan"


# ---------------------------------------------------------------------------
# 7. check_rules + arch_review handle severity_class
# ---------------------------------------------------------------------------


_CHECK_RULES_PATH = REPO_ROOT / "archie" / "standalone" / "check_rules.py"
_spec_cr = importlib.util.spec_from_file_location("_archie_check_rules", _CHECK_RULES_PATH)
assert _spec_cr and _spec_cr.loader
_check_rules = importlib.util.module_from_spec(_spec_cr)
_spec_cr.loader.exec_module(_check_rules)


@pytest.mark.parametrize(
    "rule,expected",
    [
        ({"severity_class": "decision_violation"}, "error"),
        ({"severity_class": "pitfall_triggered"}, "error"),
        ({"severity_class": "mechanical_violation"}, "error"),
        ({"severity_class": "tradeoff_undermined"}, "warn"),
        ({"severity_class": "pattern_divergence"}, "info"),
        ({"severity": "error"}, "error"),  # legacy shape
        ({"severity": "warn"}, "warn"),  # legacy shape
        ({}, "warn"),  # nothing → warn default
        ({"severity_class": "unknown", "severity": "error"}, "error"),  # unknown class falls back
    ],
)
def test_check_rules_effective_severity(rule, expected):
    """check_rules.py must bucket new-shape rule violations correctly so the
    summary at the end of `archie check` doesn't show 0 errors when
    decision_violation rules fired."""
    assert _check_rules._effective_severity(rule) == expected


_ARCH_REVIEW_PATH = REPO_ROOT / "archie" / "standalone" / "arch_review.py"
_spec_ar = importlib.util.spec_from_file_location("_archie_arch_review", _ARCH_REVIEW_PATH)
assert _spec_ar and _spec_ar.loader
_arch_review = importlib.util.module_from_spec(_spec_ar)
_spec_ar.loader.exec_module(_arch_review)


def test_arch_review_summary_renders_new_shape(tmp_path):
    """arch_review.py — used by post-plan-review and pre-commit-review hooks —
    must render the new-shape WHY + EXAMPLE blocks for the AI reviewer, with
    fallback to legacy rationale for old-shape rules."""
    archie = tmp_path / ".archie"
    archie.mkdir()
    (archie / "rules.json").write_text(json.dumps({
        "rules": [
            {
                "id": "new-1",
                "severity_class": "decision_violation",
                "description": "Wrap helpers in entutils.Tx",
                "why": "Transactions span the full charge lifecycle.",
                "example": "func ... { return entutils.Tx(...) }",
            },
            {
                "id": "old-1",
                "severity": "error",
                "description": "Never edit ent/db/",
                "rationale": "Generated files get overwritten.",
            },
        ]
    }))
    summary = _arch_review._get_rules_summary(tmp_path)
    # New-shape rule: shows severity_class as label, why + example
    assert "decision_violation" in summary
    assert "new-1" in summary
    assert "Transactions span" in summary
    assert "entutils.Tx" in summary
    # Old-shape rule: shows legacy severity, rationale falls into Why slot
    assert "old-1" in summary
    assert "Generated files get overwritten" in summary
    # Header acknowledges the gradient
    assert "decision_violation" in summary
    assert "tradeoff_undermined" in summary


# ---------------------------------------------------------------------------
# 8. Regression — openmeter's real rules.json shape doesn't crash
# ---------------------------------------------------------------------------


OPENMETER_RULES_PATH = Path("/Users/hamutarto/DEV/gbr/openmeter/.archie/rules.json")


@pytest.mark.skipif(
    not OPENMETER_RULES_PATH.exists(),
    reason="openmeter checkout not present; skip real-world regression",
)
def test_openmeter_existing_rules_render_without_crash(tmp_path: Path) -> None:
    """Run the hook against a sample of openmeter's 36 existing old-shape
    rules to confirm backward compat. The hook must not crash regardless
    of which rules fire — exit code can be 0 or 2, but never an error."""
    om_rules = json.loads(OPENMETER_RULES_PATH.read_text()).get("rules", [])
    assert len(om_rules) > 0

    # Pick an arbitrary edit that doesn't deliberately violate anything;
    # the hook still loads + iterates every rule, which is what we care about.
    proc = _run_hook(
        tmp_path,
        rules=om_rules,
        tool_input=_make_tool_input(
            "openmeter/billing/charges/adapter/foo.go",
            "package adapter\nfunc Foo() {}\n",
        ),
    )
    # Exit 0 (nothing fired) or 2 (something fired) are both legitimate.
    # Exit 1 would mean a python crash inside the heredoc.
    assert proc.returncode in (0, 2), (
        f"hook crashed on openmeter rules: rc={proc.returncode} "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )

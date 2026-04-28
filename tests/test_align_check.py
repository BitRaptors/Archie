"""Tests for archie/standalone/align_check.py — Phase 3 classifier glue.

The classifier itself talks to claude CLI, which we don't run in tests.
We exercise the parts of align_check that are deterministic: rule loading
(architectural-only filter), input parsing (PostToolUse envelope), and
diagnostic rendering with severity gating.

A subprocess-mocked variant covers the full plan flow with a fake
classifier verdict to confirm exit-code semantics.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "_archie_align_check",
    REPO_ROOT / "archie" / "standalone" / "align_check.py",
)
assert _SPEC and _SPEC.loader
_ac = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_ac)


# ---------------------------------------------------------------------------
# Rule loading
# ---------------------------------------------------------------------------


def test_loads_classifier_set_from_index(tmp_path):
    """When rule_index.json exists, _load_architectural_rules returns
    only the rule objects whose IDs are in for_classifier."""
    archie = tmp_path / ".archie"
    archie.mkdir()
    (archie / "rules.json").write_text(json.dumps({
        "rules": [
            {"id": "arch-1", "severity_class": "decision_violation",
             "description": "A", "why": "..."},
            {"id": "mech-1", "severity_class": "mechanical_violation",
             "description": "M"},
            {"id": "arch-2", "severity_class": "tradeoff_undermined",
             "description": "B", "why": "..."},
        ]
    }))
    (archie / "rule_index.json").write_text(json.dumps({
        "by_path_glob": {},
        "by_code_shape": [],
        "for_classifier": ["arch-1", "arch-2"],
    }))
    rules = _ac._load_architectural_rules(archie)
    ids = {r["id"] for r in rules}
    assert ids == {"arch-1", "arch-2"}


def test_loads_falls_back_to_severity_filter_without_index(tmp_path):
    """Without an index, classifier-eligible = anything not explicitly
    mechanical_violation. Old-shape rules with rationale qualify even if
    they also carry a mechanical check field — the rationale is the
    architectural intent the classifier reasons about."""
    archie = tmp_path / ".archie"
    archie.mkdir()
    (archie / "rules.json").write_text(json.dumps({
        "rules": [
            {"id": "arch-1", "severity_class": "decision_violation"},
            {"id": "mech-1", "severity_class": "mechanical_violation"},
            {"id": "legacy-arch", "rationale": "why"},
            {"id": "legacy-mech-with-rationale", "rationale": "intent",
             "check": "forbidden_content"},
            {"id": "legacy-bare", "check": "naming"},  # no rationale -> excluded
        ]
    }))
    rules = _ac._load_architectural_rules(archie)
    ids = {r["id"] for r in rules}
    assert ids == {"arch-1", "legacy-arch", "legacy-mech-with-rationale"}


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------


def test_read_plan_extracts_from_post_tool_use_envelope(monkeypatch):
    """PostToolUse on ExitPlanMode: tool_input.plan carries the markdown plan."""
    payload = json.dumps({
        "tool_name": "ExitPlanMode",
        "tool_input": {"plan": "1. Add a discount calculator to CheckoutForm\n2. ..."},
    })
    monkeypatch.setattr("sys.stdin.read", lambda: payload)
    out = _ac._read_plan_from_stdin()
    assert "discount calculator" in out


def test_read_plan_falls_back_to_raw_text(monkeypatch):
    """If stdin isn't JSON, treat it as the plan text directly."""
    monkeypatch.setattr("sys.stdin.read", lambda: "raw plan text without envelope")
    out = _ac._read_plan_from_stdin()
    assert out == "raw plan text without envelope"


def test_read_plan_handles_tool_response_shape(monkeypatch):
    payload = json.dumps({
        "tool_name": "ExitPlanMode",
        "tool_response": {"plan": "step 1\nstep 2"},
    })
    monkeypatch.setattr("sys.stdin.read", lambda: payload)
    out = _ac._read_plan_from_stdin()
    assert "step 1" in out


# ---------------------------------------------------------------------------
# Classifier prompt
# ---------------------------------------------------------------------------


def test_classifier_prompt_contains_each_rule_with_why_and_example():
    rules = [
        {
            "id": "tx-001",
            "severity_class": "decision_violation",
            "description": "Wrap helpers in entutils.Tx",
            "why": "Transactions span the full lifecycle.",
            "example": "func F() { return entutils.Tx(...) }",
        },
        {
            "id": "ctx-001",
            "severity_class": "pitfall_triggered",
            "description": "No context.Background()",
            "why": "Drops cancellation.",
        },
    ]
    prompt = _ac._build_classifier_prompt("step 1: add code", "plan", rules)
    assert "tx-001" in prompt
    assert "decision_violation" in prompt
    assert "Transactions span the full lifecycle" in prompt
    assert "entutils.Tx(...)" in prompt
    assert "ctx-001" in prompt
    assert "Drops cancellation" in prompt
    # Plan framing
    assert "PLAN" in prompt
    assert "step 1: add code" in prompt
    # Output schema instruction
    assert "diagnostics" in prompt
    assert "highest_severity" in prompt


def test_classifier_prompt_uses_legacy_severity_when_severity_class_missing():
    rules = [{"id": "legacy-1", "severity": "error", "description": "X", "rationale": "Y"}]
    prompt = _ac._build_classifier_prompt("plan text", "plan", rules)
    assert "legacy-1" in prompt
    # Legacy rules surface a sentinel so the model knows it's pre-Phase-1
    assert "error-legacy" in prompt
    # Rationale falls into the Why slot
    assert "Y" in prompt


# ---------------------------------------------------------------------------
# Diagnostic rendering — severity gating
# ---------------------------------------------------------------------------


def test_render_diagnostics_returns_blocking_for_decision_violation(capsys):
    verdict = {
        "diagnostics": [
            {
                "rule_id": "tx-001",
                "severity_class": "decision_violation",
                "verdict": "violates",
                "evidence": "Step 2 wraps without entutils.Tx",
                "suggested_fix": "Wrap call in entutils.Tx",
            },
        ],
    }
    blocking = _ac._render_diagnostics(verdict)
    assert blocking is True
    out = capsys.readouterr().out
    assert "BLOCKED" in out
    assert "tx-001" in out
    assert "Step 2 wraps without entutils.Tx" in out
    assert "Wrap call in entutils.Tx" in out


def test_render_diagnostics_warns_on_tradeoff(capsys):
    verdict = {
        "diagnostics": [
            {
                "rule_id": "cache-001",
                "severity_class": "tradeoff_undermined",
                "verdict": "violates",
                "evidence": "Sync I/O in hot path",
            },
        ],
    }
    blocking = _ac._render_diagnostics(verdict)
    assert blocking is False
    out = capsys.readouterr().out
    assert "WARN" in out
    assert "BLOCKED" not in out


def test_render_diagnostics_skips_non_violations(capsys):
    verdict = {
        "diagnostics": [
            {"rule_id": "x", "severity_class": "decision_violation",
             "verdict": "respects", "evidence": "fine"},
            {"rule_id": "y", "severity_class": "decision_violation",
             "verdict": "not_relevant"},
        ],
    }
    blocking = _ac._render_diagnostics(verdict)
    assert blocking is False
    assert capsys.readouterr().out == ""


def test_render_diagnostics_pattern_divergence_is_info(capsys):
    verdict = {
        "diagnostics": [
            {"rule_id": "p", "severity_class": "pattern_divergence",
             "verdict": "violates", "evidence": "ev"}
        ]
    }
    blocking = _ac._render_diagnostics(verdict)
    assert blocking is False
    assert "INFO" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# End-to-end with mocked claude CLI
# ---------------------------------------------------------------------------


def test_cmd_plan_blocks_when_classifier_returns_decision_violation(
    tmp_path, monkeypatch, capsys
):
    """Full cmd_plan flow with the claude CLI invocation mocked.

    Proves the pipeline: read stdin -> load rules -> build prompt -> run
    classifier -> render diagnostics -> exit 2 when blocking."""
    archie = tmp_path / ".archie"
    archie.mkdir()
    (archie / "rules.json").write_text(json.dumps({
        "rules": [
            {"id": "layer-001", "severity_class": "decision_violation",
             "description": "UI must not contain domain logic",
             "why": "Pricing belongs in domain/."}
        ]
    }))
    plan_payload = json.dumps({
        "tool_name": "ExitPlanMode",
        "tool_input": {"plan": "Add discount calculator to CheckoutForm.tsx"},
    })
    monkeypatch.setattr("sys.stdin.read", lambda: plan_payload)

    # Mock the classifier to return a violates verdict
    def fake_invoke(prompt):
        return {
            "diagnostics": [
                {
                    "rule_id": "layer-001",
                    "severity_class": "decision_violation",
                    "verdict": "violates",
                    "evidence": "Plan adds discount calc inside UI component",
                    "suggested_fix": "Move calc into domain/promotions/",
                }
            ],
            "highest_severity": "decision_violation",
        }
    monkeypatch.setattr(_ac, "_invoke_claude_classifier", fake_invoke)

    rc = _ac.cmd_plan(tmp_path)
    assert rc == 2
    out = capsys.readouterr().out
    assert "BLOCKED" in out
    assert "layer-001" in out
    assert "domain/promotions" in out


def test_cmd_plan_advisory_when_classifier_unavailable(
    tmp_path, monkeypatch, capsys
):
    """If claude CLI is missing, fall back to advisory mode (rule context
    printed, exit 0). Prevents Archie from breaking when claude isn't on PATH."""
    archie = tmp_path / ".archie"
    archie.mkdir()
    (archie / "rules.json").write_text(json.dumps({
        "rules": [
            {"id": "x", "severity_class": "decision_violation",
             "description": "...", "why": "..."}
        ]
    }))
    monkeypatch.setattr("sys.stdin.read", lambda: "raw plan")
    monkeypatch.setattr(_ac, "_invoke_claude_classifier", lambda p: None)

    rc = _ac.cmd_plan(tmp_path)
    assert rc == 0
    out = capsys.readouterr().out
    assert "Classifier unavailable" in out
    assert "x" in out


def test_cmd_plan_zero_when_no_rules(tmp_path, monkeypatch):
    """Empty rules.json -> nothing to compare, exit 0 silently."""
    archie = tmp_path / ".archie"
    archie.mkdir()
    (archie / "rules.json").write_text(json.dumps({"rules": []}))
    monkeypatch.setattr("sys.stdin.read", lambda: "any plan")
    rc = _ac.cmd_plan(tmp_path)
    assert rc == 0


def test_cmd_plan_zero_when_stdin_empty(tmp_path, monkeypatch):
    archie = tmp_path / ".archie"
    archie.mkdir()
    (archie / "rules.json").write_text(json.dumps({
        "rules": [{"id": "x", "severity_class": "decision_violation"}]
    }))
    monkeypatch.setattr("sys.stdin.read", lambda: "")
    rc = _ac.cmd_plan(tmp_path)
    assert rc == 0

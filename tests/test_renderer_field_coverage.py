"""Field-coverage tests for the standalone renderer.

These test that the renderer surfaces blueprint fields that inform agent
behavior — specifically the three fields that used to be silently dropped:

- `communication.integrations` — external service integration surface
- `decisions.trade_offs[].violation_signals` — code-pattern signals that
  undo a trade-off (primary enforcement surface)
- `decisions.decision_chain.forces[].violation_keywords` — code-pattern
  fingerprints at decision-chain nodes

The renderer is the canonical bridge between the blueprint and what
agents see at session start. Dropping enforcement-relevant fields here
leaks them out of the entire delivery chain.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


_RENDERER = Path(__file__).resolve().parent.parent / "archie" / "standalone" / "renderer.py"
_SPEC = importlib.util.spec_from_file_location("standalone_renderer", _RENDERER)
renderer = importlib.util.module_from_spec(_SPEC)  # type: ignore[arg-type]
_SPEC.loader.exec_module(renderer)  # type: ignore[union-attr]


def _bp(**overrides) -> dict:
    """Minimal blueprint with optional section overrides."""
    base = {
        "meta": {"repository": "test-repo", "executive_summary": "test"},
        "decisions": {
            "architectural_style": {
                "title": "Layered",
                "chosen": "Layered",
                "rationale": "x",
            },
        },
        "components": {"structure_type": "layered", "components": []},
        "technology": {"stack": [], "run_commands": {}},
        "deployment": {},
        "architecture_rules": {"file_placement_rules": [], "naming_conventions": []},
        "communication": {"patterns": [], "integrations": [], "pattern_selection_guide": []},
        "quick_reference": {"where_to_put_code": {}, "pattern_selection": {}, "error_mapping": []},
        "implementation_guidelines": [],
        "development_rules": [],
        "pitfalls": [],
        "frontend": {},
    }
    for key, val in overrides.items():
        base[key] = val
    return base


# ---------------------------------------------------------------------------
# Gap 1: communication.integrations
# ---------------------------------------------------------------------------


def test_integrations_render_in_patterns_rule():
    bp = _bp(
        communication={
            "patterns": [],
            "integrations": [
                {"service": "ClickHouse", "purpose": "high-volume analytics",
                 "integration_point": "openmeter/streaming/Connector"},
                {"service": "Kafka", "purpose": "event ingestion",
                 "integration_point": "openmeter/sink-worker"},
            ],
            "pattern_selection_guide": [],
        },
    )
    result = renderer._build_patterns_rule(bp)
    assert result is not None
    body = result["body"]
    assert "## Integrations" in body
    assert "ClickHouse" in body
    assert "high-volume analytics" in body
    assert "openmeter/streaming/Connector" in body
    assert "Kafka" in body
    assert "event ingestion" in body


def test_integrations_render_in_agents_md():
    bp = _bp(
        communication={
            "patterns": [],
            "integrations": [
                {"service": "PostgreSQL via Ent", "purpose": "primary datastore",
                 "integration_point": "openmeter/ent/db"},
            ],
            "pattern_selection_guide": [],
        },
    )
    out = renderer.generate_agents_md(bp)
    assert "## Integrations" in out
    assert "PostgreSQL via Ent" in out
    assert "primary datastore" in out
    assert "openmeter/ent/db" in out


def test_integrations_absent_no_section():
    """No integrations array → no Integrations heading."""
    bp = _bp()
    agents = renderer.generate_agents_md(bp)
    patterns = renderer._build_patterns_rule(bp)
    assert "## Integrations" not in agents
    if patterns:
        assert "## Integrations" not in patterns["body"]


def test_integrations_without_integration_point_still_render():
    bp = _bp(
        communication={
            "patterns": [],
            "integrations": [{"service": "Stripe", "purpose": "payments"}],
            "pattern_selection_guide": [],
        },
    )
    out = renderer.generate_agents_md(bp)
    assert "Stripe" in out
    assert "payments" in out


# ---------------------------------------------------------------------------
# Gap 2: trade_offs[].violation_signals
# ---------------------------------------------------------------------------


_TRADE_OFF_WITH_SIGNALS = {
    "accept": "Multi-tenant leakage risk",
    "benefit": "Zero cross-tenant data exposure",
    "caused_by": "Namespace-scoped multi-tenancy decision",
    "violation_signals": [
        "ent query on a multi-tenant entity without a Namespace predicate",
        "a new adapter method that accepts no namespace input",
        "bypass helpers called outside TransactingRepo",
    ],
}


def test_violation_signals_render_in_patterns_rule():
    bp = _bp(decisions={
        "architectural_style": {"chosen": "Layered", "rationale": "x"},
        "trade_offs": [_TRADE_OFF_WITH_SIGNALS],
        "key_decisions": [],
        "out_of_scope": [],
        "decision_chain": {},
    })
    result = renderer._build_patterns_rule(bp)
    assert result is not None
    body = result["body"]
    assert "Multi-tenant leakage risk" in body
    assert "Violation signal" in body
    assert "ent query on a multi-tenant entity without a Namespace predicate" in body
    assert "a new adapter method that accepts no namespace input" in body


def test_violation_signals_render_in_agents_md():
    bp = _bp(decisions={
        "architectural_style": {"chosen": "Layered", "rationale": "x"},
        "trade_offs": [_TRADE_OFF_WITH_SIGNALS],
        "key_decisions": [],
        "out_of_scope": [],
        "decision_chain": {},
    })
    out = renderer.generate_agents_md(bp)
    assert "Multi-tenant leakage risk" in out
    assert "Zero cross-tenant data exposure" in out
    assert "Violation signal" in out
    assert "ent query on a multi-tenant entity without a Namespace predicate" in out


def test_trade_off_without_violation_signals_still_renders():
    bp = _bp(decisions={
        "architectural_style": {"chosen": "Layered", "rationale": "x"},
        "trade_offs": [{"accept": "X", "benefit": "Y"}],
        "key_decisions": [],
        "out_of_scope": [],
        "decision_chain": {},
    })
    result = renderer._build_patterns_rule(bp)
    assert result is not None
    assert "X" in result["body"]
    assert "Y" in result["body"]
    # No violation-signals block when the field is missing.
    assert "Violation signal" not in result["body"]


# ---------------------------------------------------------------------------
# Gap 3: decision_chain.forces[].violation_keywords
# ---------------------------------------------------------------------------


def test_violation_keywords_render_in_decision_chain():
    bp = _bp(decisions={
        "architectural_style": {"chosen": "Layered", "rationale": "x"},
        "trade_offs": [],
        "key_decisions": [],
        "out_of_scope": [],
        "decision_chain": {
            "root": "Multi-tenant SaaS",
            "forces": [
                {
                    "decision": "Namespace-scoped multi-tenancy",
                    "rationale": "Every query carries tenant scope",
                    "violation_keywords": [
                        "Ent query without .Namespace predicate",
                        "bypass namespace check",
                        "global query across tenants",
                    ],
                    "forces": [],
                },
            ],
        },
    })
    out = renderer.generate_agents_md(bp)
    assert "Namespace-scoped multi-tenancy" in out
    assert "Violation keyword" in out
    assert "Ent query without .Namespace predicate" in out
    assert "bypass namespace check" in out
    assert "global query across tenants" in out


def test_violation_keywords_render_recursively():
    bp = _bp(decisions={
        "architectural_style": {"chosen": "Layered", "rationale": "x"},
        "trade_offs": [],
        "key_decisions": [],
        "out_of_scope": [],
        "decision_chain": {
            "root": "R",
            "forces": [
                {
                    "decision": "outer",
                    "rationale": "outer-rat",
                    "violation_keywords": ["outer-kw"],
                    "forces": [
                        {
                            "decision": "inner",
                            "rationale": "inner-rat",
                            "violation_keywords": ["inner-kw"],
                            "forces": [],
                        },
                    ],
                },
            ],
        },
    })
    out = renderer.generate_agents_md(bp)
    assert "outer-kw" in out
    assert "inner-kw" in out


def test_decision_chain_without_violation_keywords_still_renders():
    bp = _bp(decisions={
        "architectural_style": {"chosen": "Layered", "rationale": "x"},
        "trade_offs": [],
        "key_decisions": [],
        "out_of_scope": [],
        "decision_chain": {
            "root": "R",
            "forces": [{"decision": "D", "rationale": "rat", "forces": []}],
        },
    })
    out = renderer.generate_agents_md(bp)
    assert "**D**: rat" in out
    assert "Violation keyword" not in out

"""Phase 2: step-6 rule synthesis covers the product-law sections, excludes the
informational ones, and a domain_invariant rule round-trips through
extract_output -> classify_kind -> rule_index without special-casing.
"""
from __future__ import annotations

import json
from pathlib import Path

from archie.standalone.extract_output import cmd_rules
from archie.standalone.rule_kinds import classify_kind
from archie.standalone.rule_index import build_index

STEP6 = (
    Path(__file__).resolve().parent.parent
    / "archie" / "assets" / "workflow" / "deep-scan" / "steps" / "step-6-rule-synthesis.md"
)


def test_step6_prompt_covers_product_laws():
    """Guard against silent drift: the coverage table and policy must name the
    new sections, and must exclude the informational-only ones."""
    text = STEP6.read_text()
    # coverage rows
    assert "`domain_invariants[*]`" in text
    assert "`derived_invariants[*]`" in text
    assert "`domain_invariant`" in text
    # the informational-only sections are explicitly NOT rule sources
    assert "Do NOT emit rules from `product_model`" in text
    assert "unenforced_invariants" in text
    # the dedicated severity + dedup policy exists
    assert "Product-law rules" in text
    assert "canonical carrier" in text


def test_domain_invariant_rule_roundtrips(tmp_path):
    """A stated + a derived product-law rule survive extract_output and index."""
    agent_out = tmp_path / "agent_rules.json"
    agent_out.write_text(json.dumps({"rules": [
        {
            "id": "inv-balance-001", "kind": "domain_invariant", "topic": "data-access",
            "severity_class": "decision_violation",
            "description": "An account balance must never go negative",
            "why": "Spending below zero diverges the ledger from the charged total.",
            "triggers": {"path_glob": ["app/wallet/**"]},
        },
        {
            "id": "der-001", "kind": "domain_invariant", "topic": "data-access",
            "severity_class": "tradeoff_undermined",
            "description": "A credit cannot be reduced below its spent amount",
            "why": "Derived from inv-balance-001 + inv-ingest-001.",
        },
    ]}))
    rules_json = tmp_path / "rules.json"
    cmd_rules(str(agent_out), str(rules_json))

    saved = json.loads(rules_json.read_text())["rules"]
    by_id = {r["id"]: r for r in saved}
    assert set(by_id) == {"inv-balance-001", "der-001"}
    # both classify as domain_invariant (explicit kind preserved)
    assert classify_kind(by_id["inv-balance-001"]) == "domain_invariant"
    assert classify_kind(by_id["der-001"]) == "domain_invariant"
    # severity policy: observed blocks, derived warns
    assert by_id["inv-balance-001"]["severity_class"] == "decision_violation"
    assert by_id["der-001"]["severity_class"] == "tradeoff_undermined"
    # source stamped defensively
    assert all(r["source"] == "deep_scan" for r in saved)

    # the index picks up the observed law's enforced-at path glob
    index = build_index(saved)
    assert "app/wallet/**" in index["by_path_glob"]
    assert "inv-balance-001" in index["by_path_glob"]["app/wallet/**"]

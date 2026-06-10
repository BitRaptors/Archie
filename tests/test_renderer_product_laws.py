"""Phase 2: the renderer emits the product-model + two-tier product-laws
descriptive markdown, and routes domain_invariant enforcement rules into the
by-topic directory. The grounded/ungrounded boundary must be unmissable and a
gap entry must never leak into the grounded tier.
"""
from __future__ import annotations

import json
from pathlib import Path

from archie.standalone import renderer
from archie.standalone._common import normalize_blueprint

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "blueprint_domain_invariants.json"


def _render():
    bp = json.loads(FIXTURE.read_text())
    normalize_blueprint(bp)
    rules = [{
        "id": "inv-balance-001", "kind": "domain_invariant", "topic": "data-modeling",
        "severity_class": "decision_violation", "description": "Balance never negative",
        "why": "Spending below zero diverges ledger from charges.", "_archie_source": "project",
    }]
    return renderer.generate_all(bp, enforcement_rules=rules), bp


def test_product_laws_file_has_both_tiers():
    files, _ = _render()
    body = files[".claude/rules/product-laws.md"]
    assert "## Product Laws — enforced (grounded)" in body
    assert "## ⚠️ Unverified" in body
    # grounded enforced citation
    assert "app/wallet/balance_repo.ext:214" in body
    # derived law, anchored
    assert "_(derived)_" in body
    assert "inv-balance-001" in body
    # unverified gap shows its proof-of-work
    assert "Searched (no enforcement found)" in body


def test_gap_law_never_appears_in_grounded_tier():
    """The unenforced law's text must sit only under the ⚠️ header."""
    files, _ = _render()
    body = files[".claude/rules/product-laws.md"]
    grounded, _, unverified = body.partition("## ⚠️ Unverified")
    gap_text = "An issued charge record's total equals the sum of its line amounts."
    assert gap_text not in grounded
    assert gap_text in unverified


def test_product_model_file_rendered():
    files, _ = _render()
    body = files[".claude/rules/product-model.md"]
    assert "## Product Model" in body
    assert "Core workflow:" in body
    assert "AccountBalance" in body


def test_domain_invariant_rule_grouped_in_enforcement():
    files, _ = _render()
    assert ".claude/rules/enforcement/by-topic/data-modeling.md" in files
    assert "Balance never negative" in files[".claude/rules/enforcement/by-topic/data-modeling.md"]


def test_agents_md_summarizes_product_laws():
    files, _ = _render()
    agents = files["AGENTS.md"]
    assert "## Product Laws" in agents
    assert "Enforced (grounded)" in agents
    assert "product-laws.md" in agents
    assert "⚠️ Unverified" in agents


def test_no_product_files_when_sections_absent():
    """A blueprint with none of the new sections emits neither descriptive file."""
    bp = {"meta": {"architecture_style": "x"}, "components": {"components": []}}
    normalize_blueprint(bp)  # gives empty product_model {} and empty invariant lists
    files = renderer.generate_all(bp)
    assert ".claude/rules/product-laws.md" not in files
    assert ".claude/rules/product-model.md" not in files
    assert "## Product Laws" not in files["AGENTS.md"]

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
    # mechanism rendered as a secondary "how it's enforced" line, distinct from the law
    assert "How it's enforced:" in body
    assert "rejected past zero before the write commits" in body
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
    assert "## Product Overview" in body
    assert "### Core workflow" in body
    # workflow rendered as titled steps (new {title, description} shape)
    assert "**Ingest event**" in body
    assert "An append-only usage event is recorded" in body
    # entities are NOT rendered here — Data Models owns that inventory
    assert "AccountBalance" not in body
    assert "spend gate" not in body


def test_product_model_workflow_legacy_strings():
    """Backward compat: a workflow of plain strings still renders as numbered steps."""
    bp = {
        "meta": {"architecture_style": "x"}, "components": {"components": []},
        "product_model": {"summary": "A product.", "core_workflow": ["first thing", "second thing"]},
    }
    normalize_blueprint(bp)
    body = renderer.generate_all(bp)[".claude/rules/product-model.md"]
    assert "## Product Overview" in body
    assert "1. first thing" in body
    assert "2. second thing" in body


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


def test_product_laws_grouped_by_role_core_first():
    """domain_role groups the grounded tier with Core before Supporting before Platform."""
    bp = {
        "meta": {"architecture_style": "x"}, "components": {"components": []},
        "domain_invariants": [
            {"id": "inv-sub-1", "domain_role": "supporting", "category": "lifecycle/state",
             "invariant": "Pro is granted only on an active entitlement.", "enforced_at": ["a:1"]},
            {"id": "inv-core-1", "domain_role": "core", "category": "conservation/accounting",
             "invariant": "Temperature is normalized before the recommendation lookup.", "enforced_at": ["b:2"]},
            {"id": "inv-plat-1", "domain_role": "platform", "category": "tenant-isolation",
             "invariant": "All API calls carry a bearer token.", "enforced_at": ["c:3"]},
        ],
    }
    normalize_blueprint(bp)
    laws = renderer.generate_all(bp)[".claude/rules/product-laws.md"]
    assert "### Core product laws" in laws
    assert "### Supporting features" in laws
    assert "### Platform" in laws
    # ordering: core subheading precedes supporting precedes platform
    assert laws.index("### Core product laws") < laws.index("### Supporting features") < laws.index("### Platform")
    # the core law sits under Core, above the supporting law
    assert laws.index("Temperature is normalized") < laws.index("Pro is granted only")


def test_product_laws_flat_when_no_role():
    """Backward compat: no domain_role anywhere → flat list, no role subheadings."""
    bp = {
        "meta": {"architecture_style": "x"}, "components": {"components": []},
        "domain_invariants": [
            {"id": "inv-1", "invariant": "A law without a role.", "enforced_at": ["a:1"]},
        ],
    }
    normalize_blueprint(bp)
    laws = renderer.generate_all(bp)[".claude/rules/product-laws.md"]
    assert "A law without a role." in laws
    assert "### Core product laws" not in laws  # flat fallback


def test_derived_only_blueprint_no_dangling_header():
    """Regression (Reviewer-2): a blueprint with derived but no observed laws must
    still list the derived law in the AGENTS.md summary, not a bare header."""
    bp = {
        "meta": {"architecture_style": "x"}, "components": {"components": []},
        "derived_invariants": [{"id": "der-001", "invariant": "A derived law holds."}],
    }
    normalize_blueprint(bp)
    agents = renderer.generate_all(bp)["AGENTS.md"]
    assert "## Product Laws" in agents
    assert "A derived law holds." in agents  # listed, not a dangling header
    # the grounded summary line is immediately followed by content, not another header
    assert "**Enforced (grounded)**" in agents


def test_empty_invariant_entry_skipped():
    """Regression (Reviewer-2): a malformed entry with empty invariant text must
    not render as an empty bold bullet (`- ****`)."""
    bp = {
        "meta": {"architecture_style": "x"}, "components": {"components": []},
        "domain_invariants": [
            {"id": "inv-1", "invariant": "Real law."},
            {"id": "inv-2", "invariant": "   "},  # malformed
        ],
    }
    normalize_blueprint(bp)
    laws = renderer.generate_all(bp)[".claude/rules/product-laws.md"]
    assert "Real law." in laws
    assert "- ****" not in laws


def test_no_product_files_when_sections_absent():
    """A blueprint with none of the new sections emits neither descriptive file."""
    bp = {"meta": {"architecture_style": "x"}, "components": {"components": []}}
    normalize_blueprint(bp)  # gives empty product_model {} and empty invariant lists
    files = renderer.generate_all(bp)
    assert ".claude/rules/product-laws.md" not in files
    assert ".claude/rules/product-model.md" not in files
    assert "## Product Laws" not in files["AGENTS.md"]

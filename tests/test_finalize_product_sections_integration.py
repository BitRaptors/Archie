"""Phase 3/5 integration: a Wave 1 blueprint carrying `domain_invariants` plus a
Wave 2 Product agent sub-file flow through finalize() into blueprint.json and the
rendered product-laws.md — the full merge -> normalize -> render round-trip.
"""
from __future__ import annotations

import json
from pathlib import Path

from archie.standalone.finalize import finalize


def _setup_project(tmp_path: Path) -> Path:
    archie = tmp_path / ".archie"
    archie.mkdir()
    # Wave-1 raw blueprint: Domain agent already wrote domain_invariants here.
    raw = {
        "meta": {"architecture_style": "fixture"},
        "components": {"components": [{"name": "WalletService", "location": "app/wallet"}]},
        "domain_invariants": [{
            "id": "inv-balance-001", "entity": "AccountBalance", "category": "value-bound",
            "invariant": "Balance never goes negative.",
            "enforced_at": ["app/wallet/balance_repo.ext:214"],
            "evidence": ["guard:app/wallet/balance_repo.ext:214"],
            "failure_mode": "Customer spends unfunded value.", "confidence": "stated",
        }],
    }
    (archie / "blueprint_raw.json").write_text(json.dumps(raw))
    # Wave-2 Product agent output file.
    product = {
        "product_model": {
            "summary": "Illustrative metered-billing service.",
            "entities": [{"name": "AccountBalance", "role": "spend gate"}],
            "core_workflow": ["event", "meter", "deduct"],
        },
        "derived_invariants": [{
            "id": "der-001", "invariant": "A credit cannot be reduced below its spent amount.",
            "derived_from": ["inv-balance-001", "inv-ingest-001"],
            "failure_mode": "Negative historical balance.", "confidence": "inferred",
        }],
        "unenforced_invariants": [{
            "id": "gap-001", "expected_law": "Record total equals sum of line items.",
            "entity": "ChargeRecord", "category": "conservation",
            "why_expected": "Double-entry conservation.",
            "searched": ["app/billing/**/validate.ext"], "found_enforcement": "none",
            "risk": "Charged amount drifts from line sum.", "confidence": "inferred",
        }],
    }
    sub = archie / "tmp"
    sub.mkdir()
    (sub / "archie_sub_product_x.json").write_text(json.dumps(product))
    return archie / "tmp" / "archie_sub_product_x.json"


def test_finalize_merges_and_renders_product_sections(tmp_path):
    product_file = _setup_project(tmp_path)
    finalize(tmp_path, [str(product_file)], patch_mode=False)

    bp = json.loads((tmp_path / ".archie" / "blueprint.json").read_text())
    # Wave-1 law preserved + Wave-2 sections merged in
    assert bp["domain_invariants"][0]["id"] == "inv-balance-001"
    assert bp["product_model"]["summary"].startswith("Illustrative")
    assert bp["derived_invariants"][0]["id"] == "der-001"
    assert bp["unenforced_invariants"][0]["id"] == "gap-001"

    # rendered descriptive markdown carries both tiers, distinctly
    laws = (tmp_path / ".claude" / "rules" / "product-laws.md").read_text()
    assert "## Product Laws — enforced (grounded)" in laws
    assert "## ⚠️ Unverified" in laws
    grounded, _, unverified = laws.partition("## ⚠️ Unverified")
    assert "Balance never goes negative." in grounded
    assert "Record total equals sum of line items." in unverified  # gap only in unverified
    assert "Record total equals sum of line items." not in grounded

    model = (tmp_path / ".claude" / "rules" / "product-model.md").read_text()
    assert "AccountBalance" in model

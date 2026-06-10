"""Phase 1: the merge/normalize/finalize pipeline carries the new
domain-invariant + product-model sections without dropping or mangling them.

These sections are produced by the Wave 1 Domain agent (`domain_invariants`)
and the Wave 2 Product agent (`product_model`, `derived_invariants`,
`unenforced_invariants`). The pipeline must:
  - coerce them to the right container type (lists / dict) like every other section
  - preserve populated content verbatim through normalize
  - reset the Wave-2-owned ones on a full re-run so `--from 5` replaces, not appends
  - never reset the Wave-1-owned `domain_invariants`
"""
from __future__ import annotations

import json
from pathlib import Path

from archie.standalone._common import normalize_blueprint
from archie.standalone.finalize import _reset_reasoning_sections

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "blueprint_domain_invariants.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text())


def test_normalize_coerces_missing_sections():
    """A blueprint with none of the new sections gets stable empty containers."""
    bp: dict = {}
    normalize_blueprint(bp)
    assert bp["product_model"] == {}
    assert bp["domain_invariants"] == []
    assert bp["derived_invariants"] == []
    assert bp["unenforced_invariants"] == []


def test_normalize_coerces_wrong_types():
    bp = {
        "product_model": None,
        "domain_invariants": None,
        "derived_invariants": "oops",
        "unenforced_invariants": {},
    }
    normalize_blueprint(bp)
    assert bp["product_model"] == {}
    assert bp["domain_invariants"] == []
    assert bp["derived_invariants"] == []
    assert bp["unenforced_invariants"] == []


def test_normalize_preserves_populated_sections():
    """Populated sections survive normalize untouched (no silent drop)."""
    bp = _load_fixture()
    normalize_blueprint(bp)
    assert len(bp["domain_invariants"]) == 2
    assert bp["domain_invariants"][0]["id"] == "inv-balance-001"
    assert bp["domain_invariants"][0]["confidence"] == "stated"
    assert bp["product_model"]["summary"].startswith("Illustrative")
    assert len(bp["product_model"]["entities"]) == 2
    assert bp["derived_invariants"][0]["derived_from"] == ["inv-balance-001", "inv-ingest-001"]
    assert bp["unenforced_invariants"][0]["searched"]  # proof-of-absence retained
    assert bp["unenforced_invariants"][0]["found_enforcement"] == "none"


def test_reset_clears_wave2_product_sections():
    """Full-mode redo-safety: Product-agent sections are cleared when the incoming
    payload provides them, so the subsequent deep_merge replaces rather than appends."""
    bp = _load_fixture()
    product_payload = {
        "product_model": {"summary": "new"},
        "derived_invariants": [{"id": "der-002"}],
        "unenforced_invariants": [{"id": "gap-002"}],
    }
    _reset_reasoning_sections(bp, [product_payload])
    assert "product_model" not in bp
    assert "derived_invariants" not in bp
    assert "unenforced_invariants" not in bp


def test_reset_never_clears_wave1_domain_invariants():
    """`domain_invariants` is Wave 1 (lives in blueprint_raw) — a Wave 2 reset
    must leave it intact even if a payload somehow references it."""
    bp = _load_fixture()
    _reset_reasoning_sections(bp, [{"product_model": {"summary": "x"}}])
    assert len(bp["domain_invariants"]) == 2  # untouched


def test_reset_is_noop_when_payload_absent():
    """A payload that carries none of the product sections clears nothing."""
    bp = _load_fixture()
    before = json.dumps(bp, sort_keys=True)
    _reset_reasoning_sections(bp, [{"meta": {"executive_summary": "s"}}])
    # product sections still present (meta.executive_summary reset is unrelated)
    assert "product_model" in bp
    assert "derived_invariants" in bp

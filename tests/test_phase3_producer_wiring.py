"""Phase 3: the Domain (Wave 1) and Product (Wave 2) agents are wired into the
deep-scan orchestration — not just authored as dead prompt files. These are
step-lint assertions over the canonical workflow step files (the wire-through
discipline: a leaf prompt that nothing dispatches is dead wiring).
"""
from __future__ import annotations

from pathlib import Path

STEPS = (
    Path(__file__).resolve().parent.parent
    / "archie" / "assets" / "workflow" / "deep-scan" / "steps"
)


def _read(rel: str) -> str:
    return (STEPS / rel).read_text()


# ── Wave 1: Domain agent ────────────────────────────────────────────────────

def test_domain_agent_prompt_exists_and_is_grounded():
    body = _read("step-3-wave1/domain-agent.md")
    assert "domain_invariants" in body
    assert "Cite or omit" in body or "cite-or-omit" in body or "OBSERVE, do not invent" in body
    # the taxonomy checklist and the cite field must be present
    assert "value-bound" in body and "idempotency" in body and "tenant-isolation" in body
    assert "enforced_at" in body
    # explicit boundary vs the Data agent's schema guarantees
    assert "schema" in body.lower()


def test_domain_and_data_always_spawn_only_ui_optional():
    orch = _read("step-3-wave1/orchestration.md")
    # dispatch table rows
    assert "domain-agent.md" in orch
    assert "archie_sub6_$PROJECT_NAME.json" in orch
    # Data + Domain are Always; the persistence heuristic is no longer a spawn gate
    assert "ALWAYS spawn" in orch
    assert "only optional Wave 1 agent" in orch.lower() or "ONLY optional Wave 1 agent" in orch
    # Domain timing key registered
    assert "Domain → `domain`" in orch
    # incremental single-agent also emits domain_invariants
    assert orch.count("domain_invariants") >= 2


def test_step4_merges_domain_subfile():
    merge = _read("step-4-merge.md")
    assert "archie_sub6_$PROJECT_NAME.json" in merge
    # listed in the merge.py invocation, not just the expected-files prose
    assert merge.count("archie_sub6_$PROJECT_NAME.json") >= 2


# ── Wave 2: Product agent ───────────────────────────────────────────────────

def test_product_agent_prompt_exists_with_guardrails():
    body = _read("step-5d-product.md")
    assert "product_model" in body
    assert "derived_invariants" in body
    assert "unenforced_invariants" in body
    # derivation guardrail (cite the premises)
    assert "derived_from" in body
    assert "anchors" in body or "premises" in body
    # gap-list proof-of-absence discipline
    assert "searched" in body
    assert "proof-of-absence" in body.lower() or "proof of absence" in body.lower()


def test_product_agent_dispatched_and_gated():
    w2 = _read("step-5-wave2-reasoning.md")
    assert "step-5d-product.md" in w2
    assert "archie_sub_product_$PROJECT_NAME.json" in w2
    # gated on domain_invariants being non-empty
    assert "domain_invariants` non-empty" in w2 or "domain_invariants` array is non-empty" in w2
    # finalize lists the product file in BOTH full and patch invocations
    assert w2.count("archie_sub_product_$PROJECT_NAME.json") >= 3  # table + 2 finalize calls


def test_design_and_risk_consume_domain_invariants():
    design = _read("step-5a-design.md")
    risk = _read("step-5b-risk.md")
    # Design links decisions to the laws they preserve
    assert "domain_invariants" in design
    assert "forced_by" in design and "enables" in design
    # Risk turns laws into pitfalls
    assert "domain_invariants" in risk
    assert "pitfall" in risk.lower()
    # neither sibling emits the law sections themselves (Domain/Product own them)
    assert "do NOT" in design.lower() or "Do NOT" in design

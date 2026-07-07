import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import renderer  # noqa: E402


def test_product_laws_moves_overridden_out_of_enforced():
    bp = {"domain_invariants": [
        {"id": "inv-001", "invariant": "email unique per run", "entity": "EmailRotation",
         "category": "workflow", "enforced_at": ["worker/main.py:764"]},
        {"id": "inv-003", "invariant": "cost is never stored", "entity": "BillableStep",
         "category": "billing", "enforced_at": ["worker/persister.py:1327"],
         "status": "overridden",
         "override": {"reason": "store cost — perf decision",
                      "authorized_by": "Gabor <g@e.com>", "ratified_from": "demo/x"}},
    ]}
    rule = renderer._build_product_laws_rule(bp)
    body = rule["body"]
    assert "Overridden — no longer enforced" in body
    assert "inv-003" in body and "store cost" in body and "Gabor" in body
    # the dead law must NOT appear in the enforced section
    enforced_part = body.split("Overridden — no longer enforced")[0]
    assert "cost is never stored" not in enforced_part
    assert "email unique per run" in enforced_part


def test_product_laws_marks_branch_staged_override():
    bp = {"domain_invariants": [
        {"id": "inv-003", "invariant": "cost is never stored", "entity": "BillableStep",
         "category": "billing", "status": "override_staged",
         "override": {"reason": "store cost", "authorized_by": "Gabor <g@e.com>",
                      "branch": "demo/x"}},
    ]}
    body = renderer._build_product_laws_rule(bp)["body"]
    assert "staged" in body.lower() and "demo/x" in body

import json
import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import invariant_specialist as isp  # noqa: E402

INV = {
    "id": "inv-bill-003",
    "invariant": "cost is recomputed from billable steps, never stored",
    "entity": "BillableStep",
    "category": "billing",
    "enforced_at": ["new_worker/lib/supabase/supabase_client.py:1058"],
}
DIFF = "diff --git a/new_worker/main.py b/new_worker/main.py\n+    return stored_cost\n"


# ---- contract (pure data) ----
def test_contract_of_reads_guarantee_and_anchors():
    c = isp.contract_of(INV)
    assert c["id"] == "inv-bill-003"
    assert "recomputed" in c["guarantee"]
    assert c["anchors"] == ["new_worker/lib/supabase/supabase_client.py:1058"]


# ---- tracer prompt/parse ----
def test_tracer_prompt_grounds_on_contract_and_consumer_behavior():
    p = isp.build_tracer_prompt(isp.contract_of(INV), DIFF)
    assert "TRACER" in p and "inv-bill-003" in p
    assert "consumer-visible" in p and "under_proven" in p
    assert "supabase_client.py:1058" in p  # anchor surfaced
    assert DIFF.strip().splitlines()[-1] in p


def test_parse_tracer_defaults_and_missing_id():
    assert isp.parse_tracer("garbage") == {}
    t = isp.parse_tracer(json.dumps({"invariant_id": "x", "verdict": "VIOLATED"}))
    assert t["verdict"] == "violated"  # lowercased
    # missing verdict -> under_proven (never assume safe)
    assert isp.parse_tracer(json.dumps({"invariant_id": "x"}))["verdict"] == "under_proven"


# ---- challenger prompt/parse ----
def test_challenger_prompt_asks_to_rebut():
    p = isp.build_challenger_prompt(isp.contract_of(INV), {"verdict": "violated", "trace": "w->c", "evidence": []}, DIFF)
    assert "CHALLENGER" in p and "REBUT" in p
    assert "intermediate state" in p and "unreachable" in p


def test_parse_challenger_reject_default():
    assert isp.parse_challenger("nope") == {}
    c = isp.parse_challenger(json.dumps({"invariant_id": "x", "decision": "CONFIRM_VIOLATION",
                                         "final_verdict": "violated"}))
    assert c["decision"] == "confirm_violation" and c["final_verdict"] == "violated"


# ---- orchestration: contract -> tracer -> challenger ----
class _Recorder:
    def __init__(self, tracer_out, challenger_out):
        self.tracer_out, self.challenger_out = tracer_out, challenger_out
        self.calls = []  # (role, model)

    def __call__(self, prompt, root, verifier, model="haiku", **kw):
        role = "tracer" if "TRACER" in prompt and "CHALLENGER" not in prompt else "challenger"
        self.calls.append((role, model))
        return self.tracer_out if role == "tracer" else self.challenger_out


def test_tracer_upheld_short_circuits_no_challenge_no_finding():
    rec = _Recorder(json.dumps({"invariant_id": "inv-bill-003", "verdict": "upheld"}), "{}")
    out = isp.review_invariants(".", DIFF, [INV], run=rec)
    assert out == []
    assert [c[0] for c in rec.calls] == ["tracer"]           # challenger never ran
    assert rec.calls[0][1] == isp.TRACER_MODEL               # tracer used sonnet


def test_challenger_veto_drops_the_finding():
    tracer = json.dumps({"invariant_id": "inv-bill-003", "verdict": "violated", "file": "new_worker/main.py", "line": 2})
    challenger = json.dumps({"invariant_id": "inv-bill-003", "decision": "reject", "final_verdict": "upheld",
                             "reason": "stops at intermediate state"})
    rec = _Recorder(tracer, challenger)
    out = isp.review_invariants(".", DIFF, [INV], run=rec)
    assert out == []                                          # veto works — the point of the loop
    assert [c[0] for c in rec.calls] == ["tracer", "challenger"]
    assert rec.calls[1][1] == isp.CHALLENGER_MODEL            # challenger used opus


def test_confirmed_violation_becomes_a_finding():
    tracer = json.dumps({"invariant_id": "inv-bill-003", "verdict": "violated",
                         "trace": "write stored_cost -> returned to client", "file": "new_worker/main.py",
                         "line": 2, "evidence": ["returns stored_cost"], "confidence": 0.8})
    challenger = json.dumps({"invariant_id": "inv-bill-003", "decision": "confirm_violation",
                             "final_verdict": "violated", "reason": "consumer sees the stored value",
                             "falsification": "show the value is recomputed", "file": "new_worker/main.py",
                             "line": 2, "confidence": 0.9})
    out = isp.review_invariants(".", DIFF, [INV], run=_Recorder(tracer, challenger))
    assert len(out) == 1
    f = out[0]
    assert f["kind"] == "conformance_break" and f["edge"] == "B"
    assert f["source"] == "invariant_specialist:ctc"
    assert f["anchor"]["file"] == "new_worker/main.py" and f["anchor"]["line"] == 2
    assert f["falsification"] and f["confidence"] >= 0.6


def test_confirmed_but_no_falsification_is_dropped():
    tracer = json.dumps({"invariant_id": "inv-bill-003", "verdict": "violated"})
    challenger = json.dumps({"invariant_id": "inv-bill-003", "decision": "confirm_violation",
                             "final_verdict": "violated"})  # no falsification
    assert isp.review_invariants(".", DIFF, [INV], run=_Recorder(tracer, challenger)) == []


def test_tracer_and_challenger_request_tools():
    tracer = json.dumps({"invariant_id": "inv-x", "verdict": "violated",
                         "file": "a.py", "line": 2})
    challenger = json.dumps({"invariant_id": "inv-x", "decision": "confirm_violation",
                             "final_verdict": "violated", "reason": "r",
                             "falsification": "f", "file": "a.py", "line": 2})
    seen = []

    def rec(prompt, root, verifier, model="haiku", tools=False, **kw):
        seen.append(tools)
        return tracer if "TRACER" in prompt and "CHALLENGER" not in prompt else challenger

    isp.review_invariants(".", DIFF, [INV], run=rec)
    assert seen == [True, True]   # both roles asked for tools

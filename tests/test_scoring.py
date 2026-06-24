"""Tests for the Architecture Integrity Score composite (archie/standalone/scoring.py).

The composite blends four headline axes — Reconciliation, Product-Law Coverage,
Findings Burndown, Freshness — as a weighted arithmetic body, capped by a weighted
geometric mean over the two correctness axes {Reconciliation, Coverage}. The cap is
what makes a broken/blind contract drag the headline down natively, with no
hand-tuned floor/drag constant.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# scoring.py is a standalone (zero-dependency, 3.9+) module — import it as a
# sibling, the same way the standalone scripts import each other, so the test
# doesn't drag in the heavy `archie` package __init__ chain.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))
from scoring import composite, grade  # noqa: E402


def test_geometric_ceiling_caps_a_broken_contract_below_the_body():
    # Reconciliation low (open divergences nobody reconciled); other axes high.
    # The arithmetic body alone would be generous (~67), but the geometric
    # ceiling over {Reconciliation, Coverage} must cap the headline so a broken
    # contract cannot hide behind tidy code.
    r = composite(reconciliation=40, coverage=85, burndown=95, freshness=95)
    assert r["body"] == pytest.approx(67.25, abs=0.05)
    assert r["ceiling"] == pytest.approx(54.07, abs=0.1)
    assert r["ais"] == pytest.approx(54.1, abs=0.1)
    assert r["ais"] < r["body"]  # the ceiling bit
    assert r["grade"] == "C"


def test_unmeasured_coverage_neither_penalizes_the_body_nor_inflates_the_ceiling():
    # Laws were sought but none found (or there are none to find). Coverage must
    # drop out of BOTH terms: it must not tank the body as a 0, and it must not
    # inflate the ceiling as a free 100. Body renormalizes over {R, B, F};
    # ceiling is computed over Reconciliation alone.
    r = composite(reconciliation=80, coverage=0, burndown=90, freshness=90,
                  coverage_measured=False)
    expected_body = (0.45 * 80 + 0.20 * 90 + 0.05 * 90) / (0.45 + 0.20 + 0.05)
    assert r["body"] == pytest.approx(expected_body, abs=0.05)  # ~83.6, not 58.5
    assert r["ceiling"] == pytest.approx(80.0, abs=0.1)         # R alone, not 100
    assert r["ais"] == pytest.approx(min(expected_body, 80.0), abs=0.1)


def test_healthy_repo_scores_high_and_the_ceiling_does_not_bite():
    # Strong on every axis -> the legible arithmetic body is the answer; the
    # correctness ceiling sits above it and does not cap.
    r = composite(reconciliation=95, coverage=90, burndown=90, freshness=95)
    assert r["body"] == pytest.approx(92.5, abs=0.05)
    assert r["ais"] == pytest.approx(92.5, abs=0.1)
    assert r["ais"] == pytest.approx(r["body"], abs=0.1)  # ceiling did not bite
    assert r["grade"] == "A"


def test_unenforced_laws_cap_the_headline():
    # Reconciliation is high but most product laws are unguarded -> the ceiling
    # over {R, Coverage} caps the headline below the arithmetic body.
    r = composite(reconciliation=95, coverage=30, burndown=90, freshness=90)
    assert r["body"] == pytest.approx(74.25, abs=0.05)
    assert r["ais"] == pytest.approx(59.9, abs=0.1)
    assert r["ais"] < r["body"]
    assert r["grade"] == "C"


def test_a_perfect_repo_scores_100():
    r = composite(reconciliation=100, coverage=100, burndown=100, freshness=100)
    assert r["ais"] == 100.0
    assert r["grade"] == "A"


def test_score_is_deterministic_for_identical_inputs():
    a = composite(reconciliation=73, coverage=61, burndown=88, freshness=92)
    b = composite(reconciliation=73, coverage=61, burndown=88, freshness=92)
    assert a == b  # byte-identical dict, no wall-clock / randomness


def test_grade_boundaries():
    assert grade(100) == "A"
    assert grade(90) == "A"
    assert grade(89.9) == "B"
    assert grade(75) == "B"
    assert grade(74.9) == "C"
    assert grade(50) == "C"
    assert grade(49.9) == "D"
    assert grade(25) == "D"
    assert grade(24.9) == "F"
    assert grade(0) == "F"


def test_lowering_reconciliation_never_raises_the_score():
    # Open divergences (lower Reconciliation) must not be able to improve AIS.
    high = composite(reconciliation=90, coverage=70, burndown=80, freshness=90)
    low = composite(reconciliation=40, coverage=70, burndown=80, freshness=90)
    assert low["ais"] <= high["ais"]


# ── axis derivations from parsed artifacts ────────────────────────────────────
from scoring import derive_coverage, derive_reconciliation, derive_burndown  # noqa: E402


def test_coverage_is_unmeasured_when_there_are_no_laws():
    # A repo with no product laws -> Coverage is unmeasured (not a free 100).
    cov, measured = derive_coverage({"domain_invariants": [], "derived_invariants": [],
                                     "unenforced_invariants": []})
    assert measured is False
    cov2, measured2 = derive_coverage({})  # no blueprint keys at all
    assert measured2 is False


def test_coverage_counts_enforced_over_total_identified_laws():
    bp = {
        "domain_invariants": [
            {"id": "balance-non-negative", "enforced_at": "ledger.kt:120"},
            {"id": "issued-immutable", "enforced_at": "orders.kt:44"},
        ],
        "derived_invariants": [
            {"id": "credit-not-reducible", "enforced_at": "credit.kt:88"},
        ],
        # unenforced laws count toward the denominator only (advertise the gap)
        "unenforced_invariants": [{"id": "tenant-isolation"}],
    }
    cov, measured = derive_coverage(bp)
    assert measured is True
    assert cov == pytest.approx(75.0, abs=0.1)  # 3 enforced of 4 total


def test_reconciliation_is_100_with_no_open_violations():
    assert derive_reconciliation([], kloc=5.0) == 100.0


def test_reconciliation_drops_with_open_violations_and_is_size_normalized():
    errors = [{"severity": "error"}] * 4
    small = derive_reconciliation(errors, kloc=2.0)
    big = derive_reconciliation(errors, kloc=20.0)
    assert small < 100.0
    assert big > small          # same violations, larger repo -> less dense -> higher score
    assert big < 100.0


def test_burndown_is_100_with_no_open_findings_and_drops_with_findings():
    assert derive_burndown([], kloc=5.0) == 100.0
    some = derive_burndown([{"severity": "warning"}] * 6, kloc=5.0)
    assert some < 100.0


# ── end-to-end integration against the demo fixture ──────────────────────────
from score import compute_integrity  # noqa: E402


def test_compute_integrity_on_the_demo_fixture():
    repo = Path(__file__).resolve().parent / "fixtures" / "ais_demo"
    r = compute_integrity(repo)
    assert r["has_baseline"] is True
    assert r["open_divergences"] == 1
    assert r["worklist"][0]["file"] == "src/handlers/order.py"
    assert r["worklist"][0]["kind"] == "decision"
    assert r["coverage_measured"] is True
    assert r["protected_laws"] == {"enforced": 3, "total": 4,
                                   "unguarded": ["tenant-scoped-queries"]}
    assert r["grade"] == "B"
    assert 74.0 <= r["ais"] <= 80.0


def test_accepting_a_divergence_clears_it_from_the_worklist(tmp_path):
    # Copy the fixture and add a staged amendment keyed by the rule_id -> the
    # open divergence becomes Accepted and drops out of Reconciliation.
    import shutil
    src = Path(__file__).resolve().parent / "fixtures" / "ais_demo"
    dst = tmp_path / "repo"
    shutil.copytree(src, dst)
    (dst / ".archie" / "changes").mkdir(parents=True, exist_ok=True)
    (dst / ".archie" / "changes" / "0001.json").write_text(
        '{"claims": [{"rule_id": "no-raw-sql-in-handlers", '
        '"rationale": "legacy reporting path, migrating next sprint"}]}'
    )
    r = compute_integrity(dst)
    assert r["open_divergences"] == 0          # accepted -> not open
    assert r["axes"]["reconciliation"] == 100.0


def test_a_repo_with_no_contract_is_unmeasurable_not_a_perfect_100(tmp_path):
    # No .archie/, no rules, no laws -> nothing to measure against. AIS must be
    # "n/a", never a free 100 (absence != perfect — the empty-repo trap).
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("def f():\n    return 1\n")
    r = compute_integrity(tmp_path)
    assert r["measurable"] is False
    assert r["ais"] is None


# ── diff-scoping (the PR gate) ───────────────────────────────────────────────
from score import filter_to_changed, gate_verdict, is_grounded  # noqa: E402


def test_filter_to_changed_keeps_only_divergences_in_changed_files():
    wl = [{"file": "a.py", "severity": "error"}, {"file": "b.py", "severity": "error"}]
    assert filter_to_changed(wl, ["a.py"]) == [{"file": "a.py", "severity": "error"}]
    assert filter_to_changed(wl, ["c.py"]) == []  # PR touched an unrelated file


def test_gate_blocks_only_on_grounded_divergences_in_the_diff():
    assert is_grounded("error") is True
    assert is_grounded("warning") is False
    assert gate_verdict([{"file": "a.py", "severity": "error"}])["blocked"] is True
    assert gate_verdict([{"file": "a.py", "severity": "warning"}])["blocked"] is False
    assert gate_verdict([])["blocked"] is False  # clean PR -> pass


# ── the explanation layer (context, not just a number) ───────────────────────
from score import explain  # noqa: E402


def test_explanation_says_what_ais_is_and_what_to_do():
    repo = Path(__file__).resolve().parent / "fixtures" / "ais_demo"
    ex = explain(compute_integrity(repo))
    assert "contract" in ex["what"].lower()              # explains what AIS measures
    assert "fix" in ex["action"].lower() and "accept" in ex["action"].lower()
    assert isinstance(ex["legend"], list) and ex["legend"]


def test_explanation_state_is_capped_when_the_ceiling_bites():
    # The demo: body 80.2 > ceiling 76.73 -> correctness axes cap the headline.
    repo = Path(__file__).resolve().parent / "fixtures" / "ais_demo"
    ex = explain(compute_integrity(repo))
    assert ex["state"] == "capped"
    assert "law" in ex["why"].lower() or "diverg" in ex["why"].lower()


def test_explanation_state_is_no_contract_for_a_bare_repo(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    ex = explain(compute_integrity(tmp_path))
    assert ex["state"] == "no_contract"
    assert "deep-scan" in ex["why"].lower()


# ── baseline persistence (what /archie-deep-scan Step 9 writes) ──────────────
from score import write_baseline  # noqa: E402


def test_write_baseline_persists_score_json_and_history(tmp_path):
    import shutil, json as _json
    src = Path(__file__).resolve().parent / "fixtures" / "ais_demo"
    dst = tmp_path / "repo"
    shutil.copytree(src, dst)
    r = compute_integrity(dst)
    write_baseline(dst, r)
    sj = _json.loads((dst / ".archie" / "score.json").read_text())
    assert sj["ais"] == r["ais"]
    assert sj["score_version"]
    assert "explanation" in sj           # the context travels with the baseline
    hist = _json.loads((dst / ".archie" / "score_history.json").read_text())
    assert isinstance(hist, list) and hist and hist[-1]["ais"] == r["ais"]


# ── calibration-gated blocking (only proven-precise rules may block) ──────────
def test_gate_demotes_a_grounded_violation_whose_rule_failed_calibration():
    wl = [{"file": "a.py", "line": 1, "severity": "error", "rule_id": "jumpy"}]
    # no calibration data -> legacy behavior: a grounded violation blocks
    assert gate_verdict(wl)["blocked"] is True
    # calibration says the rule is too jumpy -> demote to advisory, do NOT block
    cal = {"jumpy": {"block_eligible": False}}
    v = gate_verdict(wl, calibration=cal)
    assert v["blocked"] is False
    assert len(v["advisory"]) == 1


def test_gate_blocks_a_grounded_violation_whose_rule_passed_calibration():
    wl = [{"file": "a.py", "line": 1, "severity": "error", "rule_id": "precise"}]
    cal = {"precise": {"block_eligible": True}}
    assert gate_verdict(wl, calibration=cal)["blocked"] is True

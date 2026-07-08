import json
import subprocess
import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import contract_delta as cd  # noqa: E402
import overrides as ov  # noqa: E402


def _project(tmp_path):
    subprocess.run(["git", "init", "-q", "-b", "demo/x", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Gabor Bakos"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "g@e.com"], check=True)
    (tmp_path / ".archie").mkdir()
    (tmp_path / ".archie" / "rules.json").write_text(json.dumps({"rules": [
        {"id": "inv-003", "description": "Run cost must never be stored",
         "forced_by": "Domain law inv-subscribe-workflow-003: ledger is the truth."},
    ]}))


# ---- retirements ----
def test_retirements_use_the_law_snapshot(tmp_path):
    _project(tmp_path)
    ov.ack(tmp_path, "inv-003", "dashboard reads total_cost",
           law="Run cost must never be stored")
    (tmp_path / ".archie" / "rules.json").write_text(json.dumps({"rules": []}))  # rule now gone
    out = cd.retirements(tmp_path)
    assert len(out) == 1
    c = out[0]
    assert c["law"] == "Run cost must never be stored"     # snapshot, not a live lookup
    assert c["reason"] == "dashboard reads total_cost"
    assert c["authorized_by"] == "Gabor Bakos <g@e.com>"
    assert len(c["date"]) == 10
    assert c["invariant_ids"] == []      # forced_by is gone with the rule; snapshot only


def test_retirements_fall_back_to_rules_json_for_legacy_entries(tmp_path):
    _project(tmp_path)
    ov.ack(tmp_path, "inv-003", "r")                        # no law snapshot
    out = cd.retirements(tmp_path)
    assert out[0]["law"] == "Run cost must never be stored"  # read from the live rule
    assert out[0]["invariant_ids"] == ["inv-subscribe-workflow-003"]


def test_acked_rule_ids_includes_aliases(tmp_path):
    _project(tmp_path)
    ov.ack(tmp_path, "inv-003", "r")
    assert cd.acked_rule_ids(tmp_path) == {"inv-003", "inv-subscribe-workflow-003"}


def test_missing_files_degrade_to_empty(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    assert cd.retirements(tmp_path) == []
    assert cd.acked_rule_ids(tmp_path) == set()


# ---- is_authorized ----
def test_authorized_rule_removal_is_explained():
    item = {"diff_op": "remove", "base_item": {"id": "inv-003"}, "branch_item": None}
    assert cd.is_authorized(item, {"inv-003"}) is True


def test_authorized_blueprint_stamp_is_explained():
    item = {"diff_op": "update", "base_item": {"id": "inv-subscribe-workflow-003"},
            "branch_item": {"id": "inv-subscribe-workflow-003"},
            "fields_changed": ["status", "override"]}
    assert cd.is_authorized(item, {"inv-subscribe-workflow-003"}) is True


def test_unauthorized_removal_is_not_explained():
    item = {"diff_op": "remove", "base_item": {"id": "inv-004"}, "branch_item": None}
    assert cd.is_authorized(item, {"inv-003"}) is False


def test_substantive_edit_to_an_acked_invariant_is_not_explained():
    """An override retires a law — it does not licence rewriting its text."""
    item = {"diff_op": "update", "base_item": {"id": "inv-003"},
            "branch_item": {"id": "inv-003"}, "fields_changed": ["status", "invariant"]}
    assert cd.is_authorized(item, {"inv-003"}) is False


def test_add_is_never_explained_by_an_override():
    item = {"diff_op": "add", "base_item": None, "branch_item": {"id": "inv-003"}}
    assert cd.is_authorized(item, {"inv-003"}) is False


# ---- judged_changes ----
def _stub_ir(monkeypatch, items):
    import intent_review as ir
    monkeypatch.setattr(ir, "load_branch_file", lambda *a: (True, {}, None))
    monkeypatch.setattr(ir, "fetch_base_file", lambda *a: (True, {}, None))
    monkeypatch.setattr(ir, "glob_ledger", lambda *a: [])
    monkeypatch.setattr(ir, "build_changed_items", lambda *a: items)
    monkeypatch.setattr(ir, "retained_rules", lambda *a: [])
    monkeypatch.setattr(ir, "build_prompt", lambda *a: ("sys", "usr"))
    return ir


def test_only_authorized_changes_makes_no_model_call(tmp_path, monkeypatch):
    _project(tmp_path)
    ov.ack(tmp_path, "inv-003", "r")
    ir = _stub_ir(monkeypatch, [{"diff_op": "remove", "base_item": {"id": "inv-003"},
                                 "branch_item": None}])
    monkeypatch.setattr(ir, "call_anthropic",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not judge")))
    out = cd.judged_changes(tmp_path, "origin/main", "sk-test")
    assert out == {"items": [], "findings": [], "model_failed": False}


def test_unexplained_change_is_judged_once(tmp_path, monkeypatch):
    _project(tmp_path)
    ov.ack(tmp_path, "inv-003", "r")
    authorized = {"diff_op": "remove", "base_item": {"id": "inv-003"}, "branch_item": None}
    unexplained = {"diff_op": "update", "base_item": {"id": "inv-007"},
                   "branch_item": {"id": "inv-007"}, "fields_changed": ["description"]}
    calls = []
    ir = _stub_ir(monkeypatch, [authorized, unexplained])
    monkeypatch.setattr(ir, "call_anthropic", lambda s, u, k, **kw: calls.append(1) or [{}])
    monkeypatch.setattr(ir, "finalize_findings",
                        lambda mf, ci, cl: [{"type": "silent_weakening", "change_summary": "cap raised",
                                             "diff_op": "update", "layer": 1,
                                             "colliding_rules": ["inv-006"]}])
    out = cd.judged_changes(tmp_path, "origin/main", "sk-test")
    assert len(calls) == 1
    assert out["items"] == [unexplained]          # the authorized removal is filtered out
    assert out["findings"][0]["type"] == "silent_weakening"
    assert out["model_failed"] is False


def test_model_failure_is_disclosed_not_swallowed(tmp_path, monkeypatch):
    _project(tmp_path)
    ir = _stub_ir(monkeypatch, [{"diff_op": "add", "base_item": None,
                                 "branch_item": {"id": "new-1"}}])
    monkeypatch.setattr(ir, "call_anthropic",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("429")))
    out = cd.judged_changes(tmp_path, "origin/main", "sk-test")
    assert out["model_failed"] is True and out["findings"] == []
    assert out["items"]                            # the deterministic diff still surfaces


def test_no_api_key_marks_model_failed(tmp_path, monkeypatch):
    _project(tmp_path)
    _stub_ir(monkeypatch, [{"diff_op": "add", "base_item": None, "branch_item": {"id": "n"}}])
    out = cd.judged_changes(tmp_path, "origin/main", "")
    assert out["model_failed"] is True             # a diff we could not judge is NOT clean


def test_unresolvable_base_ref_degrades(tmp_path, monkeypatch):
    import intent_review as ir
    monkeypatch.setattr(ir, "load_branch_file", lambda *a: (True, {}, None))
    monkeypatch.setattr(ir, "fetch_base_file", lambda *a: (False, None, "bad object"))
    out = cd.judged_changes(tmp_path, "origin/nope", "sk-test")
    assert out == {"items": [], "findings": [], "model_failed": False}


# ---- real-data regressions (caught by validating against SubscriberAgent PR #17) ----
def test_is_authorized_matches_the_differs_uppercase_diff_op():
    """intent_review.keyed_diff emits REMOVE / UPDATE / ADD, not lowercase."""
    assert cd.is_authorized(
        {"diff_op": "REMOVE", "base_item": {"id": "inv-003"}, "branch_item": None},
        {"inv-003"}) is True
    assert cd.is_authorized(
        {"diff_op": "UPDATE", "base_item": {"id": "inv-x"}, "branch_item": {"id": "inv-x"},
         "fields_changed": ["override", "status"]}, {"inv-x"}) is True
    assert cd.is_authorized(
        {"diff_op": "ADD", "base_item": None, "branch_item": {"id": "inv-003"}},
        {"inv-003"}) is False


def test_acked_rule_ids_survive_the_rule_being_removed(tmp_path):
    """override-ack removes the rule, so rule_aliases() can no longer read its
    forced_by. The aliases must be snapshotted into the entry at ack time, or the
    blueprint stamp for inv-subscribe-workflow-003 looks UNAUTHORIZED."""
    _project(tmp_path)
    ov.ack(tmp_path, "inv-003", "r", law="Run cost must never be stored",
           invariant_ids=["inv-subscribe-workflow-003"])
    (tmp_path / ".archie" / "rules.json").write_text(json.dumps({"rules": []}))  # rule gone
    assert cd.retirements(tmp_path)[0]["invariant_ids"] == ["inv-subscribe-workflow-003"]
    assert cd.acked_rule_ids(tmp_path) == {"inv-003", "inv-subscribe-workflow-003"}
    # ...so the blueprint stamp is explained
    stamp = {"diff_op": "UPDATE", "base_item": {"id": "inv-subscribe-workflow-003"},
             "branch_item": {"id": "inv-subscribe-workflow-003"},
             "fields_changed": ["override", "status"]}
    assert cd.is_authorized(stamp, cd.acked_rule_ids(tmp_path)) is True

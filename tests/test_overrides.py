import json
import subprocess
import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import overrides as ov  # noqa: E402


def _git_repo(tmp_path, branch="feature/x"):
    subprocess.run(["git", "init", "-q", "-b", branch, str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@example.com"], check=True)
    (tmp_path / ".archie").mkdir()


def test_ack_writes_entry_with_git_identity_and_is_idempotent(tmp_path):
    _git_repo(tmp_path)
    e1 = ov.ack(tmp_path, "inv-003", "store cost — perf decision")
    assert e1["rule_id"] == "inv-003" and e1["status"] == "acked"
    assert e1["branch"] == "feature/x"
    assert e1["authorized_by"] == "Test User <t@example.com>"
    assert e1["created_at"].endswith("Z")
    e2 = ov.ack(tmp_path, "inv-003", "different words")   # same rule+branch
    data = ov.load(tmp_path)
    assert len(data["overrides"]) == 1                     # idempotent
    assert e2["reason"] == e1["reason"]                    # first ruling kept


def test_load_corrupt_file_degrades_to_empty(tmp_path):
    _git_repo(tmp_path)
    (tmp_path / ".archie" / "overrides.json").write_text("{not json")
    assert ov.load(tmp_path) == {"version": 1, "overrides": []}


def test_active_maps_rule_ids(tmp_path):
    _git_repo(tmp_path)
    ov.ack(tmp_path, "inv-003", "r1")
    ov.ack(tmp_path, "trd-002", "r2")
    act = ov.active(tmp_path)
    assert set(act) == {"inv-003", "trd-002"}


def test_finding_matches_by_id_statement_and_assumptions():
    assert ov.finding_matches({"id": "f_inv_inv-003"}, "inv-003")
    assert ov.finding_matches({"problem_statement": "violates inv-003: cost stored"}, "inv-003")
    assert ov.finding_matches({"assumptions": ["invariant inv-003", "trace: x"]}, "inv-003")
    assert not ov.finding_matches({"id": "f_x", "problem_statement": "null deref"}, "inv-003")
    assert not ov.finding_matches({"problem_statement": "anything"}, "")
    # boundary-match regression: a short/crafted rule_id must not absorb-everything
    # via raw substring, and a partial id (inv-003 inside inv-0031) must not match.
    assert not ov.finding_matches({"problem_statement": "null deref"}, "e")
    assert not ov.finding_matches({"problem_statement": "violates inv-0031"}, "inv-003")


def test_partition_splits_unacked_acked_stale(tmp_path):
    _git_repo(tmp_path)
    e3 = ov.ack(tmp_path, "inv-003", "r")
    e9 = ov.ack(tmp_path, "inv-999", "never observed")
    act = ov.active(tmp_path)
    findings = [
        {"id": "f_inv_inv-003", "kind": "conformance_break"},
        {"id": "f_b1", "kind": "behavioral_break", "problem_statement": "null deref"},
    ]
    unacked, acked, stale = ov.partition(findings, act)
    assert [f["id"] for f in unacked] == ["f_b1"]
    assert len(acked) == 1 and acked[0][0]["rule_id"] == "inv-003"
    assert [f["id"] for f in acked[0][1]] == ["f_inv_inv-003"]
    assert [e["rule_id"] for e in stale] == ["inv-999"]


def test_partition_joins_ack_to_blueprint_invariant_alias(tmp_path):
    # Regression (SubscriberAgent PR #17, Run 3): acks are recorded under SHORT
    # rule ids (inv-003) but invariant-specialist findings reference the LONG
    # blueprint invariant id (inv-subscribe-workflow-003) — nothing joined, so
    # the violation counted as a break AND the ack rendered stale. The rule's
    # forced_by citation provides the alias.
    _git_repo(tmp_path)
    (tmp_path / ".archie" / "rules.json").write_text(json.dumps({"rules": [
        {"id": "inv-003", "kind": "domain_invariant",
         "description": "Run cost must never be stored",
         "forced_by": "Domain law inv-subscribe-workflow-003: the billable_steps "
                      "table is the single source of truth."},
    ]}))
    ov.ack(tmp_path, "inv-003", "store cost — authorized")
    act = ov.active(tmp_path)
    findings = [
        {"id": "f_inv_inv-subscribe-workflow-003", "kind": "conformance_break",
         "problem_statement": "violates inv-subscribe-workflow-003: cost stored"},
        {"id": "f_b1", "kind": "behavioral_break", "problem_statement": "null deref"},
    ]
    unacked, acked, stale = ov.partition(findings, act, root=tmp_path)
    assert [f["id"] for f in unacked] == ["f_b1"]      # real break survives
    assert acked and acked[0][0]["rule_id"] == "inv-003"
    assert stale == []                                  # ack matched its violation


def test_partition_without_root_keeps_old_behavior(tmp_path):
    _git_repo(tmp_path)
    ov.ack(tmp_path, "inv-003", "r")
    act = ov.active(tmp_path)
    findings = [{"id": "f_inv_inv-003", "kind": "conformance_break",
                 "problem_statement": "violates inv-003"}]
    unacked, acked, stale = ov.partition(findings, act)
    assert unacked == [] and acked and stale == []


def test_editor_gate_dedup_key_survives_list_anchor():
    # Model-shaped data: an API-path reviewer returned anchor.file as a LIST —
    # the dedup set raised unhashable-type and the gate discarded EVERY finding.
    import editor_gate
    f = {"id": "f1", "kind": "behavioral_break",
         "problem_statement": "x", "anchor": {"file": ["a.py", "b.py"], "line": [1, 2]},
         "assumptions": [], "evidence": ["e"], "falsification": "f", "confidence": 0.9}
    k1 = editor_gate._dupe_key(f)
    k2 = editor_gate._dupe_key(dict(f))
    assert k1 == k2
    assert len({k1, k2}) == 1        # hashable + stable


def test_gate_end_to_end_survives_list_shaped_finding():
    # Attempt-3 regression: the list survived past dedup into floors.get(kind),
    # changed_lines.get(file) and line-in-set — every dict/set lookup in the
    # gate must see scalars. Normalization happens at the input boundary.
    import editor_gate
    f = {"id": "f1", "kind": ["behavioral_break", "perf"], "edge": "B",
         "problem_statement": "cache grows unbounded",
         "anchor": {"file": ["worker/lib/pool_cache.py", "worker/main.py"], "line": [22]},
         "assumptions": [], "evidence": ["e"], "falsification": "prove it",
         "confidence": 0.9}
    out = editor_gate.gate([f], [], changed_lines={"worker/lib/pool_cache.py": {22}},
                           floors={"behavioral_break": 0.0},
                           file_level_kinds={"behavioral_break"})
    assert len(out["confirmed"]) == 1
    c = out["confirmed"][0]
    assert c["kind"] == "behavioral_break"
    assert c["anchor"]["file"] == "worker/lib/pool_cache.py"
    assert c["id"] == "f1"                      # identity preserved


def test_ack_snapshots_the_law_text(tmp_path):
    _git_repo(tmp_path)
    e = ov.ack(tmp_path, "inv-003", "store cost", law="Run cost must never be stored")
    assert e["law"] == "Run cost must never be stored"
    assert ov.load(tmp_path)["overrides"][0]["law"] == "Run cost must never be stored"


def test_ack_without_law_defaults_to_empty(tmp_path):
    _git_repo(tmp_path)
    assert ov.ack(tmp_path, "inv-003", "r")["law"] == ""


def test_ratification_helpers_are_gone():
    """merging is the ratification — nothing applies an override after the fact."""
    assert not hasattr(ov, "pending_ratification")
    assert not hasattr(ov, "archive")

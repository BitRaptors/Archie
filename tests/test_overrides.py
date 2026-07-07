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


def test_pending_ratification_only_foreign_branch_entries(tmp_path):
    _git_repo(tmp_path, branch="develop")
    ov.ack(tmp_path, "inv-here", "on this branch")         # branch == develop
    data = ov.load(tmp_path)
    data["overrides"].append({"rule_id": "inv-003", "reason": "merged in",
                              "authorized_by": "X", "branch": "demo/other",
                              "created_at": "2026-07-07T00:00:00Z", "status": "acked"})
    ov.save(tmp_path, data)
    pend = ov.pending_ratification(tmp_path)
    assert [e["rule_id"] for e in pend] == ["inv-003"]


def test_archive_moves_entry_to_history(tmp_path):
    _git_repo(tmp_path)
    e = ov.ack(tmp_path, "inv-003", "r")
    ov.archive(tmp_path, e, status="ratified")
    assert ov.active(tmp_path) == {}
    hist = (tmp_path / ".archie" / "overrides_history.jsonl").read_text().strip().splitlines()
    rec = json.loads(hist[0])
    assert rec["rule_id"] == "inv-003" and rec["status"] == "ratified"
    assert rec["archived_at"].endswith("Z")


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

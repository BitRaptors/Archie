import json
import subprocess
import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import overrides as ov  # noqa: E402

SYNC = _STANDALONE / "sync.py"


def _git_repo(tmp_path, branch="feature/x"):
    subprocess.run(["git", "init", "-q", "-b", branch, str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@example.com"], check=True)
    (tmp_path / ".archie").mkdir()


def test_override_ack_cli_records_entry(tmp_path):
    _git_repo(tmp_path)
    r = subprocess.run([sys.executable, str(SYNC), "override-ack", str(tmp_path),
                        "inv-003", "--reason", "store cost — user authorized"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["acked"] == "inv-003"
    act = ov.active(tmp_path)
    assert act["inv-003"]["reason"] == "store cost — user authorized"


def test_override_ack_requires_rule_and_reason(tmp_path):
    _git_repo(tmp_path)
    r = subprocess.run([sys.executable, str(SYNC), "override-ack", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 1


def test_override_ratify_applies_contract_and_archives(tmp_path):
    _git_repo(tmp_path, branch="develop")           # entry below is from demo/x → pending
    (tmp_path / ".archie" / "rules.json").write_text(json.dumps({"rules": [
        {"id": "inv-003", "severity_class": "decision_violation", "description": "never store cost"},
        {"id": "arch-001", "severity_class": "pattern_divergence", "description": "keep"},
    ]}))
    (tmp_path / ".archie" / "blueprint.json").write_text(json.dumps({"domain_invariants": [
        {"id": "inv-003", "invariant": "cost is never stored", "entity": "BillableStep"},
        {"id": "inv-001", "invariant": "keep me", "entity": "AgentRun"},
    ]}))
    (tmp_path / ".archie" / "overrides.json").write_text(json.dumps({"version": 1, "overrides": [
        {"rule_id": "inv-003", "reason": "store cost", "authorized_by": "Gabor <g@e.com>",
         "branch": "demo/x", "created_at": "2026-07-07T00:00:00Z", "status": "acked"}]}))

    r = subprocess.run([sys.executable, str(SYNC), "override-ratify", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout.strip().splitlines()[-1]) == {"ratified": ["inv-003"]}

    rules = json.loads((tmp_path / ".archie" / "rules.json").read_text())["rules"]
    assert [x["id"] for x in rules] == ["arch-001"]              # retired
    bp = json.loads((tmp_path / ".archie" / "blueprint.json").read_text())
    inv3 = next(x for x in bp["domain_invariants"] if x["id"] == "inv-003")
    assert inv3["status"] == "overridden"
    assert inv3["override"]["authorized_by"] == "Gabor <g@e.com>"
    assert ov.active(tmp_path) == {}                             # archived
    hist = (tmp_path / ".archie" / "overrides_history.jsonl").read_text()
    assert "ratified" in hist

    # idempotent: second run is a no-op
    r2 = subprocess.run([sys.executable, str(SYNC), "override-ratify", str(tmp_path)],
                        capture_output=True, text=True)
    assert json.loads(r2.stdout.strip().splitlines()[-1]) == {"ratified": []}


def test_override_ratify_skips_current_branch_entries(tmp_path):
    _git_repo(tmp_path, branch="demo/x")            # entry authored HERE → still active
    (tmp_path / ".archie" / "overrides.json").write_text(json.dumps({"version": 1, "overrides": [
        {"rule_id": "inv-003", "reason": "r", "authorized_by": "G",
         "branch": "demo/x", "created_at": "t", "status": "acked"}]}))
    r = subprocess.run([sys.executable, str(SYNC), "override-ratify", str(tmp_path)],
                       capture_output=True, text=True)
    assert json.loads(r.stdout.strip().splitlines()[-1]) == {"ratified": []}
    assert "inv-003" in ov.active(tmp_path)

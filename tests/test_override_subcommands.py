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


def test_override_ack_removes_the_rule_and_stamps_the_blueprint(tmp_path):
    _git_repo(tmp_path)
    (tmp_path / ".archie" / "rules.json").write_text(json.dumps({"rules": [
        {"id": "inv-003", "description": "Run cost must never be stored",
         "forced_by": "Domain law inv-subscribe-workflow-003: ledger is the truth."},
        {"id": "arch-001", "description": "keep me"},
    ]}))
    (tmp_path / ".archie" / "blueprint.json").write_text(json.dumps({"domain_invariants": [
        {"id": "inv-subscribe-workflow-003", "invariant": "cost is never stored"},
        {"id": "inv-other", "invariant": "keep me"},
    ]}))
    r = subprocess.run([sys.executable, str(SYNC), "override-ack", str(tmp_path),
                        "inv-003", "--reason", "dashboard reads total_cost"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["acked"] == "inv-003" and out["rule_removed"] is True

    rules = json.loads((tmp_path / ".archie" / "rules.json").read_text())["rules"]
    assert [x["id"] for x in rules] == ["arch-001"]           # removed from the branch

    bp = json.loads((tmp_path / ".archie" / "blueprint.json").read_text())
    inv = next(x for x in bp["domain_invariants"] if x["id"] == "inv-subscribe-workflow-003")
    assert inv["status"] == "overridden"
    assert inv["override"]["reason"] == "dashboard reads total_cost"
    assert inv["override"]["authorized_by"]
    assert next(x for x in bp["domain_invariants"] if x["id"] == "inv-other").get("status") is None

    e = ov.active(tmp_path)["inv-003"]
    assert e["law"] == "Run cost must never be stored"        # snapshot survives removal
    assert e["reason"] == "dashboard reads total_cost"


def test_override_ack_is_idempotent_and_survives_missing_rule(tmp_path):
    _git_repo(tmp_path)
    (tmp_path / ".archie" / "rules.json").write_text(json.dumps({"rules": []}))
    r1 = subprocess.run([sys.executable, str(SYNC), "override-ack", str(tmp_path),
                         "ghost-9", "--reason", "not in rules.json"],
                        capture_output=True, text=True)
    assert r1.returncode == 0
    assert json.loads(r1.stdout.strip().splitlines()[-1])["rule_removed"] is False
    r2 = subprocess.run([sys.executable, str(SYNC), "override-ack", str(tmp_path),
                         "ghost-9", "--reason", "different words"],
                        capture_output=True, text=True)
    assert r2.returncode == 0
    assert len(ov.load(tmp_path)["overrides"]) == 1           # first ruling kept


def test_override_ratify_command_is_gone(tmp_path):
    _git_repo(tmp_path)
    r = subprocess.run([sys.executable, str(SYNC), "override-ratify", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode != 0                                   # unknown subcommand

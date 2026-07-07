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

import json
import subprocess
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "archie" / "assets" / "hook_scripts" / "pre-validate.sh"

RULES = {"rules": [{
    "id": "inv-003",
    "severity_class": "decision_violation",
    "description": "Run cost must never be stored",
    "why": "a stored cost can drift from the billable_steps ledger",
    "check": "forbidden_content",
    "applies_to": "",
    "forbidden_patterns": ["stored_cost"],
}]}


def _project(tmp_path):
    subprocess.run(["git", "init", "-q", "-b", "feature/x", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@e.com"], check=True)
    (tmp_path / ".archie").mkdir()
    (tmp_path / ".archie" / "rules.json").write_text(json.dumps(RULES))


def _run_hook(tmp_path, file_path, content):
    envelope = json.dumps({"tool_name": "Write",
                           "tool_input": {"file_path": str(file_path), "content": content}})
    return subprocess.run(["bash", str(HOOK)], input=envelope, capture_output=True,
                          text=True, cwd=str(tmp_path))


def test_block_footer_names_the_sanctioned_door(tmp_path):
    _project(tmp_path)
    r = _run_hook(tmp_path, tmp_path / "a.py", "stored_cost = 1")
    assert r.returncode == 2
    assert "BLOCKED" in r.stdout and "inv-003" in r.stdout
    assert "override-ack" in r.stdout            # the door is advertised
    assert "user" in r.stdout.lower()            # ...and gated on user authorization


def test_acked_override_demotes_block_to_warn(tmp_path):
    _project(tmp_path)
    (tmp_path / ".archie" / "overrides.json").write_text(json.dumps({
        "version": 1, "overrides": [{
            "rule_id": "inv-003", "reason": "store cost — authorized",
            "authorized_by": "Gabor <g@e.com>", "branch": "feature/x",
            "created_at": "2026-07-07T00:00:00Z", "status": "acked"}]}))
    r = _run_hook(tmp_path, tmp_path / "a.py", "stored_cost = 1")
    assert r.returncode == 0                     # no longer blocks
    assert "overridden" in r.stdout.lower()      # still visible
    assert "Gabor" in r.stdout


def test_write_to_overrides_file_is_exempt(tmp_path):
    _project(tmp_path)
    # content would trip the rule, but the target is the overrides file itself
    r = _run_hook(tmp_path, tmp_path / ".archie" / "overrides.json",
                  '{"overrides": [{"reason": "stored_cost"}]}')
    assert r.returncode == 0
    assert "BLOCKED" not in r.stdout


def test_nested_archie_overrides_is_not_exempt(tmp_path):
    _project(tmp_path)
    nested = tmp_path / "packages" / "api" / ".archie"
    nested.mkdir(parents=True)
    r = _run_hook(tmp_path, nested / "overrides.json", "stored_cost = 1")
    assert r.returncode == 2
    assert "BLOCKED" in r.stdout


def test_lookalike_archie_dir_is_not_exempt(tmp_path):
    _project(tmp_path)
    d = tmp_path / "notes.archie"
    d.mkdir()
    r = _run_hook(tmp_path, d / "overrides.json", "stored_cost = 1")
    assert r.returncode == 2
    assert "BLOCKED" in r.stdout

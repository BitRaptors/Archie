"""Regression test: Archie's internal claude -p spawns must never be stop-nudged.

In -p mode the model's reply to a Stop-hook nudge becomes the LAST assistant
message — which is exactly what --output-format json returns as `result`. On
any repo where churn had crossed, this silently REPLACED every reviewer's JSON
findings with prose like "I haven't done any work in this session yet...",
producing zero-finding reviews (SubscriberAgent PR #17).
"""
import json
import subprocess
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "archie" / "assets" / "hook_scripts" / "stop.sh"


def _project_with_crossed_churn(tmp_path):
    """A project whose stub sync.py always reports churn crossed → nudge fires."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".archie").mkdir()
    (tmp_path / ".archie" / "blueprint.json").write_text("{}")
    (tmp_path / ".archie" / "sync.py").write_text(
        "import json, sys\n"
        "cmd = sys.argv[1] if len(sys.argv) > 1 else ''\n"
        "if cmd == 'churn-status':\n"
        "    print(json.dumps({'crossed': True, 'files': 7, 'lines': 282}))\n"
        "elif cmd == 'plan-list':\n"
        "    print(json.dumps({'plans': []}))\n"
        "else:\n"
        "    print('{}')\n"
    )


def _run_stop(tmp_path, env_extra):
    import os
    env = dict(os.environ)
    env.pop("ARCHIE_INTERNAL", None)
    env.update(env_extra)
    return subprocess.run(["bash", str(HOOK)], input="{}", capture_output=True,
                          text=True, cwd=str(tmp_path), env=env, timeout=30)


def test_nudge_fires_for_normal_sessions(tmp_path):
    _project_with_crossed_churn(tmp_path)
    r = _run_stop(tmp_path, {})
    assert r.returncode == 2
    assert "archie-sync" in r.stderr.lower() or "sync" in r.stderr.lower()


def test_internal_spawns_are_never_nudged(tmp_path):
    _project_with_crossed_churn(tmp_path)
    r = _run_stop(tmp_path, {"ARCHIE_INTERNAL": "1"})
    assert r.returncode == 0
    assert r.stderr.strip() == ""

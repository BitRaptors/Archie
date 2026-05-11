"""Tests for the Archie local viewer sidecar."""
from __future__ import annotations

import json
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture
def project_with_blueprint(tmp_path: Path) -> Path:
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    (archie_dir / "blueprint.json").write_text(json.dumps({
        "meta": {"scan_count": 1},
        "components": {"components": [{"name": "x", "location": "src/x"}]},
    }))
    return tmp_path


def test_bundle_endpoint_returns_blueprint(project_with_blueprint: Path):
    from viewer import build_app
    port = _free_port()
    app = build_app(project_with_blueprint, port=port)
    server_thread = threading.Thread(target=app.serve_forever, daemon=True)
    server_thread.start()
    try:
        time.sleep(0.05)
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/bundle", timeout=2)
        body = json.loads(resp.read())
        assert "bundle" in body
        assert body["bundle"]["blueprint"]["components"]["components"][0]["name"] == "x"
    finally:
        app.shutdown()


def test_404_for_unknown_api_path(project_with_blueprint: Path, tmp_path: Path):
    # Create a fake dist/ so build_app accepts the project
    dist = project_with_blueprint / ".archie" / "viewer" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html>local</html>")
    from viewer import build_app
    port = _free_port()
    app = build_app(project_with_blueprint, port=port)
    threading.Thread(target=app.serve_forever, daemon=True).start()
    try:
        time.sleep(0.05)
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/nonexistent", timeout=2)
        assert exc.value.code == 404
    finally:
        app.shutdown()


def test_spa_fallback_serves_index_html(project_with_blueprint: Path):
    dist = project_with_blueprint / ".archie" / "viewer" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html>local</html>")
    from viewer import build_app
    port = _free_port()
    app = build_app(project_with_blueprint, port=port)
    threading.Thread(target=app.serve_forever, daemon=True).start()
    try:
        time.sleep(0.05)
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/local", timeout=2)
        assert b"<html>local</html>" in resp.read()
    finally:
        app.shutdown()


def test_api_only_skips_static(project_with_blueprint: Path):
    from viewer import build_app
    port = _free_port()
    app = build_app(project_with_blueprint, port=port, api_only=True)
    threading.Thread(target=app.serve_forever, daemon=True).start()
    try:
        time.sleep(0.05)
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
        assert exc.value.code == 404
        # Bundle endpoint still works
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/bundle", timeout=2)
        assert resp.status == 200
    finally:
        app.shutdown()


def test_main_exits_when_blueprint_missing(tmp_path: Path, capsys):
    from viewer import main
    rc = main([str(tmp_path)])
    assert rc == 1
    captured = capsys.readouterr()
    assert "blueprint.json not found" in captured.err


def test_generated_files_endpoint(project_with_blueprint: Path):
    (project_with_blueprint / "CLAUDE.md").write_text("# root claude")
    (project_with_blueprint / "AGENTS.md").write_text("# agents")
    rules = project_with_blueprint / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "enforcement.md").write_text("# enforcement")
    (rules / "topic-x.md").write_text("# topic x")
    from viewer import build_app
    port = _free_port()
    app = build_app(project_with_blueprint, port=port, api_only=True)
    threading.Thread(target=app.serve_forever, daemon=True).start()
    try:
        time.sleep(0.05)
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/generated-files", timeout=2)
        body = json.loads(resp.read())
        assert "CLAUDE.md" in body
        assert "AGENTS.md" in body
        assert ".claude/rules/enforcement.md" in body
        assert ".claude/rules/topic-x.md" in body
        assert body["CLAUDE.md"] == "# root claude"
    finally:
        app.shutdown()


def test_intent_layer_status_empty(project_with_blueprint: Path):
    from viewer import build_app
    port = _free_port()
    app = build_app(project_with_blueprint, port=port, api_only=True)
    threading.Thread(target=app.serve_forever, daemon=True).start()
    try:
        time.sleep(0.05)
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/intent-layer-status", timeout=2)
        body = json.loads(resp.read())
        assert body == {"exists": False, "count": 0}
    finally:
        app.shutdown()


def test_intent_layer_status_with_files(project_with_blueprint: Path):
    folder = project_with_blueprint / "src" / "x"
    folder.mkdir(parents=True)
    (folder / "CLAUDE.md").write_text("# x context")
    from viewer import build_app
    port = _free_port()
    app = build_app(project_with_blueprint, port=port, api_only=True)
    threading.Thread(target=app.serve_forever, daemon=True).start()
    try:
        time.sleep(0.05)
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/intent-layer-status", timeout=2)
        body = json.loads(resp.read())
        assert body == {"exists": True, "count": 1}
        resp2 = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/folder-claude-mds", timeout=2)
        body2 = json.loads(resp2.read())
        assert "src/x/CLAUDE.md" in body2
        assert body2["src/x/CLAUDE.md"] == "# x context"
    finally:
        app.shutdown()


def test_intent_layer_status_marker_only(project_with_blueprint: Path):
    state = project_with_blueprint / ".archie" / "intent_layer_state.json"
    state.write_text(json.dumps({"processed": ["src/foo"]}))
    from viewer import build_app
    port = _free_port()
    app = build_app(project_with_blueprint, port=port, api_only=True)
    threading.Thread(target=app.serve_forever, daemon=True).start()
    try:
        time.sleep(0.05)
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/intent-layer-status", timeout=2)
        body = json.loads(resp.read())
        assert body == {"exists": True, "count": 0}
    finally:
        app.shutdown()


def test_ignored_rules_endpoint(project_with_blueprint: Path):
    # Missing ignored_rules.json → empty list, no 404
    from viewer import build_app
    port = _free_port()
    app = build_app(project_with_blueprint, port=port, api_only=True)
    threading.Thread(target=app.serve_forever, daemon=True).start()
    try:
        time.sleep(0.05)
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ignored-rules", timeout=2)
        body = json.loads(resp.read())
        assert body == {"rules": []}
        # With a populated ignored_rules.json the endpoint surfaces the rules
        ignored_path = project_with_blueprint / ".archie" / "ignored_rules.json"
        ignored_path.write_text(json.dumps({"rules": [
            {"id": "ig1", "description": "old rule", "severity_class": "pattern_divergence"},
        ]}))
        resp2 = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ignored-rules", timeout=2)
        body2 = json.loads(resp2.read())
        assert body2["rules"][0]["id"] == "ig1"
    finally:
        app.shutdown()


@pytest.fixture
def project_with_rules(tmp_path: Path) -> Path:
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    (archie_dir / "blueprint.json").write_text(json.dumps({"meta": {}}))
    (archie_dir / "rules.json").write_text(json.dumps({"rules": [
        {"id": "r1", "description": "active", "severity_class": "pattern_divergence"},
    ]}))
    (archie_dir / "proposed_rules.json").write_text(json.dumps({"rules": [
        {"id": "p1", "description": "proposed", "severity_class": "pattern_divergence"},
    ]}))
    (archie_dir / "ignored_rules.json").write_text(json.dumps({"rules": [
        {"id": "i1", "description": "ignored", "severity_class": "pattern_divergence"},
    ]}))
    return tmp_path


def _post_rule(port: int, action: str, rule_id: str, patch: dict | None = None) -> int:
    body = {"action": action, "rule_id": rule_id}
    if patch is not None:
        body["patch"] = patch
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/rules",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=2)
        return resp.status
    except urllib.error.HTTPError as e:
        return e.code


def _start_rule_server(project: Path):
    from viewer import build_app
    port = _free_port()
    app = build_app(project, port=port, api_only=True)
    threading.Thread(target=app.serve_forever, daemon=True).start()
    time.sleep(0.05)
    return app, port


def _read_rules(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        return data.get("rules", [])
    return data if isinstance(data, list) else []


def test_rule_adopt_moves_proposed_to_active(project_with_rules: Path):
    app, port = _start_rule_server(project_with_rules)
    try:
        status = _post_rule(port, "adopt", "p1")
        assert status == 200
        active = _read_rules(project_with_rules / ".archie" / "rules.json")
        proposed = _read_rules(project_with_rules / ".archie" / "proposed_rules.json")
        assert any(r["id"] == "p1" and r.get("source") == "scan-adopted" for r in active)
        assert all(r["id"] != "p1" for r in proposed)
    finally:
        app.shutdown()


def test_rule_reject_moves_proposed_to_ignored(project_with_rules: Path):
    app, port = _start_rule_server(project_with_rules)
    try:
        status = _post_rule(port, "reject", "p1")
        assert status == 200
        proposed = _read_rules(project_with_rules / ".archie" / "proposed_rules.json")
        ignored = _read_rules(project_with_rules / ".archie" / "ignored_rules.json")
        assert all(r["id"] != "p1" for r in proposed)
        assert any(r["id"] == "p1" for r in ignored)
    finally:
        app.shutdown()


def test_rule_disable_moves_active_to_ignored(project_with_rules: Path):
    app, port = _start_rule_server(project_with_rules)
    try:
        status = _post_rule(port, "disable", "r1")
        assert status == 200
        active = _read_rules(project_with_rules / ".archie" / "rules.json")
        ignored = _read_rules(project_with_rules / ".archie" / "ignored_rules.json")
        assert all(r["id"] != "r1" for r in active)
        assert any(r["id"] == "r1" for r in ignored)
    finally:
        app.shutdown()


def test_rule_enable_moves_ignored_to_active(project_with_rules: Path):
    app, port = _start_rule_server(project_with_rules)
    try:
        status = _post_rule(port, "enable", "i1")
        assert status == 200
        active = _read_rules(project_with_rules / ".archie" / "rules.json")
        ignored = _read_rules(project_with_rules / ".archie" / "ignored_rules.json")
        assert any(r["id"] == "i1" for r in active)
        assert all(r["id"] != "i1" for r in ignored)
    finally:
        app.shutdown()


def test_rule_edit_patches_description(project_with_rules: Path):
    app, port = _start_rule_server(project_with_rules)
    try:
        status = _post_rule(port, "edit", "r1", patch={"description": "updated desc"})
        assert status == 200
        active = _read_rules(project_with_rules / ".archie" / "rules.json")
        ignored = _read_rules(project_with_rules / ".archie" / "ignored_rules.json")
        # Rule stayed in active (no file move)
        assert any(r["id"] == "r1" and r["description"] == "updated desc" for r in active)
        assert all(r["id"] != "r1" for r in ignored)
    finally:
        app.shutdown()


def test_rule_edit_with_invalid_severity_returns_400(project_with_rules: Path):
    app, port = _start_rule_server(project_with_rules)
    try:
        status = _post_rule(port, "edit", "r1", patch={"severity_class": "bogus_class"})
        assert status == 400
        # Description unchanged
        active = _read_rules(project_with_rules / ".archie" / "rules.json")
        assert any(r["id"] == "r1" and r["severity_class"] == "pattern_divergence" for r in active)
    finally:
        app.shutdown()


def test_rule_unknown_id_returns_409(project_with_rules: Path):
    app, port = _start_rule_server(project_with_rules)
    try:
        # Adopt a rule that doesn't exist in proposed
        status = _post_rule(port, "adopt", "does-not-exist")
        assert status == 409
    finally:
        app.shutdown()


def test_rule_unknown_action_returns_400(project_with_rules: Path):
    app, port = _start_rule_server(project_with_rules)
    try:
        status = _post_rule(port, "frobnicate", "r1")
        assert status == 400
    finally:
        app.shutdown()


def test_rule_invalid_json_body_returns_400(project_with_rules: Path):
    app, port = _start_rule_server(project_with_rules)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/rules",
            data=b"this is not json",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=2)
            assert False, "expected HTTPError"
        except urllib.error.HTTPError as e:
            assert e.code == 400
    finally:
        app.shutdown()


def test_reload_watcher_detects_py_change(tmp_path: Path, monkeypatch):
    """The watcher must trigger os.execv when a .py file's mtime changes."""
    import os as os_mod
    watch_dir = tmp_path / "scripts"
    watch_dir.mkdir()
    target = watch_dir / "viewer.py"
    target.write_text("print('v1')\n")

    fired = threading.Event()
    execv_calls: list[tuple] = []

    def fake_execv(path, argv):
        execv_calls.append((path, list(argv)))
        fired.set()
        # Park the watcher thread so it doesn't keep firing during teardown.
        time.sleep(60)

    monkeypatch.setattr(os_mod, "execv", fake_execv)

    from viewer import _start_reload_watcher
    _start_reload_watcher(watch_dir, poll_seconds=0.05)

    time.sleep(0.1)
    target.write_text("print('v2')\n")

    assert fired.wait(timeout=2.0), "watcher never called os.execv"
    path, argv = execv_calls[0]
    assert path == sys.executable
    assert argv[0] == sys.executable

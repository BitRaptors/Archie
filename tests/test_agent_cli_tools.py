import json
import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import agent_cli as ac  # noqa: E402


def test_tool_loop_reads_jailed_file_then_answers(tmp_path, monkeypatch):
    (tmp_path / "svc.py").write_text("line1\nline2\nSECRET_LOGIC\nline4\n")
    monkeypatch.setattr(ac.shutil, "which", lambda name: None)  # force API path
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    turns = {"n": 0}

    def fake_urlopen(req, timeout=0):
        turns["n"] += 1
        body = json.loads(req.data.decode())
        if turns["n"] == 1:
            payload = {"stop_reason": "tool_use", "content": [
                {"type": "tool_use", "id": "t1", "name": "read_file",
                 "input": {"path": "svc.py", "start_line": 1, "end_line": 4}}]}
        else:
            # confirm the tool result reached the model
            last = body["messages"][-1]["content"][0]["content"]
            assert "SECRET_LOGIC" in last
            payload = {"stop_reason": "end_turn",
                       "content": [{"type": "text", "text": "verified: found SECRET_LOGIC"}]}

        class R:
            def read(self_): return json.dumps(payload).encode()
            def __enter__(self_): return self_
            def __exit__(self_, *a): return False
        return R()

    monkeypatch.setattr(ac.urllib.request, "urlopen", fake_urlopen)
    out = ac.run_verifier("review this", tmp_path, "claude", tools=True)
    assert "SECRET_LOGIC" in out


def test_tool_loop_denies_path_escape(tmp_path, monkeypatch):
    monkeypatch.setattr(ac.shutil, "which", lambda name: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    def fake_urlopen(req, timeout=0):
        body = json.loads(req.data.decode())
        if body["messages"][-1]["role"] == "user" and isinstance(body["messages"][-1]["content"], str):
            payload = {"stop_reason": "tool_use", "content": [
                {"type": "tool_use", "id": "t1", "name": "read_file",
                 "input": {"path": "../../etc/passwd"}}]}
        else:
            last = body["messages"][-1]["content"][0]["content"]
            assert "denied" in last.lower() or "outside" in last.lower()
            payload = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "ok"}]}

        class R:
            def read(self_): return json.dumps(payload).encode()
            def __enter__(self_): return self_
            def __exit__(self_, *a): return False
        return R()

    monkeypatch.setattr(ac.urllib.request, "urlopen", fake_urlopen)
    out = ac.run_verifier("go", tmp_path, "claude", tools=True)
    assert out == "ok"

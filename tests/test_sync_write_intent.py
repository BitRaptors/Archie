import sys, json
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import sync  # noqa: E402
import intent as it  # noqa: E402


def test_write_intent_writes_committed_file(tmp_path):
    payload = tmp_path / "spec.json"
    payload.write_text(json.dumps({"source": "sync", "goals": ["G"],
        "acceptance_criteria": [{"id": "a", "text": "Scoped"}], "ticket_ids": ["ARCH-9"], "raw": "plan"}))
    rc = sync.cmd_write_intent(tmp_path, str(payload))
    assert rc == 0
    got = it.load_committed_intent(tmp_path)
    assert got["acceptance_criteria"][0]["text"] == "Scoped" and got["ticket_ids"] == ["ARCH-9"]


def test_write_intent_bad_payload_leaves_file_intact(tmp_path):
    it.write_committed_intent(tmp_path, {"source": "sync", "acceptance_criteria": [{"id": "a", "text": "Keep"}],
                                         "goals": [], "ticket_ids": [], "raw": ""})
    bad = tmp_path / "bad.json"; bad.write_text("{ not json")
    rc = sync.cmd_write_intent(tmp_path, str(bad))
    assert rc == 0
    assert it.load_committed_intent(tmp_path)["acceptance_criteria"][0]["text"] == "Keep"  # unchanged

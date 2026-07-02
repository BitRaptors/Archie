import sys, json
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import intent_synthesize as isyn  # noqa: E402
import intent_capture as ic  # noqa: E402


def test_prompt_is_blind_to_implementation():
    p = isyn.build_synthesis_prompt([{"kind": "user_turn", "text": "Add tenant-scoped export"}])
    assert "tenant-scoped export" in p
    assert "NOT shown the implementation" in p
    # blindness: the prompt must not smuggle code/diff markers
    assert "diff --git" not in p and "def " not in p


def test_parse_synthesis_maps_fields():
    raw = '{"goals":["Scope export"],"acceptance_criteria":[{"id":"ac1","text":"tenant scoped"}],"non_goals":["no UI change"]}'
    out = isyn.parse_synthesis(raw)
    assert out["goals"] == ["Scope export"]
    assert out["acceptance_criteria"][0]["text"] == "tenant scoped"
    assert out["non_goals"] == ["no UI change"]


def test_synthesize_writes_unconfirmed_spec_with_provenance(tmp_path):
    ic.record_user_turn(tmp_path, "Add tenant-scoped export, rate-limited")
    fake = lambda *a, **k: '{"goals":["G"],"acceptance_criteria":[{"id":"ac1","text":"scoped"}],"non_goals":[]}'
    spec = isyn.synthesize(tmp_path, run=fake)
    assert spec["confirmed"] is False and spec["capture_points"] >= 1
    on_disk = json.loads((tmp_path / ".archie" / "intent.json").read_text())
    assert on_disk["acceptance_criteria"][0]["text"] == "scoped"


def test_resynthesize_can_retire_criteria(tmp_path):
    ic.record_user_turn(tmp_path, "v1")
    isyn.synthesize(tmp_path, run=lambda *a, **k: '{"acceptance_criteria":[{"id":"ac1","text":"old"},{"id":"ac2","text":"drop me"}],"goals":[],"non_goals":[]}')
    ic.record_user_turn(tmp_path, "v2: dropped one")
    spec = isyn.synthesize(tmp_path, run=lambda *a, **k: '{"acceptance_criteria":[{"id":"ac1","text":"old"}],"goals":[],"non_goals":[]}')
    assert [c["text"] for c in spec["acceptance_criteria"]] == ["old"]   # retired, not accreted


def test_synthesize_no_events_returns_none(tmp_path):
    assert isyn.synthesize(tmp_path, run=lambda *a, **k: "{}") is None

import json
from pathlib import Path
from archie.standalone import extract_output

def test_extract_findings_from_agent_output(tmp_path):
    inp = tmp_path / "in.json"
    out = tmp_path / "out.json"
    inp.write_text(json.dumps({
        "findings": [{"type": "cycle"}, {"type": "fragmentation"}],
        "other_data": "ignored"
    }))
    extract_output.extract_findings(str(inp), str(out))
    result = json.loads(out.read_text())
    assert result == {"findings": [{"type": "cycle"}, {"type": "fragmentation"}]}

def test_extract_findings_missing_key(tmp_path):
    inp = tmp_path / "in.json"
    out = tmp_path / "out.json"
    inp.write_text(json.dumps({"no_findings_here": True}))
    extract_output.extract_findings(str(inp), str(out))
    result = json.loads(out.read_text())
    assert result == {"findings": []}

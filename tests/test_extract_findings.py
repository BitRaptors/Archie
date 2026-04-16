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

def test_concat_findings_merges_multiple_files(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    out = tmp_path / "out.json"
    a.write_text(json.dumps({"findings": [{"type": "cycle"}]}))
    b.write_text(json.dumps({"findings": [{"type": "fragmentation"}, {"type": "god_component"}]}))
    extract_output.concat_findings([str(a), str(b)], str(out))
    result = json.loads(out.read_text())
    assert result == {"findings": [{"type": "cycle"}, {"type": "fragmentation"}, {"type": "god_component"}]}

def test_concat_findings_tolerates_missing_and_malformed(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"  # will be malformed
    c = tmp_path / "c.json"  # won't exist
    out = tmp_path / "out.json"
    a.write_text(json.dumps({"findings": [{"type": "cycle"}]}))
    b.write_text("{not json")
    extract_output.concat_findings([str(a), str(b), str(c)], str(out))
    result = json.loads(out.read_text())
    assert result == {"findings": [{"type": "cycle"}]}

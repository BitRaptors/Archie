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

def test_extract_findings_tolerates_prose_wrapped_json(tmp_path):
    """Sonnet often emits JSON inside a code fence with surrounding prose."""
    inp = tmp_path / "in.json"
    out = tmp_path / "out.json"
    inp.write_text(
        "Here's my analysis:\n"
        "\n"
        "```json\n"
        "{\n"
        '  "findings": [{"type": "cycle"}, {"type": "fragmentation"}]\n'
        "}\n"
        "```\n"
        "\n"
        "Hope this helps.\n"
    )
    extract_output.extract_findings(str(inp), str(out))
    result = json.loads(out.read_text())
    assert result == {"findings": [{"type": "cycle"}, {"type": "fragmentation"}]}

def test_extract_findings_tolerates_missing_input(tmp_path):
    out = tmp_path / "out.json"
    extract_output.extract_findings(str(tmp_path / "does_not_exist.json"), str(out))
    result = json.loads(out.read_text())
    assert result == {"findings": []}

def test_extract_findings_tolerates_malformed_json(tmp_path):
    inp = tmp_path / "in.json"
    out = tmp_path / "out.json"
    inp.write_text("{not valid json")
    extract_output.extract_findings(str(inp), str(out))
    result = json.loads(out.read_text())
    assert result == {"findings": []}

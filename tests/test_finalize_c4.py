"""finalize wires c4.build_all: blueprint gains kind/group, c4.json is written."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))
import finalize as F  # noqa: E402


def test_finalize_writes_c4_and_enriches(tmp_path):
    a = tmp_path / ".archie"
    a.mkdir()
    (a / "scan.json").write_text(json.dumps(
        {"entrypoints": [{"path": "cmd/server/main.go", "kind": "service"}]}))
    (a / "blueprint_raw.json").write_text(json.dumps({
        "meta": {"name": "demo"},
        "components": {"components": [{"name": "cmd/server", "location": "cmd/server"}]},
        "persistence_stores": ["pg"],
        "communication": {"patterns": []},
    }))
    F.finalize(tmp_path, [])  # no agent files; just normalize+render+c4

    bp = json.loads((a / "blueprint.json").read_text())
    comp = bp["components"]["components"][0]
    assert comp["kind"] == "service" and comp["group"] == "cmd"
    c4 = json.loads((a / "c4.json").read_text())
    assert c4["context"].startswith("C4Context")

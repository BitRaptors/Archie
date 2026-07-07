import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import evidence_pack as ep  # noqa: E402


def test_pack_includes_changed_file_contents(tmp_path):
    (tmp_path / "svc.py").write_text("def cost():\n    return billable * 0.12\n")
    pack = ep.build_pack(tmp_path, ["svc.py"], {}, {})
    assert "svc.py" in pack and "return billable * 0.12" in pack
    assert "CONTEXT" in pack


def test_pack_truncates_large_file_with_marker(tmp_path):
    (tmp_path / "big.py").write_text("x = 1\n" * 5000)  # ~30k chars
    pack = ep.build_pack(tmp_path, ["big.py"], {}, {}, budget_chars=40000)
    assert "[truncated" in pack


def test_pack_budget_trailer_when_over(tmp_path):
    for i in range(20):
        (tmp_path / f"f{i}.py").write_text("y = 2\n" * 2000)  # ~12k each
    files = [f"f{i}.py" for i in range(20)]
    pack = ep.build_pack(tmp_path, files, {}, {}, budget_chars=40000)
    assert len(pack) <= 40000 + 500  # budget + trailer slack
    assert "evidence truncated:" in pack


def test_pack_includes_blueprint_slice_for_touched_component(tmp_path):
    (tmp_path / "svc.py").write_text("x=1\n")
    bp = {"components": {"components": [
        {"name": "svc", "location": "svc.py", "responsibility": "does the thing",
         "key_interfaces": ["cost()"]}]}}
    pack = ep.build_pack(tmp_path, ["svc.py"], {}, bp)
    assert "does the thing" in pack


def test_pack_missing_file_is_skipped(tmp_path):
    pack = ep.build_pack(tmp_path, ["gone.py"], {}, {})
    assert isinstance(pack, str)  # no crash

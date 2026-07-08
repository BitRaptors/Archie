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


def test_pack_survives_legacy_blueprint_shapes(tmp_path):
    # Real-world regression (SubscriberAgent PR #17): legacy blueprints carry
    # heterogeneous shapes — components as plain strings, key_interfaces items
    # as dicts. This crashed _blueprint_slice and killed the ENTIRE review.
    (tmp_path / "worker").mkdir()
    (tmp_path / "worker" / "main.py").write_text("x = 1\n")
    bp = {"components": {"components": [
        "just-a-string-component",
        {"name": "Worker", "location": "worker/", "responsibility": "runs",
         "key_interfaces": [{"name": "execute_run", "signature": "async def"},
                            "plain_string_iface"]},
    ]}}
    pack = ep.build_pack(tmp_path, ["worker/main.py"], {}, bp)
    assert "Worker" in pack
    assert "execute_run" in pack          # dict iface coerced to its name
    assert "plain_string_iface" in pack   # string iface untouched


def test_pack_dict_iface_without_name_key_still_coerces():
    assert ep._iface_str({"weird": "shape"}) == "shape"
    assert ep._iface_str("plain") == "plain"

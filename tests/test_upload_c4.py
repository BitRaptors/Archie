"""build_bundle carries .archie/c4.json into bundle['c4'] (share + local viewer)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))
import upload  # noqa: E402


def _min_archie(tmp_path):
    a = tmp_path / ".archie"
    a.mkdir()
    (a / "blueprint.json").write_text(json.dumps({"meta": {"name": "x"}}))
    return a


def test_bundle_includes_c4_when_present(tmp_path):
    a = _min_archie(tmp_path)
    (a / "c4.json").write_text(json.dumps(
        {"context": "C4Context\n", "container": "", "component": ""}))
    bundle = upload.build_bundle(tmp_path)
    assert bundle["c4"]["context"].startswith("C4Context")


def test_bundle_omits_c4_when_absent(tmp_path):
    _min_archie(tmp_path)
    bundle = upload.build_bundle(tmp_path)
    assert "c4" not in bundle

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "archie" / "standalone"))
import upload  # noqa: E402


def _make_project(tmp_path: Path, files: dict) -> Path:
    archie = tmp_path / ".archie"
    archie.mkdir()
    for name, content in files.items():
        (archie / name).write_text(json.dumps(content) if not isinstance(content, str) else content)
    return tmp_path


def test_bundle_includes_bundle_version_v2(tmp_path):
    project = _make_project(tmp_path, {
        "blueprint.json": {"meta": {}},
        "semantic_findings.json": {"findings": []},
    })
    bundle = upload.build_bundle(project / ".archie")
    assert bundle.get("bundle_version") == "v2"


def test_bundle_unversioned_when_no_semantic_findings(tmp_path):
    """Old-style bundle without semantic_findings — no bundle_version key.

    A v1-shaped bundle MUST NOT claim to be v2. Consumers key off
    bundle_version to decide which fields to expect; lying here makes them
    look up semantic_findings that isn't there.
    """
    project = _make_project(tmp_path, {"blueprint.json": {"meta": {}}})
    bundle = upload.build_bundle(project / ".archie")
    assert "bundle_version" not in bundle


def test_bundle_includes_semantic_findings_when_present(tmp_path):
    project = _make_project(tmp_path, {
        "blueprint.json": {"meta": {}},
        "semantic_findings.json": {"findings": [{"type": "cycle", "category": "localized"}]}
    })
    bundle = upload.build_bundle(project / ".archie")
    assert "semantic_findings" in bundle
    assert bundle["semantic_findings"]["findings"][0]["type"] == "cycle"


def test_bundle_omits_semantic_findings_when_absent(tmp_path):
    project = _make_project(tmp_path, {"blueprint.json": {"meta": {}}})
    bundle = upload.build_bundle(project / ".archie")
    assert "semantic_findings" not in bundle


def test_bundle_still_includes_legacy_scan_report(tmp_path):
    project = _make_project(tmp_path, {
        "blueprint.json": {"meta": {}},
        "scan_report.md": "# legacy report"
    })
    bundle = upload.build_bundle(project / ".archie")
    assert bundle.get("scan_report") == "# legacy report"


def test_bundle_omits_wave_intermediates(tmp_path):
    """Internal wave1/wave2/phase2 files must NOT leak into the bundle."""
    project = _make_project(tmp_path, {
        "blueprint.json": {"meta": {}},
        "semantic_findings_wave1.json": {"findings": []},
        "semantic_findings_wave2.json": {"findings": []},
        "semantic_findings_phase2.json": {"findings": []},
    })
    bundle = upload.build_bundle(project / ".archie")
    assert "semantic_findings_wave1" not in bundle
    assert "semantic_findings_wave2" not in bundle
    assert "semantic_findings_phase2" not in bundle


def test_bundle_omits_drift_report_when_semantic_findings_present(tmp_path):
    """drift_report.json is folded into semantic_findings.json; don't duplicate."""
    project = _make_project(tmp_path, {
        "blueprint.json": {"meta": {}},
        "semantic_findings.json": {"findings": []},
        "drift_report.json": {"mechanical": []}
    })
    bundle = upload.build_bundle(project / ".archie")
    assert "drift_report" not in bundle

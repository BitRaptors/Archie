import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "archie" / "standalone"))
from upload import _strip_health, _strip_scan_meta, build_bundle  # noqa: E402


@pytest.fixture
def mock_archie_dir(tmp_path):
    archie = tmp_path / ".archie"
    archie.mkdir()
    archie.joinpath("blueprint.json").write_text(json.dumps({
        "meta": {"repository": "test/repo"},
        "components": {},
        "decisions": {},
    }))
    archie.joinpath("health.json").write_text(json.dumps({
        "erosion": 0.15,
        "gini": 0.4,
        "top20_share": 0.6,
        "verbosity": 0.05,
        "total_functions": 100,
        "high_cc_functions": 5,
        "total_loc": 5000,
        "duplicate_lines": 50,
        "functions": [{"path": "a.py", "name": "f", "cc": 15, "sloc": 20, "line": 1}],
    }))
    archie.joinpath("scan.json").write_text(json.dumps({
        "file_tree": [{"path": "a.py"}, {"path": "b.py"}],
        "framework_signals": [{"name": "React", "version": "18"}],
        "frontend_ratio": 0.3,
        "subprojects": [],
        "dependencies": [{"name": "react"}],
    }))
    return tmp_path


def test_build_bundle_includes_all(mock_archie_dir):
    archie = mock_archie_dir / ".archie"
    archie.joinpath("rules.json").write_text(json.dumps({
        "rules": [{"id": "r1", "description": "No circular deps", "source": "scan-adopted"}]
    }))
    archie.joinpath("proposed_rules.json").write_text(json.dumps({
        "rules": [{"id": "p1", "description": "Use barrel exports", "confidence": 0.7}]
    }))
    archie.joinpath("scan_report.md").write_text("# Scan\n\n## Findings\n- thing one")
    bundle = build_bundle(mock_archie_dir)
    assert "blueprint" in bundle
    assert "health" in bundle
    assert "scan_meta" in bundle
    assert "rules_adopted" in bundle
    assert "rules_proposed" in bundle
    assert "scan_report" in bundle
    assert "## Findings" in bundle["scan_report"]
    assert bundle["blueprint"]["meta"]["repository"] == "test/repo"
    assert len(bundle["rules_adopted"]["rules"]) == 1
    assert len(bundle["rules_proposed"]["rules"]) == 1


def test_build_bundle_blueprint_only(tmp_path):
    archie = tmp_path / ".archie"
    archie.mkdir()
    archie.joinpath("blueprint.json").write_text(json.dumps({"meta": {}}))
    bundle = build_bundle(tmp_path)
    assert "blueprint" in bundle
    assert "health" not in bundle
    assert "scan_meta" not in bundle
    assert "rules_adopted" not in bundle
    assert "rules_proposed" not in bundle


def test_build_bundle_missing_blueprint(tmp_path):
    (tmp_path / ".archie").mkdir()
    with pytest.raises(SystemExit):
        build_bundle(tmp_path)


def test_strip_health_keeps_top_cc_and_dupes():
    health = {
        "erosion": 0.1,
        "gini": 0.5,
        "functions": [
            {"path": "a.py", "name": "small", "cc": 3, "sloc": 5, "line": 1},
            {"path": "b.py", "name": "huge", "cc": 50, "sloc": 200, "line": 10},
            {"path": "c.py", "name": "medium", "cc": 12, "sloc": 40, "line": 5},
        ],
        "duplicates": [
            {"lines": 30, "locations": ["x.py:1", "y.py:1"]},
            {"lines": 10, "locations": ["a.py", "b.py"]},
        ],
    }
    stripped = _strip_health(health)
    assert "functions" not in stripped
    assert "duplicates" not in stripped
    assert stripped["erosion"] == 0.1
    assert stripped["top_high_cc"][0]["name"] == "huge"
    assert stripped["top_high_cc"][0]["cc"] == 50
    assert len(stripped["top_high_cc"]) == 3
    assert stripped["top_duplicates"][0]["lines"] == 30


def test_strip_scan_meta_drops_file_tree():
    scan = {
        "file_tree": [{"path": "a.py"}, {"path": "b.py"}],
        "token_counts": {"a.py": 100},
        "framework_signals": [{"name": "Django", "version": "4.2"}],
        "frontend_ratio": 0.0,
        "subprojects": [],
        "dependencies": [{"name": "django"}],
    }
    stripped = _strip_scan_meta(scan)
    assert "file_tree" not in stripped
    assert "token_counts" not in stripped
    assert stripped["total_files"] == 2
    assert stripped["dependency_count"] == 1

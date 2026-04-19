"""Tests for check_blueprint_completeness.py."""

import json
import subprocess
import sys
from pathlib import Path

HELPER = Path(__file__).parent.parent / "archie" / "standalone" / "check_blueprint_completeness.py"


def _run(project: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(HELPER), str(project)],
        capture_output=True, text=True
    )
    return proc.returncode, proc.stdout.strip()


def _full_blueprint() -> dict:
    return {
        "meta": {}, "components": [], "decisions": {}, "communication": {},
        "pitfalls": [], "technology": {}, "architecture_rules": {},
        "development_rules": [], "implementation_guidelines": [],
        "quick_reference": {}, "architecture_diagram": "",
        "capabilities": [], "data_models": [],
    }


def _write_blueprint(tmp_path: Path, content) -> None:
    archie = tmp_path / ".archie"
    archie.mkdir(exist_ok=True)
    bp_path = archie / "blueprint.json"
    if isinstance(content, str):
        bp_path.write_text(content)
    else:
        bp_path.write_text(json.dumps(content))


def test_blueprint_missing_returns_zero(tmp_path):
    """No .archie/blueprint.json at all → exit 0, MISSING."""
    code, out = _run(tmp_path)
    assert code == 0
    assert out == "MISSING"


def test_blueprint_complete_returns_zero(tmp_path):
    _write_blueprint(tmp_path, _full_blueprint())
    code, out = _run(tmp_path)
    assert code == 0
    assert out == "OK"


def test_blueprint_missing_data_models_returns_one(tmp_path):
    bp = _full_blueprint()
    del bp["data_models"]
    _write_blueprint(tmp_path, bp)
    code, out = _run(tmp_path)
    assert code == 1
    assert out.startswith("STALE")
    assert "data_models" in out
    assert "Plan 5b.1" in out


def test_blueprint_missing_multiple_returns_one(tmp_path):
    """Almost-empty blueprint should list all missing keys, sorted by intro plan."""
    _write_blueprint(tmp_path, {"meta": {}, "components": []})
    code, out = _run(tmp_path)
    assert code == 1
    assert out.startswith("STALE")
    assert "data_models" in out
    assert "capabilities" in out
    # Sort: Plan 1 keys come before Plan 2, which comes before Plan 5b.1
    assert out.index("decisions") < out.index("capabilities")
    assert out.index("capabilities") < out.index("data_models")


def test_blueprint_malformed_returns_one(tmp_path):
    _write_blueprint(tmp_path, "not { valid json")
    code, out = _run(tmp_path)
    assert code == 1
    assert out == "MALFORMED"


def test_empty_data_models_array_counts_as_present(tmp_path):
    """An empty data_models[] means the agent ran and found nothing — that's OK."""
    bp = _full_blueprint()
    assert bp["data_models"] == []  # sanity: fixture really has empty list
    _write_blueprint(tmp_path, bp)
    code, out = _run(tmp_path)
    assert code == 0
    assert out == "OK"

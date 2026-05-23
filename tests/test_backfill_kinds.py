import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "legacy_rules.json"
SCRIPT = ROOT / "archie" / "standalone" / "backfill_kinds.py"


@pytest.fixture()
def project_dir(tmp_path: Path) -> Path:
    archie = tmp_path / ".archie"
    archie.mkdir()
    (archie / "rules.json").write_bytes(FIXTURE.read_bytes())
    return tmp_path


def _run(project: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(project), *args],
        capture_output=True, text=True, check=False,
    )


def test_dry_run_reports_counts_without_writing(project_dir: Path):
    rules_path = project_dir / ".archie" / "rules.json"
    before = rules_path.read_bytes()

    result = _run(project_dir, "--dry-run")

    assert result.returncode == 0, result.stderr
    assert rules_path.read_bytes() == before, "dry-run must not touch the file"
    assert "would update" in result.stdout.lower() or "would assign" in result.stdout.lower()


def test_writes_kinds_for_legacy_rules(project_dir: Path):
    result = _run(project_dir)
    assert result.returncode == 0, result.stderr

    rules = json.loads((project_dir / ".archie" / "rules.json").read_text())["rules"]
    by_id = {r["id"]: r for r in rules}

    assert by_id["layer-001"]["kind"] == "layering"
    assert by_id["naming-001"]["kind"] == "naming_convention"
    assert by_id["placement-001"]["kind"] == "file_placement"
    assert by_id["pitfall-001"]["kind"] == "pitfall"
    assert by_id["chain-001"]["kind"] == "decision"
    assert by_id["tradeoff-001"]["kind"] == "tradeoff"
    assert by_id["pattern-001"]["kind"] == "semantic_pattern"
    assert by_id["x-001"]["kind"] == "infrastructure"
    assert by_id["x-002"]["kind"] == "coding_practice"


def test_preserves_existing_valid_kind(project_dir: Path):
    _run(project_dir)
    rules = json.loads((project_dir / ".archie" / "rules.json").read_text())["rules"]
    by_id = {r["id"]: r for r in rules}
    assert by_id["x-003"]["kind"] == "decision"


def test_reclassifies_invalid_kind(project_dir: Path):
    _run(project_dir)
    rules = json.loads((project_dir / ".archie" / "rules.json").read_text())["rules"]
    by_id = {r["id"]: r for r in rules}
    assert by_id["x-004"]["kind"] == "layering"


def test_idempotent_second_run_is_noop(project_dir: Path):
    _run(project_dir)
    first = (project_dir / ".archie" / "rules.json").read_bytes()
    result = _run(project_dir)
    assert result.returncode == 0
    second = (project_dir / ".archie" / "rules.json").read_bytes()
    assert first == second, "second run must be a no-op on already-classified rules"
    assert "0 updated" in result.stdout.lower() or "nothing to" in result.stdout.lower()


def test_missing_rules_json_is_clean_exit(tmp_path: Path):
    (tmp_path / ".archie").mkdir()
    result = _run(tmp_path)
    assert result.returncode == 0
    assert "no rules.json" in result.stdout.lower() or "skipped" in result.stdout.lower()


def test_handles_top_level_list_shape(tmp_path: Path):
    """Some legacy files store the rules array at the top level instead of {"rules": [...]}."""
    archie = tmp_path / ".archie"
    archie.mkdir()
    (archie / "rules.json").write_text(json.dumps([{"id": "layer-001", "description": "x"}]))

    result = _run(tmp_path)
    assert result.returncode == 0
    data = json.loads((archie / "rules.json").read_text())
    rules = data if isinstance(data, list) else data["rules"]
    assert rules[0]["kind"] == "layering"

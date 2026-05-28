"""State-model regressions for the deterministic intent-layer scheduler."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


_INTENT_LAYER = Path(__file__).resolve().parent.parent / "archie" / "standalone" / "intent_layer.py"
_COMMON = Path(__file__).resolve().parent.parent / "archie" / "standalone" / "_common.py"


def _load_module():
    sys.path.insert(0, str(_COMMON.parent))
    spec = importlib.util.spec_from_file_location("intent_layer_under_test", _INTENT_LAYER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def intent_layer():
    return _load_module()


def test_prepare_writes_run_metadata(intent_layer, tmp_path: Path) -> None:
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir(parents=True)
    scan = {
        "file_tree": [
            {"path": "src/a.py"},
            {"path": "src/b.py"},
        ]
    }
    (archie_dir / "scan.json").write_text(json.dumps(scan))
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("a")
    (tmp_path / "src" / "b.py").write_text("b")

    intent_layer.cmd_prepare(tmp_path)
    plan = json.loads((archie_dir / "enrich_batches.json").read_text())

    assert plan["run_id"]
    assert len(plan["run_id"]) == 12
    assert plan["project_slug"] == tmp_path.name


def test_next_ready_uses_persistent_state_done_list(intent_layer, tmp_path: Path, capsys) -> None:
    archie_dir = tmp_path / ".archie"
    enrich_dir = archie_dir / "enrichments"
    enrich_dir.mkdir(parents=True)

    plan = {
        "folders": {
            "a": {"children": [], "depth": 1, "size_chars": 1},
            "b": {"children": ["a"], "depth": 1, "size_chars": 1},
        }
    }
    (archie_dir / "enrich_batches.json").write_text(json.dumps(plan))
    (archie_dir / "enrich_state.json").write_text(json.dumps({"done": ["a"], "wave": 1}))
    (enrich_dir / "w0.json").write_text(json.dumps({"b": {"purpose": "stale"}}))

    intent_layer.cmd_next_ready(tmp_path, [])
    out = capsys.readouterr().out.strip()
    assert json.loads(out) == ["b"]


def test_save_enrichment_rejects_folders_outside_current_dag(intent_layer, tmp_path: Path) -> None:
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir(parents=True)
    (archie_dir / "enrich_batches.json").write_text(json.dumps({
        "folders": {
            "real": {"children": [], "depth": 1, "size_chars": 1},
        }
    }))
    input_file = tmp_path / "foreign.json"
    input_file.write_text(json.dumps({"ghost": {"purpose": "nope"}}))

    with pytest.raises(SystemExit):
        intent_layer.cmd_save_enrichment(tmp_path, "w0", str(input_file))


def test_save_enrichment_appends_to_persistent_done_state(intent_layer, tmp_path: Path) -> None:
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir(parents=True)
    (archie_dir / "enrich_state.json").write_text(json.dumps({"done": ["a"], "wave": 1}))
    (archie_dir / "enrich_batches.json").write_text(json.dumps({
        "folders": {
            "a": {"children": [], "depth": 1, "size_chars": 1},
            "b": {"children": [], "depth": 1, "size_chars": 1},
        }
    }))

    first = tmp_path / "w0.json"
    second = tmp_path / "w1.json"
    first.write_text(json.dumps({"a": {"purpose": "A"}}))
    second.write_text(json.dumps({"b": {"purpose": "B"}}))

    intent_layer.cmd_save_enrichment(tmp_path, "w0", str(first))
    intent_layer.cmd_save_enrichment(tmp_path, "w1", str(second))

    state = json.loads((archie_dir / "enrich_state.json").read_text())
    assert state["done"] == ["a", "b"]
    assert state["wave"] == 3

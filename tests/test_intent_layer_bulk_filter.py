"""Regression guard for the bulk-file filter in intent_layer.cmd_prepare.

Files tagged by `.archiebulk` (generated code, minified JS, Ent ORM output,
protobuf stubs, etc.) should not cause their containing directories to enter
the enrichment DAG. A folder that holds only generated code doesn't need a
hand-curated CLAUDE.md — an agent editing those files is running a codegen
tool, not writing architecture.

Real-world trigger: openmeter project had ~100 Ent codegen folders
(`openmeter/ent/db/*`) bloating the DAG. With this filter those folders
drop out entirely; only the source-of-truth `openmeter/ent/schema/` stays.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))

from intent_layer import cmd_prepare  # noqa: E402


def _write_scan(root: Path, files: list[dict]) -> None:
    (root / ".archie").mkdir(parents=True, exist_ok=True)
    (root / ".archie" / "scan.json").write_text(
        json.dumps({"file_tree": files, "bulk_content_manifest": {}})
    )
    # Minimal blueprint so downstream callers don't crash
    (root / ".archie" / "blueprint.json").write_text(json.dumps({"components": []}))


def _dag_from(root: Path) -> dict:
    cmd_prepare(root, only_folders=None)
    return json.loads((root / ".archie" / "enrich_batches.json").read_text())


def test_bulk_only_folders_are_excluded_from_dag(tmp_path):
    """Directory with only bulk-tagged files should not appear in the DAG."""
    _write_scan(
        tmp_path,
        [
            # Real source — enters DAG
            {"path": "src/api/handler.go", "size": 100, "extension": ".go"},
            # Pure generated directory — should NOT enter DAG
            {
                "path": "src/ent/db/addon.go",
                "size": 12000,
                "extension": ".go",
                "bulk": {"category": "generated", "framework": "go-ent"},
            },
            {
                "path": "src/ent/db/addon_create.go",
                "size": 14000,
                "extension": ".go",
                "bulk": {"category": "generated", "framework": "go-ent"},
            },
        ],
    )
    plan = _dag_from(tmp_path)
    dag_folders = set(plan["folders"].keys())

    # Real source folder is in the DAG
    assert "src/api" in dag_folders
    # Generated-only folder is NOT
    assert "src/ent/db" not in dag_folders


def test_mixed_folder_stays_in_dag(tmp_path):
    """If a folder has at least ONE hand-authored file, it still qualifies.

    This protects against false-positives: a folder with hand-written glue code
    alongside a generated helper shouldn't be dropped just because ONE file is
    tagged bulk.
    """
    _write_scan(
        tmp_path,
        [
            {"path": "src/mixed/real.go", "size": 500, "extension": ".go"},
            {
                "path": "src/mixed/generated.pb.go",
                "size": 5000,
                "extension": ".go",
                "bulk": {"category": "generated", "framework": "protobuf"},
            },
        ],
    )
    plan = _dag_from(tmp_path)
    assert "src/mixed" in plan["folders"]


def test_all_bulk_dropped_but_sibling_real_kept(tmp_path):
    """Sibling directories are independent — one bulk-only, one real."""
    _write_scan(
        tmp_path,
        [
            # api/real/ — real source → in DAG
            {"path": "api/real/service.go", "size": 800, "extension": ".go"},
            # api/generated/ — all bulk → dropped
            {
                "path": "api/generated/client.gen.go",
                "size": 3000,
                "extension": ".go",
                "bulk": {"category": "generated", "framework": "oapi-codegen"},
            },
            {
                "path": "api/generated/types.gen.go",
                "size": 4000,
                "extension": ".go",
                "bulk": {"category": "generated", "framework": "oapi-codegen"},
            },
        ],
    )
    plan = _dag_from(tmp_path)
    dag_folders = set(plan["folders"].keys())
    assert "api/real" in dag_folders
    assert "api/generated" not in dag_folders


def test_no_bulk_info_behaves_as_before(tmp_path):
    """Files without any bulk metadata are treated as regular source.
    Backward-compat check — old scan.json files (no bulk tags) still work."""
    _write_scan(
        tmp_path,
        [
            {"path": "src/lib/util.go", "size": 500, "extension": ".go"},
            {"path": "src/lib/helper.go", "size": 600, "extension": ".go"},
        ],
    )
    plan = _dag_from(tmp_path)
    assert "src/lib" in plan["folders"]

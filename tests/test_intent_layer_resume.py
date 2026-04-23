"""Tests for the resume + finalize-partial defensive behavior in cmd_merge.

The slash command's resume flow lets users re-enter an interrupted intent-layer
run. Those runs can produce enrichments whose target folder no longer exists on
disk (user restructured the repo, or an orphan /tmp file got ingested for a
folder that was never committed). cmd_merge must NOT crash or create empty
directories for those — it skips them cleanly.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


_INTENT_LAYER = Path(__file__).resolve().parent.parent / "archie" / "standalone" / "intent_layer.py"
_COMMON = Path(__file__).resolve().parent.parent / "archie" / "standalone" / "_common.py"


def _load_module():
    """Load intent_layer.py with its _common.py sibling available."""
    # _common is a sibling import inside intent_layer; ensure it's on the path.
    sys.path.insert(0, str(_COMMON.parent))
    spec = importlib.util.spec_from_file_location("intent_layer_under_test", _INTENT_LAYER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def intent_layer():
    return _load_module()


def _write_enrichment(enrich_dir: Path, batch_id: str, folder_to_data: dict):
    """Simulate a save-enrichment output file."""
    enrich_dir.mkdir(parents=True, exist_ok=True)
    path = enrich_dir / f"{batch_id}.json"
    path.write_text(json.dumps(folder_to_data))


# ---------------------------------------------------------------------------
# cmd_merge defensive handling
# ---------------------------------------------------------------------------


def test_merge_skips_enrichments_for_deleted_folders(intent_layer, tmp_path, capsys):
    """Enrichments pointing at folders that no longer exist get skipped silently.

    This is the safety net for:
    - User restructured the repo between runs
    - Orphan /tmp enrichments ingested during resume sweep for folders
      that never landed in the final tree
    """
    # A valid folder and a phantom folder
    (tmp_path / "src" / "real_folder").mkdir(parents=True)

    enrich_dir = tmp_path / ".archie" / "enrichments"
    _write_enrichment(enrich_dir, "w0", {
        "src/real_folder": {"purpose": "real purpose"},
        "src/deleted_folder": {"purpose": "was deleted"},
        "path/does/not/exist": {"purpose": "never existed"},
    })

    # Run merge
    intent_layer.cmd_merge(tmp_path)

    # Real folder gets CLAUDE.md
    real_md = tmp_path / "src" / "real_folder" / "CLAUDE.md"
    assert real_md.exists()
    assert "real purpose" in real_md.read_text()

    # Deleted / non-existent folder paths do NOT get directories created
    assert not (tmp_path / "src" / "deleted_folder").exists()
    assert not (tmp_path / "path").exists()

    # Summary mentions the skip
    captured = capsys.readouterr()
    assert "skipped" in captured.err.lower()


def test_merge_summary_counts_are_accurate(intent_layer, tmp_path, capsys):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "CLAUDE.md").write_text("# b\n\nmanual content\n")  # existing

    enrich_dir = tmp_path / ".archie" / "enrichments"
    _write_enrichment(enrich_dir, "w0", {
        "a": {"purpose": "A purpose"},      # created
        "b": {"purpose": "B purpose"},      # patched (existing CLAUDE.md)
        "ghost": {"purpose": "no folder"},  # skipped
    })

    intent_layer.cmd_merge(tmp_path)
    summary = capsys.readouterr().err

    # Order: "X patched, Y created, Z skipped..."
    assert "1 patched" in summary
    assert "1 created" in summary
    assert "1 skipped" in summary


def test_merge_with_all_real_folders_no_skipped_note(intent_layer, tmp_path, capsys):
    """When nothing is skipped, the summary doesn't mention skipping."""
    (tmp_path / "a").mkdir()
    enrich_dir = tmp_path / ".archie" / "enrichments"
    _write_enrichment(enrich_dir, "w0", {"a": {"purpose": "A"}})

    intent_layer.cmd_merge(tmp_path)
    summary = capsys.readouterr().err

    assert "skipped" not in summary.lower()


def test_merge_creates_claude_md_without_making_parent_dirs(intent_layer, tmp_path, capsys):
    """Regression guard: the old code used mkdir(parents=True) which would
    happily create directories for deleted folders. The new code must NOT
    create parent directories — if the folder doesn't exist, skip entirely.
    """
    enrich_dir = tmp_path / ".archie" / "enrichments"
    _write_enrichment(enrich_dir, "w0", {
        "ghost/nested/path": {"purpose": "should not create these dirs"},
    })

    intent_layer.cmd_merge(tmp_path)

    assert not (tmp_path / "ghost").exists()
    # The code previously would have made these directories; make sure the
    # fix doesn't regress.

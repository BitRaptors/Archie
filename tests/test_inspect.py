"""Tests for the intent_layer.py inspect subcommand."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = str(Path(__file__).resolve().parent.parent / "archie" / "standalone" / "intent_layer.py")


def _run_inspect(repo_dir, filename, query=None):
    """Helper to invoke inspect subcommand."""
    cmd = [sys.executable, SCRIPT, "inspect", str(repo_dir), filename]
    if query:
        cmd += ["--query", query]
    return subprocess.run(cmd, capture_output=True, text=True)


def _make_repo(tmp, filename, data):
    """Create a temp repo with .archie/<filename>."""
    archie_dir = Path(tmp) / ".archie"
    archie_dir.mkdir(parents=True, exist_ok=True)
    (archie_dir / filename).write_text(json.dumps(data))
    return Path(tmp)


class TestInspectScanJson:
    def test_summary_includes_file_count(self, tmp_path):
        repo = _make_repo(tmp_path, "scan.json", {
            "total_files": 142,
            "frontend_ratio": 0.35,
            "frameworks": ["react", "typescript", "jest"]
        })
        result = _run_inspect(repo, "scan.json")
        assert result.returncode == 0
        assert "142 files" in result.stderr
        assert "frontend_ratio=0.35" in result.stderr
        assert "3 frameworks" in result.stderr

    def test_full_json_on_stdout(self, tmp_path):
        data = {"total_files": 10, "frontend_ratio": 0.5, "frameworks": []}
        repo = _make_repo(tmp_path, "scan.json", data)
        result = _run_inspect(repo, "scan.json")
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert parsed["total_files"] == 10


class TestInspectBlueprintJson:
    def test_summary_includes_component_count(self, tmp_path):
        repo = _make_repo(tmp_path, "blueprint.json", {
            "components": [{"name": "A"}, {"name": "B"}, {"name": "C"}],
            "decisions": [{"id": 1}],
            "pitfalls": [{"id": 1}, {"id": 2}],
            "meta": {"architecture_style": "layered"}
        })
        result = _run_inspect(repo, "blueprint.json")
        assert result.returncode == 0
        assert "3 components" in result.stderr
        assert "1 decisions" in result.stderr
        assert "2 pitfalls" in result.stderr
        assert "style=layered" in result.stderr

    def test_components_as_dict(self, tmp_path):
        repo = _make_repo(tmp_path, "blueprint.json", {
            "components": {"components": [{"name": "X"}, {"name": "Y"}]},
            "decisions": [],
            "pitfalls": []
        })
        result = _run_inspect(repo, "blueprint.json")
        assert result.returncode == 0
        assert "2 components" in result.stderr


class TestInspectQuery:
    def test_query_top_level_key(self, tmp_path):
        repo = _make_repo(tmp_path, "scan.json", {
            "total_files": 42,
            "frontend_ratio": 0.35,
            "frameworks": []
        })
        result = _run_inspect(repo, "scan.json", query=".frontend_ratio")
        assert result.returncode == 0
        assert result.stdout.strip() == "0.35"

    def test_query_nested_key(self, tmp_path):
        repo = _make_repo(tmp_path, "scan.json", {
            "meta": {"version": "1.2.3"}
        })
        result = _run_inspect(repo, "scan.json", query=".meta.version")
        assert result.returncode == 0
        assert result.stdout.strip() == "1.2.3"

    def test_query_length(self, tmp_path):
        repo = _make_repo(tmp_path, "dependency_graph.json", {
            "nodes": ["a", "b", "c", "d"],
            "edges": [],
            "cycles": []
        })
        result = _run_inspect(repo, "dependency_graph.json", query=".nodes|length")
        assert result.returncode == 0
        assert result.stdout.strip() == "4"


class TestInspectErrors:
    def test_missing_file_returns_exit_1(self, tmp_path):
        archie_dir = tmp_path / ".archie"
        archie_dir.mkdir(parents=True, exist_ok=True)
        result = _run_inspect(tmp_path, "nonexistent.json")
        assert result.returncode == 1
        assert "not found" in result.stderr

    def test_invalid_json_returns_exit_1(self, tmp_path):
        archie_dir = tmp_path / ".archie"
        archie_dir.mkdir(parents=True, exist_ok=True)
        (archie_dir / "bad.json").write_text("{not valid json}")
        result = _run_inspect(tmp_path, "bad.json")
        assert result.returncode == 1
        assert "invalid JSON" in result.stderr


class TestInspectHealthHistory:
    def test_list_format(self, tmp_path):
        repo = _make_repo(tmp_path, "health_history.json", [
            {"erosion_index": 0.3}, {"erosion_index": 0.25}
        ])
        result = _run_inspect(repo, "health_history.json")
        assert result.returncode == 0
        assert "2 entries" in result.stderr

    def test_dict_format(self, tmp_path):
        repo = _make_repo(tmp_path, "health_history.json", {
            "history": [{"erosion_index": 0.3}]
        })
        result = _run_inspect(repo, "health_history.json")
        assert result.returncode == 0
        assert "1 entries" in result.stderr

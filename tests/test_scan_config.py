"""Tests for intent_layer.py scan-config subcommand."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "archie" / "standalone" / "intent_layer.py"


def _run(project: Path, *args, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "scan-config", str(project), *args],
        capture_output=True,
        text=True,
        input=stdin,
    )


def _write_config(project: Path, config: dict) -> subprocess.CompletedProcess:
    return _run(project, "write", stdin=json.dumps(config))


def test_read_missing_config_exits_1(tmp_path):
    (tmp_path / ".archie").mkdir()
    r = _run(tmp_path, "read")
    assert r.returncode == 1
    assert r.stdout == ""


def test_write_single_scope_no_workspaces(tmp_path):
    (tmp_path / ".archie").mkdir()
    r = _write_config(tmp_path, {"scope": "single", "monorepo_type": "none"})
    assert r.returncode == 0, r.stderr
    cfg = json.loads((tmp_path / ".archie" / "archie_config.json").read_text())
    assert cfg["scope"] == "single"
    assert cfg["monorepo_type"] == "none"
    assert cfg["workspaces"] == []
    assert cfg["schema_version"] == 1
    assert "reconfigured_at" in cfg


def test_write_whole_scope(tmp_path):
    (tmp_path / ".archie").mkdir()
    r = _write_config(tmp_path, {"scope": "whole", "monorepo_type": "bun-workspaces"})
    assert r.returncode == 0
    cfg = json.loads((tmp_path / ".archie" / "archie_config.json").read_text())
    assert cfg["scope"] == "whole"
    assert cfg["monorepo_type"] == "bun-workspaces"


def test_write_per_package_requires_workspaces(tmp_path):
    (tmp_path / ".archie").mkdir()
    r = _write_config(tmp_path, {"scope": "per-package", "monorepo_type": "pnpm"})
    assert r.returncode != 0
    assert "non-empty workspaces" in r.stderr


def test_write_per_package_with_workspaces(tmp_path):
    (tmp_path / ".archie").mkdir()
    (tmp_path / "apps" / "webui").mkdir(parents=True)
    (tmp_path / "packages" / "core").mkdir(parents=True)
    r = _write_config(
        tmp_path,
        {
            "scope": "per-package",
            "monorepo_type": "bun-workspaces",
            "workspaces": ["apps/webui", "packages/core"],
        },
    )
    assert r.returncode == 0, r.stderr
    cfg = json.loads((tmp_path / ".archie" / "archie_config.json").read_text())
    assert cfg["workspaces"] == ["apps/webui", "packages/core"]


def test_write_rejects_invalid_scope(tmp_path):
    (tmp_path / ".archie").mkdir()
    r = _write_config(tmp_path, {"scope": "bogus", "monorepo_type": "none"})
    assert r.returncode != 0
    assert "scope must be one of" in r.stderr


def test_read_after_write_roundtrip(tmp_path):
    (tmp_path / ".archie").mkdir()
    _write_config(tmp_path, {"scope": "whole", "monorepo_type": "bun-workspaces"})
    r = _run(tmp_path, "read")
    assert r.returncode == 0
    cfg = json.loads(r.stdout)
    assert cfg["scope"] == "whole"


def test_write_preserves_unknown_keys(tmp_path):
    (tmp_path / ".archie").mkdir()
    config_path = tmp_path / ".archie" / "archie_config.json"
    config_path.write_text(json.dumps({
        "schema_version": 1,
        "scope": "whole",
        "monorepo_type": "pnpm",
        "workspaces": [],
        "custom_future_key": "preserved",
    }))
    _write_config(tmp_path, {"scope": "whole", "monorepo_type": "pnpm"})
    cfg = json.loads(config_path.read_text())
    assert cfg["custom_future_key"] == "preserved"


def test_validate_missing_exits_1(tmp_path):
    (tmp_path / ".archie").mkdir()
    r = _run(tmp_path, "validate")
    assert r.returncode == 1


def test_validate_single_ok(tmp_path):
    (tmp_path / ".archie").mkdir()
    _write_config(tmp_path, {"scope": "single", "monorepo_type": "none"})
    r = _run(tmp_path, "validate")
    assert r.returncode == 0, r.stderr


def test_validate_detects_workspace_drift(tmp_path):
    (tmp_path / ".archie").mkdir()
    (tmp_path / "apps" / "webui").mkdir(parents=True)
    _write_config(
        tmp_path,
        {
            "scope": "per-package",
            "monorepo_type": "bun-workspaces",
            "workspaces": ["apps/webui", "apps/ghost"],  # ghost doesn't exist
        },
    )
    r = _run(tmp_path, "validate")
    assert r.returncode == 1
    assert "apps/ghost" in r.stderr

"""Tests for per-folder CLAUDE.md generation (archie.renderer.intent_layer)."""
from __future__ import annotations

import json
from pathlib import Path

from archie.renderer.intent_layer import generate_folder_context


def _write_scan(tmp_path: Path, scan_data: dict) -> Path:
    """Write scan data to .archie/scan.json and return the scan path."""
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir(parents=True, exist_ok=True)
    scan_path = archie_dir / "scan.json"
    scan_path.write_text(json.dumps(scan_data), encoding="utf-8")
    return scan_path


def test_generates_context_for_directory(tmp_path: Path) -> None:
    """Scan with files in src/api/, blueprint with API component -> CLAUDE.md generated."""
    scan_data = {
        "file_tree": [
            {"path": "src/api/routes.py", "size": 100, "extension": ".py"},
            {"path": "src/api/middleware.py", "size": 200, "extension": ".py"},
            {"path": "src/api/dto.py", "size": 150, "extension": ".py"},
        ],
        "import_graph": {},
    }
    blueprint = {
        "components": {
            "components": [
                {
                    "name": "API Layer",
                    "location": "src/api",
                    "responsibility": "HTTP request handling",
                }
            ]
        }
    }
    scan_path = _write_scan(tmp_path, scan_data)
    result = generate_folder_context(blueprint, scan_path)

    assert "src/api/CLAUDE.md" in result
    content = result["src/api/CLAUDE.md"]
    assert "# api" in content
    assert "API Layer" in content
    assert "HTTP request handling" in content
    assert "`routes.py`" in content
    assert "`middleware.py`" in content


def test_skips_small_directories(tmp_path: Path) -> None:
    """Directory with only 1 source file should not get a CLAUDE.md."""
    scan_data = {
        "file_tree": [
            {"path": "src/utils/helper.py", "size": 50, "extension": ".py"},
        ],
        "import_graph": {},
    }
    scan_path = _write_scan(tmp_path, scan_data)
    result = generate_folder_context({}, scan_path)

    assert len(result) == 0


def test_includes_import_info(tmp_path: Path) -> None:
    """Directory with import graph data should have a Dependencies section."""
    scan_data = {
        "file_tree": [
            {"path": "src/api/routes.py", "size": 100, "extension": ".py"},
            {"path": "src/api/handler.py", "size": 100, "extension": ".py"},
            {"path": "src/services/user_service.py", "size": 200, "extension": ".py"},
            {"path": "src/services/auth_service.py", "size": 200, "extension": ".py"},
        ],
        "import_graph": {
            "src/api/routes.py": ["src/services/user_service.py"],
            "src/services/auth_service.py": ["src/api/handler.py"],
        },
    }
    scan_path = _write_scan(tmp_path, scan_data)
    result = generate_folder_context({}, scan_path)

    api_content = result["src/api/CLAUDE.md"]
    assert "## Dependencies" in api_content
    assert "Imports from:" in api_content
    assert "src/services" in api_content

    svc_content = result["src/services/CLAUDE.md"]
    assert "## Dependencies" in svc_content
    assert "Imported by:" in svc_content or "Imports from:" in svc_content


def test_empty_blueprint(tmp_path: Path) -> None:
    """Empty blueprint should still generate basic file listings."""
    scan_data = {
        "file_tree": [
            {"path": "lib/core.py", "size": 100, "extension": ".py"},
            {"path": "lib/utils.py", "size": 100, "extension": ".py"},
        ],
        "import_graph": {},
    }
    scan_path = _write_scan(tmp_path, scan_data)
    result = generate_folder_context({}, scan_path)

    assert "lib/CLAUDE.md" in result
    content = result["lib/CLAUDE.md"]
    assert "## Files" in content
    assert "`core.py`" in content
    assert "`utils.py`" in content


def test_returns_file_map(tmp_path: Path) -> None:
    """Result should be a dict mapping paths to content strings."""
    scan_data = {
        "file_tree": [
            {"path": "app/models.py", "size": 100, "extension": ".py"},
            {"path": "app/views.py", "size": 100, "extension": ".py"},
            {"path": "app/urls.py", "size": 100, "extension": ".py"},
        ],
        "import_graph": {},
    }
    scan_path = _write_scan(tmp_path, scan_data)
    result = generate_folder_context({}, scan_path)

    assert isinstance(result, dict)
    for key, value in result.items():
        assert key.endswith("/CLAUDE.md") or key == "CLAUDE.md"
        assert isinstance(value, str)
        assert len(value) > 0

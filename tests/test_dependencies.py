"""Tests for archie.engine.dependencies."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from archie.engine.dependencies import collect_dependencies


def test_parse_requirements_txt():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "requirements.txt").write_text(
            "# comment\n"
            "requests>=2.28\n"
            "flask[async]==2.3.0\n"
            "-r other.txt\n"
            "pydantic\n"
        )
        deps = collect_dependencies(root)
        names = {d.name for d in deps}
        assert "requests" in names
        assert "flask" in names  # extras stripped
        assert "pydantic" in names
        # flags/comments not included
        assert not any(d.name.startswith("#") for d in deps)
        assert not any(d.name.startswith("-") for d in deps)
        # Check version parsed
        req = next(d for d in deps if d.name == "requests")
        assert "2.28" in req.version
        # source is relative
        assert req.source == "requirements.txt"


def test_parse_package_json():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pkg = {
            "dependencies": {"react": "^18.2.0", "axios": "1.4.0"},
            "devDependencies": {"jest": "^29.0.0"},
            "peerDependencies": {"react-dom": "^18.0.0"},
        }
        (root / "package.json").write_text(json.dumps(pkg))
        deps = collect_dependencies(root)
        names = {d.name for d in deps}
        assert names == {"react", "axios", "jest", "react-dom"}
        react = next(d for d in deps if d.name == "react")
        assert react.version == "^18.2.0"
        assert react.source == "package.json"


def test_parse_go_mod():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "go.mod").write_text(
            "module example.com/mymod\n\n"
            "go 1.21\n\n"
            "require (\n"
            "\tgithub.com/gin-gonic/gin v1.9.1\n"
            "\tgolang.org/x/sync v0.3.0\n"
            ")\n"
        )
        deps = collect_dependencies(root)
        assert len(deps) == 2
        names = {d.name for d in deps}
        assert "github.com/gin-gonic/gin" in names
        gin = next(d for d in deps if "gin" in d.name)
        assert gin.version == "v1.9.1"
        assert gin.source == "go.mod"


def test_parse_no_manifests():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "README.md").write_text("hello")
        deps = collect_dependencies(root)
        assert deps == []


def test_parse_multiple_manifests():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "requirements.txt").write_text("flask==2.3.0\n")
        pkg = {"dependencies": {"express": "^4.18.0"}}
        (root / "package.json").write_text(json.dumps(pkg))
        deps = collect_dependencies(root)
        names = {d.name for d in deps}
        assert "flask" in names
        assert "express" in names
        sources = {d.source for d in deps}
        assert "requirements.txt" in sources
        assert "package.json" in sources


def test_parse_nested_manifests():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        backend = root / "backend"
        backend.mkdir()
        (backend / "requirements.txt").write_text("django>=4.2\n")
        frontend = root / "frontend"
        frontend.mkdir()
        pkg = {"dependencies": {"vue": "^3.3.0"}}
        (frontend / "package.json").write_text(json.dumps(pkg))
        deps = collect_dependencies(root)
        names = {d.name for d in deps}
        assert "django" in names
        assert "vue" in names
        django = next(d for d in deps if d.name == "django")
        assert django.source == "backend/requirements.txt"
        vue = next(d for d in deps if d.name == "vue")
        assert vue.source == "frontend/package.json"

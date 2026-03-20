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


def test_parse_pyproject_toml_pep621():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pyproject.toml").write_text(
            '[project]\n'
            'name = "myapp"\n'
            'dependencies = [\n'
            '    "fastapi>=0.104.0",\n'
            '    "pydantic>=2.5.0",\n'
            '    "requests[security]>=2.28",\n'
            '    "click",\n'
            ']\n'
        )
        deps = collect_dependencies(root)
        names = {d.name for d in deps}
        assert names == {"fastapi", "pydantic", "requests", "click"}
        fastapi = next(d for d in deps if d.name == "fastapi")
        assert "0.104.0" in fastapi.version
        click = next(d for d in deps if d.name == "click")
        assert click.version == ""
        assert fastapi.source == "pyproject.toml"


def test_parse_pyproject_toml_poetry():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pyproject.toml").write_text(
            '[tool.poetry.dependencies]\n'
            'python = "^3.11"\n'
            'django = "^4.2"\n'
            'celery = {version = "^5.3", extras = ["redis"]}\n'
            '\n'
            '[tool.poetry.dev-dependencies]\n'
            'pytest = "^7.4"\n'
        )
        deps = collect_dependencies(root)
        names = {d.name for d in deps}
        # python should be excluded
        assert "python" not in names
        assert names == {"django", "celery", "pytest"}
        django = next(d for d in deps if d.name == "django")
        assert django.version == "^4.2"
        celery = next(d for d in deps if d.name == "celery")
        assert celery.version == "^5.3"
        pytest_dep = next(d for d in deps if d.name == "pytest")
        assert pytest_dep.version == "^7.4"
        assert pytest_dep.source == "pyproject.toml"


def test_parse_pyproject_toml_optional_deps():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pyproject.toml").write_text(
            '[project]\n'
            'name = "mylib"\n'
            'dependencies = ["httpx>=0.24"]\n'
            '\n'
            '[project.optional-dependencies]\n'
            'dev = ["pytest>=7.0", "ruff>=0.1.0"]\n'
            'docs = ["sphinx>=6.0"]\n'
        )
        deps = collect_dependencies(root)
        names = {d.name for d in deps}
        assert names == {"httpx", "pytest", "ruff", "sphinx"}
        sphinx = next(d for d in deps if d.name == "sphinx")
        assert "6.0" in sphinx.version
        assert sphinx.source == "pyproject.toml"

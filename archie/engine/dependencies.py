"""Parse dependency manifests from a repository tree."""
from __future__ import annotations

import json
import os
import re
import tomllib
from pathlib import Path

from archie.engine.models import DependencyEntry

SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}

MANIFEST_NAMES = {"requirements.txt", "package.json", "go.mod", "Cargo.toml", "pyproject.toml"}

MAX_DEPTH = 3


def _find_manifests(root: Path) -> list[Path]:
    """Walk *root* up to MAX_DEPTH levels, skipping SKIP_DIRS."""
    manifests: list[Path] = []
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth >= MAX_DEPTH:
            dirnames.clear()
            continue
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            if fname in MANIFEST_NAMES:
                manifests.append(Path(dirpath) / fname)
    return manifests


def _parse_requirements_txt(path: Path, rel_source: str) -> list[DependencyEntry]:
    entries: list[DependencyEntry] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Strip extras  e.g. requests[security]>=2.0
        m = re.match(r"([A-Za-z0-9_][A-Za-z0-9_.+-]*)(?:\[.*?\])?\s*([><=!~]=?\s*\S+)?", line)
        if m:
            name = m.group(1)
            version = (m.group(2) or "").strip()
            entries.append(DependencyEntry(name=name, version=version, source=rel_source))
    return entries


def _parse_package_json(path: Path, rel_source: str) -> list[DependencyEntry]:
    entries: list[DependencyEntry] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return entries
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        deps = data.get(key)
        if isinstance(deps, dict):
            for name, version in deps.items():
                entries.append(DependencyEntry(name=name, version=str(version), source=rel_source))
    return entries


def _parse_go_mod(path: Path, rel_source: str) -> list[DependencyEntry]:
    entries: list[DependencyEntry] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    # Match require ( ... ) blocks
    for block in re.finditer(r"require\s*\((.*?)\)", text, re.DOTALL):
        for line in block.group(1).splitlines():
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                entries.append(DependencyEntry(name=parts[0], version=parts[1], source=rel_source))
    return entries


def _parse_cargo_toml(path: Path, rel_source: str) -> list[DependencyEntry]:
    entries: list[DependencyEntry] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    # Find [dependencies] and [dev-dependencies] sections
    section_re = re.compile(r"^\[(dev-)?dependencies\]\s*$", re.MULTILINE)
    for m in section_re.finditer(text):
        start = m.end()
        # Section ends at next [header] or EOF
        next_section = re.search(r"^\[", text[start:], re.MULTILINE)
        section_text = text[start: start + next_section.start()] if next_section else text[start:]
        for line in section_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # name = "version"  or  name = { version = "..." }
            kv = re.match(r"([A-Za-z0-9_-]+)\s*=\s*(.*)", line)
            if not kv:
                continue
            name = kv.group(1)
            value = kv.group(2).strip()
            if value.startswith('"') or value.startswith("'"):
                version = value.strip("\"'")
            elif value.startswith("{"):
                vm = re.search(r'version\s*=\s*"([^"]*)"', value)
                version = vm.group(1) if vm else ""
            else:
                version = value
            entries.append(DependencyEntry(name=name, version=version, source=rel_source))
    return entries


def _parse_pep621_dep(spec: str) -> tuple[str, str]:
    """Extract (name, version) from a PEP 621 dependency string like 'fastapi>=0.104.0'."""
    m = re.match(r"([A-Za-z0-9_][A-Za-z0-9_.+-]*)(?:\[.*?\])?\s*([><=!~]=?\s*\S+)?", spec)
    if m:
        return m.group(1), (m.group(2) or "").strip()
    return spec.strip(), ""


def _parse_pyproject_toml(path: Path, rel_source: str) -> list[DependencyEntry]:
    entries: list[DependencyEntry] = []
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return entries

    # PEP 621: [project.dependencies]
    project = data.get("project", {})
    for spec in project.get("dependencies", []):
        if isinstance(spec, str):
            name, version = _parse_pep621_dep(spec)
            entries.append(DependencyEntry(name=name, version=version, source=rel_source))

    # PEP 621: [project.optional-dependencies]
    optional = project.get("optional-dependencies", {})
    if isinstance(optional, dict):
        for specs in optional.values():
            if isinstance(specs, list):
                for spec in specs:
                    if isinstance(spec, str):
                        name, version = _parse_pep621_dep(spec)
                        entries.append(DependencyEntry(name=name, version=version, source=rel_source))

    # Legacy Poetry: [tool.poetry.dependencies]
    tool = data.get("tool", {})
    poetry = tool.get("poetry", {})
    for section_key in ("dependencies", "dev-dependencies"):
        deps = poetry.get(section_key, {})
        if isinstance(deps, dict):
            for name, value in deps.items():
                if name == "python":
                    continue
                if isinstance(value, str):
                    version = value
                elif isinstance(value, dict):
                    version = value.get("version", "")
                else:
                    version = ""
                entries.append(DependencyEntry(name=name, version=version, source=rel_source))

    return entries


_PARSERS = {
    "requirements.txt": _parse_requirements_txt,
    "package.json": _parse_package_json,
    "go.mod": _parse_go_mod,
    "Cargo.toml": _parse_cargo_toml,
    "pyproject.toml": _parse_pyproject_toml,
}


def collect_dependencies(root: Path) -> list[DependencyEntry]:
    """Scan *root* for dependency manifests and return parsed entries."""
    root = root.resolve()
    results: list[DependencyEntry] = []
    for manifest in _find_manifests(root):
        parser = _PARSERS.get(manifest.name)
        if parser is None:
            continue
        rel_source = str(manifest.relative_to(root))
        results.extend(parser(manifest, rel_source))
    return results

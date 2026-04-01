"""Scan assembler — orchestrates all local analysis into a single RawScan."""
from __future__ import annotations

import json
import os
from pathlib import Path

from archie.engine.dependencies import collect_dependencies
from archie.engine.frameworks import detect_frameworks
from archie.engine.hasher import count_tokens, hash_files
from archie.engine.imports import build_import_graph
from archie.engine.models import RawScan
from archie.engine.scanner import scan_directory

ENTRY_POINT_NAMES: set[str] = {
    "main.py", "app.py", "server.py", "index.py", "cli.py", "manage.py",
    "main.ts", "app.ts", "server.ts", "index.ts",
    "main.js", "app.js", "server.js", "index.js",
    "main.go", "main.rs",
}

CONFIG_FILES: list[str] = [
    "docker-compose.yml",
    "docker-compose.yaml",
    "Dockerfile",
    ".gitlab-ci.yml",
    "Makefile",
    "tsconfig.json",
    "pyproject.toml",
    "setup.cfg",
]

CONFIG_DIRS: list[str] = [
    ".github/workflows",
]

MAX_CONFIG_CHARS = 500


def _detect_entry_points(file_tree: list) -> list[str]:
    """Return paths of files whose basename matches a known entry-point name."""
    results: list[str] = []
    for entry in file_tree:
        basename = entry.path.rsplit("/", 1)[-1] if "/" in entry.path else entry.path
        if basename in ENTRY_POINT_NAMES:
            results.append(entry.path)
    results.sort()
    return results


def _collect_config_patterns(repo_path: Path) -> dict[str, str]:
    """Read first MAX_CONFIG_CHARS of known config files."""
    patterns: dict[str, str] = {}

    # Individual config files
    for name in CONFIG_FILES:
        full = repo_path / name
        if full.is_file():
            try:
                text = full.read_text(encoding="utf-8", errors="replace")[:MAX_CONFIG_CHARS]
                patterns[name] = text
            except OSError:
                continue

    # Config directories (e.g. .github/workflows)
    for dir_name in CONFIG_DIRS:
        full_dir = repo_path / dir_name
        if full_dir.is_dir():
            try:
                for fname in sorted(os.listdir(full_dir)):
                    fpath = full_dir / fname
                    if fpath.is_file():
                        try:
                            text = fpath.read_text(encoding="utf-8", errors="replace")[:MAX_CONFIG_CHARS]
                            patterns[f"{dir_name}/{fname}"] = text
                        except OSError:
                            continue
            except OSError:
                continue

    return patterns


def _build_directory_structure(file_tree: list) -> dict[str, list[str]]:
    """Build a mapping of directory -> list of filenames."""
    structure: dict[str, list[str]] = {}
    for entry in file_tree:
        if "/" in entry.path:
            dir_part, file_part = entry.path.rsplit("/", 1)
        else:
            dir_part, file_part = ".", entry.path
        structure.setdefault(dir_part, []).append(file_part)
    for key in structure:
        structure[key].sort()
    return structure


def run_scan(repo_path: Path, save: bool = False) -> RawScan:
    """Orchestrate all local analysis steps and return a RawScan.

    Parameters
    ----------
    repo_path:
        Root directory of the repository to scan.
    save:
        If True, write the result to ``.archie/scan.json`` inside *repo_path*.
    """
    repo_path = Path(repo_path).resolve()

    # 1. File tree
    file_tree = scan_directory(repo_path)

    # 2. Dependencies
    dependencies = collect_dependencies(repo_path)

    # 3. Framework detection
    framework_signals = detect_frameworks(file_tree, dependencies)

    # 4. File hashes
    file_hashes = hash_files(repo_path, file_tree)

    # 5. Token counts
    token_counts = count_tokens(repo_path, file_tree)

    # 6. Import graph
    import_graph = build_import_graph(file_tree, repo_path)

    # 7. Entry points
    entry_points = _detect_entry_points(file_tree)

    # 8. Config patterns
    config_patterns = _collect_config_patterns(repo_path)

    # 9. Directory structure
    directory_structure = _build_directory_structure(file_tree)

    # 10. Assemble
    raw_scan = RawScan(
        file_tree=file_tree,
        token_counts=token_counts,
        dependencies=dependencies,
        framework_signals=framework_signals,
        config_patterns=config_patterns,
        import_graph=import_graph,
        directory_structure=directory_structure,
        file_hashes=file_hashes,
        entry_points=entry_points,
    )

    # 11. Optionally persist
    if save:
        archie_dir = repo_path / ".archie"
        archie_dir.mkdir(parents=True, exist_ok=True)
        scan_file = archie_dir / "scan.json"
        scan_file.write_text(
            json.dumps(raw_scan.model_dump(), indent=2),
            encoding="utf-8",
        )

    return raw_scan

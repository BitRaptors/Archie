#!/usr/bin/env python3
"""Archie link-store — resolves the external artifact store and its manifests.

Zero dependencies beyond Python 3.9+ stdlib. The store lives OUTSIDE the repo
so the working tree stays clean; only `.archie-link.json` is committed.
"""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
from pathlib import Path

LINK_FILENAME = ".archie-link.json"

DEFAULT_EXPOSURE = {
    "schema_version": 1,
    # Only agent-readable artifacts are gateable. `.archie/` raw data is
    # infrastructure (tooling + hooks + JSON the agent never reads directly)
    # and is always exposed — see linker.INFRASTRUCTURE_PATHS.
    "categories": {
        "rules": True,
        "folder_context": True,
    },
    "overrides": {},
}


def archie_home() -> Path:
    env = os.environ.get("ARCHIE_HOME")
    if env:
        return Path(env).expanduser()
    if sys.platform.startswith("win"):
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "archie"
    return Path.home() / ".archie"


def project_store(project_id: str) -> Path:
    return archie_home() / "projects" / project_id


def _atomic_write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".tmp.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=2))
            f.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _read_json(path: Path, default):
    if not path.exists():
        return copy.deepcopy(default)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return copy.deepcopy(default)


def read_link_file(repo: Path) -> dict | None:
    path = repo / LINK_FILENAME
    if not path.exists():
        return None
    return _read_json(path, None)


def write_link_file(repo: Path, data: dict) -> None:
    _atomic_write(repo / LINK_FILENAME, data)


def read_exposure(store: Path) -> dict:
    return _read_json(store / "exposure.json", DEFAULT_EXPOSURE)


def write_exposure(store: Path, data: dict) -> None:
    _atomic_write(store / "exposure.json", data)


def read_placements(store: Path) -> list:
    return _read_json(store / "placements.json", [])


def write_placements(store: Path, items: list) -> None:
    _atomic_write(store / "placements.json", items)

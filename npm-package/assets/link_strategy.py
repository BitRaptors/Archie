#!/usr/bin/env python3
"""Archie link-strategy — OS-specific presentation of external artifacts.

The external store is always the source of truth; this module decides HOW it
surfaces in the working tree (POSIX symlink, NTFS junction, or copy fallback)
and enforces the safety invariant: never remove a file we did not place.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def strategy_for(kind: str) -> str:
    """kind: 'dir' or 'file'. Returns 'symlink' | 'junction' | 'copy'."""
    if not sys.platform.startswith("win"):
        return "symlink"
    if kind == "dir":
        return "junction"
    if os.environ.get("ARCHIE_FORCE_SYMLINK") == "1":
        return "symlink"
    return "copy"


def _remove_existing(link_path: Path) -> None:
    if link_path.is_symlink() or link_path.exists():
        if link_path.is_dir() and not link_path.is_symlink():
            shutil.rmtree(link_path)
        else:
            link_path.unlink()


def create_link(target: Path, link_path: Path, kind: str) -> str:
    """Create the presentation of `target` at `link_path`. Returns strategy used.

    kind: 'dir' | 'file' resolves via strategy_for; 'file_copy' forces copy.
    """
    link_path.parent.mkdir(parents=True, exist_ok=True)
    _remove_existing(link_path)

    strategy = "copy" if kind == "file_copy" else strategy_for(kind)
    if strategy == "symlink":
        is_dir = kind == "dir"
        os.symlink(target, link_path, target_is_directory=is_dir)
    elif strategy == "junction":
        import _winapi  # Windows only
        _winapi.CreateJunction(str(target), str(link_path))
    else:  # copy
        if target.is_dir():
            shutil.copytree(target, link_path)
        else:
            shutil.copyfile(target, link_path)
    return strategy


def is_managed(link_path: Path, store: Path) -> bool:
    if not link_path.is_symlink() and not link_path.exists():
        return False
    if not link_path.is_symlink():
        # Junctions on Windows resolve but aren't is_symlink(); fall through to
        # the resolve check for them. A plain real file is NOT managed.
        if not sys.platform.startswith("win"):
            return False
    try:
        resolved = link_path.resolve()
        store_resolved = store.resolve()
        return str(resolved).startswith(str(store_resolved))
    except OSError:
        return False


def remove_managed(link_path: Path, store: Path, strategy: str,
                   target: Path | None = None) -> bool:
    """Remove link_path only if it is provably ours. Returns True if removed.

    symlink/junction: the link must resolve inside the store.
    copy: the in-tree file must still byte-match the store source (`target`).
      A user edit or a foreign file with the same path no longer matches, so it
      is preserved — upholding "never delete a file we did not place" even for
      the Windows copy fallback where there is no link to verify.
    """
    if strategy in {"symlink", "junction"}:
        if not is_managed(link_path, store):
            return False
        try:
            link_path.unlink()
            return True
        except OSError:
            return False
    if strategy == "copy":
        if not (link_path.is_file() and not link_path.is_dir()):
            return False
        if target is None or not Path(target).exists():
            return False  # cannot prove ownership → refuse
        try:
            if link_path.read_bytes() != Path(target).read_bytes():
                return False  # modified or foreign — preserve it
            link_path.unlink()
            return True
        except OSError:
            return False
    return False

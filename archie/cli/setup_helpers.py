"""Shared helpers for materializing a project's `.archie/` directory.

Every code path that creates `.archie/` must write the tool-managed
`.gitignore` so Archie's vendored internals + install-only scripts are never
committed into the host repo. Centralized here so no path forgets it.
(The npx installer writes the same asset itself, in `npm-package/bin/archie.mjs`.)
"""
from __future__ import annotations

from pathlib import Path


def write_archie_gitignore(archie_dir: Path) -> None:
    """Write `.archie/.gitignore` from the bundled `assets/gitignore.default`.

    Idempotent and best-effort: never raises, so it can't break a setup path.
    """
    try:
        src = Path(__file__).resolve().parent.parent / "assets" / "gitignore.default"
        if src.exists():
            (archie_dir / ".gitignore").write_text(src.read_text())
    except OSError:
        pass

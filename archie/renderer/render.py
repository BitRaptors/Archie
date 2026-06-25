"""Renderer adapter — bridges archie CLI to standalone renderer."""
from __future__ import annotations

from pathlib import Path


def render_outputs(blueprint_dict: dict, project_root: Path) -> dict[str, str]:
    """Render all output files from a blueprint dict.

    Returns a dict of {relative_path: content} for all generated files.
    Also writes them to disk under project_root.
    """
    from archie.standalone.renderer import (
        generate_all,
        render_mergeable,
        MERGEABLE_FILES,
    )
    from archie.renderer.intent_layer import generate_folder_context

    files: dict[str, str] = generate_all(blueprint_dict)

    # Per-folder CLAUDE.md files
    scan_path = project_root / ".archie" / "scan.json"
    if scan_path.exists():
        folder_files = generate_folder_context(blueprint_dict, scan_path)
        files.update(folder_files)

    # Write all files to disk. The root CLAUDE.md / AGENTS.md may coexist with
    # hand-authored content, so route them through render_mergeable — it owns
    # only the block between Archie's markers and preserves everything outside
    # it. Everything else is fully Archie-owned → plain write. (A blind
    # write_text here used to clobber a project's hand-written root CLAUDE.md.)
    written: dict[str, str] = {}
    for rel_path, content in files.items():
        full_path = project_root / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        if rel_path in MERGEABLE_FILES:
            content = render_mergeable(full_path, content)
        full_path.write_text(content)
        written[rel_path] = content

    return written

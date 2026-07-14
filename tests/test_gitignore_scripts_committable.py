"""Tests that the installer no longer gitignores .archie/*.py.

The delivery-review CI workflow reads delivery_review.py (and its siblings)
from the BASE ref. That requires the scripts to be committed. The archieGitignoreBlock
written into the root .gitignore must NOT contain a bare `.archie/*.py` ignore
line (with or without a leading slash).
"""
from __future__ import annotations

import re
from pathlib import Path


_ARCHIE_MJS = Path(__file__).resolve().parent.parent / "npm-package" / "bin" / "archie.mjs"


def _read_archie_mjs() -> str:
    return _ARCHIE_MJS.read_text(encoding="utf-8")


def test_archie_gitignore_block_does_not_ignore_py_scripts() -> None:
    """archieGitignoreBlock must NOT include a bare .archie/*.py ignore line."""
    src = _read_archie_mjs()

    # Extract the archieGitignoreBlock template string.
    # It is assigned as a template literal or a plain string on one logical line.
    match = re.search(r'archieGitignoreBlock\s*=\s*`([^`]*)`', src, re.DOTALL)
    assert match, "Could not locate archieGitignoreBlock in archie.mjs"

    block = match.group(1)

    # Check that there's no bare .archie/*.py ignore line (with or without
    # a leading slash).
    bare_py_ignore = re.search(r'^\/?\.archie/\*\.py\s*$', block, re.MULTILINE)
    assert bare_py_ignore is None, (
        "archieGitignoreBlock still contains a bare '.archie/*.py' ignore line. "
        "Remove it so .archie/*.py scripts are committed and CI can read them "
        "from the base ref.\n"
        f"Matched: {bare_py_ignore.group() if bare_py_ignore else ''!r}"
    )


def test_archie_gitignore_block_still_ignores_pycache() -> None:
    """.archie/__pycache__/ must remain gitignored."""
    src = _read_archie_mjs()
    match = re.search(r'archieGitignoreBlock\s*=\s*`([^`]*)`', src, re.DOTALL)
    assert match, "Could not locate archieGitignoreBlock in archie.mjs"
    block = match.group(1)
    assert ".archie/__pycache__/" in block, (
        ".archie/__pycache__/ should remain in the gitignore block"
    )

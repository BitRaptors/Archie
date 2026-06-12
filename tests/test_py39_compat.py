"""Guard: every shipped .py must import on Python 3.9 (the documented floor).

The macOS-bundled /usr/bin/python3 is 3.9.6, and `npx @bitraptors/archie`
drives the connector install loop with whatever `python3` is on PATH. A PEP 604
union (`str | None`) in a class body or function signature is EVALUATED at
import time unless the module has `from __future__ import annotations` — on
3.9 that raises TypeError and the install dies before writing any CLI shim
(the v2.7.0–v2.9.0 regression: ConfigPatch.section in manifest.py).

py_compile can't catch this (it's a runtime error, not a syntax error), and CI
may not have a 3.9 interpreter — so this test walks the AST instead: any
annotation containing `X | Y` in a module without the future import fails.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Everything that ships to user machines and runs under the user's python3.
SHIPPED_GLOBS = [
    ("archie/standalone", "*.py"),
    ("archie", "manifest.py"),
    ("archie", "manifest_data.py"),
    ("archie", "install.py"),
    ("archie/connectors", "*.py"),
    ("npm-package/assets", "*.py"),
    ("npm-package/assets/_install_pkg", "*.py"),
    ("npm-package/assets/_install_pkg/connectors", "*.py"),
]


def _shipped_files() -> list[Path]:
    files: set[Path] = set()
    for rel, pattern in SHIPPED_GLOBS:
        base = ROOT / rel
        if base.is_dir():
            files.update(base.glob(pattern))
    return sorted(f for f in files if f.name != "__init__.py" or f.stat().st_size > 0)


def _has_future_annotations(tree: ast.Module) -> bool:
    return any(
        isinstance(node, ast.ImportFrom)
        and node.module == "__future__"
        and any(a.name == "annotations" for a in node.names)
        for node in tree.body
    )


def _union_annotations(tree: ast.Module) -> list[int]:
    """Line numbers of annotations containing a `|` union (BinOp BitOr)."""

    def contains_bitor(node: ast.AST) -> bool:
        return any(
            isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr)
            for n in ast.walk(node)
        )

    lines: list[int] = []
    for node in ast.walk(tree):
        annotation = None
        if isinstance(node, ast.AnnAssign):
            annotation = node.annotation
        elif isinstance(node, ast.arg) and node.annotation is not None:
            annotation = node.annotation
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns is not None:
            annotation = node.returns
        if annotation is not None and contains_bitor(annotation):
            lines.append(annotation.lineno)
    return lines


@pytest.mark.parametrize("path", _shipped_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_runtime_union_annotations_without_future_import(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    if _has_future_annotations(tree):
        return  # lazy annotations — unions are never evaluated, 3.9-safe
    lines = _union_annotations(tree)
    assert not lines, (
        f"{path.relative_to(ROOT)} uses `X | Y` annotations at lines {lines} "
        "without `from __future__ import annotations` — this raises TypeError "
        "at import time on Python 3.9 (the macOS system python3) and kills the "
        "npx install loop. Add the future import."
    )

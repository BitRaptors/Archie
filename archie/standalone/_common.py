"""Archie shared utilities — imported by other standalone scripts.

Deduplicates helpers that were copy-pasted across 6+ files.

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path


# ── Shared constants ──────────────────────────────────────────────────────

SOURCE_EXTENSIONS = {
    ".py", ".kt", ".kts", ".java", ".js", ".jsx", ".ts", ".tsx",
    ".swift", ".go", ".rs", ".rb", ".c", ".cpp", ".cc", ".cxx", ".h",
    ".hpp", ".cs", ".php", ".scala", ".m", ".mm",
}

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", ".next", ".nuxt", ".svelte-kit",
    "coverage", ".nyc_output", ".turbo", ".parcel-cache",
    "vendor", "Pods", ".gradle", ".idea", ".vscode",
    ".archie", ".claude", ".cursor",
}

# Regex decision-point patterns for non-Python languages.
# NOTE: bare ``else`` is intentionally excluded — it is NOT a decision point
# in cyclomatic complexity (it's the default path, not an independent one).
DECISION_RE = re.compile(
    r"""(?x)
    \b(?:if|elif|else\s+if|elseif|for|foreach|while|do\b.*\bwhile|
        switch|case|catch|except|when|guard)\b
    | \?\s*[^?]     # ternary  ?:
    | &&             # logical AND
    | \|\|           # logical OR
    """
)


# ── Shared helpers ────────────────────────────────────────────────────────

def _load_json(path: Path) -> dict | list:
    """Load a JSON file, returning empty dict on failure."""
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _read_file(path: str) -> str | None:
    """Read a file, returning None on failure."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


# ── Cyclomatic complexity ─────────────────────────────────────────────────

def _cc_python_function(source: str, func_start: int, func_end: int) -> int:
    """Compute cyclomatic complexity of a Python function via AST."""
    lines = source.splitlines(True)
    func_lines = lines[func_start - 1 : func_end]
    if not func_lines:
        return 1

    # Dedent to column 0 so ast.parse works
    min_indent = 9999
    for ln in func_lines:
        stripped = ln.rstrip("\n\r")
        if stripped.strip():
            indent = len(stripped) - len(stripped.lstrip())
            min_indent = min(min_indent, indent)
    if min_indent == 9999:
        min_indent = 0

    dedented = "".join(ln[min_indent:] if len(ln) > min_indent else ln for ln in func_lines)

    try:
        tree = ast.parse(dedented, mode="exec")
    except SyntaxError:
        return 1

    cc = 1
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.Assert)):
            cc += 1
        elif isinstance(node, ast.BoolOp):
            cc += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            cc += 1
            cc += len(node.ifs)
    return cc


def _cc_regex(lines: list[str]) -> int:
    """Approximate cyclomatic complexity via regex for non-Python files."""
    cc = 1
    for line in lines:
        cleaned = re.sub(r'"(?:[^"\\]|\\.)*"', '""', line)
        cleaned = re.sub(r"'(?:[^'\\]|\\.)*'", "''", cleaned)
        cc += len(DECISION_RE.findall(cleaned))
    return cc

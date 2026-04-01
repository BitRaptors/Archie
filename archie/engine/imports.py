"""Import graph builder for Python and JS/TS source files."""
from __future__ import annotations

import ast
import re
from pathlib import Path

from archie.engine.models import FileEntry

# Common Python stdlib module names (quick heuristic, not exhaustive).
_STDLIB_TOP_LEVEL: set[str] = {
    "abc", "argparse", "ast", "asyncio", "base64", "builtins", "calendar",
    "cmath", "cmd", "codecs", "collections", "colorsys", "configparser",
    "contextlib", "copy", "csv", "ctypes", "dataclasses", "datetime",
    "decimal", "difflib", "dis", "email", "enum", "errno", "faulthandler",
    "fileinput", "fnmatch", "fractions", "ftplib", "functools", "gc",
    "getpass", "gettext", "glob", "gzip", "hashlib", "heapq", "hmac",
    "html", "http", "imaplib", "importlib", "inspect", "io", "ipaddress",
    "itertools", "json", "keyword", "linecache", "locale", "logging",
    "lzma", "mailbox", "math", "mimetypes", "mmap", "multiprocessing",
    "numbers", "operator", "os", "pathlib", "pickle", "pkgutil", "platform",
    "plistlib", "poplib", "posixpath", "pprint", "profile", "pstats",
    "py_compile", "queue", "random", "re", "readline", "reprlib",
    "resource", "sched", "secrets", "select", "shelve", "shlex", "shutil",
    "signal", "site", "smtplib", "socket", "socketserver", "sqlite3",
    "ssl", "stat", "statistics", "string", "struct", "subprocess", "sys",
    "sysconfig", "syslog", "tarfile", "tempfile", "test", "textwrap",
    "threading", "time", "timeit", "tkinter", "token", "tokenize",
    "tomllib", "trace", "traceback", "tracemalloc", "tty", "turtle",
    "types", "typing", "unicodedata", "unittest", "urllib", "uuid",
    "venv", "warnings", "wave", "weakref", "webbrowser", "xml",
    "xmlrpc", "zipfile", "zipimport", "zlib",
}

# Regex patterns for JS/TS imports.
_JS_IMPORT_FROM_RE = re.compile(
    r"""import\s+(?:.*?)\s+from\s+['"]([^'"]+)['"]""",
)
_JS_REQUIRE_RE = re.compile(
    r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""",
)

_JS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs"}


def _is_stdlib(module_name: str) -> bool:
    """Return True if *module_name* looks like a Python stdlib module."""
    top = module_name.split(".")[0]
    return top in _STDLIB_TOP_LEVEL


def _extract_python_imports(path: Path) -> list[str]:
    """Parse a Python file and return internal-looking import strings."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return []

    if not source.strip():
        return []

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if "." in node.module and not _is_stdlib(node.module):
                imports.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if "." in alias.name and not _is_stdlib(alias.name):
                    imports.append(alias.name)
    return imports


def _extract_js_imports(path: Path) -> list[str]:
    """Parse a JS/TS file and return relative import strings."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return []

    if not source.strip():
        return []

    imports: list[str] = []
    for match in _JS_IMPORT_FROM_RE.finditer(source):
        specifier = match.group(1)
        if specifier.startswith("."):
            imports.append(specifier)
    for match in _JS_REQUIRE_RE.finditer(source):
        specifier = match.group(1)
        if specifier.startswith("."):
            imports.append(specifier)
    return imports


def build_import_graph(
    file_entries: list[FileEntry],
    repo_root: Path,
) -> dict[str, list[str]]:
    """Build a mapping of file path -> list of imported module/path strings.

    Only source files (.py, .js, .jsx, .ts, .tsx, .mjs) are processed.
    """
    graph: dict[str, list[str]] = {}

    for entry in file_entries:
        full_path = repo_root / entry.path
        ext = Path(entry.path).suffix

        if ext == ".py":
            imports = _extract_python_imports(full_path)
        elif ext in _JS_EXTENSIONS:
            imports = _extract_js_imports(full_path)
        else:
            continue

        if imports:
            graph[entry.path] = imports

    return graph

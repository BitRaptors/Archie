#!/usr/bin/env python3
"""Archie standalone scanner — zero dependencies beyond Python 3.11+ stdlib.

Run: python3 scanner.py /path/to/repo
Output: JSON to stdout (the RawScan equivalent)

This script is designed to be copy-pasted or downloaded into any project.
It does NOT require pip install, pydantic, tiktoken, or any third-party package.
"""
import ast
import hashlib
import json
import os
import re
import sys
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", ".next", ".nuxt", ".svelte-kit",
    "coverage", ".nyc_output", ".turbo", ".parcel-cache",
    "vendor", "Pods", ".gradle", ".idea", ".vscode",
    ".archie", ".claude", ".cursor",
}

SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".bmp",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".webm",
    ".zip", ".tar", ".gz", ".bz2", ".rar", ".7z",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe",
    ".lock", ".sum",
}

ALLOWED_DOTFILES = {".env.example", ".gitignore", ".dockerignore", ".editorconfig"}

# ── File Scanner ───────────────────────────────────────────────────────────

def scan_files(root: Path) -> list[dict]:
    entries = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext in SKIP_EXTENSIONS:
                continue
            if fname.startswith(".") and fname not in ALLOWED_DOTFILES:
                continue
            full = Path(dirpath) / fname
            try:
                stat = full.stat()
            except OSError:
                continue
            entries.append({
                "path": str(full.relative_to(root)),
                "size": stat.st_size,
                "extension": ext,
            })
    return sorted(entries, key=lambda e: e["path"])


# ── Dependency Parser ──────────────────────────────────────────────────────

def parse_dependencies(root: Path) -> list[dict]:
    deps = []
    for dirpath, dirnames, filenames in os.walk(root):
        depth = str(Path(dirpath).relative_to(root)).count(os.sep)
        if depth >= 3:
            dirnames.clear()
            continue
        dirnames[:] = [d for d in dirnames if d not in {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}]

        for fname in filenames:
            full = Path(dirpath) / fname
            rel = str(full.relative_to(root))
            try:
                content = full.read_text(errors="ignore")
            except OSError:
                continue

            if fname == "requirements.txt":
                deps.extend(_parse_requirements(content, rel))
            elif fname == "package.json":
                deps.extend(_parse_package_json(content, rel))
            elif fname == "go.mod":
                deps.extend(_parse_go_mod(content, rel))
            elif fname == "pyproject.toml":
                deps.extend(_parse_pyproject_toml(content, rel))
    return deps


def _parse_requirements(content: str, source: str) -> list[dict]:
    entries = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        match = re.match(r"^([a-zA-Z0-9_-]+)(?:\[.*?\])?\s*(.*)", line)
        if match:
            entries.append({"name": match.group(1), "version": match.group(2).strip(), "source": source})
    return entries


def _parse_package_json(content: str, source: str) -> list[dict]:
    entries = []
    try:
        pkg = json.loads(content)
    except json.JSONDecodeError:
        return entries
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        for name, ver in pkg.get(key, {}).items():
            entries.append({"name": name, "version": ver, "source": source})
    return entries


def _parse_go_mod(content: str, source: str) -> list[dict]:
    entries = []
    in_req = False
    for line in content.splitlines():
        s = line.strip()
        if s.startswith("require ("):
            in_req = True
            continue
        if in_req:
            if s == ")":
                in_req = False
                continue
            parts = s.split()
            if len(parts) >= 2:
                entries.append({"name": parts[0], "version": parts[1], "source": source})
    return entries


def _parse_pyproject_toml(content: str, source: str) -> list[dict]:
    """Parse pyproject.toml without tomllib — regex-based for broad compat."""
    entries = []
    # PEP 621: dependencies = ["fastapi>=0.104.0", ...]
    dep_match = re.search(r'dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
    if dep_match:
        for item in re.findall(r'"([^"]+)"', dep_match.group(1)):
            match = re.match(r'^([a-zA-Z0-9_-]+)(?:\[.*?\])?\s*(.*)', item)
            if match:
                entries.append({"name": match.group(1), "version": match.group(2).strip(), "source": source})
    return entries


# ── Framework Detector ─────────────────────────────────────────────────────

DEP_SIGNALS = {
    "fastapi": "FastAPI", "django": "Django", "flask": "Flask",
    "next": "Next.js", "react": "React", "vue": "Vue.js",
    "nuxt": "Nuxt.js", "angular": "Angular", "svelte": "Svelte",
    "express": "Express", "nestjs": "NestJS",
    "spring-boot-starter-web": "Spring Boot",
    "gin-gonic/gin": "Gin", "gofiber/fiber": "Fiber",
}

FILE_SIGNALS = {
    "next.config.js": "Next.js", "next.config.ts": "Next.js", "next.config.mjs": "Next.js",
    "nuxt.config.ts": "Nuxt.js", "angular.json": "Angular", "svelte.config.js": "Svelte",
    "manage.py": "Django", "pubspec.yaml": "Flutter", "Cargo.toml": "Rust", "go.mod": "Go",
    "docker-compose.yml": "Docker", "docker-compose.yaml": "Docker", "Dockerfile": "Docker",
    "tailwind.config.js": "Tailwind CSS", "tailwind.config.ts": "Tailwind CSS",
    "build.gradle": "Android/Gradle", "build.gradle.kts": "Android/Gradle",
    "settings.gradle": "Android/Gradle", "settings.gradle.kts": "Android/Gradle",
    "AndroidManifest.xml": "Android",
    "Podfile": "iOS/CocoaPods", "Package.swift": "Swift",
}


def detect_frameworks(files: list[dict], deps: list[dict]) -> list[dict]:
    seen = {}
    for dep in deps:
        key = dep["name"].lower()
        if key in DEP_SIGNALS:
            name = DEP_SIGNALS[key]
            if name not in seen:
                seen[name] = {"name": name, "version": dep.get("version", ""), "evidence": []}
            seen[name]["evidence"].append(f"dep:{dep['name']}")

    for f in files:
        fname = f["path"].rsplit("/", 1)[-1] if "/" in f["path"] else f["path"]
        if fname in FILE_SIGNALS:
            name = FILE_SIGNALS[fname]
            if name not in seen:
                seen[name] = {"name": name, "version": "", "evidence": []}
            seen[name]["evidence"].append(f"file:{f['path']}")

    return sorted(seen.values(), key=lambda s: s["name"])


# ── Import Graph ───────────────────────────────────────────────────────────

PYTHON_EXTS = {".py"}
JS_EXTS = {".js", ".jsx", ".ts", ".tsx", ".mjs"}
KOTLIN_EXTS = {".kt", ".kts"}
JAVA_EXTS = {".java"}
SWIFT_EXTS = {".swift"}

JS_IMPORT_RE = re.compile(r"""(?:import\s+.*?from\s+['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\))""")
KOTLIN_IMPORT_RE = re.compile(r'^import\s+([\w.]+)', re.MULTILINE)
JAVA_IMPORT_RE = re.compile(r'^import\s+(?:static\s+)?([\w.]+)', re.MULTILINE)
SWIFT_IMPORT_RE = re.compile(r'^import\s+(\w+)', re.MULTILINE)

STDLIB_MODULES = {
    "os", "sys", "re", "json", "ast", "math", "time", "datetime",
    "pathlib", "typing", "collections", "functools", "itertools",
    "hashlib", "io", "abc", "dataclasses", "enum", "logging",
    "unittest", "tempfile", "shutil", "subprocess", "threading",
    "asyncio", "concurrent", "contextlib", "copy", "csv",
    "http", "urllib", "email", "html", "xml", "sqlite3",
    "socket", "ssl", "struct", "textwrap", "traceback",
    "uuid", "warnings", "weakref", "zipfile", "gzip", "tomllib",
}


def build_import_graph(root: Path, files: list[dict]) -> dict[str, list[str]]:
    graph = {}
    for f in files:
        ext = f.get("extension", "")
        path = root / f["path"]
        imports = []

        if ext in PYTHON_EXTS:
            imports = _python_imports(path)
        elif ext in JS_EXTS:
            imports = _js_imports(path)
        elif ext in KOTLIN_EXTS:
            imports = _regex_imports(path, KOTLIN_IMPORT_RE)
        elif ext in JAVA_EXTS:
            imports = _regex_imports(path, JAVA_IMPORT_RE)
        elif ext in SWIFT_EXTS:
            imports = _regex_imports(path, SWIFT_IMPORT_RE)

        if imports:
            graph[f["path"]] = imports
    return graph


def _python_imports(path: Path) -> list[str]:
    try:
        source = path.read_text(errors="ignore")
    except OSError:
        return []
    if not source.strip():
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return [i for i in imports if "." in i and i.split(".")[0] not in STDLIB_MODULES]


def _js_imports(path: Path) -> list[str]:
    try:
        source = path.read_text(errors="ignore")
    except OSError:
        return []
    return [m.group(1) or m.group(2) for m in JS_IMPORT_RE.finditer(source) if (m.group(1) or m.group(2)).startswith(".")]


def _regex_imports(path: Path, pattern: re.Pattern) -> list[str]:
    try:
        source = path.read_text(errors="ignore")
    except OSError:
        return []
    return pattern.findall(source)


# ── File Hasher ────────────────────────────────────────────────────────────

def hash_files(root: Path, files: list[dict]) -> dict[str, str]:
    hashes = {}
    for f in files:
        try:
            content = (root / f["path"]).read_bytes()
            hashes[f["path"]] = hashlib.sha256(content).hexdigest()
        except OSError:
            pass
    return hashes


# ── Token Estimator (no tiktoken needed) ───────────────────────────────────

def estimate_tokens(root: Path, files: list[dict]) -> dict[str, int]:
    """Estimate tokens using ~4 chars per token heuristic. No dependencies."""
    counts = {}
    for f in files:
        if f["size"] > 1_000_000:
            continue
        try:
            content = (root / f["path"]).read_text(errors="ignore")
            counts[f["path"]] = max(1, len(content) // 4) if content else 0
        except OSError:
            pass
    return counts


# ── Entry Points ───────────────────────────────────────────────────────────

ENTRY_POINT_NAMES = {
    "main.py", "app.py", "server.py", "index.py", "cli.py", "manage.py",
    "main.ts", "app.ts", "server.ts", "index.ts",
    "main.js", "app.js", "server.js", "index.js",
    "main.go", "main.rs", "main.kt", "Main.kt", "Application.kt",
    "MainActivity.kt", "App.tsx", "App.jsx", "App.vue",
    "Main.java", "Application.java", "AppDelegate.swift", "main.swift",
}


def detect_entry_points(files: list[dict]) -> list[str]:
    return [f["path"] for f in files if f["path"].rsplit("/", 1)[-1] in ENTRY_POINT_NAMES]


# ── Config Collector ───────────────────────────────────────────────────────

CONFIG_FILES = [
    "docker-compose.yml", "docker-compose.yaml", "Dockerfile",
    "Makefile", "tsconfig.json", "pyproject.toml", "setup.cfg",
    "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts",
    "AndroidManifest.xml", "Podfile", "Package.swift",
    ".github/workflows", ".gitlab-ci.yml",
]


def collect_configs(root: Path) -> dict[str, str]:
    configs = {}
    for name in CONFIG_FILES:
        path = root / name
        if path.is_file():
            try:
                configs[name] = path.read_text(errors="ignore")[:500]
            except OSError:
                pass
    return configs


# ── Main Scanner ───────────────────────────────────────────────────────────

def run_scan(repo_path: str) -> dict:
    root = Path(repo_path).resolve()

    files = scan_files(root)
    deps = parse_dependencies(root)
    frameworks = detect_frameworks(files, deps)
    hashes = hash_files(root, files)
    tokens = estimate_tokens(root, files)
    imports = build_import_graph(root, files)
    entry_points = detect_entry_points(files)
    configs = collect_configs(root)

    return {
        "file_tree": files,
        "token_counts": tokens,
        "dependencies": deps,
        "framework_signals": frameworks,
        "config_patterns": configs,
        "import_graph": imports,
        "file_hashes": hashes,
        "entry_points": entry_points,
    }


# ── CLI Entry Point ───────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scanner.py /path/to/repo", file=sys.stderr)
        sys.exit(1)

    repo = sys.argv[1]
    if not Path(repo).is_dir():
        print(f"Error: {repo} is not a directory", file=sys.stderr)
        sys.exit(1)

    scan = run_scan(repo)

    # Save to .archie/scan.json
    archie_dir = Path(repo) / ".archie"
    archie_dir.mkdir(exist_ok=True)
    out_path = archie_dir / "scan.json"
    out_path.write_text(json.dumps(scan, indent=2))

    # Print summary to stderr, JSON to stdout
    total_tokens = sum(scan["token_counts"].values())
    fw_names = ", ".join(f["name"] for f in scan["framework_signals"]) or "none detected"
    print(f"Scanned: {len(scan['file_tree'])} files", file=sys.stderr)
    print(f"Frameworks: {fw_names}", file=sys.stderr)
    print(f"Dependencies: {len(scan['dependencies'])}", file=sys.stderr)
    print(f"Tokens (est): {total_tokens:,}", file=sys.stderr)
    print(f"Saved to: {out_path}", file=sys.stderr)

    # Output JSON to stdout
    json.dump(scan, sys.stdout, indent=2)

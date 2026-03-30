#!/usr/bin/env python3
"""Archie standalone scanner — zero dependencies beyond Python 3.9+ stdlib.

Run: python3 scanner.py /path/to/repo
Output: JSON to stdout (the RawScan equivalent)

This script is designed to be copy-pasted or downloaded into any project.
It does NOT require pip install, pydantic, tiktoken, or any third-party package.
"""
from __future__ import annotations

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
    "dist", "build", ".build", ".next", ".nuxt", ".svelte-kit",
    "coverage", ".nyc_output", ".turbo", ".parcel-cache",
    "vendor", "Pods", "DerivedData", ".gradle", ".idea", ".vscode",
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

# ── Sub-project Detection ─────────────────────────────────────────────────

# Build file → project type mapping
SUBPROJECT_SIGNALS = {
    "build.gradle": "android/jvm",
    "build.gradle.kts": "android/jvm",
    "AndroidManifest.xml": "android",
    "package.json": "node",
    "pyproject.toml": "python",
    "setup.py": "python",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "pubspec.yaml": "flutter",
    "Podfile": "ios",
    "pom.xml": "java",
}

# Extension-based signals (matched via glob)
SUBPROJECT_EXT_SIGNALS = {
    ".xcodeproj": "ios",
    ".xcworkspace": "ios",
    ".csproj": "dotnet",
    ".sln": "dotnet",
}

# Dirs to skip during sub-project detection (superset of SKIP_DIRS)
SUBPROJECT_SKIP_DIRS = SKIP_DIRS | {
    "node_modules", "Pods", "build", ".gradle", "DerivedData",
    "storage", "fixtures", "testdata", "test_data", "__fixtures__",
}


def _detect_workspace_modules(root: Path) -> set[str]:
    """Detect directories that are declared modules of a root workspace/project.

    These are sub-modules of a single project, NOT independent sub-projects.
    Examples: Gradle include(":app"), npm workspaces, Cargo workspace members.
    """
    modules: set[str] = set()

    # Gradle: settings.gradle.kts / settings.gradle — include(":app", ":lib")
    for name in ("settings.gradle.kts", "settings.gradle"):
        path = root / name
        if path.is_file():
            try:
                content = path.read_text(errors="ignore")
            except OSError:
                continue
            # Match include(":app"), include(":app", ":lib"), include ":app"
            for m in re.findall(r'include\s*\(?\s*["\']:([\w.-]+)["\']', content):
                modules.add(m)
            # Also match buildSrc which is an implicit Gradle module
            if (root / "buildSrc").is_dir():
                modules.add("buildSrc")

    # npm/yarn/pnpm workspaces in package.json
    pkg_path = root / "package.json"
    if pkg_path.is_file():
        try:
            pkg = json.loads(pkg_path.read_text(errors="ignore"))
            workspaces = pkg.get("workspaces", [])
            # Can be list or {"packages": [...]}
            if isinstance(workspaces, dict):
                workspaces = workspaces.get("packages", [])
            if isinstance(workspaces, list):
                for ws in workspaces:
                    # Resolve simple workspace entries (no glob)
                    if "*" not in ws and "?" not in ws:
                        modules.add(ws.rstrip("/"))
        except (json.JSONDecodeError, OSError):
            pass

    # Cargo workspace in Cargo.toml — members = ["crate-a", "crate-b"]
    cargo_path = root / "Cargo.toml"
    if cargo_path.is_file():
        try:
            content = cargo_path.read_text(errors="ignore")
            members_match = re.search(r'members\s*=\s*\[(.*?)\]', content, re.DOTALL)
            if members_match:
                for m in re.findall(r'"([^"]+)"', members_match.group(1)):
                    modules.add(m.rstrip("/"))
        except OSError:
            pass

    return modules


def _primary_type(types: set[str]) -> str:
    """Determine the primary project type from a set of signal types."""
    if "android" in types:
        return "android"
    if "android/jvm" in types:
        return "android"
    if "ios" in types:
        return "ios"
    for t in sorted(types):
        if "/" not in t:
            return t
    return sorted(types)[0]


def detect_subprojects(root: Path) -> list[dict]:
    """Detect independent sub-projects in a monorepo by build file signals.

    A sub-project is an independent, self-contained project with its own build
    system — NOT a module/package within a single project's workspace.
    """
    root = root.resolve()

    # First, detect workspace modules declared by the root project.
    # These are sub-modules of one project, not separate projects.
    workspace_modules = _detect_workspace_modules(root)

    # Collect all (directory, signal_file, type) tuples
    candidates: dict[str, dict] = {}  # dir_rel -> {types, signals}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SUBPROJECT_SKIP_DIRS]
        rel_dir = str(Path(dirpath).relative_to(root))
        if rel_dir == ".":
            rel_dir = ""

        for fname in filenames:
            sig_type = None
            if fname in SUBPROJECT_SIGNALS:
                sig_type = SUBPROJECT_SIGNALS[fname]
            else:
                ext = os.path.splitext(fname)[1].lower()
                if ext in SUBPROJECT_EXT_SIGNALS:
                    sig_type = SUBPROJECT_EXT_SIGNALS[ext]

            if sig_type is None:
                continue

            if rel_dir not in candidates:
                candidates[rel_dir] = {"types": set(), "signals": []}
            candidates[rel_dir]["types"].add(sig_type)
            candidates[rel_dir]["signals"].append(fname)

        # Also check directory names for .xcodeproj/.xcworkspace
        for dname in list(dirnames):
            ext = os.path.splitext(dname)[1].lower()
            if ext in SUBPROJECT_EXT_SIGNALS:
                sig_type = SUBPROJECT_EXT_SIGNALS[ext]
                if rel_dir not in candidates:
                    candidates[rel_dir] = {"types": set(), "signals": []}
                candidates[rel_dir]["types"].add(sig_type)
                candidates[rel_dir]["signals"].append(dname)

    if not candidates:
        return []

    # Filter out workspace modules — these are parts of the root project
    for mod in workspace_modules:
        candidates.pop(mod, None)

    # Also filter any candidate whose top-level dir is a workspace module
    # (e.g., "app/src/main" should be filtered if "app" is a module)
    to_remove = []
    for dir_rel in candidates:
        if dir_rel:
            top = dir_rel.split("/")[0]
            if top in workspace_modules:
                to_remove.append(dir_rel)
    for d in to_remove:
        del candidates[d]

    if not candidates:
        return []

    # Resolve nesting: keep outermost project roots, skip sub-modules
    sorted_dirs = sorted(candidates.keys(), key=lambda d: d.count("/") if d else -1)

    # Check if deeper sub-projects exist (to detect root wrappers)
    has_deeper = any(d for d in sorted_dirs if d)

    accepted: list[dict] = []
    accepted_dirs: list[str] = []

    for dir_rel in sorted_dirs:
        info = candidates[dir_rel]
        is_root = dir_rel == ""

        # Skip if an already-accepted non-wrapper ancestor covers this dir
        skip = False
        for acc_dir in accepted_dirs:
            if acc_dir == "":
                continue
            if dir_rel.startswith(acc_dir + "/"):
                skip = True
                break
        if skip:
            continue

        is_root_wrapper = is_root and has_deeper
        name = Path(dir_rel).name if dir_rel else Path(root).name
        primary = _primary_type(info["types"])

        accepted.append({
            "path": dir_rel if dir_rel else ".",
            "name": name,
            "type": primary,
            "signals": sorted(set(info["signals"])),
            "is_root_wrapper": is_root_wrapper,
        })
        accepted_dirs.append(dir_rel)

    return accepted


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

    # Compute frontend file ratio for Agent D threshold
    frontend_exts = {".tsx", ".jsx", ".vue", ".svelte", ".swift", ".xib",
                     ".storyboard", ".dart", ".xaml"}
    frontend_files = sum(1 for f in files if f.get("extension", "") in frontend_exts)
    total_source = sum(1 for f in files if f.get("extension", "") not in (
        ".json", ".xml", ".yaml", ".yml", ".toml", ".lock", ".md", ".txt",
        ".png", ".jpg", ".svg", ".gif", ".ico", ".webp",
    ))
    frontend_ratio = frontend_files / max(total_source, 1)

    return {
        "file_tree": files,
        "token_counts": tokens,
        "dependencies": deps,
        "framework_signals": frameworks,
        "config_patterns": configs,
        "import_graph": imports,
        "file_hashes": hashes,
        "entry_points": entry_points,
        "frontend_ratio": round(frontend_ratio, 2),
    }


# ── CLI Entry Point ───────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scanner.py /path/to/repo [--detect-subprojects]", file=sys.stderr)
        sys.exit(1)

    args = sys.argv[1:]
    detect_only = "--detect-subprojects" in args
    repo = [a for a in args if not a.startswith("--")][0]

    if not Path(repo).is_dir():
        print(f"Error: {repo} is not a directory", file=sys.stderr)
        sys.exit(1)

    if detect_only:
        # Fast mode: only detect sub-projects, no full scan
        subprojects = detect_subprojects(Path(repo))
        non_wrapper = [s for s in subprojects if not s["is_root_wrapper"]]
        print(f"Detected {len(non_wrapper)} sub-project(s)", file=sys.stderr)
        for sp in non_wrapper:
            print(f"  {sp['name']} ({sp['type']}) — {sp['path']}", file=sys.stderr)
        json.dump({"subprojects": subprojects}, sys.stdout, indent=2)
        sys.exit(0)

    scan = run_scan(repo)

    # Add sub-project info to full scan
    scan["subprojects"] = detect_subprojects(Path(repo))

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

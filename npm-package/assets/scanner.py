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
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import BulkMatcher, IgnoreMatcher, SKIP_DIRS  # noqa: E402

# ── Configuration ──────────────────────────────────────────────────────────

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


def detect_monorepo_type(root: Path) -> str:
    """Classify the monorepo build system by checking signal files.

    Returns one of: "bun-workspaces", "npm-workspaces", "pnpm", "turborepo",
    "nx", "lerna", "cargo", "gradle", or "none". First match wins.

    Signals checked in priority order so that tools layered on top
    (turborepo/nx over bun/pnpm) are reported by their outer layer.
    """
    root = root.resolve()

    def has(name: str) -> bool:
        return (root / name).exists()

    def read_json(name: str) -> dict:
        try:
            return json.loads((root / name).read_text())
        except (OSError, json.JSONDecodeError):
            return {}

    def read_text(name: str) -> str:
        try:
            return (root / name).read_text()
        except OSError:
            return ""

    # Higher-level orchestrators first — they wrap other workspace systems.
    if has("turbo.json"):
        return "turborepo"
    if has("nx.json") or has("workspace.json"):
        return "nx"
    if has("lerna.json"):
        return "lerna"

    # JS workspace flavours
    if has("pnpm-workspace.yaml") or has("pnpm-workspace.yml"):
        return "pnpm"

    pkg = read_json("package.json")
    has_workspaces = bool(pkg.get("workspaces"))
    if has_workspaces:
        # Bun signalled by bun.lock or bunfig.toml
        if has("bun.lock") or has("bun.lockb") or has("bunfig.toml"):
            return "bun-workspaces"
        return "npm-workspaces"

    # Cargo workspace
    cargo = read_text("Cargo.toml")
    if cargo and "[workspace]" in cargo:
        return "cargo"

    # Gradle multi-project (settings.gradle or settings.gradle.kts declares `include`)
    for settings_name in ("settings.gradle", "settings.gradle.kts"):
        settings = read_text(settings_name)
        if settings and re.search(r"\binclude\b", settings):
            return "gradle"

    return "none"


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

def scan_files(root: Path, matcher: IgnoreMatcher | None = None) -> list[dict]:
    entries = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir == ".":
            rel_dir = ""

        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS  # hardcoded fallback
            and not (matcher and matcher.should_skip_dir(d, rel_dir))
        ]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext in SKIP_EXTENSIONS:
                continue
            if fname.startswith(".") and fname not in ALLOWED_DOTFILES:
                continue
            if matcher and matcher.should_skip_file(fname, rel_dir):
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

def parse_dependencies(root: Path, max_depth: int | None = 3) -> list[dict]:
    deps = []
    for dirpath, dirnames, filenames in os.walk(root):
        depth = str(Path(dirpath).relative_to(root)).count(os.sep)
        if max_depth is not None and depth >= max_depth:
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


# ── Persistence Signal Detector ────────────────────────────────────────────
#
# Decides whether the Wave 1 Data agent should spawn. ANY positive signal
# flips `has_persistence_signal` to True. The signals are intentionally broad
# — a false positive costs one extra sub-agent ($) on a repo without a DB;
# a false negative loses the entire data-models surface. Tilt toward
# spawning. The agent itself gracefully returns empty arrays when there's
# nothing to inventory.

PERSISTENCE_DEP_SIGNALS = {
    # Python ORMs / DB toolkits
    "sqlalchemy", "alembic", "django", "tortoise-orm", "peewee", "pony",
    "psycopg2", "psycopg2-binary", "psycopg", "asyncpg", "aiomysql",
    "aiosqlite", "pymysql", "pymongo", "motor", "redis", "aioredis",
    "elasticsearch", "boto3",
    # Node.js ORMs / DB clients
    "prisma", "@prisma/client", "typeorm", "sequelize", "mikro-orm",
    "@mikro-orm/core", "drizzle-orm", "kysely", "knex", "objection",
    "bookshelf", "mongoose", "ioredis", "@elastic/elasticsearch", "pg",
    "mysql", "mysql2", "sqlite3", "better-sqlite3", "level", "lowdb",
    # Go ORMs
    "gorm.io/gorm", "github.com/jinzhu/gorm", "entgo.io/ent",
    "github.com/jmoiron/sqlx", "github.com/go-pg/pg",
    "github.com/uptrace/bun", "github.com/lib/pq",
    "github.com/go-sql-driver/mysql", "github.com/mattn/go-sqlite3",
    "go.mongodb.org/mongo-driver",
    # Rust ORMs
    "diesel", "sqlx", "sea-orm", "rusqlite", "mongodb",
    # Java / Kotlin
    "org.hibernate:hibernate-core", "org.springframework.boot:spring-boot-starter-data-jpa",
    "androidx.room:room-runtime", "androidx.room:room-ktx",
    "io.objectbox:objectbox-android", "io.realm:realm-gradle-plugin",
    # Ruby
    "activerecord", "sequel", "rom-sql", "mongoid",
    # PHP
    "doctrine/orm", "illuminate/database",
    # .NET
    "entityframework", "entityframeworkcore", "dapper",
    # Mobile / Dart
    "sqflite", "drift", "isar", "hive", "realm",
    # iOS / Swift Package Manager-style
    "grdb.swift", "realm-swift",
}

PERSISTENCE_FILE_NAME_SIGNALS = {
    # Schema files
    "schema.prisma", "schema.sql", "schema.rb", "structure.sql",
    "ddl.sql", "init.sql", "create-tables.sql",
    # ORM config
    "alembic.ini", "alembic.cfg", "database.yml", "database.yaml",
    "ormconfig.json", "ormconfig.ts", "ormconfig.js",
    "knexfile.js", "knexfile.ts", "drizzle.config.ts", "drizzle.config.js",
    "mikro-orm.config.ts", "sequelize.config.js",
    # Mobile / desktop DB
    "Realm.swift", "CoreDataModel.xcdatamodeld",
}

PERSISTENCE_DIR_NAMES = {
    "migrations", "migration", "alembic", "db",
}

PERSISTENCE_PATH_SUFFIXES = (
    "/migrations", "/migration", "/alembic/versions",
    "/prisma/migrations", "/db/migrate", "/database/migrations",
    "/app/database/migrations",
)

# Local persistence markers visible inside source files (mobile / desktop).
# These are content checks, not extension checks — we scan a small sample
# rather than every file to keep the scanner fast.
LOCAL_PERSISTENCE_KEYWORDS = (
    "UserDefaults.standard",
    "NSUserDefaults",
    "SharedPreferences",
    "androidx.datastore",
    "@Entity",
    "NSManagedObject",
    "RealmObject",
    "@Persistent",
)

# Tech-stack engine names that indicate a primary DB (matched case-insensitively
# against `framework_signals[*].name` — fed to detector after detect_frameworks).
PERSISTENCE_FRAMEWORK_NAMES = {
    "postgresql", "postgres", "mysql", "mariadb", "sqlite", "mongodb",
    "redis", "elasticsearch", "dynamodb", "cassandra", "firestore",
    "supabase", "firebase", "snowflake",
}


def detect_persistence_signal(
    files: list[dict],
    deps: list[dict],
    bulk_manifest: dict,
    frameworks: list[dict],
    root: Path,
) -> dict:
    """Detect whether this codebase has any data-persistence surface.

    Returns {"has_signal": bool, "evidence": {category: [hits, ...]}}.
    Evidence is informational — the Data agent reads it to know where to
    look first. The boolean gates whether the Data agent spawns at all.
    """
    evidence: dict[str, list[str]] = {
        "deps": [],
        "schema_files": [],
        "migrations_dirs": [],
        "frameworks": [],
        "local_persistence": [],
    }

    # 1. Dependency-driven detection (highest signal).
    for dep in deps:
        key = dep.get("name", "").lower()
        if key in PERSISTENCE_DEP_SIGNALS:
            evidence["deps"].append(key)

    # 2. Schema / config files by basename.
    for f in files:
        path = f.get("path", "")
        basename = path.rsplit("/", 1)[-1] if "/" in path else path
        if basename in PERSISTENCE_FILE_NAME_SIGNALS:
            evidence["schema_files"].append(path)
        # Catch any *.sql with a "schema" or "migration" parent dir
        if path.endswith(".sql") and any(
            seg in PERSISTENCE_DIR_NAMES for seg in path.split("/")
        ):
            evidence["schema_files"].append(path)

    # 3. Migrations directory detection — from bulk_manifest's `migration`
    # category (set by `.archiebulk`) and from raw file paths.
    migration_bulk = bulk_manifest.get("migration") or {}
    migration_paths = migration_bulk.get("files") or []
    seen_dirs: set[str] = set()
    for p in migration_paths:
        parent = "/".join(p.split("/")[:-1])
        if parent:
            seen_dirs.add(parent)
    # Also catch migration dirs that aren't bulk-tagged (small repos)
    for f in files:
        path = f.get("path", "")
        for suffix in PERSISTENCE_PATH_SUFFIXES:
            if suffix in ("/" + path):
                # Find the directory matching this suffix and record it
                idx = path.find(suffix.lstrip("/"))
                if idx >= 0:
                    seen_dirs.add(path[: idx + len(suffix.lstrip("/"))])
                break
    evidence["migrations_dirs"] = sorted(seen_dirs)

    # 4. Tech-stack engine names already detected by detect_frameworks.
    for fw in frameworks:
        name = fw.get("name", "").lower()
        if any(known in name for known in PERSISTENCE_FRAMEWORK_NAMES):
            evidence["frameworks"].append(fw.get("name", ""))

    # 5. Local-persistence keyword sniff. Sample up to 200 readable
    # source files to keep this fast — a single hit is enough to flip
    # the flag for mobile / desktop repos with no other signal.
    extensions = {".swift", ".kt", ".java", ".m", ".mm", ".dart", ".cs"}
    sampled = 0
    for f in files:
        if sampled >= 200:
            break
        ext = f.get("extension", "")
        if ext not in extensions:
            continue
        path = root / f.get("path", "")
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        sampled += 1
        for keyword in LOCAL_PERSISTENCE_KEYWORDS:
            if keyword in text:
                evidence["local_persistence"].append(f.get("path", ""))
                break

    has_signal = any(evidence.values())
    return {"has_signal": has_signal, "evidence": evidence}


# ── Import Graph ───────────────────────────────────────────────────────────

PYTHON_EXTS = {".py"}
JS_EXTS = {".js", ".jsx", ".ts", ".tsx", ".mjs"}
KOTLIN_EXTS = {".kt", ".kts"}
JAVA_EXTS = {".java"}
SWIFT_EXTS = {".swift"}
GO_EXTS = {".go"}
RUST_EXTS = {".rs"}

JS_IMPORT_RE = re.compile(r"""(?:import\s+.*?from\s+['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\))""")
KOTLIN_IMPORT_RE = re.compile(r'^import\s+([\w.]+)', re.MULTILINE)
JAVA_IMPORT_RE = re.compile(r'^import\s+(?:static\s+)?([\w.]+)', re.MULTILINE)
SWIFT_IMPORT_RE = re.compile(r'^import\s+(\w+)', re.MULTILINE)
GO_BLOCK_RE = re.compile(r'import\s*\(([^)]*)\)', re.S)
GO_SINGLE_RE = re.compile(r'import\s+(?:[.\w]+\s+)?"([^"]+)"')
GO_QUOTED_RE = re.compile(r'"([^"]+)"')
RUST_USE_RE = re.compile(r'^\s*(?:pub\s+)?use\s+([^;]+);', re.MULTILINE)

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


def _go_module_path(root: Path) -> str:
    """The module path declared in go.mod (prefix of internal import paths)."""
    try:
        text = (root / "go.mod").read_text(errors="ignore")
    except OSError:
        return ""
    m = re.search(r'^\s*module\s+(\S+)', text, re.MULTILINE)
    return m.group(1) if m else ""


def _all_dirs(files: list[dict]) -> set[str]:
    """Every directory (and ancestor) present in the file tree."""
    dirs: set[str] = set()
    for f in files:
        p = f["path"]
        if "/" not in p:
            continue
        parent = p.rsplit("/", 1)[0]
        segs = parent.split("/")
        for i in range(1, len(segs) + 1):
            dirs.add("/".join(segs[:i]))
    return dirs


def build_import_graph(root: Path, files: list[dict]) -> dict[str, list[str]]:
    graph = {}
    go_module = _go_module_path(root)
    dirs = _all_dirs(files)  # for Go/Rust internal resolution
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
        elif ext in GO_EXTS:
            imports = _go_imports(path, go_module)
        elif ext in RUST_EXTS:
            imports = _rust_imports(path, f["path"], dirs)

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


def _go_imports(path: Path, module_prefix: str) -> list[str]:
    """Internal Go imports resolved to repo-relative package dirs.

    Go imports are absolute package paths (e.g. `github.com/org/repo/foo/bar`).
    Internal ones start with the go.mod module path; stripping it yields the
    package directory (`foo/bar`). Std-lib / third-party imports are dropped.
    """
    if not module_prefix:
        return []
    try:
        source = path.read_text(errors="ignore")
    except OSError:
        return []
    raw: list[str] = []
    for block in GO_BLOCK_RE.findall(source):
        raw.extend(GO_QUOTED_RE.findall(block))
    raw.extend(GO_SINGLE_RE.findall(source))
    out = []
    for imp in raw:
        if imp == module_prefix or imp.startswith(module_prefix + "/"):
            rel = imp[len(module_prefix):].lstrip("/")
            if rel:
                out.append(rel)
    return out


def _parent_dir(d: str) -> str:
    return d.rsplit("/", 1)[0] if "/" in d else ""


def _rust_imports(path: Path, rel_path: str, dirs: set[str]) -> list[str]:
    """Internal Rust imports resolved to repo-relative dirs (best-effort).

    Resolves only the explicit-internal forms `crate::`, `self::`, `super::`
    (external crates and 2018-edition bare paths are ambiguous with crate names,
    so they are skipped — a miss yields no edge, never a wrong one). Rust's
    module tree is not 1:1 with directories, so the longest path prefix that
    matches a real directory is used.
    """
    try:
        source = path.read_text(errors="ignore")
    except OSError:
        return []
    parts = rel_path.split("/")
    src_root = "/".join(parts[:parts.index("src") + 1]) if "src" in parts else ""
    file_dir = _parent_dir(rel_path)
    out: set[str] = set()
    for use in RUST_USE_RE.findall(source):
        head = use.strip().split("{")[0].split(" as ")[0].strip().rstrip(":")
        segs = [s for s in head.split("::") if s]
        if not segs:
            continue
        if segs[0] == "crate":
            base, rest = src_root, segs[1:]
        elif segs[0] == "self":
            base, rest = file_dir, segs[1:]
        elif segs[0] == "super":
            base, i = file_dir, 0
            while i < len(segs) and segs[i] == "super":
                base = _parent_dir(base)
                i += 1
            rest = segs[i:]
        else:
            continue  # external crate or bare path — skip
        # The trailing segments may name a type/fn; try longest dir prefix.
        for drop in range(0, len(rest) + 1):
            cand = "/".join(([base] if base else []) + rest[:len(rest) - drop]).strip("/")
            if cand and cand in dirs:
                out.add(cand)
                break
    return sorted(out)


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


# ── Skeleton Extraction ───────────────────────────────────────────────────

_SKELETON_PATTERNS: dict[str, list[tuple[str, re.Pattern[str]]]] = {
    ".py": [
        ("class", re.compile(r'^\s*(class\s+\w+[^:]*)', re.MULTILINE)),
        ("func", re.compile(r'^\s*((?:async\s+)?def\s+\w+\s*\([^)]*\)[^:]*)', re.MULTILINE)),
    ],
    ".kt": [
        ("class", re.compile(
            r'^\s*((?:(?:private|public|internal|abstract|open|data|sealed|inline|inner)\s+)*class\s+\w+[^{]*)',
            re.MULTILINE)),
        ("interface", re.compile(
            r'^\s*((?:(?:private|public|internal)\s+)*interface\s+\w+[^{]*)', re.MULTILINE)),
        ("object", re.compile(
            r'^\s*((?:(?:private|public|internal)\s+)*(?:companion\s+)?object\s+\w+[^{]*)', re.MULTILINE)),
        ("func", re.compile(
            r'^\s*((?:(?:private|public|internal|protected|override|suspend|abstract|open|inline|actual|expect)\s+)*fun\s+(?:<[^>]+>\s*)?\w+\s*\([^)]*\)[^{]*)',
            re.MULTILINE)),
    ],
    ".kts": None,  # filled below
    ".java": [
        ("class", re.compile(
            r'^\s*((?:(?:public|private|protected|static|final|abstract)\s+)*class\s+\w+[^{]*)',
            re.MULTILINE)),
        ("interface", re.compile(
            r'^\s*((?:(?:public|private|protected|static)\s+)*interface\s+\w+[^{]*)',
            re.MULTILINE)),
        ("func", re.compile(
            r'^\s*((?:(?:public|private|protected|static|final|abstract|synchronized)\s+)*(?:[\w<>\[\]?,\s]+)\s+\w+\s*\([^)]*\))',
            re.MULTILINE)),
    ],
    ".swift": [
        ("class", re.compile(
            r'^\s*((?:(?:public|private|fileprivate|internal|open|final)\s+)*class\s+\w+[^{]*)', re.MULTILINE)),
        ("struct", re.compile(
            r'^\s*((?:(?:public|private|fileprivate|internal)\s+)*struct\s+\w+[^{]*)', re.MULTILINE)),
        ("protocol", re.compile(
            r'^\s*((?:(?:public|private|fileprivate|internal)\s+)*protocol\s+\w+[^{]*)', re.MULTILINE)),
        ("enum", re.compile(
            r'^\s*((?:(?:public|private|fileprivate|internal)\s+)*enum\s+\w+[^{]*)', re.MULTILINE)),
        ("func", re.compile(
            r'^\s*((?:(?:public|private|fileprivate|internal|open|static|class|override|mutating|@\w+\s+)\s*)*(?:init|func\s+\w+)\s*\([^)]*\)[^{]*)',
            re.MULTILINE)),
    ],
    ".go": [
        ("func", re.compile(
            r'^(func\s+(?:\(\s*\w+\s+\*?\w+\s*\)\s*)?\w+\s*\([^)]*\)[^{]*)', re.MULTILINE)),
        ("struct", re.compile(r'^(type\s+\w+\s+struct)', re.MULTILINE)),
        ("interface", re.compile(r'^(type\s+\w+\s+interface)', re.MULTILINE)),
    ],
}

# JS/TS patterns shared across extensions
_JS_TS_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("func", re.compile(
        r'^((?:(?:export|async|default)\s+)*function\s+\w+\s*\([^)]*\))', re.MULTILINE)),
    ("class", re.compile(
        r'^((?:(?:export|abstract|default)\s+)*class\s+\w+[^{]*)', re.MULTILINE)),
    ("interface", re.compile(
        r'^((?:export\s+)?interface\s+\w+[^{]*)', re.MULTILINE)),
    ("type", re.compile(
        r'^((?:export\s+)?type\s+\w+\s*(?:<[^>]*>)?\s*=)', re.MULTILINE)),
    ("func", re.compile(
        r'^((?:export\s+)?(?:const|let)\s+\w+\s*=)', re.MULTILINE)),
]

for _ext in (".js", ".jsx", ".ts", ".tsx", ".mjs"):
    _SKELETON_PATTERNS[_ext] = _JS_TS_PATTERNS

# .kts shares Kotlin patterns
_SKELETON_PATTERNS[".kts"] = _SKELETON_PATTERNS[".kt"]

# Lines that are imports / blank / comment-only — skipped when building header
_HEADER_SKIP_RE = re.compile(
    r'^\s*$'
    r'|^\s*#'           # Python / shell comments
    r'|^\s*//'          # C-style line comments
    r'|^\s*/\*'         # C-style block comment start
    r'|^\s*\*'          # C-style block comment continuation
    r'|^import\s'       # import statements
    r'|^from\s+\S+\s+import'  # Python from-import
    r'|^package\s'      # Kotlin/Java package
    r'|^using\s'        # C# using
    r'|^require\('      # JS require
    r"|^'use strict'"   # JS strict mode
    r'|^"use strict"'
    r'|^@file:'         # Kotlin file annotations
    r'|^from\s+__future__'
)


def extract_skeletons(root: Path, files: list[dict]) -> dict[str, dict]:
    """Extract per-file skeletons: header lines + symbol signatures."""
    skeletons: dict[str, dict] = {}

    for f in files:
        if f["size"] > 500_000:
            continue
        ext = f.get("extension", "")
        fpath = root / f["path"]
        try:
            content = fpath.read_text(errors="ignore")
        except OSError:
            continue

        lines = content.splitlines()
        line_count = len(lines)

        patterns = _SKELETON_PATTERNS.get(ext)

        # Unsupported extension → header only (first 20 lines)
        if patterns is None:
            skeletons[f["path"]] = {
                "header": "\n".join(lines[:20]),
                "symbols": [],
                "line_count": line_count,
            }
            continue

        # Build header: first 2-3 non-import, non-blank, non-comment lines
        header_lines: list[str] = []
        for ln in lines:
            if len(header_lines) >= 3:
                break
            if not _HEADER_SKIP_RE.match(ln):
                header_lines.append(ln)

        # Extract symbols
        symbols: list[dict] = []
        for kind, regex in patterns:
            for m in regex.finditer(content):
                sig = m.group(1).rstrip(" {:\t")
                # Compute line number (1-based)
                line_no = content[:m.start()].count("\n") + 1
                # Extract symbol name
                name = _extract_name(kind, sig)
                if name:
                    symbols.append({
                        "kind": kind,
                        "name": name,
                        "signature": sig.strip(),
                        "line": line_no,
                    })

        # Sort by line number, deduplicate by line
        symbols.sort(key=lambda s: s["line"])
        seen_lines: set[int] = set()
        deduped: list[dict] = []
        for sym in symbols:
            if sym["line"] not in seen_lines:
                seen_lines.add(sym["line"])
                deduped.append(sym)

        skeletons[f["path"]] = {
            "header": "\n".join(header_lines),
            "symbols": deduped,
            "line_count": line_count,
        }

    return skeletons


def _extract_name(kind: str, signature: str) -> str:
    """Pull the symbol name out of a matched signature."""
    # class Foo, interface Foo, struct Foo, protocol Foo, enum Foo, object Foo, type Foo
    if kind in ("class", "interface", "struct", "protocol", "enum", "object", "type"):
        m = re.search(r'(?:class|interface|struct|protocol|enum|object|type)\s+(\w+)', signature)
        return m.group(1) if m else ""
    # func / method
    if kind == "func":
        # Go receiver methods: func (r Receiver) Name(
        m = re.search(r'func\s+\([^)]*\)\s*(\w+)', signature)
        if m:
            return m.group(1)
        # Regular func/fun/function/def
        m = re.search(r'(?:func|fun|function|def)\s+(\w+)', signature)
        if m:
            return m.group(1)
        # init (Swift)
        if re.search(r'\binit\s*\(', signature):
            return "init"
        # const/let arrow functions
        m = re.search(r'(?:const|let)\s+(\w+)\s*=', signature)
        if m:
            return m.group(1)
    return ""


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


# ── Deployable-unit detection (language / platform agnostic) ─────────────────
# A C4 "container" is an independently deployable unit. Detected from two
# agnostic signals, NOT a hand-tuned per-language filename list:
#
#   (1) ENTRY_STEMS — source files whose name *stem* is a universal
#       process-entry convention, across ANY extension. Covers Go (main.go),
#       Rust (main.rs), C/C++ (main.cpp), C# (Program.cs), Java/Kotlin
#       (Main.*, Application.*), Android (MainActivity.kt), Swift
#       (main.swift, AppDelegate.swift), Dart (main.dart), Python
#       (__main__.py + idiomatic app/server/manage/wsgi), Node (main.ts/js).
#       Barrels (index.*) and UI roots (App.tsx) are deliberately excluded.
#       This recovers per-binary splits in monorepos (Go cmd/*, Rust src/bin/*).
#
#   (2) MANIFEST markers — project/deploy manifests that mark a deployable app
#       even with no conventional entry file, and carry the platform: mobile
#       (AndroidManifest.xml, pubspec.yaml), desktop (*.csproj), apple
#       (Package.swift), containerized service (Dockerfile), etc. An umbrella
#       manifest (root go.mod/Dockerfile sitting above cmd/* binaries) is
#       suppressed so it does not double-count; a mobile/desktop manifest
#       upgrades the platform `kind` of the entry files beneath it.

ENTRY_STEMS = {
    "main", "Main", "Program", "__main__",
    "MainActivity", "AppDelegate", "Application",
}
PY_ENTRY_STEMS = {"app", "server", "manage", "wsgi", "asgi"}
# The stem rule applies only to programming-language source files — so that a
# `main.tsp` (TypeSpec schema), `main.css`, `main.md` etc. is NOT a deployable.
# This is a "is it code?" set, not a per-language entrypoint list.
CODE_EXTS = {
    ".go", ".rs", ".c", ".cc", ".cpp", ".cxx", ".cs", ".fs", ".vb",
    ".java", ".kt", ".kts", ".scala", ".clj", ".cljs", ".groovy",
    ".swift", ".m", ".mm", ".dart", ".py", ".rb", ".php", ".ex", ".exs",
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".lua", ".jl",
    ".erl", ".hs", ".ml", ".nim", ".zig", ".cr",
}

# Manifest basename -> coarse platform kind.
MANIFEST_KINDS = {
    "Dockerfile": "service", "Containerfile": "service",
    "AndroidManifest.xml": "mobile", "pubspec.yaml": "mobile",
    "Package.swift": "app",
    "go.mod": "service", "Cargo.toml": "app",
    "pom.xml": "service", "build.gradle": "app", "build.gradle.kts": "app",
}
MANIFEST_EXT_KINDS = {".csproj": "desktop", ".fsproj": "desktop", ".vcxproj": "desktop"}
# Source-root segments stripped when naming a module from its directory.
_MODULE_STRIP = {"src", "main", "java", "kotlin", "lib"}


def _entry_kind(path: str) -> str:
    """Classify a deployable entrypoint by its parent directory name."""
    parts = path.split("/")
    parent = parts[-2].lower() if len(parts) >= 2 else ""
    if "worker" in parent:
        return "worker"
    if parent == "server" or parent.endswith(("-service", "_service")) or "service" in parent:
        return "service"
    if parent in ("jobs", "cli") or parent.endswith("-cli"):
        return "cli"
    return "app"


def _dir_of(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else ""


def _module_name(d: str) -> str:
    """Human name for a deployable's directory (strips src/main/... roots)."""
    segs = [s for s in d.split("/") if s]
    while len(segs) > 1 and segs[-1] in _MODULE_STRIP:
        segs.pop()
    return segs[-1] if segs else ""


def _under(child: str, parent: str) -> bool:
    """True if `child` dir is at or under `parent` dir ('' == repo root)."""
    if parent == "":
        return True
    return child == parent or child.startswith(parent + "/")


def _manifest_kind(base: str) -> str | None:
    if base in MANIFEST_KINDS:
        return MANIFEST_KINDS[base]
    ext = base[base.rfind("."):] if "." in base else ""
    return MANIFEST_EXT_KINDS.get(ext)


def _pkgjson_is_app(root: Path, rel: str) -> bool:
    """package.json is a deployable only if it declares a bin or start/dev script."""
    try:
        data = json.loads((root / rel).read_text())
    except (OSError, json.JSONDecodeError):
        return False
    if data.get("bin"):
        return True
    scripts = data.get("scripts") or {}
    return any(k in scripts for k in ("start", "dev", "serve"))


def detect_build_targets(files: list[dict], root: Path | None = None) -> list[dict]:
    """Deployable units (C4 containers) from entry-stem files + manifests.
    Returns [{path, kind, name}], sorted by path (byte-stable)."""
    paths = sorted(f["path"] for f in files)

    # (1) source entry files, keyed by directory (one deployable per dir)
    entries: dict[str, dict] = {}
    for p in paths:
        base = p.rsplit("/", 1)[-1]
        if "." not in base:
            continue
        stem = base.split(".", 1)[0]
        ext = base[base.rfind("."):]
        if ext not in CODE_EXTS:
            continue
        if not (stem in ENTRY_STEMS or (ext == ".py" and stem in PY_ENTRY_STEMS)):
            continue
        d = _dir_of(p)
        entries.setdefault(d, {"path": p, "kind": _entry_kind(p),
                               "name": _module_name(d) or stem})

    # (2) manifests
    manifests: list[tuple[str, str, str]] = []
    for p in paths:
        base = p.rsplit("/", 1)[-1]
        if base == "package.json":
            if root is not None and _pkgjson_is_app(root, p):
                manifests.append((_dir_of(p), "service", p))
            continue
        k = _manifest_kind(base)
        if k:
            manifests.append((_dir_of(p), k, p))

    # platform upgrade: a mobile/desktop manifest sets the platform of entries beneath it
    for d, k, _ in manifests:
        if k in ("mobile", "desktop"):
            for ed, e in entries.items():
                if _under(ed, d):
                    e["kind"] = k

    # standalone manifests: a deployable app with no source entry beneath it
    for d, k, mp in manifests:
        if not any(_under(ed, d) for ed in entries):
            entries.setdefault(d, {"path": mp, "kind": k, "name": _module_name(d) or "app"})

    return sorted(entries.values(), key=lambda t: t["path"])


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

def run_scan(repo_path: str, comprehensive: bool = False) -> dict:
    root = Path(repo_path).resolve()

    matcher = IgnoreMatcher(root)
    bulk = BulkMatcher(root)
    files = scan_files(root, matcher=matcher)

    # ── Bulk-content classification ──────────────────────────────────────
    # Files matching `.archiebulk` patterns are tagged and excluded from
    # content-reading operations (skeletons, hashes, tokens, imports). Their
    # existence still counts toward inventory ratios.
    for f in files:
        bulk_info = bulk.classify(f["path"])
        if bulk_info:
            f["bulk"] = bulk_info

    # Comprehensive: the read-boundary is the ignore system alone. `.archiebulk`
    # still classifies (frontend_ratio etc.) but no longer gates reading.
    if comprehensive:
        readable_files = files
    else:
        readable_files = [f for f in files if "bulk" not in f]

    deps = parse_dependencies(root, max_depth=None if comprehensive else 3)
    frameworks = detect_frameworks(readable_files, deps)
    hashes = hash_files(root, readable_files)
    tokens = estimate_tokens(root, readable_files)
    imports = build_import_graph(root, readable_files)
    entry_points = detect_entry_points(readable_files)
    configs = collect_configs(root)
    skeletons = extract_skeletons(root, readable_files)

    # Aggregate token counts by directory
    tokens_by_dir: dict[str, int] = defaultdict(int)
    for path, count in tokens.items():
        parent = str(Path(path).parent) if "/" in path else "."
        tokens_by_dir[parent] += count

    # ── Build bulk-content manifest ──────────────────────────────────────
    # Shape shared with agents: counts + framework breakdown + file paths
    # (no content). Agents reference by path; they must not Read them.
    bulk_manifest: dict[str, dict] = {}
    for f in files:
        info = f.get("bulk")
        if not info:
            continue
        cat = info["category"]
        bucket = bulk_manifest.setdefault(cat, {
            "count": 0,
            "frameworks": {},
            "files": [],
        })
        bucket["count"] += 1
        fw = info.get("framework") or "-"
        bucket["frameworks"][fw] = bucket["frameworks"].get(fw, 0) + 1
        bucket["files"].append(f["path"])

    # ── Frontend ratio ────────────────────────────────────────────────────
    # Numerator: extension-tagged UI source (Swift/JSX/etc.) + any bulk file
    # tagged `ui_resource` (Android res/, iOS storyboards, etc.).
    # Denominator: readable source files + bulk categories that represent
    # source shape (ui_resource/generated/localization/migration/fixture).
    # Bulk categories that aren't source shape (asset, lockfile, dependency,
    # data) are excluded from both ratio sides.
    frontend_exts = {".tsx", ".jsx", ".vue", ".svelte", ".swift", ".xib",
                     ".storyboard", ".dart", ".xaml"}
    # Compute the ratio on the NON-BULK set regardless of depth: bulk-shaped
    # files are added back via the bulk-category sums below. Using readable_files
    # here would double-count bulk files in comprehensive depth (where
    # readable_files == files), making frontend_ratio depth-dependent.
    non_bulk_files = [f for f in files if "bulk" not in f]
    frontend_files = sum(1 for f in non_bulk_files if f.get("extension", "") in frontend_exts)
    ui_bulk_files = sum(1 for f in files if f.get("bulk", {}).get("category") == "ui_resource")

    source_bulk_categories = {"ui_resource", "generated", "localization", "migration", "fixture"}
    total_source = sum(1 for f in non_bulk_files if f.get("extension", "") not in (
        ".json", ".xml", ".yaml", ".yml", ".toml", ".lock", ".md", ".txt",
        ".png", ".jpg", ".svg", ".gif", ".ico", ".webp",
    ))
    total_source += sum(1 for f in files if f.get("bulk", {}).get("category") in source_bulk_categories)
    frontend_ratio = (frontend_files + ui_bulk_files) / max(total_source, 1)

    # ── Persistence signal ────────────────────────────────────────────────
    # Gates whether the Wave 1 Data agent spawns. Evidence dict is exposed
    # so the agent can read it as a starting point rather than re-deriving.
    persistence = detect_persistence_signal(
        readable_files, deps, bulk_manifest, frameworks, root
    )

    return {
        "file_tree": files,
        "token_counts": tokens,
        "tokens_by_directory": dict(tokens_by_dir),
        "dependencies": deps,
        "framework_signals": frameworks,
        "config_patterns": configs,
        "import_graph": imports,
        "file_hashes": hashes,
        "entry_points": entry_points,
        "entrypoints": detect_build_targets(readable_files, root),
        "frontend_ratio": round(frontend_ratio, 2),
        "has_persistence_signal": persistence["has_signal"],
        "persistence_signals": persistence["evidence"],
        "bulk_content_manifest": bulk_manifest,
        "_skeletons": skeletons,
    }


# ── CLI Entry Point ───────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scanner.py /path/to/repo [--detect-subprojects]", file=sys.stderr)
        sys.exit(1)

    args = sys.argv[1:]
    detect_only = "--detect-subprojects" in args
    comprehensive = "--comprehensive" in args
    args = [a for a in args if a != "--comprehensive"]
    repo = [a for a in args if not a.startswith("--")][0]

    if not Path(repo).is_dir():
        print(f"Error: {repo} is not a directory", file=sys.stderr)
        sys.exit(1)

    if detect_only:
        # Fast mode: only detect sub-projects, no full scan
        subprojects = detect_subprojects(Path(repo))
        monorepo_type = detect_monorepo_type(Path(repo))
        non_wrapper = [s for s in subprojects if not s["is_root_wrapper"]]
        print(f"Detected {len(non_wrapper)} sub-project(s) (monorepo_type={monorepo_type})", file=sys.stderr)
        for sp in non_wrapper:
            print(f"  {sp['name']} ({sp['type']}) — {sp['path']}", file=sys.stderr)
        json.dump({"monorepo_type": monorepo_type, "subprojects": subprojects}, sys.stdout, indent=2)
        sys.exit(0)

    scan = run_scan(repo, comprehensive=comprehensive)

    # Add sub-project info to full scan
    scan["subprojects"] = detect_subprojects(Path(repo))

    # Pop skeletons out of the main scan dict — saved separately
    skeletons = scan.pop("_skeletons", {})

    # Save to .archie/scan.json
    archie_dir = Path(repo) / ".archie"
    archie_dir.mkdir(exist_ok=True)
    out_path = archie_dir / "scan.json"
    out_path.write_text(json.dumps(scan, indent=2))

    # Save skeletons to .archie/skeletons.json
    skel_path = archie_dir / "skeletons.json"
    skel_path.write_text(json.dumps(skeletons, indent=2))

    # Print summary to stderr, JSON to stdout
    total_tokens = sum(scan["token_counts"].values())
    fw_names = ", ".join(f["name"] for f in scan["framework_signals"]) or "none detected"
    skel_with_symbols = sum(1 for s in skeletons.values() if s.get("symbols"))
    print(f"Scanned: {len(scan['file_tree'])} files", file=sys.stderr)
    print(f"Frameworks: {fw_names}", file=sys.stderr)
    print(f"Dependencies: {len(scan['dependencies'])}", file=sys.stderr)
    print(f"Tokens (est): {total_tokens:,}", file=sys.stderr)
    print(f"Skeletons: {len(skeletons)} files ({skel_with_symbols} with symbols)", file=sys.stderr)
    print(f"Saved to: {out_path}", file=sys.stderr)

    # Output JSON to stdout (without skeletons)
    json.dump(scan, sys.stdout, indent=2)

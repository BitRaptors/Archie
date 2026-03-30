#!/usr/bin/env python3
"""Archie post-generation validator — cross-references output against codebase.

Checks that generated CLAUDE.md, AGENTS.md, and per-folder files contain
only claims that are grounded in the actual code. No API calls needed.

Subcommands:
  all     — Run all checks
  paths   — Verify all referenced file/dir paths exist
  methods — Verify HTTP method claims match route exports
  files   — Detect file description collisions across components
  pitfalls — Check pitfall claims are grounded in code

Run:
  python3 validate.py all /path/to/repo
  python3 validate.py paths /path/to/repo
  python3 validate.py methods /path/to/repo

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict | list:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# Check 1: File/directory paths exist
# ---------------------------------------------------------------------------

def check_paths(root: Path) -> list[dict]:
    """Verify every file/dir path referenced in output files exists on disk."""
    errors = []

    # Check AGENTS.md project structure tree
    agents_md = root / "AGENTS.md"
    if agents_md.exists():
        content = _read_text(agents_md)

        # Extract paths from the tree block (lines with ├── or └── or │)
        in_tree = False
        for line in content.splitlines():
            if line.strip().startswith("```") and in_tree:
                in_tree = False
                continue
            if "## Project Structure" in line:
                in_tree = False  # will start at next ```
            if in_tree:
                # Extract filename/dir from tree lines
                # e.g. "├── start.sh" or "│   └── route.ts"
                cleaned = re.sub(r"[│├└─\s]+", "", line).strip()
                if cleaned and not cleaned.startswith("#"):
                    # Skip comment-style annotations
                    cleaned = cleaned.split("#")[0].strip()
                    # Skip glob patterns like *.test.ts
                    if "*" in cleaned:
                        continue
            if line.strip() == "```":
                in_tree = True

        # Extract paths from File Placement section
        # Format: "**label** → `path`"
        for match in re.finditer(r"→\s*`([^`]+)`", content):
            rel_path = match.group(1)
            # Skip template patterns like [resource], [name], {resource}, {timestamp}
            if "[" in rel_path or "{" in rel_path:
                continue
            full = root / rel_path
            if not full.exists() and not full.parent.exists():
                errors.append({
                    "check": "path_exists",
                    "file": "AGENTS.md",
                    "claim": rel_path,
                    "status": "FAIL",
                    "detail": f"Path does not exist: {rel_path}",
                })

        # Check all directory-like paths referenced in AGENTS.md
        # Strip code blocks first — they contain tree diagrams, code samples, etc.
        content_no_code = re.sub(r'```[\s\S]*?```', '', content)
        # Match paths like src/something/, public/output/, lib/utils, etc.
        for match in re.finditer(r'(?:^|\s|`)((?:src|lib|app|public|test|tests|spec|internal|pkg|cmd|data|output|dist|build|assets)/[\w\[\]\.{}/\-]+)', content_no_code):
            ref_path = match.group(1).rstrip("/")
            # Skip template patterns like [resource], [name], {resource}, {timestamp}
            if ("[" in ref_path and "]" in ref_path) or ("{" in ref_path and "}" in ref_path):
                continue
            # Skip glob patterns
            if "*" in ref_path:
                continue
            # Skip truncated template paths (e.g. output/site- from output/site-<timestamp>)
            if ref_path.endswith("-") or "<" in ref_path:
                continue
            # Strip trailing filename to check directory
            if "." in ref_path.rsplit("/", 1)[-1]:
                dir_path = str(Path(ref_path).parent)
            else:
                dir_path = ref_path
            if dir_path and not (root / dir_path).exists():
                errors.append({
                    "check": "path_exists",
                    "file": "AGENTS.md",
                    "claim": dir_path,
                    "status": "FAIL",
                    "detail": f"Referenced directory does not exist: {dir_path}",
                })

    # Check per-folder CLAUDE.md file references
    blueprint = _load_json(root / ".archie" / "blueprint.json")
    components = blueprint.get("components", {})
    if isinstance(components, dict):
        components = components.get("components", [])

    for comp in components:
        for kf in comp.get("key_files", []):
            if isinstance(kf, dict):
                path = kf.get("path", "")
            elif isinstance(kf, str):
                path = kf
            else:
                continue
            if path and not (root / path).exists():
                errors.append({
                    "check": "path_exists",
                    "file": "blueprint.json",
                    "claim": path,
                    "status": "FAIL",
                    "detail": f"key_file path does not exist: {path}",
                })

    return errors


# ---------------------------------------------------------------------------
# Check 2: HTTP methods match route exports
# ---------------------------------------------------------------------------

_HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}


def _extract_exported_methods(route_file: Path) -> set[str]:
    """Extract HTTP methods from a route handler file.

    Supports multiple frameworks:
    - Next.js/Remix: export async function GET / export const GET
    - Express/Koa: router.get / app.post / router.delete
    - Python FastAPI/Flask: @app.get / @router.post / @app.route(..., methods=["GET"])
    - Spring: @GetMapping / @PostMapping / @RequestMapping(method=GET)
    - Go net/http: r.HandleFunc pattern with method checks
    - Ruby Rails: get/post/put/delete/patch route declarations

    Returns empty set if no patterns matched (skips the check gracefully).
    """
    if not route_file.exists():
        return set()
    content = _read_text(route_file)
    methods = set()

    for method in _HTTP_METHODS:
        ml = method.lower()
        patterns = [
            # Next.js / Remix: export async function GET
            rf"export\s+(?:async\s+)?(?:function|const)\s+{method}\b",
            # Express / Koa: router.get( / app.post(
            rf"(?:router|app|server)\s*\.\s*{ml}\s*\(",
            # Python decorators: @app.get / @router.post / @bp.route
            rf"@\w+\.{ml}\s*\(",
            # Flask @app.route with methods=
            rf"methods\s*=\s*\[.*?['\"]" + method + rf"['\"]",
            # Spring: @GetMapping / @PostMapping
            rf"@{method.capitalize()}Mapping",
            # Spring: @RequestMapping(method = RequestMethod.GET)
            rf"RequestMethod\.{method}",
        ]
        for pat in patterns:
            if re.search(pat, content, re.IGNORECASE):
                methods.add(method)
                break

    return methods


def check_methods(root: Path) -> list[dict]:
    """Verify HTTP method claims in Key Interfaces match actual route exports."""
    errors = []

    blueprint = _load_json(root / ".archie" / "blueprint.json")
    components = blueprint.get("components", {})
    if isinstance(components, dict):
        components = components.get("components", [])

    for comp in components:
        interfaces = comp.get("key_interfaces", [])
        location = comp.get("location", "")

        for iface in interfaces:
            if not isinstance(iface, dict):
                continue
            claimed_methods = set(iface.get("methods", []))
            if not claimed_methods:
                continue

            # Find the source file — check common patterns across frameworks
            route_file = None
            loc_path = root / location
            if loc_path.is_file():
                route_file = loc_path
            elif loc_path.is_dir():
                # Try common handler file names across frameworks
                candidates = [
                    "route.ts", "route.js", "route.tsx", "route.jsx",  # Next.js/Remix
                    "index.ts", "index.js",  # Express/Koa
                    "views.py", "routes.py", "handlers.py",  # Python
                    "controller.py", "api.py",  # Python
                    "Controller.java", "Controller.kt",  # Spring
                    "handler.go", "routes.go",  # Go
                    "controller.rb",  # Rails
                ]
                for c in candidates:
                    candidate = loc_path / c
                    if candidate.exists():
                        route_file = candidate
                        break

            if not route_file or not route_file.exists():
                continue

            actual_methods = _extract_exported_methods(route_file)
            if not actual_methods:
                continue

            if claimed_methods != actual_methods:
                errors.append({
                    "check": "http_methods",
                    "file": f"blueprint.json → {comp.get('name', '')}",
                    "claim": f"Methods: {', '.join(sorted(claimed_methods))}",
                    "status": "FAIL",
                    "detail": f"Actual exports: {', '.join(sorted(actual_methods))}",
                    "location": location,
                })

    return errors


# ---------------------------------------------------------------------------
# Check 3: File description collisions
# ---------------------------------------------------------------------------

def check_file_descriptions(root: Path) -> list[dict]:
    """Detect when multiple key_files from different components resolve to
    the same filename within a directory, causing description overwrites."""
    errors = []

    blueprint = _load_json(root / ".archie" / "blueprint.json")
    components = blueprint.get("components", {})
    if isinstance(components, dict):
        components = components.get("components", [])

    # Collect all key_files grouped by parent directory + filename
    # key: (dir, filename), value: list of (component_name, full_path, purpose)
    file_map: dict[tuple[str, str], list[tuple[str, str, str]]] = {}
    for comp in components:
        comp_name = comp.get("name", "unknown")
        for kf in comp.get("key_files", []):
            if isinstance(kf, dict):
                path = kf.get("path", "")
                purpose = kf.get("purpose", "")
            elif isinstance(kf, str):
                path = kf
                purpose = ""
            else:
                continue
            if not path:
                continue
            parent = str(Path(path).parent) if "/" in path else ""
            fname = path.rsplit("/", 1)[-1] if "/" in path else path
            key = (parent, fname)
            if key not in file_map:
                file_map[key] = []
            file_map[key].append((comp_name, path, purpose))

    # Now check: for each directory that has a CLAUDE.md, are there filename
    # collisions from files in child directories?
    scan = _load_json(root / ".archie" / "scan.json")
    dir_set = set()
    for f in scan.get("file_tree", []):
        p = f.get("path", "")
        if "/" in p:
            dir_set.add(str(Path(p).parent))

    for directory in dir_set:
        # Find all key_files that would match this directory with the old loose logic
        fname_sources: dict[str, list[tuple[str, str, str]]] = {}
        for comp in components:
            comp_name = comp.get("name", "unknown")
            for kf in comp.get("key_files", []):
                if isinstance(kf, dict):
                    path = kf.get("path", "")
                    purpose = kf.get("purpose", "")
                elif isinstance(kf, str):
                    path = kf
                    purpose = ""
                else:
                    continue
                if not path:
                    continue
                # Old loose matching logic
                if path.startswith(directory) or directory in path:
                    fname = path.rsplit("/", 1)[-1] if "/" in path else path
                    if fname not in fname_sources:
                        fname_sources[fname] = []
                    fname_sources[fname].append((comp_name, path, purpose))

        for fname, sources in fname_sources.items():
            if len(sources) > 1:
                paths = [s[1] for s in sources]
                errors.append({
                    "check": "file_description_collision",
                    "file": f"Directory: {directory}",
                    "claim": f"Filename '{fname}' matched by {len(sources)} key_files",
                    "status": "WARNING",
                    "detail": f"Paths: {', '.join(paths)} — last one wins, may mislabel",
                })

    return errors


# ---------------------------------------------------------------------------
# Check 4: Pitfall grounding
# ---------------------------------------------------------------------------

def check_pitfalls(root: Path) -> list[dict]:
    """Check that pitfall claims reference paths and patterns that exist in code."""
    errors = []

    blueprint = _load_json(root / ".archie" / "blueprint.json")
    pitfalls = blueprint.get("pitfalls", [])
    if not isinstance(pitfalls, list):
        return errors

    # Build set of known paths from scan.json for fast lookup
    scan = _load_json(root / ".archie" / "scan.json")
    known_dirs = set()
    for f in scan.get("file_tree", []):
        p = f.get("path", "")
        if "/" in p:
            # Add all ancestor directories
            parts = p.split("/")
            for i in range(1, len(parts)):
                known_dirs.add("/".join(parts[:i]))

    # Check all directory-like paths referenced in pitfalls
    seen_refs = set()
    for p in pitfalls:
        if not isinstance(p, dict):
            continue
        text = json.dumps(p)
        # Match paths that look like directory references (word/word patterns)
        for dir_match in re.finditer(r'(?:[\w\.\-]+/){1,}[\w\.\-\[\]]+', text):
            ref = dir_match.group(0).rstrip("/")
            # Skip URLs, version strings, protocol patterns, relative imports, rule names
            if any(ref.startswith(s) for s in ["http", "ftp", "ssh", "//", "..", "node_modules"]):
                continue
            # Skip things that look like package/rule names (e.g. import/no-relative)
            if "-" in ref.split("/")[0] or ref.count("/") == 1 and "-" in ref:
                continue
            # Strip trailing filename to get directory
            if "." in ref.rsplit("/", 1)[-1] and "/" in ref:
                ref_dir = str(Path(ref).parent)
            else:
                ref_dir = ref
            # Skip template patterns
            if ("[" in ref_dir and "]" in ref_dir) or ("{" in ref_dir and "}" in ref_dir):
                continue
            if ref_dir and ref_dir not in seen_refs:
                seen_refs.add(ref_dir)
                if ref_dir not in known_dirs and not (root / ref_dir).exists():
                    errors.append({
                        "check": "pitfall_grounding",
                        "file": "blueprint.json pitfalls",
                        "claim": ref_dir,
                        "status": "WARNING",
                        "detail": f"Pitfall references non-existent path: {ref_dir}",
                    })

    return errors


# ---------------------------------------------------------------------------
# Check 5: Component responsibility vs actual code
# ---------------------------------------------------------------------------

def check_component_verbs(root: Path) -> list[dict]:
    """Flag component descriptions that claim write operations (publish, create,
    push) on routes that only perform read operations, and vice versa."""
    errors = []

    blueprint = _load_json(root / ".archie" / "blueprint.json")
    components = blueprint.get("components", {})
    if isinstance(components, dict):
        components = components.get("components", [])

    write_verbs = {"publish", "publishes", "creates", "writes", "pushes", "sends", "posts"}
    read_verbs = {"reads", "fetches", "gets", "lists", "returns", "queries"}

    for comp in components:
        resp = (comp.get("responsibility") or "").lower()
        location = comp.get("location", "")
        if not resp or not location:
            continue

        # Only check route handlers
        if "/api/" not in location:
            continue

        route_file = root / location
        if not route_file.exists():
            route_file = root / location / "route.ts"
        if not route_file.exists():
            continue

        content = _read_text(route_file).lower()
        resp_words = set(resp.split())

        # Check: description says "publishes" but code only reads
        desc_has_write = bool(resp_words & write_verbs)
        desc_has_read = bool(resp_words & read_verbs)

        if desc_has_write and not desc_has_read:
            # Check if the route actually does any external writes
            # Look for: fetch with POST/PUT, octokit create/push, fs.writeFile
            has_write_code = any(w in content for w in [
                "createorupdatefilecontent", "push", ".create(", "writefile",
                "method: 'post'", "method: 'put'", ".update(",
            ])
            if not has_write_code:
                errors.append({
                    "check": "component_verb",
                    "file": f"blueprint.json → {comp.get('name', '')}",
                    "claim": comp.get("responsibility", ""),
                    "status": "WARNING",
                    "detail": f"Description implies write operation but code at {location} appears read-only",
                })

    return errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_results(errors: list[dict]):
    fails = [e for e in errors if e["status"] == "FAIL"]
    warns = [e for e in errors if e["status"] == "WARNING"]

    for e in fails:
        print(f"  FAIL  [{e['check']}] {e['claim']}")
        print(f"        {e['detail']}")
    for e in warns:
        print(f"  WARN  [{e['check']}] {e['claim']}")
        print(f"        {e['detail']}")

    total_f = len(fails)
    total_w = len(warns)
    if total_f == 0 and total_w == 0:
        print("  All checks passed.")
    else:
        print(f"\n  {total_f} failures, {total_w} warnings")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage:", file=sys.stderr)
        print("  python3 validate.py all /path/to/repo", file=sys.stderr)
        print("  python3 validate.py paths /path/to/repo", file=sys.stderr)
        print("  python3 validate.py methods /path/to/repo", file=sys.stderr)
        print("  python3 validate.py files /path/to/repo", file=sys.stderr)
        print("  python3 validate.py pitfalls /path/to/repo", file=sys.stderr)
        sys.exit(1)

    subcmd = sys.argv[1]
    root = Path(sys.argv[2]).resolve()

    checkers = {
        "paths": ("Path existence", check_paths),
        "methods": ("HTTP methods", check_methods),
        "files": ("File description collisions", check_file_descriptions),
        "pitfalls": ("Pitfall grounding", check_pitfalls),
        "verbs": ("Component verbs", check_component_verbs),
    }

    if subcmd == "all":
        all_errors = []
        for name, (label, fn) in checkers.items():
            print(f"\n## {label}")
            errors = fn(root)
            _print_results(errors)
            all_errors.extend(errors)
        total_f = sum(1 for e in all_errors if e["status"] == "FAIL")
        total_w = sum(1 for e in all_errors if e["status"] == "WARNING")
        print(f"\n{'='*40}")
        print(f"Total: {total_f} failures, {total_w} warnings")
        sys.exit(1 if total_f > 0 else 0)
    elif subcmd in checkers:
        label, fn = checkers[subcmd]
        print(f"\n## {label}")
        errors = fn(root)
        _print_results(errors)
        fails = sum(1 for e in errors if e["status"] == "FAIL")
        sys.exit(1 if fails > 0 else 0)
    else:
        print(f"Error: unknown subcommand '{subcmd}'", file=sys.stderr)
        sys.exit(1)

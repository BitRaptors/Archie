#!/usr/bin/env python3
"""Archie standalone intent layer — generates per-folder CLAUDE.md from blueprint.

Run: python3 intent_layer.py /path/to/repo
Output: Creates CLAUDE.md files in significant directories

Zero dependencies beyond Python 3.11+ stdlib.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path


def load_scan(root: Path) -> dict:
    scan_path = root / ".archie" / "scan.json"
    if scan_path.exists():
        try:
            return json.loads(scan_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def load_blueprint(root: Path) -> dict:
    bp_path = root / ".archie" / "blueprint.json"
    if bp_path.exists():
        try:
            return json.loads(bp_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def group_files_by_dir(files: list[dict]) -> dict[str, list[str]]:
    """Group file paths by their parent directory."""
    groups: dict[str, list[str]] = defaultdict(list)
    for f in files:
        path = f["path"]
        parent = str(Path(path).parent)
        if parent == ".":
            continue  # Skip root-level files
        groups[parent].append(path)
    return dict(groups)


def find_component(directory: str, components: list[dict]) -> dict | None:
    """Find the blueprint component that matches this directory."""
    best = None
    best_len = 0
    for comp in components:
        comp_path = comp.get("path", "").rstrip("/")
        if not comp_path:
            continue
        if directory.startswith(comp_path) or comp_path.startswith(directory):
            if len(comp_path) > best_len:
                best = comp
                best_len = len(comp_path)
    return best


def get_relevant_rules(directory: str, blueprint: dict) -> list[str]:
    """Get architecture rules relevant to this directory."""
    rules = []
    arch_rules = blueprint.get("architecture_rules", {})

    for r in arch_rules.get("file_placement_rules", []):
        loc = r.get("location", "")
        if loc and (directory.startswith(loc.rstrip("/")) or loc.rstrip("/").startswith(directory)):
            rules.append(r.get("description", r.get("pattern", "")))

    for n in arch_rules.get("naming_conventions", []):
        rules.append(f"{n.get('target', '')}: {n.get('convention', '')} (e.g. `{n.get('example', '')}`)")

    return rules


def get_imports_for_dir(directory: str, import_graph: dict) -> tuple[set[str], set[str]]:
    """Get what this directory imports from and what imports from it."""
    imports_from: set[str] = set()
    imported_by: set[str] = set()

    for file_path, imports in import_graph.items():
        file_dir = str(Path(file_path).parent)

        if file_dir == directory or file_dir.startswith(directory + "/"):
            # This file is in our directory — where does it import from?
            for imp in imports:
                # Try to resolve import to a directory
                if "/" in imp or "." in imp:
                    imp_parts = imp.replace(".", "/").split("/")
                    if len(imp_parts) >= 2:
                        imp_dir = "/".join(imp_parts[:2])
                        if imp_dir != directory and not imp_dir.startswith(directory + "/"):
                            imports_from.add(imp_dir)
        else:
            # This file is outside our directory — does it import from us?
            for imp in imports:
                imp_norm = imp.replace(".", "/")
                if imp_norm.startswith(directory) or directory.startswith(imp_norm.split("/")[0] if "/" in imp_norm else ""):
                    if file_dir:
                        top = file_dir.split("/")[0]
                        dir_top = directory.split("/")[0]
                        if top != dir_top:
                            imported_by.add(file_dir)

    return imports_from, imported_by


def generate_folder_claude_md(
    directory: str,
    files: list[str],
    component: dict | None,
    rules: list[str],
    imports_from: set[str],
    imported_by: set[str],
) -> str:
    """Generate a concise CLAUDE.md for a single directory."""
    dir_name = directory.rsplit("/", 1)[-1] if "/" in directory else directory
    lines = [f"# {dir_name}", ""]

    # Component info
    if component:
        lines.append(f"> Part of **{component.get('name', '')}** — {component.get('purpose', '')}")
        lines.append("")

    # Files
    lines.append("## Files")
    lines.append("")
    for f in sorted(files):
        fname = f.rsplit("/", 1)[-1] if "/" in f else f
        lines.append(f"- `{fname}`")
    lines.append("")

    # Architecture rules
    if rules:
        lines.append("## Architecture Rules")
        lines.append("")
        for r in rules[:5]:
            lines.append(f"- {r}")
        lines.append("")

    # Dependencies
    if imports_from or imported_by:
        lines.append("## Dependencies")
        lines.append("")
        if imports_from:
            lines.append(f"- **Imports from:** {', '.join(sorted(imports_from))}")
        if imported_by:
            lines.append(f"- **Imported by:** {', '.join(sorted(imported_by))}")
        lines.append("")

    lines.append("---")
    lines.append("*Auto-generated by Archie. Updates on `archie refresh`.*")

    return "\n".join(lines)


def generate_all(root: Path) -> dict[str, str]:
    """Generate per-folder CLAUDE.md files. Returns {path: content}."""
    scan = load_scan(root)
    blueprint = load_blueprint(root)

    files = scan.get("file_tree", [])
    import_graph = scan.get("import_graph", {})
    raw_components = blueprint.get("components", {})
    if isinstance(raw_components, list):
        components = raw_components
    elif isinstance(raw_components, dict):
        components = raw_components.get("components", [])
    else:
        components = []

    dir_files = group_files_by_dir(files)
    result: dict[str, str] = {}

    for directory, file_list in sorted(dir_files.items()):
        # Skip small directories
        if len(file_list) < 2:
            continue

        # Skip deep nested dirs (3+ levels) unless they have many files
        depth = directory.count("/")
        if depth > 3 and len(file_list) < 5:
            continue

        component = find_component(directory, components)
        rules = get_relevant_rules(directory, blueprint)
        imports_from, imported_by = get_imports_for_dir(directory, import_graph)

        content = generate_folder_claude_md(
            directory, file_list, component, rules, imports_from, imported_by,
        )

        output_path = f"{directory}/CLAUDE.md"
        result[output_path] = content

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 intent_layer.py /path/to/repo", file=sys.stderr)
        sys.exit(1)

    repo = sys.argv[1]
    root = Path(repo).resolve()

    if not root.is_dir():
        print(f"Error: {repo} is not a directory", file=sys.stderr)
        sys.exit(1)

    files = generate_all(root)

    # Write files to disk
    for rel_path, content in files.items():
        full = root / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)

    print(f"Generated {len(files)} per-folder CLAUDE.md files", file=sys.stderr)
    for path in sorted(files.keys()):
        print(f"  {path}", file=sys.stderr)

    # Also output JSON summary
    json.dump({"files_generated": len(files), "paths": sorted(files.keys())}, sys.stdout, indent=2)

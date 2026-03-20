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


def load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def group_files_by_dir(files: list[dict]) -> dict[str, list[dict]]:
    """Group files by their parent directory, keeping full file info."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for f in files:
        parent = str(Path(f["path"]).parent)
        if parent == ".":
            parent = "__root__"
        groups[parent].append(f)
    return dict(groups)


def find_matching_components(directory: str, components: list[dict]) -> list[dict]:
    """Find all blueprint components whose location matches this directory."""
    matched = []
    for comp in components:
        loc = (comp.get("location") or comp.get("path") or "").rstrip("/")
        if not loc:
            continue
        # Match if directory is the component location or a child of it
        if directory == loc or directory.startswith(loc + "/") or loc.startswith(directory):
            matched.append(comp)
    return matched


def get_file_descriptions(directory: str, components: list[dict]) -> dict[str, str]:
    """Build filename → description map from component key_files."""
    descriptions: dict[str, str] = {}
    for comp in components:
        for kf in comp.get("key_files", []):
            if isinstance(kf, dict):
                path = kf.get("path", "")
                purpose = kf.get("purpose", "")
            elif isinstance(kf, str):
                path = kf
                purpose = ""
            else:
                continue
            if path and (path.startswith(directory) or directory in path):
                fname = path.rsplit("/", 1)[-1] if "/" in path else path
                if purpose:
                    descriptions[fname] = purpose
    return descriptions


def get_relevant_rules(directory: str, blueprint: dict) -> list[str]:
    """Get architecture rules relevant to this directory."""
    rules = []
    arch = blueprint.get("architecture_rules", {})
    if not isinstance(arch, dict):
        return rules

    for r in arch.get("file_placement_rules", []):
        if not isinstance(r, dict):
            continue
        loc = (r.get("location") or "").rstrip("/")
        desc = r.get("description", r.get("pattern", ""))
        if loc and (directory.startswith(loc) or loc.startswith(directory)):
            if desc:
                rules.append(desc)

    for n in arch.get("naming_conventions", []):
        if not isinstance(n, dict):
            continue
        scope = n.get("scope") or n.get("target") or ""
        pattern = n.get("pattern") or n.get("convention") or ""
        examples = n.get("examples", [])
        if isinstance(examples, str):
            examples = [examples]
        example = n.get("example") or (examples[0] if examples else "")
        desc = n.get("description", "")
        if desc:
            rules.append(desc)
        elif scope and pattern:
            entry = f"{scope}: use {pattern}"
            if example:
                entry += f" (e.g. `{example}`)"
            rules.append(entry)

    return rules


def get_imports_for_dir(directory: str, import_graph: dict) -> tuple[set[str], set[str]]:
    """Get what this directory imports from and what imports from it."""
    imports_from: set[str] = set()
    imported_by: set[str] = set()

    for file_path, imports in import_graph.items():
        file_dir = str(Path(file_path).parent)
        if file_dir == "__root__" or file_dir == ".":
            file_dir = "__root__"

        is_in_dir = (file_dir == directory or file_dir.startswith(directory + "/"))

        if is_in_dir:
            for imp in imports:
                if "/" in imp or "." in imp:
                    parts = imp.replace(".", "/").split("/")
                    if len(parts) >= 2:
                        imp_dir = "/".join(parts[:2])
                        if not imp_dir.startswith(directory):
                            imports_from.add(imp_dir)
        else:
            for imp in imports:
                imp_norm = imp.replace(".", "/")
                if directory in imp_norm:
                    imported_by.add(file_dir)

    return imports_from, imported_by


def generate_folder_claude_md(
    directory: str,
    files: list[dict],
    components: list[dict],
    file_descriptions: dict[str, str],
    rules: list[str],
    imports_from: set[str],
    imported_by: set[str],
) -> str:
    """Generate a rich CLAUDE.md for a single directory."""
    dir_name = directory.rsplit("/", 1)[-1] if "/" in directory else directory
    lines = [f"# {dir_name}", ""]

    # Component descriptions
    for comp in components:
        name = comp.get("name", "")
        resp = comp.get("responsibility") or comp.get("purpose") or ""
        if name and resp:
            lines.append(f"> **{name}** — {resp}")
            lines.append("")
            # Show dependencies
            deps = comp.get("depends_on", [])
            if deps:
                lines.append(f"Depends on: {', '.join(deps)}")
                lines.append("")
            exposes = comp.get("exposes_to", [])
            if exposes:
                lines.append(f"Exposes to: {', '.join(exposes)}")
                lines.append("")
            break  # Show primary component only

    # Files with descriptions
    lines.append("## Files")
    lines.append("")
    for f in sorted(files, key=lambda x: x["path"]):
        fname = f["path"].rsplit("/", 1)[-1] if "/" in f["path"] else f["path"]
        desc = file_descriptions.get(fname, "")
        if desc:
            lines.append(f"- `{fname}` — {desc}")
        else:
            lines.append(f"- `{fname}`")
    lines.append("")

    # Architecture rules (only non-empty, deduplicated)
    seen_rules = set()
    clean_rules = []
    for r in rules:
        r = r.strip()
        if r and r not in seen_rules:
            seen_rules.add(r)
            clean_rules.append(r)

    if clean_rules:
        lines.append("## Architecture Rules")
        lines.append("")
        for r in clean_rules[:8]:
            lines.append(f"- {r}")
        lines.append("")

    # Key interfaces from components
    for comp in components:
        interfaces = comp.get("key_interfaces", [])
        if interfaces:
            lines.append("## Key Interfaces")
            lines.append("")
            for iface in interfaces:
                if isinstance(iface, dict):
                    name = iface.get("name", "")
                    methods = iface.get("methods", [])
                    desc = iface.get("description", "")
                    if name:
                        lines.append(f"- **{name}**: {desc}")
                        if methods:
                            lines.append(f"  Methods: {', '.join(methods)}")
            lines.append("")
            break

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
    lines.append("*Auto-generated by Archie.*")

    return "\n".join(lines)


def generate_all(root: Path) -> dict[str, str]:
    """Generate per-folder CLAUDE.md files. Returns {path: content}."""
    scan = load_json(root / ".archie" / "scan.json")
    blueprint = load_json(root / ".archie" / "blueprint.json")

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
        if directory == "__root__":
            continue

        # Generate for directories with 1+ source files
        # (API routes often have single route.ts files)
        if not file_list:
            continue

        # Skip deep nested dirs unless they have enough files
        depth = directory.count("/")
        if depth > 4 and len(file_list) < 3:
            continue

        matched_comps = find_matching_components(directory, components)
        file_descs = get_file_descriptions(directory, components)
        rules = get_relevant_rules(directory, blueprint)
        imports_from, imported_by = get_imports_for_dir(directory, import_graph)

        content = generate_folder_claude_md(
            directory, file_list, matched_comps, file_descs,
            rules, imports_from, imported_by,
        )

        result[f"{directory}/CLAUDE.md"] = content

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 intent_layer.py /path/to/repo", file=sys.stderr)
        sys.exit(1)

    root = Path(sys.argv[1]).resolve()
    if not root.is_dir():
        print(f"Error: {sys.argv[1]} is not a directory", file=sys.stderr)
        sys.exit(1)

    result = generate_all(root)

    for rel_path, content in result.items():
        full = root / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)

    print(f"Generated {len(result)} per-folder CLAUDE.md files", file=sys.stderr)
    for p in sorted(result.keys()):
        print(f"  {p}", file=sys.stderr)

    json.dump({"files_generated": len(result), "paths": sorted(result.keys())}, sys.stdout, indent=2)

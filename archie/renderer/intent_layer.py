"""Per-folder CLAUDE.md generation from blueprint + scan data."""
from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath


# Source file extensions considered significant
_SOURCE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".kt", ".go",
    ".rs", ".rb", ".swift", ".c", ".cpp", ".h", ".hpp", ".cs",
    ".scala", ".clj", ".ex", ".exs", ".vue", ".svelte", ".dart",
    ".php", ".lua", ".zig", ".nim", ".ml", ".hs",
}

# Minimum number of source files for a directory to be "significant"
_MIN_FILES = 2


def generate_folder_context(
    blueprint: dict,
    scan_path: Path,
) -> dict[str, str]:
    """Generate per-folder CLAUDE.md files from blueprint and scan data.

    Parameters
    ----------
    blueprint:
        The blueprint dict (StructuredBlueprint-compatible).
    scan_path:
        Path to the ``.archie/scan.json`` file on disk.

    Returns
    -------
    dict mapping ``relative_dir_path + "/CLAUDE.md"`` to the generated content.
    """
    scan_data = _load_scan(scan_path)
    if scan_data is None:
        return {}

    file_tree = scan_data.get("file_tree", [])
    import_graph: dict[str, list[str]] = scan_data.get("import_graph", {})

    # Group source files by directory
    dir_files: dict[str, list[str]] = {}
    for entry in file_tree:
        path = entry.get("path", "") if isinstance(entry, dict) else str(entry)
        if not path:
            continue
        ext = PurePosixPath(path).suffix
        if ext not in _SOURCE_EXTENSIONS:
            continue
        parent = str(PurePosixPath(path).parent)
        if parent == ".":
            parent = ""
        dir_files.setdefault(parent, []).append(path)

    # Build component lookup: directory -> component info
    components = _extract_components(blueprint)
    # Build rules lookup
    placement_rules, naming_conventions = _extract_rules(blueprint)
    # Build reverse import graph
    reverse_graph = _build_reverse_graph(import_graph)

    # Pre-resolve scope values to a per-component item map. We do this once
    # so each folder's render is a dict lookup rather than a re-resolution.
    project_root = scan_path.parent.parent if scan_path.parent.name == ".archie" else scan_path.parent
    component_to_igs, component_to_patterns = _resolve_blueprint_scoped_items(
        blueprint, components, project_root,
    )

    results: dict[str, str] = {}
    for dir_path, files in sorted(dir_files.items()):
        if len(files) < _MIN_FILES:
            continue
        content = _render_folder_md(
            dir_path=dir_path,
            files=sorted(files),
            components=components,
            placement_rules=placement_rules,
            naming_conventions=naming_conventions,
            import_graph=import_graph,
            reverse_graph=reverse_graph,
            blueprint=blueprint,
            component_to_igs=component_to_igs,
            component_to_patterns=component_to_patterns,
        )
        key = f"{dir_path}/CLAUDE.md" if dir_path else "CLAUDE.md"
        results[key] = content

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_scan(scan_path: Path) -> dict | None:
    try:
        return json.loads(scan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _extract_components(blueprint: dict) -> dict[str, dict]:
    """Map normalised directory paths to component info dicts."""
    mapping: dict[str, dict] = {}
    comps_section = blueprint.get("components", {})
    if not isinstance(comps_section, dict):
        return mapping
    for comp in comps_section.get("components", []):
        location = comp.get("location", "")
        if location:
            # Normalise: strip leading/trailing slashes
            norm = location.strip("/")
            mapping[norm] = comp
    return mapping


def _extract_rules(blueprint: dict) -> tuple[list[dict], list[dict]]:
    rules_section = blueprint.get("architecture_rules", {})
    if not isinstance(rules_section, dict):
        return [], []
    placement = rules_section.get("file_placement_rules", [])
    naming = rules_section.get("naming_conventions", [])
    return placement, naming


def _build_reverse_graph(import_graph: dict[str, list[str]]) -> dict[str, list[str]]:
    """Build a reverse mapping: module -> list of modules that import it."""
    reverse: dict[str, list[str]] = {}
    for source, targets in import_graph.items():
        for target in targets:
            reverse.setdefault(target, []).append(source)
    return reverse


def _dir_of(file_path: str) -> str:
    parent = str(PurePosixPath(file_path).parent)
    return "" if parent == "." else parent


def _module_name(file_path: str) -> str:
    """Convert a file path to a dotted module-style name."""
    p = PurePosixPath(file_path)
    stem = p.stem
    parts = list(p.parent.parts) + [stem]
    return ".".join(parts)


def _collect_dir_imports(
    dir_path: str,
    files: list[str],
    import_graph: dict[str, list[str]],
    reverse_graph: dict[str, list[str]],
) -> tuple[set[str], set[str]]:
    """Return (imports_from_dirs, imported_by_dirs) for a directory."""
    file_set = set(files)
    imports_from: set[str] = set()
    imported_by: set[str] = set()

    for f in files:
        # What this file imports
        for target in import_graph.get(f, []):
            target_dir = _dir_of(target)
            if target_dir != dir_path and target not in file_set:
                imports_from.add(target_dir if target_dir else "(root)")
        # What imports this file
        for source in reverse_graph.get(f, []):
            source_dir = _dir_of(source)
            if source_dir != dir_path and source not in file_set:
                imported_by.add(source_dir if source_dir else "(root)")

    return imports_from, imported_by


def _relevant_rules(
    dir_path: str,
    placement_rules: list[dict],
    naming_conventions: list[dict],
) -> tuple[list[str], list[str]]:
    """Return (placement_lines, naming_lines) relevant to this directory."""
    placement_lines: list[str] = []
    for rule in placement_rules:
        location = rule.get("location", "").strip("/")
        if location and dir_path.startswith(location) or location.startswith(dir_path):
            desc = rule.get("component_type", "")
            pattern = rule.get("naming_pattern", "")
            line = desc
            if pattern:
                line += f" — pattern: `{pattern}`"
            if line:
                placement_lines.append(line)

    naming_lines: list[str] = []
    for conv in naming_conventions:
        pattern = conv.get("pattern", "")
        description = conv.get("description", "")
        # Include if pattern or description mentions the directory name
        dir_name = PurePosixPath(dir_path).name if dir_path else ""
        text = f"{pattern} {description}".lower()
        if dir_name and dir_name.lower() in text:
            line = description or pattern
            if line:
                naming_lines.append(line)

    return placement_lines, naming_lines


def _scoped_block_lines(
    component_name: str,
    in_scope_igs: list[dict],
    in_scope_patterns: list[dict],
) -> list[str]:
    """Render the scoped-rules block for a component, or empty list if none.

    Caller is responsible for resolving scope values to per-component item
    lists first (via ``_resolve_blueprint_scoped_items``). The resolver is
    lenient — it handles both literal component names and concrete code
    symbols (class / interface / object / Koin val module).
    """
    if not in_scope_igs and not in_scope_patterns:
        return []

    lines = ["## Scoped Architecture Rules", ""]
    lines.append(f"*From blueprint — these rules are scoped to the `{component_name}` component.*")
    lines.append("")

    if in_scope_igs:
        lines.append("### Implementation Guidelines")
        lines.append("")
        for gl in in_scope_igs:
            cap = gl.get("capability", "")
            if not cap:
                continue
            cat = gl.get("category", "")
            heading = f"#### {cap}" + (f" [{cat}]" if cat else "")
            lines.append(heading)
            if gl.get("pattern_description"):
                lines.append(f"Pattern: {gl['pattern_description']}")
            libs = gl.get("libraries") or []
            if libs:
                lines.append(f"Libraries: {', '.join(f'`{l}`' for l in libs)}")
            kf = gl.get("key_files") or []
            if kf:
                lines.append(f"Key files: {', '.join(f'`{f}`' for f in kf)}")
            if gl.get("usage_example"):
                lines.append(f"Example: `{gl['usage_example']}`")
            if gl.get("applicable_when"):
                lines.append(f"**Applicable when:** {gl['applicable_when']}")
            do_not = gl.get("do_not_apply_when") or []
            do_not = [d for d in do_not if isinstance(d, str) and d.strip()]
            if do_not:
                lines.append("**Do NOT apply when:**")
                for d in do_not:
                    lines.append(f"  - {d}")
            lines.append("")

    if in_scope_patterns:
        lines.append("### Communication Patterns")
        lines.append("")
        for pat in in_scope_patterns:
            name = pat.get("name", "")
            if not name:
                continue
            lines.append(f"#### {name}")
            if pat.get("when_to_use"):
                lines.append(f"- **When:** {pat['when_to_use']}")
            if pat.get("how_it_works"):
                lines.append(f"- **How:** {pat['how_it_works']}")
            if pat.get("applicable_when"):
                lines.append(f"- **Applicable when:** {pat['applicable_when']}")
            do_not = pat.get("do_not_apply_when") or []
            do_not = [d for d in do_not if isinstance(d, str) and d.strip()]
            if do_not:
                lines.append("- **Do NOT apply when:**")
                for d in do_not:
                    lines.append(f"  - {d}")
            lines.append("")

    return lines


def _filename_hint(path: str) -> str:
    """Generate a brief hint from a filename."""
    stem = PurePosixPath(path).stem
    # Convert snake_case/camelCase to words
    words = stem.replace("_", " ").replace("-", " ")
    return words


def _render_folder_md(
    dir_path: str,
    files: list[str],
    components: dict[str, dict],
    placement_rules: list[dict],
    naming_conventions: list[dict],
    import_graph: dict[str, list[str]],
    reverse_graph: dict[str, list[str]],
    blueprint: dict | None = None,
    component_to_igs: dict[str, list[dict]] | None = None,
    component_to_patterns: dict[str, list[dict]] | None = None,
) -> str:
    dir_name = PurePosixPath(dir_path).name if dir_path else "(root)"
    lines: list[str] = []

    # Header
    lines.append(f"# {dir_name}")
    lines.append("")

    # Component info
    comp = components.get(dir_path)
    if comp:
        comp_name = comp.get("name", dir_name)
        comp_resp = comp.get("responsibility", "")
        if comp_resp:
            lines.append(f"> Part of **{comp_name}** — {comp_resp}")
        else:
            lines.append(f"> Part of **{comp_name}**")
        lines.append("")

    # Files section
    lines.append("## Files")
    for f in files:
        fname = PurePosixPath(f).name
        hint = _filename_hint(f)
        lines.append(f"- `{fname}` — {hint}")
    lines.append("")

    # Architecture rules
    placement_lines, naming_lines = _relevant_rules(
        dir_path, placement_rules, naming_conventions
    )
    if placement_lines or naming_lines:
        lines.append("## Architecture Rules")
        for pl in placement_lines:
            lines.append(f"- {pl}")
        for nl in naming_lines:
            lines.append(f"- {nl}")
        lines.append("")

    # Dependencies
    imports_from, imported_by = _collect_dir_imports(
        dir_path, files, import_graph, reverse_graph
    )
    if imports_from or imported_by:
        lines.append("## Dependencies")
        if imports_from:
            lines.append(f"- **Imports from:** {', '.join(sorted(imports_from))}")
        if imported_by:
            lines.append(f"- **Imported by:** {', '.join(sorted(imported_by))}")
        lines.append("")

    # Scoped Architecture Rules — only emit at the component's root location.
    # Nested subfolders inherit the section via Claude Code's per-folder
    # ancestor-loading, so duplicating it deeper would just bloat token usage.
    if blueprint and comp:
        comp_location = (comp.get("location") or "").strip("/")
        if dir_path == comp_location:
            comp_name = comp.get("name", "")
            igs = (component_to_igs or {}).get(comp_name, [])
            pats = (component_to_patterns or {}).get(comp_name, [])
            scoped_lines = _scoped_block_lines(comp_name, igs, pats)
            if scoped_lines:
                lines.extend(scoped_lines)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Lenient scope resolver (mirror of standalone/intent_layer.py). Walks the
# project root once, indexes class / interface / object / enum / Koin
# `val foo = module {}` declarations, then resolves blueprint scope values
# (which Wave 2 often emits as concrete code symbols rather than literal
# component names) to the owning component via file→directory→component.
# ---------------------------------------------------------------------------

_RESOLVER_SOURCE_EXTS = {
    ".kt", ".kts", ".java", ".scala",
    ".py",
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".swift",
    ".go", ".rs",
    ".rb", ".cs", ".php",
}

_RESOLVER_SKIP_DIRS = {
    ".archie", ".claude", "node_modules", ".venv", ".git",
    "vendor", "dist", "build", "target", ".next", ".nuxt",
    "__pycache__",
}

_DECL_RE = re.compile(
    r"\b(?:class|interface|object|enum|trait|struct|protocol|record)\s+([A-Z][A-Za-z0-9_]*)\b"
)
_VAL_MODULE_RE = re.compile(
    r"\bval\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*module\b"
)


def _build_symbol_index(root: Path) -> dict[str, str]:
    """Walk source files once; map declared identifier -> first-seen rel path."""
    index: dict[str, str] = {}
    if not root.is_dir():
        return index
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in _RESOLVER_SOURCE_EXTS:
            continue
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if any(part in _RESOLVER_SKIP_DIRS for part in rel.parts):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel_str = str(rel)
        for m in _DECL_RE.finditer(content):
            index.setdefault(m.group(1), rel_str)
        for m in _VAL_MODULE_RE.finditer(content):
            index.setdefault(m.group(1), rel_str)
    return index


def _resolve_blueprint_scoped_items(
    blueprint: dict,
    components_by_dir: dict[str, dict],
    project_root: Path,
) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    """Aggregate blueprint scoped items per component name.

    Returns ``(component_to_igs, component_to_patterns)`` — keys are
    component names, values are the items that resolve to that component.
    Resolution chain: literal component name match -> symbol index lookup
    (class/interface/object/val module) -> dropped silently if neither.
    """
    component_to_igs: dict[str, list[dict]] = {}
    component_to_patterns: dict[str, list[dict]] = {}

    # Build name lookup + reverse map (location -> component name).
    comp_by_name: dict[str, dict] = {}
    for c in components_by_dir.values():
        if isinstance(c, dict) and c.get("name"):
            comp_by_name[c["name"]] = c
    if not comp_by_name:
        return component_to_igs, component_to_patterns

    symbol_index = _build_symbol_index(project_root)

    def _component_for_path(rel_path: str) -> str | None:
        parent = str(PurePosixPath(rel_path).parent)
        # Longest-prefix match against component locations.
        best, best_len = None, -1
        for loc, comp in components_by_dir.items():
            if not loc:
                continue
            if parent == loc or parent.startswith(loc + "/"):
                if len(loc) > best_len:
                    best, best_len = comp.get("name"), len(loc)
        return best

    def _resolve(value: str) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        if value in comp_by_name:
            return value
        rel = symbol_index.get(value)
        if rel:
            return _component_for_path(rel)
        return None

    for ig in blueprint.get("implementation_guidelines") or []:
        if not isinstance(ig, dict) or not ig.get("capability"):
            continue
        targets: set[str] = set()
        for s in ig.get("scope") or []:
            cn = _resolve(s)
            if cn:
                targets.add(cn)
        for cn in targets:
            component_to_igs.setdefault(cn, []).append(ig)

    for pat in (blueprint.get("communication") or {}).get("patterns") or []:
        if not isinstance(pat, dict) or not pat.get("name"):
            continue
        targets = set()
        for s in pat.get("scope") or []:
            cn = _resolve(s)
            if cn:
                targets.add(cn)
        for cn in targets:
            component_to_patterns.setdefault(cn, []).append(pat)

    return component_to_igs, component_to_patterns

#!/usr/bin/env python3
"""Archie deterministic architecture diagram generator.

Renders the blueprint's structural facts into a Mermaid `graph TD` string
without any AI call. Reads:
  - `components.components[*]` — nodes
  - `components.components[*].depends_on` — edges
  - `components.components[*].platform` — subgraph clustering
  - `communication.integrations[*]` — external service pills
  - `persistence_stores[*]` — cylinder nodes
  - `data_models[*].{owned_by_component, store}` — owner==>store edges

Used by `finalize.py` to set `bp["architecture_diagram"]` deterministically,
replacing the AI-generated diagram that Wave 2 used to produce. Zero AI
cost, fully reproducible, no hallucinated edges.

Run:
  python3 diagram.py /path/to/project        # writes bp.architecture_diagram
  python3 diagram.py /path/to/project --print # prints diagram only

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# Cap on total component nodes — keeps Mermaid layouts readable on huge
# repos. AI version aimed at 8-12; 15 matches that ballpark while still
# showing meaningful structure on monorepo subpackages. When exceeded,
# top-N is selected by edge degree (out + in), the rest are summarized
# in a single "… N hidden" note node.
_COMPONENT_NODE_LIMIT = 15


def generate(bp: dict) -> str:
    """Generate a Mermaid `graph TD` string from a blueprint dict.

    Returns the empty string when the blueprint has no components — no
    diagram is better than a misleading single-node placeholder.
    """
    components = _components_from(bp)
    if not components:
        return ""

    total_components = len(components)
    selected = _select_top_n(components, _COMPONENT_NODE_LIMIT)
    selected_names = {c.get("name") for c in selected if c.get("name")}

    lines: list[str] = ["graph TD"]

    # ── Components ────────────────────────────────────────────────────────
    # Subgraph clustering only when >1 platform is present. Single-platform
    # repos (backend-only, frontend-only) get a flat list — no point in a
    # single subgraph wrapping everything.
    by_platform = _group_by_platform(selected)
    if len(by_platform) > 1:
        for platform_key in sorted(by_platform.keys()):
            comps = by_platform[platform_key]
            label = _platform_label(platform_key)
            lines.append(f"  subgraph {_node_id(platform_key)}[{_quote(label)}]")
            for c in comps:
                name = c.get("name", "")
                lines.append(f"    {_node_id(name)}[{_quote(name)}]")
            lines.append("  end")
    else:
        for c in selected:
            name = c.get("name", "")
            lines.append(f"  {_node_id(name)}[{_quote(name)}]")

    # ── Component → component edges from depends_on ──────────────────────
    # Wave 1 agents emit depends_on in a few shapes: bare component name,
    # folder slug ("page_settings"), or descriptive string with paren
    # ("common/domain (domainModule)"). `_resolve_to_component` handles
    # all three. Edges to unresolvable values (3rd-party libs, dropped
    # top-N components, free-form prose with no anchor) are silently
    # dropped — never render edges to nonexistent nodes.
    seen_edges: set[tuple[str, str]] = set()
    for c in selected:
        src_name = c.get("name", "")
        if not src_name:
            continue
        src = _node_id(src_name)
        for dep in c.get("depends_on") or []:
            if not isinstance(dep, str):
                continue
            target = _resolve_to_component(dep, selected, selected_names)
            if not target or target == src_name or target not in selected_names:
                continue
            edge = (src_name, target)
            if edge in seen_edges:
                continue
            seen_edges.add(edge)
            lines.append(f"  {src} --> {_node_id(target)}")

    # ── External integrations (Stripe, Firebase, etc.) ──────────────────
    # Rendered as rounded pills `([Service])`. Dotted edge from the
    # component whose location is the deepest prefix of integration_point.
    # When we can't resolve the attachment, the external node is added on
    # its own — still visually informative.
    integrations = _get(bp, "communication", "integrations", default=[]) or []
    seen_externals: set[str] = set()
    for integ in integrations:
        if not isinstance(integ, dict):
            continue
        service = (integ.get("service") or "").strip()
        if not service or service in seen_externals:
            continue
        seen_externals.add(service)
        ext_id = _node_id(f"ext_{service}")
        lines.append(f"  {ext_id}([{_quote(service)}])")
        attach = _find_component_for_path(
            integ.get("integration_point", ""), selected
        )
        if attach and attach in selected_names:
            lines.append(f"  {_node_id(attach)} -.->|integrates| {ext_id}")

    # ── Persistence layer — stores + owner→store edges ──────────────────
    # Cylinder nodes for stores. Edges aggregated by (owner_component,
    # store) so multiple models owned by the same component don't draw
    # one arrow per model.
    stores = bp.get("persistence_stores") or []
    rendered_stores: set[str] = set()
    for s in stores:
        if not isinstance(s, dict):
            continue
        name = (s.get("name") or "").strip()
        if not name or name in rendered_stores:
            continue
        rendered_stores.add(name)
        lines.append(f"  {_node_id(f'store_{name}')}[({_quote(name)})]")

    persistence_edges: set[tuple[str, str]] = set()
    for m in bp.get("data_models") or []:
        if not isinstance(m, dict):
            continue
        owner_raw = (m.get("owned_by_component") or "").strip()
        store = (m.get("store") or "").strip()
        if not owner_raw or not store:
            continue
        # Resolve folder-slug/path/descriptive-string owners to a real
        # component name (see _resolve_to_component for the shapes handled).
        owner = _resolve_to_component(owner_raw, selected, selected_names)
        if not owner or owner not in selected_names:
            continue
        if store not in rendered_stores:
            continue
        persistence_edges.add((owner, store))
    for owner, store in sorted(persistence_edges):
        lines.append(
            f"  {_node_id(owner)} ==>|persists| {_node_id(f'store_{store}')}"
        )

    # ── Hidden-count note (when top-N cap engaged) ───────────────────────
    if total_components > len(selected):
        hidden = total_components - len(selected)
        note_id = _node_id("note_hidden_components")
        lines.append(
            f'  {note_id}[/"… {hidden} more components hidden"/]'
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _components_from(bp: dict) -> list[dict]:
    """Extract the components list from the blueprint, defensively."""
    comps = (bp.get("components") or {}).get("components") or []
    return [c for c in comps if isinstance(c, dict) and c.get("name")]


def _get(bp: dict, *keys, default=None):
    """Safe nested dict access. _get(bp, 'a', 'b') == bp['a']['b']."""
    cur = bp
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


def _select_top_n(components: list[dict], limit: int) -> list[dict]:
    """Pick the top-N components by edge degree (out + in).

    Out-degree counts only edges to other named components in the set
    (filters out 3rd-party library dependencies). Stable tie-break on
    name ascending so the diagram is reproducible across runs.
    """
    if len(components) <= limit:
        return list(components)
    name_set = {c.get("name") for c in components if c.get("name")}
    in_degree: dict[str, int] = {}
    out_degree: dict[str, int] = {}
    for c in components:
        name = c.get("name", "")
        deps = [d for d in (c.get("depends_on") or []) if isinstance(d, str) and d in name_set and d != name]
        out_degree[name] = len(deps)
        for d in deps:
            in_degree[d] = in_degree.get(d, 0) + 1

    def score(c: dict) -> tuple[int, str]:
        name = c.get("name", "")
        return (-(in_degree.get(name, 0) + out_degree.get(name, 0)), name)

    return sorted(components, key=score)[:limit]


def _group_by_platform(components: list[dict]) -> dict[str, list[dict]]:
    """Group selected components by platform. Empty/missing platform falls
    into a `shared` bucket so it still gets clustered with other untagged
    components instead of disappearing."""
    out: dict[str, list[dict]] = {}
    for c in components:
        platform = (c.get("platform") or "").strip().lower() or "shared"
        out.setdefault(platform, []).append(c)
    return out


_PLATFORM_LABELS = {
    "backend": "Backend",
    "frontend": "Frontend",
    "ios": "iOS",
    "android": "Android",
    "shared": "Shared",
    "mobile": "Mobile",
    "desktop": "Desktop",
    "cli": "CLI",
    "web": "Web",
}


def _platform_label(platform: str) -> str:
    """Human-readable platform label for the subgraph heading."""
    return _PLATFORM_LABELS.get(platform.lower(), platform.title())


def _find_component_for_path(path: str, components: list[dict]) -> str:
    """Return the name of the component whose `location` is the deepest
    prefix of `path`. Empty string if no component matches."""
    if not isinstance(path, str) or not path:
        return ""
    path = path.strip().lstrip("./").rstrip("/")
    best_name = ""
    best_len = -1
    for c in components:
        loc = (c.get("location") or "").strip().lstrip("./").rstrip("/")
        if not loc:
            continue
        if path == loc or path.startswith(loc + "/"):
            if len(loc) > best_len:
                best_len = len(loc)
                best_name = c.get("name", "")
    return best_name


def _resolve_to_component(
    value: str,
    components: list[dict],
    component_name_set: set[str],
) -> str:
    """Resolve a string to a known component name, tolerating common shapes
    Wave 1 agents emit:

      1. Exact name match (`"OrderService"` → `"OrderService"`)
      2. Descriptive strings with parenthetical (`"common/domain (domainModule)"`
         → strip paren, try again)
      3. Folder slug — match against the deepest segment of a component's
         `location` (`"page_settings"` → "Settings Page" if any component's
         location ends with `/page_settings`)
      4. Full path — match against a `location` prefix (handled by
         `_find_component_for_path`)

    Returns empty string when no match — caller filters out unresolved
    references rather than rendering edges to nonexistent nodes.
    """
    if not isinstance(value, str) or not value.strip():
        return ""
    raw = value.strip()
    # 1. Direct name match (fast path)
    if raw in component_name_set:
        return raw
    # 2. Strip parenthetical and try again
    stripped = raw.split("(", 1)[0].strip().rstrip(",").strip()
    if stripped and stripped != raw and stripped in component_name_set:
        return stripped
    # 3. Folder slug — match component whose location's deepest segment
    #    matches the value (e.g. value=`page_settings` matches a location
    #    ending in `/page_settings`).
    candidate = stripped or raw
    candidate_clean = candidate.lstrip("./").rstrip("/")
    if candidate_clean:
        for c in components:
            loc = (c.get("location") or "").rstrip("/")
            if loc.endswith("/" + candidate_clean) or loc == candidate_clean:
                return c.get("name", "")
    # 4. Full-path resolver fallback (component whose location is a prefix
    #    of the value)
    return _find_component_for_path(candidate_clean, components)


_NODE_ID_RE = re.compile(r"[^A-Za-z0-9_]")


def _node_id(name: str) -> str:
    """Convert an arbitrary name into a valid Mermaid identifier.

    Mermaid IDs are alphanumeric + underscore. Non-conforming chars are
    replaced with underscore; IDs starting with a digit are prefixed
    with `n_` so Mermaid's parser accepts them.
    """
    if not isinstance(name, str):
        name = str(name)
    safe = _NODE_ID_RE.sub("_", name).strip("_") or "n"
    if not safe[0].isalpha() and safe[0] != "_":
        safe = "n_" + safe
    return safe


def _quote(label: str) -> str:
    """Escape a display label for use inside Mermaid `[...]`/`(...)` brackets.

    Mermaid label parsing breaks on unescaped quotes and newlines. Wrapping
    in double quotes and replacing both keeps the diagram parseable.
    """
    if not isinstance(label, str):
        label = str(label)
    safe = label.replace('"', "'").replace("\n", " ").strip()
    return f'"{safe}"'


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    args = sys.argv[1:]
    print_only = "--print" in args
    args = [a for a in args if a != "--print"]
    if not args:
        print(
            "Usage: python3 diagram.py /path/to/project [--print]",
            file=sys.stderr,
        )
        return 1

    root = Path(args[0]).resolve()
    bp_path = root / ".archie" / "blueprint.json"
    if not bp_path.exists():
        print(f"Error: {bp_path} not found", file=sys.stderr)
        return 1

    try:
        bp = json.loads(bp_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"Error reading blueprint: {e}", file=sys.stderr)
        return 1

    diagram = generate(bp)

    if print_only:
        if diagram:
            print(diagram)
        else:
            print("(no diagram — empty components list)", file=sys.stderr)
        return 0

    bp["architecture_diagram"] = diagram
    bp_path.write_text(json.dumps(bp, indent=2), encoding="utf-8")
    line_count = len(diagram.split("\n")) if diagram else 0
    print(
        f"Wrote architecture_diagram ({line_count} lines) into {bp_path.relative_to(root)}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

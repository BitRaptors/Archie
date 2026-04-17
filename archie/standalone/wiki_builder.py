"""Archie standalone wiki builder — generates .archie/wiki/** from blueprint.

Zero dependencies beyond Python 3.9+ stdlib. Designed to run both as
archie/standalone/wiki_builder.py in the dev repo and as .archie/wiki_builder.py
copied into consumer projects.

Pipeline:
  Pass 1: blueprint.json -> page markdown under .archie/wiki/{type}/<slug>.md + index.md
  Pass 2: wiki_index.py walks the pages, builds _meta/backlinks.json and
          _meta/provenance.json, then appends "## Referenced by" to each page.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


_SLUG_RE = re.compile(r"[^a-z0-9]+")
# Matches lower/digit followed by UpperLower (e.g. userService → user-Service)
_CAMEL_RE1 = re.compile(r"([a-z0-9])([A-Z][a-z])")
# Matches a run of caps followed by UpperLower (e.g. XMLParser → XML-Parser)
_CAMEL_RE2 = re.compile(r"([A-Z]+)([A-Z][a-z])")


def slugify(name: str) -> str:
    """Lowercase, alphanumerics-and-hyphens only, no leading/trailing hyphens.

    Handles CamelCase/PascalCase by inserting hyphens at word boundaries
    (e.g. UserService → user-service, XMLParser → xml-parser) while leaving
    all-caps acronyms like PostgreSQL intact.
    """
    name = _CAMEL_RE1.sub(r"\1-\2", name)
    name = _CAMEL_RE2.sub(r"\1-\2", name)
    slug = _SLUG_RE.sub("-", name.lower()).strip("-")
    return slug or "untitled"


def slugify_unique(name: str, seen: set[str]) -> str:
    """Return a slug that is not in `seen`. Adds numeric suffix on collision.

    Mutates `seen` by adding the returned slug. Call with a shared set per page
    type so collisions are namespaced (components are independent from pitfalls).
    """
    base = slugify(name)
    candidate = base
    n = 2
    while candidate in seen:
        candidate = f"{base}-{n}"
        n += 1
    seen.add(candidate)
    return candidate


def _frontmatter(**kv: str) -> str:
    """Render a YAML frontmatter block. Values must be strings (we do not escape)."""
    lines = ["---"]
    for key, value in kv.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _section(heading: str, body: str) -> str:
    """Render a section if body is non-empty, else empty string."""
    body = body.strip()
    if not body:
        return ""
    return f"\n## {heading}\n\n{body}\n"


def _list_lines(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items if item)


def render_decision(decision: dict, slug: str) -> str:
    """Render a single decision as markdown with frontmatter.

    Expects a decision dict from blueprint.decisions.key_decisions[]. Missing
    optional fields are rendered as "_(not specified)_" or the section is omitted.
    """
    title = decision.get("title", "Untitled decision")
    chosen = decision.get("chosen", "_(not specified)_")
    rationale = decision.get("rationale", "").strip()
    forced_by = decision.get("forced_by", "").strip()
    enables = decision.get("enables", "").strip()
    alternatives = decision.get("alternatives_rejected", []) or []

    parts = [
        _frontmatter(type="decision", slug=slug, provenance="EXTRACTED"),
        f"\n# {title}\n",
        f"\n**Chosen:** {chosen}\n",
    ]
    if rationale:
        parts.append(f"\n**Rationale:** {rationale}\n")
    parts.append(_section("Forced by", forced_by))
    parts.append(_section("Enables", enables))
    if alternatives:
        parts.append(_section("Alternatives rejected", _list_lines(alternatives)))
    # Referenced-by is appended by wiki_index.py in Pass 2.
    return "".join(parts)


def _link_or_text(name: str, slugs: dict[str, str], dir_name: str) -> str:
    """Return '[Name](../dir/slug.md)' if name is known, else 'Name' plain."""
    slug = slugs.get(name)
    if slug:
        return f"[{name}](../{dir_name}/{slug}.md)"
    return name


def render_component(component: dict, slug: str, component_slugs: dict[str, str]) -> str:
    name = component.get("name", "Untitled component")
    purpose = component.get("purpose", "").strip()
    depends_on = component.get("depends_on", []) or []
    exposes_to = component.get("exposes_to", []) or []

    dep_links = [_link_or_text(n, component_slugs, "components") for n in depends_on]
    exp_links = [_link_or_text(n, component_slugs, "components") for n in exposes_to]

    parts = [
        _frontmatter(type="component", slug=slug, provenance="EXTRACTED"),
        f"\n# {name}\n",
    ]
    if purpose:
        parts.append(f"\n**Purpose:** {purpose}\n")
    if dep_links:
        parts.append(_section("Depends on", _list_lines(dep_links)))
    if exp_links:
        parts.append(_section("Exposes to", _list_lines(exp_links)))
    return "".join(parts)


def render_pattern(pattern: dict, slug: str) -> str:
    name = pattern.get("name", "Untitled pattern")
    when_to_use = pattern.get("when_to_use", "").strip()
    when_not = pattern.get("when_not_to_use", "").strip()

    parts = [
        _frontmatter(type="pattern", slug=slug, provenance="EXTRACTED"),
        f"\n# {name}\n",
    ]
    parts.append(_section("When to use", when_to_use))
    parts.append(_section("When NOT to use", when_not))
    return "".join(parts)


def render_pitfall(pitfall: dict, slug: str, decision_slugs: dict[str, str]) -> str:
    area = pitfall.get("area", "Untitled pitfall")
    description = pitfall.get("description", "").strip()
    stems_from = pitfall.get("stems_from", "").strip()
    recommendation = pitfall.get("recommendation", "").strip()

    parts = [
        _frontmatter(type="pitfall", slug=slug, provenance="EXTRACTED"),
        f"\n# {area}\n",
    ]
    if description:
        parts.append(f"\n**Description:** {description}\n")
    if stems_from:
        linked = _link_or_text(stems_from, decision_slugs, "decisions")
        parts.append(f"\n**Stems from:** {linked}\n")
    if recommendation:
        parts.append(f"\n**Recommendation:** {recommendation}\n")
    return "".join(parts)


def render_index(blueprint: dict, slug_map: dict[str, dict[str, str]]) -> str:
    project_name = blueprint.get("meta", {}).get("project_name", "Project")
    decisions = slug_map.get("decisions", {})
    components = slug_map.get("components", {})
    patterns = slug_map.get("patterns", {})
    pitfalls = slug_map.get("pitfalls", {})

    def _list(name_to_slug: dict[str, str], subdir: str) -> str:
        return "\n".join(
            f"- [{name}](./{subdir}/{slug}.md)" for name, slug in sorted(name_to_slug.items())
        )

    parts = [f"# {project_name} Wiki\n"]
    parts.append(
        "\n> Generated by Archie. Start here before implementing anything — follow\n"
        "> links to understand decisions, components, and pitfalls that affect your work.\n"
    )
    parts.append(
        "\n## Browse by type\n\n"
        f"- **Decisions ({len(decisions)})** — why the architecture is the way it is\n"
        f"- **Components ({len(components)})** — the parts of the system and how they connect\n"
        f"- **Patterns ({len(patterns)})** — reusable design choices\n"
        f"- **Pitfalls ({len(pitfalls)})** — known traps and how to avoid them\n"
    )
    if decisions:
        parts.append("\n## Decisions\n\n" + _list(decisions, "decisions") + "\n")
    if components:
        parts.append("\n## Components\n\n" + _list(components, "components") + "\n")
    if patterns:
        parts.append("\n## Patterns\n\n" + _list(patterns, "patterns") + "\n")
    if pitfalls:
        parts.append("\n## Pitfalls\n\n" + _list(pitfalls, "pitfalls") + "\n")
    return "".join(parts)


def _build_slug_map(blueprint: dict) -> dict[str, dict[str, str]]:
    """Return {type: {name: slug}} where each type has its own slug namespace."""
    decisions = blueprint.get("decisions", {}).get("key_decisions", []) or []
    components = blueprint.get("components", []) or []
    patterns = blueprint.get("communication", {}).get("patterns", []) or []
    pitfalls = blueprint.get("pitfalls", []) or []

    def _map(items: list[dict], key: str) -> dict[str, str]:
        seen: set[str] = set()
        out: dict[str, str] = {}
        for item in items:
            name = item.get(key)
            if not name:
                continue
            out[name] = slugify_unique(name, seen)
        return out

    return {
        "decisions": _map(decisions, "title"),
        "components": _map(components, "name"),
        "patterns": _map(patterns, "name"),
        "pitfalls": _map(pitfalls, "area"),
    }


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_wiki(project_root: Path) -> None:
    """Pass 1: read blueprint.json, emit all pages + index.md under .archie/wiki/."""
    blueprint_path = project_root / ".archie" / "blueprint.json"
    if not blueprint_path.exists():
        raise FileNotFoundError(f"blueprint.json not found at {blueprint_path}")
    blueprint = json.loads(blueprint_path.read_text(encoding="utf-8"))

    wiki_root = project_root / ".archie" / "wiki"
    # Full rebuild — Plan 1 has no incremental update.
    if wiki_root.exists():
        shutil.rmtree(wiki_root)
    wiki_root.mkdir(parents=True)

    slug_map = _build_slug_map(blueprint)

    for decision in blueprint.get("decisions", {}).get("key_decisions", []) or []:
        slug = slug_map["decisions"].get(decision.get("title"))
        if not slug:
            continue
        _write(wiki_root / "decisions" / f"{slug}.md", render_decision(decision, slug))

    for component in blueprint.get("components", []) or []:
        slug = slug_map["components"].get(component.get("name"))
        if not slug:
            continue
        _write(
            wiki_root / "components" / f"{slug}.md",
            render_component(component, slug, slug_map["components"]),
        )

    for pattern in blueprint.get("communication", {}).get("patterns", []) or []:
        slug = slug_map["patterns"].get(pattern.get("name"))
        if not slug:
            continue
        _write(wiki_root / "patterns" / f"{slug}.md", render_pattern(pattern, slug))

    for pitfall in blueprint.get("pitfalls", []) or []:
        slug = slug_map["pitfalls"].get(pitfall.get("area"))
        if not slug:
            continue
        _write(
            wiki_root / "pitfalls" / f"{slug}.md",
            render_pitfall(pitfall, slug, slug_map["decisions"]),
        )

    _write(wiki_root / "index.md", render_index(blueprint, slug_map))

    # Pass 2: backlinks + referenced-by + provenance.
    import wiki_index
    backlinks = wiki_index.build_backlinks(wiki_root)
    wiki_index.write_backlinks(wiki_root, backlinks)
    wiki_index.inject_referenced_by(wiki_root, backlinks)
    wiki_index.write_provenance(wiki_root, last_refreshed=date.today().isoformat())


def _wiki_enabled(project_root: "Path | None" = None) -> bool:
    """Return False only when explicitly disabled via env var or .archie/archie.json."""
    env_val = os.environ.get("ARCHIE_WIKI_ENABLED", "").strip().lower()
    if env_val:
        return env_val not in {"false", "0", "no", "off"}
    # Fall back to .archie/archie.json
    if project_root is not None:
        archie_json = Path(project_root) / ".archie" / "archie.json"
        if archie_json.exists():
            try:
                cfg = json.loads(archie_json.read_text(encoding="utf-8"))
                if cfg.get("wiki_enabled") is False:
                    return False
            except Exception:
                pass
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archie LLM Wiki builder (Pass 1 + Pass 2).")
    parser.add_argument("project_root", help="Path to project with .archie/blueprint.json")
    args = parser.parse_args(argv)
    if not _wiki_enabled(project_root=Path(args.project_root)):
        print("Wiki generation disabled (ARCHIE_WIKI_ENABLED=false). Skipped.")
        return 0
    build_wiki(Path(args.project_root))
    print(f"Wiki built at {args.project_root}/.archie/wiki/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
import fnmatch
import hashlib
import json
import os
import re
import shutil
import sys
from collections.abc import Callable
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


def diff_scans(old_scan: dict, new_scan: dict) -> dict[str, list[str]]:
    """Return {added, modified, deleted} lists of file paths based on hashes.

    Both scans are expected to have a top-level `files` key that is a list of
    {path, hash} dicts. Missing or empty inputs are treated as zero files.
    """
    def _hashes(scan: dict) -> dict[str, str]:
        return {f["path"]: f.get("hash", "") for f in scan.get("files", []) or []}

    old = _hashes(old_scan)
    new = _hashes(new_scan)
    added = sorted(set(new) - set(old))
    deleted = sorted(set(old) - set(new))
    modified = sorted(p for p in set(new) & set(old) if new[p] != old[p])
    return {"added": added, "modified": modified, "deleted": deleted}


def affected_pages(provenance: dict, changed_files: list[str]) -> list[str]:
    """Return wiki-root-relative page paths whose evidence globs match any
    changed file. Pages without an `evidence` field are never considered
    affected (their regeneration must be triggered by a blueprint-structure change).
    """
    affected = []
    for page, prov in provenance.items():
        evidence = prov.get("evidence") or []
        if not evidence:
            continue
        for glob in evidence:
            if any(fnmatch.fnmatch(f, glob) for f in changed_files):
                affected.append(page)
                break
    return sorted(affected)


def write_if_changed(
    path: Path,
    content: str,
    normalize_existing: "Callable[[str], str] | None" = None,
) -> bool:
    """Write content to path only if the file content differs. Returns True when
    the file was written. Creates parent directories as needed.

    ``normalize_existing`` is an optional callable applied to the on-disk content
    before comparison. Use it to strip auto-appended sections (e.g. '## Referenced
    by') so that pages are only rewritten when the canonical body has changed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing_text = path.read_text(encoding="utf-8")
        compared = normalize_existing(existing_text) if normalize_existing else existing_text
        if compared == content:
            return False
    path.write_text(content, encoding="utf-8")
    return True


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


def render_capability(capability: dict, slug: str, slugs: dict[str, dict[str, str]]) -> str:
    """Render a capability page.

    `slugs` has sub-dicts keyed by type ('components', 'decisions', 'pitfalls').
    Unknown references degrade to plain text.
    """
    name = capability.get("name", "Untitled capability")
    purpose = capability.get("purpose", "").strip()
    provenance = capability.get("provenance", "INFERRED")
    entry_points = capability.get("entry_points", []) or []
    uses = capability.get("uses_components", []) or []
    decisions = capability.get("constrained_by_decisions", []) or []
    pitfalls = capability.get("related_pitfalls", []) or []
    key_files = capability.get("key_files", []) or []
    evidence = capability.get("evidence", []) or []

    parts = [
        _frontmatter(type="capability", slug=slug, provenance=provenance),
        f"\n# {name}\n",
    ]
    if purpose:
        parts.append(f"\n**Purpose:** {purpose}\n")
    if entry_points:
        parts.append(_section("Entry points", _list_lines(entry_points)))
    if uses:
        linked = [_link_or_text(n, slugs.get("components", {}), "components") for n in uses]
        parts.append(_section("Components", _list_lines(linked)))
    if decisions:
        linked = [_link_or_text(n, slugs.get("decisions", {}), "decisions") for n in decisions]
        parts.append(_section("Decisions", _list_lines(linked)))
    if pitfalls:
        linked = [_link_or_text(n, slugs.get("pitfalls", {}), "pitfalls") for n in pitfalls]
        parts.append(_section("Pitfalls", _list_lines(linked)))
    if key_files:
        parts.append(_section("Key files", _list_lines([f"`{f}`" for f in key_files])))
    if evidence:
        parts.append(_section("Evidence", _list_lines([f"`{e}`" for e in evidence])))
    return "".join(parts)


def render_index(blueprint: dict, slug_map: dict[str, dict[str, str]]) -> str:
    project_name = blueprint.get("meta", {}).get("project_name", "Project")
    decisions = slug_map.get("decisions", {})
    components = slug_map.get("components", {})
    patterns = slug_map.get("patterns", {})
    pitfalls = slug_map.get("pitfalls", {})
    capabilities = slug_map.get("capabilities", {})

    cap_entries = []
    for cap in blueprint.get("capabilities", []) or []:
        name = cap.get("name")
        slug = capabilities.get(name)
        if not slug:
            continue
        purpose = (cap.get("purpose") or "").strip().replace("\n", " ")
        cap_entries.append((name, slug, purpose))

    def _list(name_to_slug: dict[str, str], subdir: str) -> str:
        return "\n".join(
            f"- [{name}](./{subdir}/{slug}.md)" for name, slug in sorted(name_to_slug.items())
        )

    parts = [f"# {project_name} Wiki\n"]

    if cap_entries:
        parts.append(
            "\n## Before you implement anything\n\n"
            "These capabilities already exist. If your task belongs to one, open it and\n"
            "follow its links before writing any code.\n\n"
        )
        for name, slug, purpose in sorted(cap_entries):
            suffix = f" — {purpose}" if purpose else ""
            parts.append(f"- [{name}](./capabilities/{slug}.md){suffix}\n")
        parts.append("\n")
    else:
        parts.append(
            "\n> Generated by Archie. Start here before implementing anything — follow\n"
            "> links to understand decisions, components, and pitfalls that affect your work.\n"
        )

    parts.append(
        "\n## Browse by type\n\n"
        f"- **Capabilities ({len(capabilities)})** — user-facing features\n"
        f"- **Decisions ({len(decisions)})** — why the architecture is the way it is\n"
        f"- **Components ({len(components)})** — system parts and how they connect\n"
        f"- **Patterns ({len(patterns)})** — reusable design choices\n"
        f"- **Pitfalls ({len(pitfalls)})** — known traps and how to avoid them\n"
    )
    if capabilities:
        parts.append("\n## Capabilities\n\n" + _list(capabilities, "capabilities") + "\n")
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
    capabilities = blueprint.get("capabilities", []) or []

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
        "capabilities": _map(capabilities, "name"),
    }


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _collect_evidence_map(blueprint: dict, slug_map: dict[str, dict[str, str]]) -> dict[str, list[str]]:
    """Return a map of wiki-root-relative page paths to their evidence globs.

    Only capability pages carry evidence globs (from the capabilities agent).
    All other page types depend on blueprint structure, not file evidence, so
    they are intentionally omitted.
    """
    evidence_map: dict[str, list[str]] = {}
    for capability in blueprint.get("capabilities", []) or []:
        slug = slug_map["capabilities"].get(capability.get("name"))
        if not slug:
            continue
        evidence = capability.get("evidence") or []
        if evidence:
            evidence_map[f"capabilities/{slug}.md"] = list(evidence)
    return evidence_map


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

    for capability in blueprint.get("capabilities", []) or []:
        slug = slug_map["capabilities"].get(capability.get("name"))
        if not slug:
            continue
        _write(
            wiki_root / "capabilities" / f"{slug}.md",
            render_capability(capability, slug, slug_map),
        )

    _write(wiki_root / "index.md", render_index(blueprint, slug_map))

    # Pass 2: backlinks + referenced-by + provenance.
    import wiki_index
    backlinks = wiki_index.build_backlinks(wiki_root)
    wiki_index.write_backlinks(wiki_root, backlinks)
    wiki_index.inject_referenced_by(wiki_root, backlinks)
    evidence_map = _collect_evidence_map(blueprint, slug_map)
    wiki_index.write_provenance(wiki_root, last_refreshed=date.today().isoformat(), evidence_map=evidence_map)


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


def _load_previous_scan(raw: str | None, project: Path) -> dict:
    import sys as _sys
    if not raw:
        return {"files": []}
    p = Path(raw)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"warning: previous scan at {p} is malformed JSON: {exc}. Treating as empty.", file=_sys.stderr)
            return {"files": []}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"files": []}


def _blueprint_structure_changed(provenance: dict, blueprint: dict) -> bool:
    """Return True if the set of decisions/components/pitfalls/patterns in the
    blueprint does not match the set of pages recorded in provenance."""
    def _pages(prefix: str) -> set[str]:
        return {p for p in provenance if p.startswith(prefix)}

    expected_decisions = {
        slugify(d.get("title", ""))
        for d in blueprint.get("decisions", {}).get("key_decisions", []) or []
    }
    expected_components = {slugify(c.get("name", "")) for c in blueprint.get("components", []) or []}
    expected_patterns = {
        slugify(p.get("name", ""))
        for p in blueprint.get("communication", {}).get("patterns", []) or []
    }
    expected_pitfalls = {slugify(p.get("area", "")) for p in blueprint.get("pitfalls", []) or []}

    def _slugs(prefix: str) -> set[str]:
        return {Path(p).stem for p in _pages(prefix)}

    return (
        expected_decisions != _slugs("decisions/")
        or expected_components != _slugs("components/")
        or expected_patterns != _slugs("patterns/")
        or expected_pitfalls != _slugs("pitfalls/")
    )


def _find_capability_by_slug(blueprint: dict, slug: str, slug_map: dict[str, str]) -> dict | None:
    for cap in blueprint.get("capabilities", []) or []:
        if slug_map.get(cap.get("name")) == slug:
            return cap
    return None


def build_wiki_incremental(project_root: Path, previous_scan: dict) -> None:
    """Refresh only pages whose evidence files changed. Aborts (raising
    RuntimeError) if the blueprint structure indicates a need for full rebuild."""
    wiki_root = project_root / ".archie" / "wiki"
    prov_path = wiki_root / "_meta" / "provenance.json"
    if not prov_path.exists():
        # No prior wiki: fall back to full build.
        build_wiki(project_root)
        return
    provenance = json.loads(prov_path.read_text(encoding="utf-8"))
    new_scan_path = project_root / ".archie" / "scan.json"
    new_scan = (
        json.loads(new_scan_path.read_text(encoding="utf-8"))
        if new_scan_path.exists() else {"files": []}
    )
    diff = diff_scans(previous_scan, new_scan)
    changed_files = diff["added"] + diff["modified"] + diff["deleted"]
    if not changed_files:
        print("Wiki incremental: no changed files, nothing to do.")
        return

    # Blueprint structure changes require a full rebuild.
    blueprint = json.loads((project_root / ".archie" / "blueprint.json").read_text())
    if _blueprint_structure_changed(provenance, blueprint):
        raise RuntimeError(
            "Blueprint structure changed (decisions/components/pitfalls). "
            "Run /archie-deep-scan instead of /archie-scan."
        )

    affected = affected_pages(provenance, changed_files)
    if not affected:
        print("Wiki incremental: no affected pages.")
        return

    slug_map = _build_slug_map(blueprint)
    rewritten: list[str] = []
    for page_rel in affected:
        # Only capability pages are regenerated by scan. All other pages depend
        # on blueprint structure and are handled by full rebuild.
        if not page_rel.startswith("capabilities/"):
            continue
        slug = Path(page_rel).stem
        cap = _find_capability_by_slug(blueprint, slug, slug_map["capabilities"])
        if not cap:
            continue
        content = render_capability(cap, slug, slug_map)
        page_abs = wiki_root / page_rel
        # Strip the auto-appended "## Referenced by" section before comparing so
        # we only rewrite when the canonical body (not the injected backlinks) has
        # actually changed.
        import wiki_index as _wi
        if write_if_changed(page_abs, content, normalize_existing=_wi._strip_block):
            rewritten.append(page_rel)

    # Rebuild backlinks + "Referenced by" + provenance on any rewrite.
    if rewritten:
        import wiki_index
        backlinks = wiki_index.build_backlinks(wiki_root)
        wiki_index.write_backlinks(wiki_root, backlinks)
        wiki_index.inject_referenced_by(wiki_root, backlinks)
        evidence_map = _collect_evidence_map(blueprint, slug_map)
        wiki_index.write_provenance(wiki_root, last_refreshed=date.today().isoformat(), evidence_map=evidence_map)
    print(f"Wiki incremental: {len(rewritten)} pages rewritten.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archie LLM Wiki builder.")
    parser.add_argument("project_root", help="Path to project with .archie/blueprint.json")
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Only refresh pages whose evidence files changed.",
    )
    parser.add_argument(
        "--previous-scan",
        default=None,
        help="Path to or inline JSON of the previous scan snapshot.",
    )
    args = parser.parse_args(argv)
    if not _wiki_enabled(Path(args.project_root)):
        print("Wiki generation disabled (ARCHIE_WIKI_ENABLED=false). Skipped.")
        return 0
    project = Path(args.project_root)
    if args.incremental:
        prev = _load_previous_scan(args.previous_scan, project)
        build_wiki_incremental(project, prev)
    else:
        build_wiki(project)
    print(f"Wiki built at {project}/.archie/wiki/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

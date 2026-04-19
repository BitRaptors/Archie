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
from collections import defaultdict
from collections.abc import Callable
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


_SLUG_RE = re.compile(r"[^a-z0-9]+")
# Matches lower/digit followed by UpperLower (e.g. userService → user-Service)
_CAMEL_RE1 = re.compile(r"([a-z0-9])([A-Z][a-z])")
# Matches a run of caps followed by UpperLower (e.g. XMLParser → XML-Parser)
_CAMEL_RE2 = re.compile(r"([A-Z]+)([A-Z][a-z])")


def _as_dict(value) -> dict:
    """Return value if dict, else empty dict. Defensive against malformed blueprints."""
    return value if isinstance(value, dict) else {}


def _as_list(value) -> list:
    """Return value if list, else empty list."""
    return value if isinstance(value, list) else []


def _extract_components(blueprint: dict) -> list:
    """Return the components list, handling two real-world shapes:
      1. `blueprint.components` is a list directly.
      2. `blueprint.components` is a dict with a nested `components` list.
    """
    raw = blueprint.get("components")
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        inner = raw.get("components")
        if isinstance(inner, list):
            return inner
    return []


def _as_text(value) -> str:
    """Safely coerce to a stripped string.

    - None/empty -> ''
    - str -> stripped
    - list -> newline-joined non-empty elements
    - other -> str() then stripped
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(_as_text(v) for v in value if v)
    return str(value).strip()


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
    chosen = _as_text(decision.get("chosen")) or "_(not specified)_"
    rationale = _as_text(decision.get("rationale"))
    forced_by = _as_text(decision.get("forced_by"))
    enables = _as_text(decision.get("enables"))
    alternatives = _as_list(decision.get("alternatives_rejected"))

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


def render_component(
    component: dict,
    slug: str,
    component_slugs: dict[str, str],
    *,
    data_models: "list[tuple[str, str]] | None" = None,
) -> str:
    name = _as_text(component.get("name")) or "Untitled component"
    purpose = _as_text(component.get("purpose"))
    responsibility = _as_text(component.get("responsibility"))
    location = _as_text(component.get("location"))
    platform = _as_text(component.get("platform"))
    depends_on = _as_list(component.get("depends_on"))
    exposes_to = _as_list(component.get("exposes_to"))
    key_interfaces = _as_list(component.get("key_interfaces"))
    key_files = _as_list(component.get("key_files"))

    parts = [
        _frontmatter(type="component", slug=slug, provenance="EXTRACTED"),
        f"\n# {name}\n",
    ]

    # Inline meta lines (platform, location) — each conditional on presence
    meta_bullets = []
    if platform:
        meta_bullets.append(f"**Platform:** {platform}")
    if location:
        meta_bullets.append(f"**Location:** `{location}`")
    if meta_bullets:
        parts.append("\n" + "\n\n".join(meta_bullets) + "\n")

    if purpose:
        parts.append(f"\n**Purpose:** {purpose}\n")
    if responsibility:
        parts.append(f"\n## Responsibility\n\n{responsibility}\n")

    dep_links = [_link_or_text(n, component_slugs, "components") for n in depends_on]
    exp_links = [_link_or_text(n, component_slugs, "components") for n in exposes_to]
    if dep_links:
        parts.append(_section("Depends on", _list_lines(dep_links)))
    if exp_links:
        parts.append(_section("Exposes to", _list_lines(exp_links)))

    # Public interface
    if key_interfaces:
        lines = ["## Public interface\n"]
        for iface in key_interfaces:
            iname = _as_text(iface.get("name")) if isinstance(iface, dict) else None
            sig = _as_text(iface.get("signature")) if isinstance(iface, dict) else None
            desc = _as_text(iface.get("description")) if isinstance(iface, dict) else None
            if not iname and not sig:
                continue
            head = f"\n- **`{iname}`**" if iname else "\n- "
            if sig:
                head += f" — `{sig}`"
            lines.append(head)
            if desc:
                lines.append(f"  {desc}")
        parts.append("\n".join(lines) + "\n")

    # Key files
    if key_files:
        lines = ["## Key files\n"]
        for kf in key_files:
            fpath = _as_text(kf.get("file")) if isinstance(kf, dict) else _as_text(kf)
            fdesc = _as_text(kf.get("description")) if isinstance(kf, dict) else ""
            if not fpath:
                continue
            if fdesc:
                lines.append(f"\n- `{fpath}` — {fdesc}")
            else:
                lines.append(f"\n- `{fpath}`")
        parts.append("\n".join(lines) + "\n")

    # Data models (reverse map injected by build_wiki)
    if data_models:
        links = [f"[{name}](../data-models/{dm_slug}.md)" for name, dm_slug in data_models]
        parts.append(_section("Data models", _list_lines(links)))

    return "".join(parts)


_PRIMITIVES: dict[str, str] = {
    "string": "string", "str": "string",
    "int": "int", "integer": "int",
    "bool": "bool", "boolean": "bool",
    "float": "float", "double": "float", "number": "float",
    "long": "long",
    "char": "char", "character": "char",
    "bytes": "bytes",
    "void": "void", "none": "void", "unit": "void",
}

_OPT_PATTERNS = [
    re.compile(r"^Optional\s*<\s*(.+?)\s*>$"),
    re.compile(r"^Optional\s*\[\s*(.+?)\s*\]$"),
    re.compile(r"^(.+?)\s*\|\s*None$"),
    re.compile(r"^(.+?)\?$"),
]


def _normalize_field_type(raw) -> str:
    """Map language-specific type notations to a canonical form.

    Optional notations supported:
      Foo?              → foo? (lowercase only when foo is a known primitive)
      Optional<Foo>     → foo?
      Optional[foo]     → foo?
      foo | None        → foo?

    Primitive name canonicalization (case-insensitive, output lowercase):
      String / Str            → string
      Int / Integer           → int
      Bool / Boolean          → bool
      Float / Double / Number → float
      Long                    → long
      Char / Character        → char
      Bytes                   → bytes
      Void / None / Unit      → void

    Custom types (anything not in the primitive map) are preserved verbatim
    minus the optional wrapper.

    Returns "" for None/empty input.
    """
    if not raw:
        return ""
    raw = str(raw).strip()
    if not raw:
        return ""

    # Try each optional wrapper pattern in order
    optional = False
    inner = raw
    for pat in _OPT_PATTERNS:
        m = pat.match(raw)
        if m:
            inner = m.group(1).strip()
            optional = True
            break

    # Canonicalize via primitives map (case-insensitive)
    canonical_inner = _PRIMITIVES.get(inner.lower(), inner)

    if optional:
        return canonical_inner + "?"
    return canonical_inner


def _extract_data_model_refs(
    model: dict,
    known_model_names: "set[str]",
) -> "list[tuple[str, list[str]]]":
    """Find data-model references in field types.

    Scans each field's raw `type` string for any token matching a name in
    known_model_names (word-boundary regex). Excludes self-references.
    Returns [(referenced_name, [field_name, ...]), ...] sorted by referenced_name.
    Field names within each tuple are sorted by appearance order in fields[],
    deduplicated.
    """
    own_name = model.get("name")
    candidates = sorted(n for n in known_model_names if n and n != own_name)
    if not candidates:
        return []

    # Word-boundary regex to avoid partial matches: \b(Foo|Bar|Baz)\b
    pattern = re.compile(r"\b(" + "|".join(re.escape(n) for n in candidates) + r")\b")

    # ref_name -> ordered list of field_names (deduplicated)
    refs: dict[str, list[str]] = {}
    for field in _as_list(model.get("fields")):
        if not isinstance(field, dict):
            continue
        ftype = _as_text(field.get("type"))
        fname = _as_text(field.get("name"))
        if not ftype or not fname:
            continue
        for match in pattern.findall(ftype):
            field_list = refs.setdefault(match, [])
            if fname not in field_list:
                field_list.append(fname)

    return sorted(refs.items(), key=lambda kv: kv[0])


def render_data_model(
    model: dict,
    slug: str,
    component_slugs: dict[str, str],
    *,
    model_slugs: "dict[str, str] | None" = None,
) -> str:
    """Render a single data model entity as markdown with frontmatter.

    Required: name. All other fields are optional and degrade gracefully.
    """
    name = _as_text(model.get("name")) or "Untitled data model"
    purpose = _as_text(model.get("purpose"))
    location = _as_text(model.get("location"))
    fields = _as_list(model.get("fields"))
    used_by = _as_list(model.get("used_by_components"))
    provenance = _as_text(model.get("provenance")) or "INFERRED"

    parts = [
        _frontmatter(type="data-model", slug=slug, provenance=provenance),
        f"\n# {name}\n",
    ]

    if location:
        parts.append(f"\n**Location:** `{location}`\n")
    if purpose:
        parts.append(f"\n**Purpose:** {purpose}\n")

    if fields:
        rows = [
            "\n## Fields\n",
            "",
            "| Name | Type | Nullable |",
            "|---|---|---|",
        ]
        for field in fields:
            fname = _as_text(field.get("name") if isinstance(field, dict) else None)
            ftype = _as_text(field.get("type") if isinstance(field, dict) else None)
            fnullable = field.get("nullable", False) if isinstance(field, dict) else False
            nullable_str = "yes" if fnullable else "no"
            canonical = _normalize_field_type(ftype)
            if canonical and canonical != ftype:
                type_display = f"{canonical} ({ftype})"
            elif canonical:
                type_display = canonical
            else:
                type_display = ftype  # fallback: empty/None canonical → original
            rows.append(f"| `{fname}` | `{type_display}` | {nullable_str} |")
        parts.append("\n".join(rows) + "\n")

    if model_slugs:
        relations = _extract_data_model_refs(model, set(model_slugs.keys()))
        if relations:
            lines = ["## Related models\n"]
            for ref_name, field_names in relations:
                ref_slug = model_slugs.get(ref_name)
                link = f"[{ref_name}](./{ref_slug}.md)" if ref_slug else ref_name
                field_word = "field" if len(field_names) == 1 else "fields"
                field_list = ", ".join(f"`{f}`" for f in field_names)
                lines.append(f"- {link} — via {field_list} {field_word}")
            parts.append("\n" + "\n".join(lines) + "\n")

    if used_by:
        linked = [_link_or_text(n, component_slugs, "components") for n in used_by]
        parts.append(_section("Used by", _list_lines(linked)))

    return "".join(parts)


def render_pattern(pattern: dict, slug: str) -> str:
    name = pattern.get("name", "Untitled pattern")
    when_to_use = _as_text(pattern.get("when_to_use"))
    when_not = _as_text(pattern.get("when_not_to_use"))

    parts = [
        _frontmatter(type="pattern", slug=slug, provenance="EXTRACTED"),
        f"\n# {name}\n",
    ]
    parts.append(_section("When to use", when_to_use))
    parts.append(_section("When NOT to use", when_not))
    return "".join(parts)


def render_pitfall(pitfall: dict, slug: str, decision_slugs: dict[str, str]) -> str:
    area = pitfall.get("area", "Untitled pitfall")
    description = _as_text(pitfall.get("description"))
    stems_from_raw = pitfall.get("stems_from")
    recommendation = _as_text(pitfall.get("recommendation"))

    parts = [
        _frontmatter(type="pitfall", slug=slug, provenance="EXTRACTED"),
        f"\n# {area}\n",
    ]
    if description:
        parts.append(f"\n**Description:** {description}\n")
    # stems_from can be a string (single upstream decision) OR a list (multiple).
    if isinstance(stems_from_raw, list):
        items = [s.strip() for s in stems_from_raw if isinstance(s, str) and s.strip()]
        if items:
            linked = [_link_or_text(s, decision_slugs, "decisions") for s in items]
            parts.append("\n**Stems from:**\n" + _list_lines(linked) + "\n")
    elif isinstance(stems_from_raw, str) and stems_from_raw.strip():
        linked = _link_or_text(stems_from_raw.strip(), decision_slugs, "decisions")
        parts.append(f"\n**Stems from:** {linked}\n")
    if recommendation:
        parts.append(f"\n**Recommendation:** {recommendation}\n")
    applies_to = _as_list(pitfall.get("applies_to"))
    if applies_to:
        paths = [str(p) for p in applies_to if _as_text(p)]
        if paths:
            body = "```\n" + "\n".join(paths) + "\n```"
            parts.append(f"\n## Applies to\n\n{body}\n")
    return "".join(parts)


def render_capability(capability: dict, slug: str, slugs: dict[str, dict[str, str]]) -> str:
    """Render a capability page.

    `slugs` has sub-dicts keyed by type ('components', 'decisions', 'pitfalls').
    Unknown references degrade to plain text.
    """
    name = capability.get("name", "Untitled capability")
    purpose = _as_text(capability.get("purpose"))
    provenance = _as_text(capability.get("provenance")) or "INFERRED"
    entry_points = _as_list(capability.get("entry_points"))
    uses = _as_list(capability.get("uses_components"))
    decisions = _as_list(capability.get("constrained_by_decisions"))
    pitfalls = _as_list(capability.get("related_pitfalls"))
    key_files = _as_list(capability.get("key_files"))
    evidence = _as_list(capability.get("evidence"))

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


def render_guideline(guideline: dict, slug: str) -> str:
    """Render an implementation guideline as a how-to page.

    Required: name, pattern_description.
    Optional: category, libraries[], key_files[], usage_example, tips[].
    """
    name = guideline.get("name", "Untitled guideline")
    category = _as_text(guideline.get("category"))
    pattern_description = _as_text(guideline.get("pattern_description"))
    libraries = _as_list(guideline.get("libraries"))
    key_files = _as_list(guideline.get("key_files"))
    usage_example = _as_text(guideline.get("usage_example"))
    tips = _as_list(guideline.get("tips"))

    # Frontmatter — include category if present
    fm_kwargs = {"type": "guideline", "slug": slug, "provenance": "EXTRACTED"}
    if category:
        fm_kwargs["category"] = category
    parts = [_frontmatter(**fm_kwargs), f"\n# {name}\n"]

    if category:
        parts.append(f"\n**Category:** {category}\n")
    if pattern_description:
        parts.append(_section("Pattern", pattern_description))
    if libraries:
        parts.append(_section("Libraries", _list_lines(libraries)))
    if key_files:
        parts.append(_section("Key files", _list_lines([f"`{f}`" for f in key_files])))
    if usage_example:
        # Fenced code block. Don't assume a language; leave bare fence.
        parts.append(f"\n## Usage example\n\n```\n{usage_example}\n```\n")
    if tips:
        parts.append(_section("Tips", _list_lines(tips)))
    return "".join(parts)


def render_architecture_rules(blueprint: dict) -> str:
    """Render rules/architecture.md combining file_placement_rules + naming_conventions.

    Returns empty string when both sections are empty — caller should skip writing in that case.
    """
    rules = _as_dict(blueprint.get("architecture_rules"))
    file_placement = _as_list(rules.get("file_placement_rules"))
    naming = _as_list(rules.get("naming_conventions"))

    if not file_placement and not naming:
        return ""

    parts = [
        _frontmatter(type="rules-page", slug="rules-architecture"),
        "\n# Architecture rules\n",
    ]

    if file_placement:
        rows = ["## File placement\n", "", "| Pattern | Location | Rationale |", "|---|---|---|"]
        for r in file_placement:
            pattern = _as_text(r.get("pattern")) or "_(unspecified)_"
            location = _as_text(r.get("location"))
            rationale = _as_text(r.get("rationale"))
            rows.append(f"| {pattern} | `{location}` | {rationale} |")
        parts.append("\n" + "\n".join(rows) + "\n")

    if naming:
        rows = ["## Naming conventions\n", "", "| Applies to | Convention | Example |", "|---|---|---|"]
        for r in naming:
            applies = _as_text(r.get("applies_to")) or "_(unspecified)_"
            convention = _as_text(r.get("convention"))
            example = _as_text(r.get("example"))
            rows.append(f"| {applies} | {convention} | `{example}` |")
        parts.append("\n" + "\n".join(rows) + "\n")

    return "".join(parts)


def render_development_rules(blueprint: dict) -> str:
    """Render rules/development.md grouped by category (insertion order preserved).

    Returns empty string when no rules exist.
    """
    rules = _as_list(blueprint.get("development_rules"))
    if not rules:
        return ""

    # Group preserving first-seen category order; uncategorized always last.
    grouped: dict[str, list[dict]] = {}
    uncategorized: list[dict] = []
    for r in rules:
        if not isinstance(r, dict) or not _as_text(r.get("rule")):
            continue
        cat = _as_text(r.get("category"))
        if cat:
            grouped.setdefault(cat, []).append(r)
        else:
            uncategorized.append(r)

    if not grouped and not uncategorized:
        return ""

    parts = [
        _frontmatter(type="rules-page", slug="rules-development"),
        "\n# Development rules\n",
    ]

    def _word(n: int, singular: str, plural: str) -> str:
        return f"{n} {singular}" if n == 1 else f"{n} {plural}"

    def _render_group(title: str, items: list[dict]) -> str:
        header = f"\n## {title} ({_word(len(items), 'rule', 'rules')})\n\n"
        lines = []
        for r in items:
            rule_text = _as_text(r.get("rule"))
            rationale = _as_text(r.get("rationale"))
            applies_to = _as_list(r.get("applies_to"))
            entry = f"- **{rule_text}**"
            if rationale:
                entry += f"\n  {rationale}"
            if applies_to:
                globs = ", ".join(f"`{g}`" for g in applies_to if g)
                if globs:
                    entry += f"\n  _Applies to:_ {globs}"
            lines.append(entry)
        return header + "\n".join(lines) + "\n"

    for cat, items in grouped.items():
        parts.append(_render_group(cat, items))
    if uncategorized:
        parts.append(_render_group("Uncategorized rules", uncategorized))

    return "".join(parts)


def render_technology(blueprint: dict) -> str:
    """Render technology.md with Stack + External integrations + Run commands.

    Returns empty string when all three sub-sections are empty.
    """
    tech = _as_dict(blueprint.get("technology"))
    stack = _as_list(tech.get("stack"))
    run_commands = _as_dict(tech.get("run_commands"))
    integrations = _as_list(_as_dict(blueprint.get("communication")).get("integrations"))

    if not stack and not run_commands and not integrations:
        return ""

    parts = [
        _frontmatter(type="technology", slug="technology"),
        "\n# Technology\n",
    ]

    if stack:
        rows = ["## Stack\n", "", "| Category | Name | Version | Purpose |", "|---|---|---|---|"]
        for s in stack:
            cat = _as_text(s.get("category"))
            name = _as_text(s.get("name"))
            version = _as_text(s.get("version"))
            purpose = _as_text(s.get("purpose"))
            rows.append(f"| {cat} | {name} | {version} | {purpose} |")
        parts.append("\n" + "\n".join(rows) + "\n")

    if integrations:
        lines = ["## External integrations\n"]
        for it in integrations:
            service = _as_text(it.get("service"))
            purpose = _as_text(it.get("purpose"))
            point = _as_text(it.get("integration_point"))
            line = f"\n- **{service}** — {purpose}" if purpose else f"\n- **{service}**"
            if point:
                line += f"\n  _Integration point:_ `{point}`"
            lines.append(line)
        parts.append("\n".join(lines) + "\n")

    if run_commands:
        lines = ["\n## Run commands\n", "", "```bash"]
        for label, cmd in run_commands.items():
            cmd_text = _as_text(cmd)
            if cmd_text:
                lines.append(f"# {label}")
                lines.append(cmd_text)
                lines.append("")
        lines.append("```")
        parts.append("\n".join(lines) + "\n")

    return "".join(parts)


def render_quick_reference(blueprint: dict) -> str:
    """Render quick-reference.md with pattern-selection table + decision tree + error handling.

    Returns empty string when all sub-sections are empty.
    """
    qr = _as_dict(blueprint.get("quick_reference"))
    pattern_selection = _as_list(qr.get("pattern_selection"))
    error_mapping = _as_list(qr.get("error_mapping"))
    decision_tree = _as_list(_as_dict(blueprint.get("communication")).get("pattern_selection_guide"))

    if not pattern_selection and not error_mapping and not decision_tree:
        return ""

    parts = [
        _frontmatter(type="quick-reference", slug="quick-reference"),
        "\n# Quick reference\n",
    ]

    if pattern_selection:
        rows = ["## Which pattern should I use?\n", "", "| Scenario | Recommended pattern |", "|---|---|"]
        for e in pattern_selection:
            scenario = _as_text(e.get("scenario"))
            pattern = _as_text(e.get("pattern"))
            rows.append(f"| {scenario} | {pattern} |")
        parts.append("\n" + "\n".join(rows) + "\n")

    if decision_tree:
        lines = ["## Pattern decision tree\n"]
        for e in decision_tree:
            scenario = _as_text(e.get("scenario"))
            pattern = _as_text(e.get("recommended_pattern"))
            lines.append(f"\n- **{scenario}** → {pattern}")
        parts.append("\n".join(lines) + "\n")

    if error_mapping:
        rows = ["\n## Error handling\n", "", "| Error | Status code | Solution |", "|---|---|---|"]
        for e in error_mapping:
            err = _as_text(e.get("error"))
            code = e.get("status_code")
            code_str = str(code) if code is not None else ""
            solution = _as_text(e.get("solution"))
            rows.append(f"| {err} | {code_str} | {solution} |")
        parts.append("\n".join(rows) + "\n")

    return "".join(parts)


_FRONTEND_FIELD_ORDER = [
    ("framework", "Framework"),
    ("state_management", "State management"),
    ("routing", "Routing"),
    ("styling", "Styling"),
    ("data_fetching", "Data fetching"),
    ("rendering_strategy", "Rendering strategy"),
    ("ui_components", "UI components"),
]


def render_frontend(blueprint: dict) -> str:
    """Render frontend.md from blueprint.frontend.

    Returns empty string when blueprint.frontend is missing/empty OR all fields are empty strings.
    """
    fe = _as_dict(blueprint.get("frontend"))
    if not fe:
        return ""

    bullets = []
    for key, label in _FRONTEND_FIELD_ORDER:
        value = _as_text(fe.get(key))
        if value:
            bullets.append(f"**{label}:** {value}")
    conventions = _as_text(fe.get("conventions"))

    if not bullets and not conventions:
        return ""

    parts = [
        _frontmatter(type="frontend", slug="frontend"),
        "\n# Frontend\n",
    ]
    if bullets:
        parts.append("\n" + "\n\n".join(bullets) + "\n")
    if conventions:
        parts.append(f"\n## Conventions\n\n{conventions}\n")
    return "".join(parts)


def render_architecture(blueprint: dict) -> str:
    """Render architecture.md with a prose overview (executive_summary +
    architecture_style) plus the Mermaid diagram in a fenced block.

    Returns empty string if neither a diagram nor prose is available.
    """
    meta = _as_dict(blueprint.get("meta"))
    summary = _as_text(meta.get("executive_summary"))
    style = _as_text(meta.get("architecture_style"))
    diagram = _as_text(blueprint.get("architecture_diagram"))

    if not summary and not style and not diagram:
        return ""

    parts = [
        _frontmatter(type="architecture", slug="architecture"),
        "\n# Architecture\n",
    ]

    if summary:
        parts.append(f"\n{summary}\n")
    if style:
        parts.append(f"\n## Architectural style\n\n{style}\n")
    if diagram:
        parts.append(f"\n## System diagram\n\n```mermaid\n{diagram}\n```\n")

    return "".join(parts)


def render_index(
    blueprint: dict,
    slug_map: dict[str, dict[str, str]],
    project_root: "Path | None" = None,
    *,
    symbol_count: int = 0,
) -> str:
    meta = _as_dict(blueprint.get("meta"))
    project_name = _as_text(meta.get("project_name"))
    if not project_name and project_root is not None:
        project_name = project_root.name
    if not project_name:
        project_name = "Project"

    decisions = slug_map.get("decisions", {})
    components = slug_map.get("components", {})
    data_models = slug_map.get("data_models", {})
    patterns = slug_map.get("patterns", {})
    pitfalls = slug_map.get("pitfalls", {})
    capabilities = slug_map.get("capabilities", {})
    guidelines = slug_map.get("guidelines", {})

    # Check which single-page outputs the blueprint supports (for browse list)
    has_tech = bool(_as_dict(blueprint.get("technology"))) or bool(
        _as_list(_as_dict(blueprint.get("communication")).get("integrations"))
    )
    has_qr = bool(_as_dict(blueprint.get("quick_reference"))) or bool(
        _as_list(_as_dict(blueprint.get("communication")).get("pattern_selection_guide"))
    )
    has_frontend = bool(_as_dict(blueprint.get("frontend")))
    exec_summary = _as_text(meta.get("executive_summary"))
    has_architecture = bool(_as_text(blueprint.get("architecture_diagram"))) or bool(exec_summary)
    rules_pages = []
    rules = _as_dict(blueprint.get("architecture_rules"))
    if _as_list(rules.get("file_placement_rules")) or _as_list(rules.get("naming_conventions")):
        rules_pages.append("architecture")
    if _as_list(blueprint.get("development_rules")):
        rules_pages.append("development")

    cap_entries = []
    for cap in _as_list(blueprint.get("capabilities")):
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

    # System overview — rendered before capabilities
    arch_style = _as_text(meta.get("architecture_style"))
    platforms = _as_list(meta.get("platforms"))
    if exec_summary or arch_style or platforms:
        parts.append("\n## System overview\n")
        if platforms:
            parts.append(f"\n**Platforms:** {', '.join(str(p) for p in platforms if p)}\n")
        if exec_summary:
            parts.append(f"\n{exec_summary}\n")
        if arch_style:
            parts.append(f"\n### Architecture style\n\n{arch_style}\n")

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
    elif not capabilities:
        # Preserve the old blockquote for projects without capabilities or system overview.
        parts.append(
            "\n> Generated by Archie. Start here before implementing anything — follow\n"
            "> links to understand decisions, components, and pitfalls that affect your work.\n"
        )

    # Browse by type — extended
    browse_lines = [
        "\n## Browse by type\n",
        f"- **Capabilities ({len(capabilities)})** — user-facing features",
        f"- **Decisions ({len(decisions)})** — why the architecture is the way it is",
        f"- **Components ({len(components)})** — system parts and how they connect",
    ]
    if data_models:
        browse_lines.append(
            f"- **Data models ({len(data_models)})** — entities moving through the system"
        )
    browse_lines += [
        f"- **Patterns ({len(patterns)})** — reusable design choices",
        f"- **Pitfalls ({len(pitfalls)})** — known traps and how to avoid them",
        f"- **Guidelines ({len(guidelines)})** — implementation recipes",
    ]
    if symbol_count:
        browse_lines.append(
            f"- **Utilities ({symbol_count} functions)** — existing helpers; grep before implementing new ones"
        )
    if rules_pages:
        browse_lines.append(f"- **Rules ({len(rules_pages)} pages)** — architecture + development rules")
    if has_tech:
        browse_lines.append("- **Technology** — stack + integrations + commands")
    if has_qr:
        browse_lines.append("- **Quick reference** — pattern selection + error handling")
    if has_frontend:
        browse_lines.append("- **Frontend** — framework + conventions")
    if has_architecture:
        browse_lines.append("- **Architecture** — diagram + overview")
    parts.append("\n".join(browse_lines) + "\n")

    if capabilities:
        parts.append("\n## Capabilities\n\n" + _list(capabilities, "capabilities") + "\n")
    if decisions:
        parts.append(
            "\n## Decisions\n\n"
            "- [Decisions overview](./decisions/index.md)\n"
            + _list(decisions, "decisions") + "\n"
        )
    if components:
        parts.append("\n## Components\n\n" + _list(components, "components") + "\n")
    if data_models:
        parts.append("\n## Data models\n\n" + _list(data_models, "data-models") + "\n")
    if patterns:
        parts.append("\n## Patterns\n\n" + _list(patterns, "patterns") + "\n")
    if pitfalls:
        parts.append("\n## Pitfalls\n\n" + _list(pitfalls, "pitfalls") + "\n")
    if guidelines:
        parts.append("\n## Guidelines\n\n" + _list(guidelines, "guidelines") + "\n")
    if symbol_count:
        parts.append("\n## Utilities\n\n- [Utilities catalog](./utilities.md)\n")
    return "".join(parts)


def _build_slug_map(blueprint: dict) -> dict[str, dict[str, str]]:
    """Return {type: {name: slug}} where each type has its own slug namespace."""
    decisions = _as_list(_as_dict(blueprint.get("decisions")).get("key_decisions"))
    components = _extract_components(blueprint)
    patterns = _as_list(_as_dict(blueprint.get("communication")).get("patterns"))
    pitfalls = _as_list(blueprint.get("pitfalls"))
    capabilities = _as_list(blueprint.get("capabilities"))
    guidelines = _as_list(blueprint.get("implementation_guidelines"))

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
        "guidelines": _map(guidelines, "name"),
        "data_models": _map(_as_list(blueprint.get("data_models")), "name"),
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
    for capability in _as_list(blueprint.get("capabilities")):
        slug = slug_map["capabilities"].get(capability.get("name"))
        if not slug:
            continue
        evidence = capability.get("evidence") or []
        if evidence:
            evidence_map[f"capabilities/{slug}.md"] = list(evidence)
    for model in _as_list(blueprint.get("data_models")):
        slug = slug_map["data_models"].get(model.get("name"))
        if not slug:
            continue
        evidence = model.get("evidence") or []
        if evidence:
            evidence_map[f"data-models/{slug}.md"] = list(evidence)
    return evidence_map


def _build_component_to_data_models(
    blueprint: dict,
    data_model_slugs: dict[str, str],
) -> dict[str, list[tuple[str, str]]]:
    """Reverse map: component name -> [(data_model_name, data_model_slug), ...] in blueprint order."""
    reverse: dict[str, list[tuple[str, str]]] = {}
    for model in _as_list(blueprint.get("data_models")):
        model_name = model.get("name")
        model_slug = data_model_slugs.get(model_name)
        if not model_slug:
            continue
        for comp_name in _as_list(model.get("used_by_components")):
            reverse.setdefault(comp_name, []).append((model_name, model_slug))
    return reverse


def render_decisions_index(blueprint: dict, slug_map: dict[str, dict[str, str]]) -> str:
    """Render decisions/index.md overview: architectural_style + trade_offs + out_of_scope + decisions list.

    Returns empty string when no content at all (no style, no trade_offs, no out_of_scope, no key_decisions).
    """
    decisions = _as_dict(blueprint.get("decisions"))
    style = _as_dict(decisions.get("architectural_style"))
    trade_offs = _as_list(decisions.get("trade_offs"))
    out_of_scope = _as_list(decisions.get("out_of_scope"))
    key_decisions = _as_list(decisions.get("key_decisions"))

    style_chosen = _as_text(style.get("chosen"))
    style_rationale = _as_text(style.get("rationale"))
    decision_slugs = _as_dict(slug_map.get("decisions"))

    has_content = (
        style_chosen or style_rationale
        or trade_offs or out_of_scope
        or (key_decisions and decision_slugs)
    )
    if not has_content:
        return ""

    parts = [
        _frontmatter(type="decisions-index", slug="decisions-index"),
        "\n# Architectural decisions\n",
    ]

    if style_chosen or style_rationale:
        parts.append("\n## Architectural style\n")
        if style_chosen:
            parts.append(f"\n**Chosen:** {style_chosen}\n")
        if style_rationale:
            parts.append(f"\n**Rationale:** {style_rationale}\n")

    if trade_offs:
        rows = ["\n## Trade-offs accepted\n", "", "| Accepted cost | Gained benefit |", "|---|---|"]
        for t in trade_offs:
            cost = _as_text(t.get("accepted_cost"))
            benefit = _as_text(t.get("gained_benefit"))
            if cost or benefit:
                rows.append(f"| {cost} | {benefit} |")
        parts.append("\n".join(rows) + "\n")

    if out_of_scope:
        parts.append("\n## Explicitly out of scope\n\n")
        for item in out_of_scope:
            text = _as_text(item)
            if text:
                parts.append(f"- {text}\n")

    if key_decisions and decision_slugs:
        parts.append("\n## All decisions\n\n")
        listed = []
        for d in key_decisions:
            title = _as_text(d.get("title"))
            slug = decision_slugs.get(title) if isinstance(d, dict) else None
            if title and slug:
                listed.append((title, slug))
        for title, slug in sorted(listed):
            parts.append(f"- [{title}](./{slug}.md)\n")

    return "".join(parts)


_TOPIC_WORDS: dict[str, str] = {
    "date": "Date", "dates": "Date", "time": "Time",
    "string": "String", "strings": "String",
    "array": "Array", "arrays": "Array",
    "number": "Number", "numbers": "Number",
    "url": "URL", "urls": "URL",
    "json": "JSON",
    "file": "File", "files": "File", "path": "Path", "paths": "Path",
    "color": "Color", "colors": "Color",
}

_STRIP_SUFFIXES = ("Ext", "Extensions", "Extension", "Utils", "Util",
                   "Helper", "Helpers")


def _categorize_symbol(symbol: dict) -> str:
    """Return a category string for a symbol, used to group the utilities catalog.

    Priority:
    1. Filename topic — stem split on +/-/_, strip common suffixes, match TOPIC_WORDS.
    2. Function-name prefix — format*, is*/has*/can*/should*, to*/from*/parse*/stringify*.
    3. Fallback — "Uncategorized".
    """
    file_path = symbol.get("file") or ""
    stem = Path(file_path).stem if file_path else ""
    # Try filename topic
    parts = re.split(r"[+\-_]", stem)
    for raw in parts:
        cleaned = raw
        for suf in _STRIP_SUFFIXES:
            if cleaned.endswith(suf) and len(cleaned) > len(suf):
                cleaned = cleaned[: -len(suf)]
                break
        topic = _TOPIC_WORDS.get(cleaned.lower())
        if topic:
            return topic
    # Try function-name prefix
    name = symbol.get("name") or ""
    bare = name.split(".")[-1]  # strip "Type." prefix from extension methods
    lower = bare.lower()
    if lower.startswith("format"):
        return "Formatting"
    if any(lower.startswith(p) for p in ("is", "has", "can", "should")):
        return "Predicate"
    if any(lower.startswith(p) for p in ("to", "from", "parse", "stringify")):
        return "Conversion"
    return "Uncategorized"


def render_utilities_catalog(symbols: list[dict] | None) -> str:
    """Render symbols[] as a single grouped utilities.md page.

    Returns empty string when symbols is empty/None — caller should skip writing.

    Rendering choice: we render the literal `signature` field for the bold entry.
    Extension methods (name contains a '.') get an _(extension)_ marker appended.
    This preserves the full function signature (e.g. `func trimmed() -> String`)
    while the marker conveys it extends an existing type.
    """
    if not symbols:
        return ""

    # Group by category
    groups: dict[str, list[dict]] = defaultdict(list)
    for sym in symbols:
        if not sym.get("name") or not sym.get("signature"):
            continue
        cat = _categorize_symbol(sym)
        groups[cat].append(sym)

    if not groups:
        return ""

    # Sort categories alphabetically, Uncategorized always last
    sorted_cats = sorted(
        groups.keys(),
        key=lambda c: (c == "Uncategorized", c),
    )

    parts = [
        _frontmatter(type="utilities-catalog", slug="utilities"),
        "\n# Utilities catalog\n",
        "\nReusable helper functions discovered in the codebase. "
        "Grep the wiki before implementing similar logic.\n",
    ]

    for cat in sorted_cats:
        entries = sorted(groups[cat], key=lambda s: (s.get("file", ""), s.get("name", "")))
        n = len(entries)
        noun = "function" if n == 1 else "functions"
        parts.append(f"\n## {cat} ({n} {noun})\n")
        for sym in entries:
            sig = sym["signature"]
            name = sym["name"]
            file_path = sym.get("file", "")
            extension_marker = " _(extension)_" if "." in name else ""
            parts.append(f"\n- **`{sig}`**{extension_marker}")
            parts.append(f"\n  `{file_path}`")
        parts.append("\n")

    return "".join(parts)


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
    component_to_models = _build_component_to_data_models(blueprint, slug_map["data_models"])

    for decision in _as_list(_as_dict(blueprint.get("decisions")).get("key_decisions")):
        slug = slug_map["decisions"].get(decision.get("title"))
        if not slug:
            continue
        _write(wiki_root / "decisions" / f"{slug}.md", render_decision(decision, slug))

    decisions_index_md = render_decisions_index(blueprint, slug_map)
    if decisions_index_md:
        _write(wiki_root / "decisions" / "index.md", decisions_index_md)

    for component in _extract_components(blueprint):
        slug = slug_map["components"].get(component.get("name"))
        if not slug:
            continue
        _write(
            wiki_root / "components" / f"{slug}.md",
            render_component(
                component,
                slug,
                slug_map["components"],
                data_models=component_to_models.get(component.get("name"), []),
            ),
        )

    for pattern in _as_list(_as_dict(blueprint.get("communication")).get("patterns")):
        slug = slug_map["patterns"].get(pattern.get("name"))
        if not slug:
            continue
        _write(wiki_root / "patterns" / f"{slug}.md", render_pattern(pattern, slug))

    for pitfall in _as_list(blueprint.get("pitfalls")):
        slug = slug_map["pitfalls"].get(pitfall.get("area"))
        if not slug:
            continue
        _write(
            wiki_root / "pitfalls" / f"{slug}.md",
            render_pitfall(pitfall, slug, slug_map["decisions"]),
        )

    for capability in _as_list(blueprint.get("capabilities")):
        slug = slug_map["capabilities"].get(capability.get("name"))
        if not slug:
            continue
        _write(
            wiki_root / "capabilities" / f"{slug}.md",
            render_capability(capability, slug, slug_map),
        )

    for model in _as_list(blueprint.get("data_models")):
        slug = slug_map["data_models"].get(model.get("name"))
        if not slug:
            continue
        _write(
            wiki_root / "data-models" / f"{slug}.md",
            render_data_model(model, slug, slug_map["components"], model_slugs=slug_map["data_models"]),
        )

    for guideline in _as_list(blueprint.get("implementation_guidelines")):
        slug = slug_map["guidelines"].get(guideline.get("name"))
        if not slug:
            continue
        _write(
            wiki_root / "guidelines" / f"{slug}.md",
            render_guideline(guideline, slug),
        )

    # Rules pages (single-page outputs with gating).
    rules_arch = render_architecture_rules(blueprint)
    if rules_arch:
        _write(wiki_root / "rules" / "architecture.md", rules_arch)

    rules_dev = render_development_rules(blueprint)
    if rules_dev:
        _write(wiki_root / "rules" / "development.md", rules_dev)

    tech_page = render_technology(blueprint)
    if tech_page:
        _write(wiki_root / "technology.md", tech_page)

    qr_page = render_quick_reference(blueprint)
    if qr_page:
        _write(wiki_root / "quick-reference.md", qr_page)

    frontend_page = render_frontend(blueprint)
    if frontend_page:
        _write(wiki_root / "frontend.md", frontend_page)

    arch_page = render_architecture(blueprint)
    if arch_page:
        _write(wiki_root / "architecture.md", arch_page)

    # Utilities catalog (from scan.json.symbols, not the blueprint)
    scan_path = project_root / ".archie" / "scan.json"
    symbols: list[dict] = []
    if scan_path.exists():
        try:
            scan_data = json.loads(scan_path.read_text(encoding="utf-8"))
            symbols = _as_list(scan_data.get("symbols"))
        except (json.JSONDecodeError, OSError):
            symbols = []

    utilities_page = render_utilities_catalog(symbols)
    if utilities_page:
        _write(wiki_root / "utilities.md", utilities_page)

    _write(
        wiki_root / "index.md",
        render_index(blueprint, slug_map, project_root=project_root, symbol_count=len(symbols)),
    )

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
        for d in _as_list(_as_dict(blueprint.get("decisions")).get("key_decisions"))
    }
    expected_components = {slugify(c.get("name", "")) for c in _extract_components(blueprint)}
    expected_patterns = {
        slugify(p.get("name", ""))
        for p in _as_list(_as_dict(blueprint.get("communication")).get("patterns"))
    }
    expected_pitfalls = {slugify(p.get("area", "")) for p in _as_list(blueprint.get("pitfalls"))}

    def _slugs(prefix: str) -> set[str]:
        return {Path(p).stem for p in _pages(prefix) if Path(p).stem != "index"}

    return (
        expected_decisions != _slugs("decisions/")
        or expected_components != _slugs("components/")
        or expected_patterns != _slugs("patterns/")
        or expected_pitfalls != _slugs("pitfalls/")
    )


def _find_capability_by_slug(blueprint: dict, slug: str, slug_map: dict[str, str]) -> dict | None:
    for cap in _as_list(blueprint.get("capabilities")):
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

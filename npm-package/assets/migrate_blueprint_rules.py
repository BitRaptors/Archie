#!/usr/bin/env python3
"""Migrate legacy blueprint-derived rule sections into proposed_rules.json.

Pre-3.0 blueprints carried four parallel rule taxonomies:

    blueprint.architecture_rules.file_placement_rules
    blueprint.architecture_rules.naming_conventions
    blueprint.development_rules
    blueprint.infrastructure_rules

…none of which the pre-validate hook consumed. The 3.0 unification collapses
them into the same rules.json / proposed_rules.json / ignored_rules.json
state machine the user already curates through the viewer.

This script reads those four sections, converts each entry into a rule with
a stable id + a kind tag (file_placement, naming_convention, coding_practice),
appends them to proposed_rules.json (de-duped against any rule already
adopted or ignored or already proposed), and strips the legacy sections
from blueprint.json.

Idempotent: re-running on a clean blueprint is a no-op. Stable hash-based
ids mean the same input always produces the same rule id, so a partial
prior run plus a fresh run can't produce duplicates.

CLI:
    python3 migrate_blueprint_rules.py /path/to/project [--dry-run]

Exits 0 on success (even when nothing to migrate). Exits 1 on I/O error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable

DEFAULT_SEVERITY = "pattern_divergence"  # safe default: inform, never block

LEGACY_PATHS = [
    # path: (location-in-blueprint, kind-label, severity-default, generator)
    ("architecture_rules.file_placement_rules", "file_placement", "fp"),
    ("architecture_rules.naming_conventions", "naming_convention", "nc"),
    ("development_rules", "coding_practice", "cp"),
    ("infrastructure_rules", "coding_practice", "ir"),
]


def _stable_id(prefix: str, payload: dict) -> str:
    """Hash-based id: same input → same id, every time. Re-running migrate
    on partially-migrated data can't produce duplicates."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    h = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8]
    return f"bp-{prefix}-{h}"


def _atomic_write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    os.replace(tmp, path)


def _read_json_or(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _rules_list(data: Any) -> list[dict]:
    if isinstance(data, dict) and isinstance(data.get("rules"), list):
        return data["rules"]
    if isinstance(data, list):
        return data
    return []


def _existing_ids(*paths: Path) -> set[str]:
    seen: set[str] = set()
    for p in paths:
        for r in _rules_list(_read_json_or(p, {})):
            rid = r.get("id")
            if isinstance(rid, str):
                seen.add(rid)
    return seen


# --- Per-section converters --------------------------------------------------
# Each takes ONE legacy entry and returns a rule dict (or None to skip).

def _convert_file_placement(entry: dict) -> dict | None:
    if not isinstance(entry, dict):
        return None
    pattern = entry.get("pattern") or entry.get("file_pattern") or ""
    location = entry.get("location") or entry.get("path") or ""
    kind_label = entry.get("kind") or entry.get("type") or ""
    scope = entry.get("scope") or ""
    rationale = entry.get("rationale") or entry.get("why") or ""
    if not pattern and not location:
        return None
    # Build a description that reads as a complete sentence so it makes sense
    # standalone in the viewer's Rules card. Three patterns depending on which
    # fields are populated.
    subject = kind_label.strip() + ("s" if kind_label and not kind_label.endswith("s") else "")
    if subject and pattern and location:
        description = f"{subject} (matching `{pattern}`) must live under `{location}`"
    elif subject and location:
        description = f"{subject} must live under `{location}`"
    elif pattern and location:
        description = f"Files matching `{pattern}` must live under `{location}`"
    elif location:
        description = f"This kind of file must live under `{location}`"
    elif pattern:
        description = f"Files matching `{pattern}` must follow the codebase's placement convention"
    else:
        description = "File placement convention from blueprint"
    rule = {
        "kind": "file_placement",
        "severity_class": DEFAULT_SEVERITY,
        "description": description,
        "why": rationale or "Migrated from blueprint's file_placement_rules — keeps layer boundaries explicit so the codebase stays navigable.",
        "source": "blueprint_migrated",
    }
    if scope:
        rule["scope"] = scope
    if pattern:
        rule["file_pattern"] = pattern
    if location:
        rule["applies_to"] = location
    rule["id"] = _stable_id("fp", {"pattern": pattern, "location": location, "kind": kind_label})
    return rule


def _convert_naming_convention(entry: dict) -> dict | None:
    if not isinstance(entry, dict):
        return None
    pattern = entry.get("pattern") or entry.get("file_pattern") or ""
    scope = entry.get("scope") or entry.get("applies_to") or ""
    examples = entry.get("examples") or entry.get("example") or []
    rationale = entry.get("rationale") or entry.get("why") or ""
    if not pattern:
        return None
    if isinstance(examples, list):
        example_str = ", ".join(str(e) for e in examples[:3])
    else:
        example_str = str(examples)
    scope_phrase = f" in {scope}" if scope else ""
    description = f"Files{scope_phrase} must follow the `{pattern}` naming convention"
    rule = {
        "kind": "naming_convention",
        "severity_class": DEFAULT_SEVERITY,
        "description": description,
        "why": rationale or "Migrated from blueprint's naming_conventions — keeps file/identifier names predictable so search and grep stay reliable.",
        "example": example_str,
        "source": "blueprint_migrated",
        "check": "file_naming",
        "file_pattern": pattern,
    }
    if scope:
        rule["applies_to"] = scope
    rule["id"] = _stable_id("nc", {"pattern": pattern, "scope": scope})
    return rule


def _convert_practice(entry: Any, id_prefix: str) -> dict | None:
    """development_rules / infrastructure_rules entries are either bare
    strings ("Always validate at boundaries") OR full objects
    ({rule, severity, confidence})."""
    if isinstance(entry, str):
        text = entry.strip()
        if not text:
            return None
        return {
            "id": _stable_id(id_prefix, {"text": text}),
            "kind": "coding_practice",
            "severity_class": DEFAULT_SEVERITY,
            "description": text,
            "source": "blueprint_migrated",
        }
    if isinstance(entry, dict):
        text = entry.get("rule") or entry.get("description") or ""
        if not text:
            return None
        rule = {
            "id": _stable_id(id_prefix, {"text": text}),
            "kind": "coding_practice",
            "severity_class": entry.get("severity_class") or DEFAULT_SEVERITY,
            "description": text,
            "source": "blueprint_migrated",
        }
        if entry.get("rationale") or entry.get("why"):
            rule["why"] = entry.get("rationale") or entry.get("why")
        return rule
    return None


def _drill(d: dict, dotted: str) -> Any:
    cur: Any = d
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _set_drill_to_default(d: dict, dotted: str) -> None:
    """Remove the final key of `dotted` from `d`. Intermediate keys stay."""
    parts = dotted.split(".")
    cur: Any = d
    for part in parts[:-1]:
        if not isinstance(cur, dict):
            return
        cur = cur.get(part)
    if isinstance(cur, dict):
        cur.pop(parts[-1], None)


def migrate(project_root: Path, dry_run: bool = False) -> dict:
    """Convert legacy blueprint rule sections into proposed_rules.json.

    Returns a summary: {added: int, skipped: int, sections_stripped: list[str]}.
    """
    archie = project_root / ".archie"
    blueprint_path = archie / "blueprint.json"
    proposed_path = archie / "proposed_rules.json"
    rules_path = archie / "rules.json"
    ignored_path = archie / "ignored_rules.json"

    if not blueprint_path.exists():
        return {"added": 0, "skipped": 0, "sections_stripped": [], "note": "no blueprint.json"}

    blueprint = _read_json_or(blueprint_path, {})
    if not isinstance(blueprint, dict):
        return {"added": 0, "skipped": 0, "sections_stripped": [], "note": "blueprint not an object"}

    existing = _existing_ids(rules_path, proposed_path, ignored_path)
    proposed_doc = _read_json_or(proposed_path, {"rules": []})
    if not (isinstance(proposed_doc, dict) and isinstance(proposed_doc.get("rules"), list)):
        proposed_doc = {"rules": _rules_list(proposed_doc)}

    added: list[dict] = []
    skipped = 0
    sections_stripped: list[str] = []

    # Architecture rules → file_placement
    fp_section = _drill(blueprint, "architecture_rules.file_placement_rules")
    if isinstance(fp_section, list):
        for entry in fp_section:
            rule = _convert_file_placement(entry)
            if rule is None:
                continue
            if rule["id"] in existing:
                skipped += 1
                continue
            existing.add(rule["id"])
            added.append(rule)
        sections_stripped.append("architecture_rules.file_placement_rules")

    # Architecture rules → naming_convention
    nc_section = _drill(blueprint, "architecture_rules.naming_conventions")
    if isinstance(nc_section, list):
        for entry in nc_section:
            rule = _convert_naming_convention(entry)
            if rule is None:
                continue
            if rule["id"] in existing:
                skipped += 1
                continue
            existing.add(rule["id"])
            added.append(rule)
        sections_stripped.append("architecture_rules.naming_conventions")

    # Development rules → coding_practice
    dev_section = blueprint.get("development_rules")
    if isinstance(dev_section, list):
        for entry in dev_section:
            rule = _convert_practice(entry, "cp")
            if rule is None:
                continue
            if rule["id"] in existing:
                skipped += 1
                continue
            existing.add(rule["id"])
            added.append(rule)
        sections_stripped.append("development_rules")

    # Infrastructure rules → coding_practice (with id-prefix `ir` so they
    # don't collide with development_rules entries of identical text).
    infra_section = blueprint.get("infrastructure_rules")
    if isinstance(infra_section, list):
        for entry in infra_section:
            rule = _convert_practice(entry, "ir")
            if rule is None:
                continue
            if rule["id"] in existing:
                skipped += 1
                continue
            existing.add(rule["id"])
            added.append(rule)
        sections_stripped.append("infrastructure_rules")

    if dry_run:
        return {"added": len(added), "skipped": skipped, "sections_stripped": sections_stripped}

    if added:
        proposed_doc["rules"].extend(added)
        _atomic_write_json(proposed_path, proposed_doc)

    # Strip the legacy sections from blueprint AFTER successful proposed write.
    if sections_stripped:
        for dotted in sections_stripped:
            _set_drill_to_default(blueprint, dotted)
        # Clean up an empty architecture_rules object so it doesn't linger.
        ar = blueprint.get("architecture_rules")
        if isinstance(ar, dict) and not ar:
            blueprint.pop("architecture_rules", None)
        _atomic_write_json(blueprint_path, blueprint)

    return {
        "added": len(added),
        "skipped": skipped,
        "sections_stripped": sections_stripped,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy blueprint rule sections.")
    parser.add_argument("project_root", help="Path to the project (.archie/ inside it)")
    parser.add_argument("--dry-run", action="store_true", help="Report what would migrate without writing")
    args = parser.parse_args(argv)

    root = Path(args.project_root).resolve()
    try:
        summary = migrate(root, dry_run=args.dry_run)
    except OSError as e:
        print(f"Migration I/O error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Merge subagent outputs into a single unified blueprint dict."""
from __future__ import annotations

import json
import logging
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from archie.engine.models import RawScan

logger = logging.getLogger(__name__)

# Top-level fields that are lists of objects (deduplicated by a key field)
_LIST_FIELDS: dict[str, str] = {
    "developer_recipes": "task",
    "pitfalls": "area",
    "implementation_guidelines": "capability",
    "development_rules": "rule",
}

# Top-level fields that are dicts (deep-merged)
_DICT_FIELDS = {
    "meta",
    "architecture_rules",
    "decisions",
    "components",
    "communication",
    "quick_reference",
    "technology",
    "frontend",
    "deployment",
}


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Recursively merge *overlay* into *base*, preferring non-empty values."""
    result = deepcopy(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        elif key in result and isinstance(result[key], list) and isinstance(value, list):
            # For lists inside dict fields, concatenate
            result[key] = result[key] + value
        elif value or not result.get(key):
            # Prefer non-empty values
            result[key] = deepcopy(value)
    return result


def _dedup_list(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    """Deduplicate a list of dicts by *key*, keeping the last occurrence."""
    seen: dict[str, dict[str, Any]] = {}
    for item in items:
        k = item.get(key, "")
        if k:
            seen[k] = item
        else:
            # Items without a key are always kept (use id as unique key)
            seen[f"__nokey_{id(item)}"] = item
    return list(seen.values())


def merge_subagent_outputs(
    outputs: list[dict],
    scan: RawScan,
    repo_name: str = "",
) -> dict:
    """Merge partial blueprint dicts from subagents into one complete blueprint.

    Parameters
    ----------
    outputs:
        List of partial blueprint dicts, one per subagent.
    scan:
        The RawScan from the local analysis engine.
    repo_name:
        Repository name for the meta section.

    Returns
    -------
    A merged dict conforming to the StructuredBlueprint schema.
    """
    merged: dict[str, Any] = {}

    for output in outputs:
        for field in _DICT_FIELDS:
            if field in output and isinstance(output[field], dict):
                merged[field] = _deep_merge(merged.get(field, {}), output[field])

        for field, dedup_key in _LIST_FIELDS.items():
            if field in output and isinstance(output[field], list):
                existing = merged.get(field, [])
                merged[field] = _dedup_list(existing + output[field], dedup_key)

        # architecture_diagram is a plain string — prefer non-empty
        if "architecture_diagram" in output and output["architecture_diagram"]:
            merged["architecture_diagram"] = output["architecture_diagram"]

    # --- Fill meta from scan data ---
    meta = merged.setdefault("meta", {})
    meta["repository"] = repo_name or meta.get("repository", "")
    meta["analyzed_at"] = datetime.now(timezone.utc).isoformat()
    meta["schema_version"] = "2.0.0"

    # Derive platforms from framework signals
    if not meta.get("platforms") and scan.framework_signals:
        platforms: list[str] = []
        for sig in scan.framework_signals:
            name_lower = sig.name.lower()
            if any(kw in name_lower for kw in ("react", "vue", "angular", "next", "svelte")):
                if "web-frontend" not in platforms:
                    platforms.append("web-frontend")
            elif any(kw in name_lower for kw in ("flutter", "swift", "kotlin", "react native")):
                if "mobile" not in platforms:
                    platforms.append("mobile")
            elif any(kw in name_lower for kw in ("fastapi", "django", "express", "flask", "spring")):
                if "backend" not in platforms:
                    platforms.append("backend")
        meta["platforms"] = platforms

    # --- Fill quick_reference.where_to_put_code from architecture_rules ---
    arch_rules = merged.get("architecture_rules", {})
    placement_rules = arch_rules.get("file_placement_rules", [])
    qr = merged.setdefault("quick_reference", {})
    if not qr.get("where_to_put_code") and placement_rules:
        where: dict[str, str] = {}
        for rule in placement_rules:
            comp_type = rule.get("component_type", "")
            location = rule.get("location", "")
            if comp_type and location:
                where[comp_type] = location
        qr["where_to_put_code"] = where

    # --- Placeholder architecture diagram ---
    if not merged.get("architecture_diagram"):
        merged["architecture_diagram"] = "graph TD\n  A[Architecture diagram placeholder]"

    # Ensure all top-level keys exist
    for field in _DICT_FIELDS:
        merged.setdefault(field, {})
    for field in _LIST_FIELDS:
        merged.setdefault(field, [])
    merged.setdefault("architecture_diagram", "")

    return merged


def save_blueprint(project_root: Path, blueprint: dict) -> None:
    """Write the blueprint to ``.archie/blueprint.json``."""
    out_dir = project_root / ".archie"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "blueprint.json"
    out_path.write_text(json.dumps(blueprint, indent=2, ensure_ascii=False))
    logger.info("Blueprint saved to %s", out_path)


def load_blueprint(project_root: Path) -> dict | None:
    """Load a blueprint from ``.archie/blueprint.json``.

    Returns ``None`` if the file is missing or cannot be parsed.
    """
    bp_path = project_root / ".archie" / "blueprint.json"
    if not bp_path.exists():
        return None
    try:
        return json.loads(bp_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load blueprint from %s: %s", bp_path, exc)
        return None

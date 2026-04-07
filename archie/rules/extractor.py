"""Extract enforcement rules from an Archie blueprint dict."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

STOPWORDS = frozenset(
    "the and for are but not you all any can had her was one our out day get has him his how its may new now old see way who did".split()
)

CONVENTION_REGEX: dict[str, str] = {
    "snake_case": r"^[a-z][a-z0-9_]*(\.[a-z]+)?$",
    "camelCase": r"^[a-z][a-zA-Z0-9]*(\.[a-z]+)?$",
    "PascalCase": r"^[A-Z][a-zA-Z0-9]*(\.[a-z]+)?$",
    "kebab-case": r"^[a-z][a-z0-9\-]*(\.[a-z]+)?$",
}


def _convention_to_regex(convention: str) -> str:
    """Convert a naming convention name to a regex pattern."""
    return CONVENTION_REGEX.get(convention, convention)


def _keywords_from_text(text: str) -> list[str]:
    """Extract keywords (3+ chars, no stopwords) from a text string."""
    words = re.findall(r"[a-zA-Z]{3,}", text)
    return [w.lower() for w in words if w.lower() not in STOPWORDS]


def extract_rules(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract enforcement rules from a blueprint dict.

    Sources:
    - architecture_rules.file_placement_rules  -> check=file_placement
    - architecture_rules.naming_conventions     -> check=naming
    - components.components                     -> check=file_placement (layer rules)
    """
    rules: list[dict[str, Any]] = []

    # Read per-section confidence from blueprint meta (AI-assigned during deep scan)
    meta_conf = blueprint.get("meta", {}).get("confidence", {})
    arch_conf = meta_conf.get("architecture_rules", 1.0)
    comp_conf = meta_conf.get("components", 1.0)

    arch_rules = blueprint.get("architecture_rules", {})

    # --- file_placement_rules ---
    for idx, fpr in enumerate(arch_rules.get("file_placement_rules", []), start=1):
        description = fpr.get("description", "")
        rule: dict[str, Any] = {
            "id": f"placement-{idx}",
            "check": "file_placement",
            "severity": "warn",
            "source": "blueprint",
            "confidence": arch_conf,
            "allowed_dirs": fpr.get("allowed_dirs", fpr.get("directories", [])),
            "keywords": _keywords_from_text(description),
        }
        if description:
            rule["description"] = description
        rules.append(rule)

    # --- naming_conventions ---
    for idx, nc in enumerate(arch_rules.get("naming_conventions", []), start=1):
        convention = nc.get("convention", nc.get("pattern", ""))
        description = nc.get("description", "")
        pattern = _convention_to_regex(convention)
        rule = {
            "id": f"naming-{idx}",
            "check": "naming",
            "severity": "warn",
            "source": "blueprint",
            "confidence": arch_conf,
            "pattern": pattern,
            "keywords": _keywords_from_text(description),
        }
        if description:
            rule["description"] = description
        rules.append(rule)

    # --- components -> layer rules ---
    components_section = blueprint.get("components", {})
    component_list = components_section.get("components", [])
    layer_idx = 0
    for comp in component_list:
        path = comp.get("path")
        if not path:
            continue
        layer_idx += 1
        description = comp.get("description", comp.get("name", ""))
        rule = {
            "id": f"layer-{layer_idx}",
            "check": "file_placement",
            "severity": "warn",
            "source": "blueprint",
            "confidence": comp_conf,
            "allowed_dirs": [path],
            "keywords": _keywords_from_text(description),
        }
        if description:
            rule["description"] = description
        rules.append(rule)

    return rules


def save_rules(project_root: Path, rules: list[dict[str, Any]]) -> None:
    """Write rules to .archie/rules.json."""
    archie_dir = project_root / ".archie"
    archie_dir.mkdir(parents=True, exist_ok=True)
    rules_file = archie_dir / "rules.json"
    rules_file.write_text(json.dumps({"rules": rules}, indent=2) + "\n")


def load_rules(project_root: Path) -> list[dict[str, Any]]:
    """Read rules from .archie/rules.json. Returns [] if missing or corrupt."""
    rules_file = project_root / ".archie" / "rules.json"
    if not rules_file.exists():
        return []
    try:
        data = json.loads(rules_file.read_text())
        return data.get("rules", [])
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def promote_rule(project_root: Path, rule_id: str) -> bool:
    """Set severity to 'error' for the given rule. Returns False if not found."""
    rules = load_rules(project_root)
    for rule in rules:
        if rule.get("id") == rule_id:
            rule["severity"] = "error"
            save_rules(project_root, rules)
            return True
    return False


def demote_rule(project_root: Path, rule_id: str) -> bool:
    """Set severity to 'warn' for the given rule. Returns False if not found."""
    rules = load_rules(project_root)
    for rule in rules:
        if rule.get("id") == rule_id:
            rule["severity"] = "warn"
            save_rules(project_root, rules)
            return True
    return False

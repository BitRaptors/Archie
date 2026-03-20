#!/usr/bin/env python3
"""Archie standalone rule extractor — extracts enforcement rules from blueprint.

Run: python3 rules.py /path/to/repo
Output: Writes .archie/rules.json

Zero dependencies beyond Python 3.11+ stdlib.
"""
import json
import re
import sys
from pathlib import Path


def extract_rules(blueprint: dict) -> list[dict]:
    """Extract enforcement rules from a blueprint dict."""
    rules: list[dict] = []
    arch = blueprint.get("architecture_rules", {})
    if isinstance(arch, str):
        return rules

    # File placement rules
    for i, r in enumerate(arch.get("file_placement_rules", [])):
        if not isinstance(r, dict):
            continue
        location = r.get("location", "")
        description = r.get("description", r.get("pattern", ""))
        rules.append({
            "id": f"placement-{i}",
            "check": "file_placement",
            "description": description,
            "allowed_dirs": [location] if location else [],
            "severity": "warn",
            "keywords": _extract_keywords(description),
        })

    # Naming conventions
    for i, n in enumerate(arch.get("naming_conventions", [])):
        if not isinstance(n, dict):
            continue
        scope = n.get("scope", n.get("target", ""))
        convention = n.get("pattern", n.get("convention", ""))
        examples = n.get("examples", [])
        if isinstance(examples, str):
            examples = [examples]
        example_str = examples[0] if examples else ""
        rules.append({
            "id": f"naming-{i}",
            "check": "naming",
            "description": f"{scope}: {convention}" + (f" (e.g. {example_str})" if example_str else ""),
            "pattern": _convention_to_regex(convention),
            "severity": "warn",
            "keywords": _extract_keywords(f"{scope} {convention}"),
        })

    # Component layer rules
    raw_components = blueprint.get("components", {})
    if isinstance(raw_components, list):
        comp_list = raw_components
    elif isinstance(raw_components, dict):
        comp_list = raw_components.get("components", [])
    else:
        comp_list = []
    if comp_list:
        for i, comp in enumerate(comp_list):
            if not isinstance(comp, dict):
                continue
            path = comp.get("location", comp.get("path", ""))
            name = comp.get("name", "")
            if path:
                rules.append({
                    "id": f"layer-{i}",
                    "check": "file_placement",
                    "description": f"{name} files belong in {path}",
                    "allowed_dirs": [path],
                    "severity": "warn",
                    "keywords": _extract_keywords(f"{name} {path}"),
                })

    return rules


def _convention_to_regex(convention: str) -> str:
    patterns = {
        "snake_case": r"^[a-z][a-z0-9_]*(\.[a-z]+)?$",
        "camelCase": r"^[a-z][a-zA-Z0-9]*(\.[a-z]+)?$",
        "PascalCase": r"^[A-Z][a-zA-Z0-9]*(\.[a-z]+)?$",
        "kebab-case": r"^[a-z][a-z0-9-]*(\.[a-z]+)?$",
    }
    return patterns.get(convention, "")


def _extract_keywords(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    stop = {"the", "and", "for", "are", "this", "that", "with", "from", "use", "must", "files", "belong"}
    return [w for w in words if w not in stop]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 rules.py /path/to/repo", file=sys.stderr)
        sys.exit(1)

    root = Path(sys.argv[1]).resolve()
    bp_path = root / ".archie" / "blueprint.json"

    if not bp_path.exists():
        print("No .archie/blueprint.json found", file=sys.stderr)
        sys.exit(1)

    bp = json.loads(bp_path.read_text())

    # Preserve promoted rules from existing rules.json
    old_severities: dict[str, str] = {}
    old_rules_path = root / ".archie" / "rules.json"
    if old_rules_path.exists():
        try:
            old = json.loads(old_rules_path.read_text())
            for r in old.get("rules", []):
                if r.get("severity") == "error":
                    old_severities[r["id"]] = "error"
        except (json.JSONDecodeError, OSError):
            pass

    rules = extract_rules(bp)

    # Restore promoted severities
    for r in rules:
        if r["id"] in old_severities:
            r["severity"] = old_severities[r["id"]]

    # Save
    (root / ".archie").mkdir(exist_ok=True)
    with open(root / ".archie" / "rules.json", "w") as f:
        json.dump({"rules": rules}, f, indent=2)

    promoted = sum(1 for r in rules if r["severity"] == "error")
    print(f"Extracted {len(rules)} rules ({promoted} promoted to error)", file=sys.stderr)

"""Rule storage helpers — save, load, promote, demote.

`extract_rules()` was retired in v2.5.0 (Phase 1 of the richer-rules plan).
The deep-scan slash command pipeline never invoked it, and Step 6 (Sonnet
AI rule synthesis in `/archie-deep-scan`) produces richer placement+naming
rules with full semantic content (`why` + `example`) that the agent reads
inline at edit time. Fresh `archie init` now writes an empty rules.json;
users run `/archie-deep-scan` or `/archie-scan` to populate it.

The remaining functions here are still used by `archie rules promote/demote`
CLI commands and by `check_command.py`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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

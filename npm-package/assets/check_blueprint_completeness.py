#!/usr/bin/env python3
"""Check whether .archie/blueprint.json contains all expected top-level keys.

Run: python3 check_blueprint_completeness.py /path/to/project

Exit codes:
  0 — blueprint complete OR blueprint absent (let downstream first-run handle MISSING)
  1 — blueprint exists but is STALE (missing expected keys) or MALFORMED

stdout (single token + optional reason):
  OK
  MISSING
  MALFORMED
  STALE: missing data_models (Plan 5b.1), capabilities (Plan 2)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


# Canonical list of expected top-level blueprint keys.
# Maintained alongside command updates.
# Format: (key_name, introduced_in_plan)
# NOTE: `frontend` is conditional (only present when project has frontend code) → NOT listed.
# NOTE: `utilities` lives in scan.json.symbols[], NOT blueprint → NOT listed.
EXPECTED_KEYS = [
    ("meta", "Plan 1"),
    ("components", "Plan 1"),
    ("decisions", "Plan 1"),
    ("communication", "Plan 1"),
    ("pitfalls", "Plan 1"),
    ("technology", "Plan 1"),
    ("architecture_rules", "Plan 1"),
    ("development_rules", "Plan 1"),
    ("implementation_guidelines", "Plan 1"),
    ("quick_reference", "Plan 1"),
    ("architecture_diagram", "Plan 1"),
    ("capabilities", "Plan 2"),
    ("data_models", "Plan 5b.1"),
]


def check_completeness(project_root: Path) -> tuple[str, int]:
    """Check blueprint completeness.

    Returns (status_string, exit_code).
    """
    bp_path = project_root / ".archie" / "blueprint.json"

    if not bp_path.exists():
        return "MISSING", 0

    try:
        data = json.loads(bp_path.read_text())
    except (json.JSONDecodeError, ValueError):
        return "MALFORMED", 1

    if not isinstance(data, dict):
        return "MALFORMED", 1

    missing = [
        (key, plan)
        for key, plan in EXPECTED_KEYS
        if key not in data
    ]

    if not missing:
        return "OK", 0

    # Sort by (plan_string, key_name) — string sort works correctly:
    # "Plan 1" < "Plan 2" < "Plan 5b.1" lexicographically.
    missing_sorted = sorted(missing, key=lambda item: (item[1], item[0]))
    parts = ", ".join(f"{key} ({plan})" for key, plan in missing_sorted)
    return f"STALE: missing {parts}", 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: python3 check_blueprint_completeness.py /path/to/project",
            file=sys.stderr,
        )
        sys.exit(2)
    project_root = Path(sys.argv[1])
    status, exit_code = check_completeness(project_root)
    print(status)
    sys.exit(exit_code)

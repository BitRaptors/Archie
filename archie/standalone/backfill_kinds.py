#!/usr/bin/env python3
"""Backfill the `kind` field on rules that lack one (or have an invalid value).

Run on a project that already has `.archie/rules.json`:

    python3 backfill_kinds.py /path/to/project [--dry-run]

Uses archie.standalone.rule_kinds.classify_kind to pick a kind from the
rule's id prefix, severity_class, structural fields, and source path.
Idempotent: re-running on a fully-classified file is a no-op.

Exits 0 on success (including "nothing to do"). Exits 1 on I/O error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# Allow running both as a script (npm package install) and as a module.
try:
    from archie.standalone.rule_kinds import KINDS, classify_kind, is_valid_kind
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from rule_kinds import KINDS, classify_kind, is_valid_kind  # type: ignore[no-redef]


def _atomic_write_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _rules_list(data: Any) -> list[dict]:
    if isinstance(data, dict) and isinstance(data.get("rules"), list):
        return data["rules"]
    if isinstance(data, list):
        return data
    return []


def backfill(project_root: Path, dry_run: bool = False) -> int:
    rules_path = project_root / ".archie" / "rules.json"
    if not rules_path.exists():
        print(f"no rules.json at {rules_path} — skipped")
        return 0

    data = json.loads(rules_path.read_text())
    rules = _rules_list(data)
    if not rules:
        print("rules.json contains no rules — skipped")
        return 0

    updated = 0
    by_new_kind: dict[str, int] = {}
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        current = rule.get("kind")
        if is_valid_kind(current):
            continue
        new_kind = classify_kind(rule)
        rule["kind"] = new_kind
        updated += 1
        by_new_kind[new_kind] = by_new_kind.get(new_kind, 0) + 1

    if dry_run:
        print(f"DRY RUN: would update {updated} of {len(rules)} rules")
    else:
        if updated > 0:
            _atomic_write_json(rules_path, data)
        if updated == 0:
            print(f"0 updated, {len(rules)} already classified")
        else:
            print(f"{updated} updated, {len(rules) - updated} already classified")

    if by_new_kind:
        print("by kind:")
        for k in KINDS:
            if k in by_new_kind:
                print(f"  {k}: {by_new_kind[k]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Project root containing .archie/")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing")
    args = parser.parse_args(argv)
    try:
        return backfill(args.project, dry_run=args.dry_run)
    except json.JSONDecodeError as exc:
        print(f"rules.json is not valid JSON: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"I/O error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""Pre-computed rule index for hot-path edit-time enforcement.

Reads `.archie/rules.json` and `.archie/platform_rules.json`, walks each
rule's `triggers` block, and emits `.archie/rule_index.json` with three
lookup buckets:

    {
      "by_path_glob": { "<glob>": ["rule_id1", ...] },
      "by_code_shape": [
          {"rule_id": "...", "shape": {...}},
          ...
      ],
      "for_classifier": ["rule_id1", "rule_id2", ...]
    }

- `by_path_glob` is a fast path-prefix narrowing for the pre-validate
  hook. The hook keys into this on the edited file's relative path and
  gets a candidate list to actually check.
- `by_code_shape` is a flat list of (rule_id, shape) entries so the
  hook can iterate shapes against the diff content with no further
  decode work.
- `for_classifier` is the architectural rule set (everything that
  isn't `severity_class: mechanical_violation`) — the Phase 3 plan/
  commit classifier reads this to know which rules to reason about.

Subcommands:
    python3 rule_index.py build <project_root>
    python3 rule_index.py show <project_root>      # pretty-print

Zero dependencies beyond Python 3.9+ stdlib + sibling code_shape.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(_SCRIPT_DIR))


def _load_rules(archie_dir: Path) -> list[dict[str, Any]]:
    """Concatenate rules.json + platform_rules.json. Skip missing/malformed."""
    rules: list[dict[str, Any]] = []
    for fname in ("rules.json", "platform_rules.json"):
        path = archie_dir / fname
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        items = data if isinstance(data, list) else data.get("rules", [])
        if isinstance(items, list):
            for r in items:
                if isinstance(r, dict) and r.get("id"):
                    rules.append(r)
    return rules


def build_index(rules: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the rule_index.json structure from a flat rule list."""
    by_path_glob: dict[str, list[str]] = {}
    by_code_shape: list[dict[str, Any]] = []
    for_classifier: list[str] = []

    for rule in rules:
        rid = rule.get("id", "")
        if not rid:
            continue

        sc = rule.get("severity_class", "")
        # Architectural rules feed the plan/commit classifier. Only rules
        # explicitly tagged `mechanical_violation` are excluded — those are
        # pure regex housekeeping (don't-edit-generated, file-naming) where
        # the classifier adds nothing the edit-time hook didn't already do.
        # Old-shape rules (no severity_class) still get classified as long
        # as they carry rationale text — even if they ALSO have a `check`
        # field, the rationale is architectural reasoning the classifier
        # should weigh against intent.
        if sc:
            if sc != "mechanical_violation":
                for_classifier.append(rid)
        elif rule.get("rationale") or rule.get("why"):
            for_classifier.append(rid)

        # Pull triggers if present (Phase 2 shape). Fall back to legacy
        # `applies_to` for old-shape rules so they still get indexed.
        triggers = rule.get("triggers")
        if isinstance(triggers, dict):
            globs = triggers.get("path_glob") or []
            if isinstance(globs, str):
                globs = [globs]
            for g in globs:
                if isinstance(g, str) and g:
                    by_path_glob.setdefault(g, []).append(rid)
            shapes = triggers.get("code_shape") or []
            if isinstance(shapes, list):
                for s in shapes:
                    if isinstance(s, dict) and s.get("must_match"):
                        by_code_shape.append({"rule_id": rid, "shape": s})
        else:
            # Legacy fallback: derive a path_glob from `applies_to` so
            # old-shape rules still get O(1) narrowing at the hook.
            applies_to = rule.get("applies_to")
            if isinstance(applies_to, str) and applies_to:
                key = applies_to if applies_to.endswith("/") else applies_to + "/"
                by_path_glob.setdefault(key, []).append(rid)

    return {
        "by_path_glob": by_path_glob,
        "by_code_shape": by_code_shape,
        "for_classifier": for_classifier,
    }


def cmd_build(project_root: str) -> int:
    root = Path(project_root)
    archie_dir = root / ".archie"
    if not archie_dir.is_dir():
        print(f"Error: {archie_dir} does not exist", file=sys.stderr)
        return 1

    rules = _load_rules(archie_dir)
    index = build_index(rules)
    out_path = archie_dir / "rule_index.json"
    out_path.write_text(json.dumps(index, indent=2))
    print(
        f"Wrote {out_path} "
        f"({len(index['by_path_glob'])} path globs, "
        f"{len(index['by_code_shape'])} code shapes, "
        f"{len(index['for_classifier'])} classifier rules)",
        file=sys.stderr,
    )
    return 0


def cmd_show(project_root: str) -> int:
    root = Path(project_root)
    path = root / ".archie" / "rule_index.json"
    if not path.is_file():
        print(f"No index at {path} — run `rule_index.py build <root>` first.", file=sys.stderr)
        return 1
    print(path.read_text())
    return 0


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage:", file=sys.stderr)
        print("  python3 rule_index.py build <project_root>", file=sys.stderr)
        print("  python3 rule_index.py show <project_root>", file=sys.stderr)
        return 1
    subcmd, project_root = sys.argv[1], sys.argv[2]
    if subcmd == "build":
        return cmd_build(project_root)
    if subcmd == "show":
        return cmd_show(project_root)
    print(f"Unknown subcommand: {subcmd}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

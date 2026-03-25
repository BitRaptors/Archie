#!/usr/bin/env python3
"""Archie finalize — one command to merge Agent X, normalize, render, validate.

Run: python3 finalize.py /path/to/project [/tmp/archie_sub_x.json]

Chains: merge Agent X → deterministic normalize → render → intent layer → rules → hooks → validate.
Replaces 6+ manual commands with 1.

Zero dependencies beyond Python 3.11+ stdlib.
"""
import json
import sys
from pathlib import Path


def finalize(root: Path, agent_x_file: str | None = None):
    """Run the full finalization pipeline."""
    archie_dir = root / ".archie"
    bp_raw_path = archie_dir / "blueprint_raw.json"

    bp_path_fallback = archie_dir / "blueprint.json"
    if bp_raw_path.exists():
        bp = json.loads(bp_raw_path.read_text())
    elif bp_path_fallback.exists():
        bp = json.loads(bp_path_fallback.read_text())
    else:
        print("Error: no blueprint found (.archie/blueprint_raw.json or .archie/blueprint.json)", file=sys.stderr)
        sys.exit(1)

    # ── 1. Merge Agent X output (if provided) ─────────────────────────────
    if agent_x_file:
        from archie.standalone.merge import extract_json_from_text, deep_merge

        agent_x_path = Path(agent_x_file)
        if agent_x_path.exists():
            text = agent_x_path.read_text()
            parsed = extract_json_from_text(text)
            if parsed:
                bp = deep_merge(bp, parsed)
                bp_raw_path.write_text(json.dumps(bp, indent=2))
                print("  Merged Agent X output into blueprint_raw.json", file=sys.stderr)
            else:
                print(f"  Warning: could not parse JSON from {agent_x_file}", file=sys.stderr)
        else:
            print(f"  Warning: {agent_x_file} not found, skipping merge", file=sys.stderr)

    # ── 2. Deterministic normalize ─────────────────────────────────────────
    for key in ("meta", "architecture_rules", "decisions", "components",
                "communication", "quick_reference", "technology", "frontend",
                "deployment"):
        if key not in bp or not isinstance(bp.get(key), dict):
            bp[key] = bp.get(key, {})
            if not isinstance(bp[key], dict):
                bp[key] = {}

    for key in ("pitfalls", "implementation_guidelines", "development_rules"):
        if key not in bp or not isinstance(bp.get(key), list):
            bp[key] = bp.get(key, [])
            if not isinstance(bp[key], list):
                bp[key] = []

    bp.setdefault("architecture_diagram", "")

    bp_path = archie_dir / "blueprint.json"
    bp_path.write_text(json.dumps(bp, indent=2))

    comps = bp.get("components", {})
    comp_count = len(comps.get("components", [])) if isinstance(comps, dict) else 0
    pattern_count = len(bp.get("communication", {}).get("patterns", []))
    decision_count = len(bp.get("decisions", {}).get("key_decisions", []))
    style = bp.get("meta", {}).get("architecture_style", "")
    print(f"  Blueprint: {style}", file=sys.stderr)
    print(f"  {comp_count} components, {pattern_count} patterns, {decision_count} decisions", file=sys.stderr)

    # ── 3. Render ──────────────────────────────────────────────────────────
    from archie.standalone.renderer import generate_all

    files = generate_all(bp)
    for rel_path, content in files.items():
        full_path = root / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
    print(f"  Rendered {len(files)} files", file=sys.stderr)

    # ── 4. Intent layer ────────────────────────────────────────────────────
    from archie.standalone.intent_layer import generate_all as generate_intent

    scan_path = archie_dir / "scan.json"
    if scan_path.exists():
        il_files = generate_intent(root)
        for rel_path, content in il_files.items():
            full_path = root / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
        print(f"  Intent layer: {len(il_files)} per-folder CLAUDE.md files", file=sys.stderr)

    # ── 5. Rules ───────────────────────────────────────────────────────────
    from archie.standalone.rules import extract_rules

    # Preserve promoted rules
    old_severities: dict[str, str] = {}
    old_rules_path = archie_dir / "rules.json"
    if old_rules_path.exists():
        try:
            old = json.loads(old_rules_path.read_text())
            for r in old.get("rules", []):
                if r.get("severity") == "error":
                    old_severities[r["id"]] = "error"
        except (json.JSONDecodeError, OSError):
            pass

    rules = extract_rules(bp)
    for r in rules:
        if r["id"] in old_severities:
            r["severity"] = old_severities[r["id"]]

    with open(archie_dir / "rules.json", "w") as f:
        json.dump({"rules": rules}, f, indent=2)

    promoted = sum(1 for r in rules if r["severity"] == "error")
    print(f"  Rules: {len(rules)} extracted ({promoted} promoted to error)", file=sys.stderr)

    # ── 6. Hooks ───────────────────────────────────────────────────────────
    from archie.standalone.install_hooks import install

    install(root)
    print("  Hooks installed", file=sys.stderr)

    # ── 7. Validate (informational) ────────────────────────────────────────
    from archie.standalone.validate import check_paths, check_methods, check_pitfalls

    all_errors = []
    for name, fn in [("paths", check_paths), ("methods", check_methods), ("pitfalls", check_pitfalls)]:
        errors = fn(root)
        all_errors.extend(errors)

    fails = [e for e in all_errors if e["status"] == "FAIL"]
    warns = [e for e in all_errors if e["status"] == "WARNING"]
    if fails:
        print(f"  Validation: {len(fails)} failures, {len(warns)} warnings", file=sys.stderr)
        for f in fails[:5]:
            print(f"    FAIL: {f['claim']}", file=sys.stderr)
    elif warns:
        print(f"  Validation: 0 failures, {len(warns)} warnings", file=sys.stderr)
    else:
        print("  Validation: all checks passed", file=sys.stderr)

    print(f"\nFinalized: {root}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 finalize.py /path/to/project [agent_x_output.json]", file=sys.stderr)
        sys.exit(1)

    project_root = Path(sys.argv[1]).resolve()
    agent_x = sys.argv[2] if len(sys.argv) > 2 else None
    finalize(project_root, agent_x)

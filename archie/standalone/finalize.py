#!/usr/bin/env python3
"""Archie finalize — one command to merge Agent X, normalize, render, validate.

Run: python3 finalize.py /path/to/project [/tmp/archie_sub_x.json]

Chains: merge Agent X → deterministic normalize → render → hooks → validate.
Replaces 6+ manual commands with 1.

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import sys
from pathlib import Path


def _now_iso_short() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H%M")


def _merge_findings_into_store(archie_dir: Path, new_findings: list) -> int:
    """Upsert deep-scan findings into .archie/findings.json.

    Existing entries whose id matches one in `new_findings` are replaced by
    the new entry — preserving `first_seen` — and their `confirmed_in_scan`
    counter is bumped by 1. Existing entries not referenced in
    `new_findings` are left untouched (scan is responsible for marking
    resolution).

    Returns the new total count.
    """
    store_path = archie_dir / "findings.json"
    if store_path.exists():
        try:
            store = json.loads(store_path.read_text())
        except (json.JSONDecodeError, OSError):
            store = {}
    else:
        store = {}

    existing: list = store.get("findings") or []
    by_id: dict = {f.get("id"): f for f in existing if isinstance(f, dict) and f.get("id")}

    now = _now_iso_short()
    for nf in new_findings:
        if not isinstance(nf, dict):
            continue
        fid = nf.get("id")
        if not fid:
            continue
        prior = by_id.get(fid)
        if prior:
            merged = dict(nf)
            merged["first_seen"] = prior.get("first_seen") or nf.get("first_seen") or now
            merged["confirmed_in_scan"] = (prior.get("confirmed_in_scan") or 0) + 1
            # Preserve resolution unless deep-scan explicitly changed it.
            if "status" not in merged and prior.get("status"):
                merged["status"] = prior["status"]
            by_id[fid] = merged
        else:
            merged = dict(nf)
            merged.setdefault("first_seen", now)
            merged.setdefault("confirmed_in_scan", 1)
            merged.setdefault("status", "active")
            by_id[fid] = merged

    store["findings"] = list(by_id.values())
    store["scanned_at"] = now
    store_path.write_text(json.dumps(store, indent=2))
    return len(store["findings"])

# When running standalone (.archie/), import sibling scripts directly by path
_SCRIPT_DIR = Path(__file__).resolve().parent

def _import_sibling(name: str):
    """Import a sibling .py file by name (e.g. 'merge' → merge.py in same dir)."""
    spec = importlib.util.spec_from_file_location(name, _SCRIPT_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def finalize(root: Path, agent_x_file: str | None = None, patch_mode: bool = False):
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

    # ── 1. Merge Agent X / patch output ───────────────────────────────────
    if agent_x_file:
        _merge = _import_sibling("merge")
        extract_json_from_text = _merge.extract_json_from_text
        deep_merge = _merge.deep_merge

        agent_x_path = Path(agent_x_file)
        if agent_x_path.exists():
            text = agent_x_path.read_text()
            parsed = extract_json_from_text(text)
            if parsed:
                # Findings live in .archie/findings.json, not in the blueprint.
                # Extract and merge id-stably before deep-merging the rest.
                new_findings = parsed.pop("findings", None)
                if isinstance(new_findings, list) and new_findings:
                    total = _merge_findings_into_store(archie_dir, new_findings)
                    print(f"  Findings store: {total} entries after deep-scan upgrade", file=sys.stderr)

                bp = deep_merge(bp, parsed)
                if patch_mode:
                    # In patch mode, write directly to blueprint.json (skip raw)
                    bp_path = archie_dir / "blueprint.json"
                    bp_path.write_text(json.dumps(bp, indent=2))
                    print("  Patched blueprint.json with incremental reasoning", file=sys.stderr)
                else:
                    bp_raw_path.write_text(json.dumps(bp, indent=2))
                    print("  Merged Agent X output into blueprint_raw.json", file=sys.stderr)
            else:
                print(f"  Warning: could not parse JSON from {agent_x_file}", file=sys.stderr)
        else:
            print(f"  Warning: {agent_x_file} not found, skipping merge", file=sys.stderr)

    # ── 2. Deterministic normalize ─────────────────────────────────────────
    sys.path.insert(0, str(_SCRIPT_DIR))
    from _common import normalize_blueprint  # noqa: E402
    normalize_blueprint(bp)

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
    generate_all = _import_sibling("renderer").generate_all

    files = generate_all(bp)
    for rel_path, content in files.items():
        full_path = root / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
    print(f"  Rendered {len(files)} files", file=sys.stderr)

    # ── 4. Hooks ───────────────────────────────────────────────────────────
    if not patch_mode:
        install = _import_sibling("install_hooks").install
        install(root)
        print("  Hooks installed", file=sys.stderr)

    # ── 7. Validate (informational) ────────────────────────────────────────
    _validate = _import_sibling("validate")
    check_paths, check_methods, check_pitfalls = _validate.check_paths, _validate.check_methods, _validate.check_pitfalls

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


def normalize_only(root: Path):
    """Read blueprint.json, normalize it, write it back. Idempotent."""
    archie_dir = root / ".archie"
    bp_path = archie_dir / "blueprint.json"
    if not bp_path.exists():
        print("Error: .archie/blueprint.json not found", file=sys.stderr)
        sys.exit(1)

    bp = json.loads(bp_path.read_text())

    sys.path.insert(0, str(_SCRIPT_DIR))
    from _common import normalize_blueprint  # noqa: E402
    normalize_blueprint(bp)

    bp_path.write_text(json.dumps(bp, indent=2))

    comp_count = len(bp.get("components", {}).get("components", []))
    print(f"Normalized blueprint.json ({comp_count} components)", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 finalize.py /path/to/project [agent_x_output.json]", file=sys.stderr)
        print("  Or:  python3 finalize.py /path/to/project --patch incremental_reasoning.json", file=sys.stderr)
        print("  Or:  python3 finalize.py /path/to/project --normalize-only", file=sys.stderr)
        sys.exit(1)

    project_root = Path(sys.argv[1]).resolve()

    if len(sys.argv) > 2 and sys.argv[2] == "--normalize-only":
        normalize_only(project_root)
    elif len(sys.argv) > 2 and sys.argv[2] == "--patch":
        agent_x = sys.argv[3] if len(sys.argv) > 3 else None
        finalize(project_root, agent_x, patch_mode=True)
    else:
        agent_x = sys.argv[2] if len(sys.argv) > 2 else None
        finalize(project_root, agent_x)

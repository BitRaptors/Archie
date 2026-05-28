#!/usr/bin/env python3
"""Archie finalize — one command to merge Agent X, normalize, render, validate.

Run: python3 finalize.py /path/to/project [.archie/tmp/archie_sub_x.json]

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


# Verifier-pipeline state fields owned by apply_verdicts.py. The synthesizer
# never re-emits these on a fresh finding, so finalize must preserve them
# from the prior entry when merging — otherwise every scan wipes the
# verdict_history and breaks cross-run hysteresis. The new emission can
# still override any of these fields explicitly (rare, but keeps the door
# open for an upstream step that wants to reset state intentionally).
_VERIFIER_PIPELINE_FIELDS = (
    "verdict_history",
    "last_verdict_reason",
    "last_verdict_confidence",
    "pending_demotion",
    "pending_promotion",
    "demoted_at",
    "dropped_at",
)


def _merge_findings_into_store(archie_dir: Path, new_findings: list) -> int:
    """Upsert deep-scan findings into .archie/findings.json.

    Existing entries whose id matches one in `new_findings` are replaced by
    the new entry — preserving `first_seen`, `confirmed_in_scan` (bumped by
    1), `status` when the new entry doesn't carry one, and the
    verifier-pipeline state (verdict_history, pending_*, demoted_at,
    dropped_at, last_verdict_*) when the new entry doesn't carry those
    either. Existing entries not referenced in `new_findings` are left
    untouched (scan is responsible for marking resolution).

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
            # Preserve verifier-pipeline state — owned by apply_verdicts.py,
            # never re-emitted by the synthesizer. Without this, every scan
            # wipes verdict_history and hysteresis breaks across runs.
            for field in _VERIFIER_PIPELINE_FIELDS:
                if field not in merged and field in prior:
                    merged[field] = prior[field]
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

    # ── 2b. Deterministic architecture diagram ─────────────────────────────
    # Overwrites whatever `architecture_diagram` value Wave 2 may have
    # emitted with one rendered purely from the structured blueprint
    # (components, depends_on, integrations, data_models, persistence_stores).
    # Single source of truth — see archie/standalone/diagram.py for the rules.
    # The Wave 2 prompt no longer asks for a diagram; this is the canonical
    # producer for `bp["architecture_diagram"]`.
    try:
        generate_diagram = _import_sibling("diagram").generate
        bp["architecture_diagram"] = generate_diagram(bp)
    except Exception as e:  # pragma: no cover — defensive
        print(f"  Warning: diagram generation failed ({e}); keeping prior value", file=sys.stderr)

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
    # Load enforcement rules (rules.json + platform_rules.json) if they
    # already exist on disk — they may not on the first deep-scan pass
    # (rules.json is generated at Step 6, finalize runs at Step 5), but
    # any subsequent invocation (incremental scan, manual finalize re-run,
    # the post-Step-6 render step) finds them and emits enforcement.md.
    enforcement_rules: list = []
    for fname, src in (("rules.json", "project"), ("platform_rules.json", "platform")):
        path = archie_dir / fname
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        items = data if isinstance(data, list) else data.get("rules", [])
        if isinstance(items, list):
            for r in items:
                if isinstance(r, dict):
                    r.setdefault("_archie_source", src)
                    enforcement_rules.append(r)

    generate_all = _import_sibling("renderer").generate_all

    files = generate_all(bp, enforcement_rules=enforcement_rules)
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

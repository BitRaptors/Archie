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


def merge_platform_pitfalls(pitfalls, signals, catalog):
    """Append deterministic platform pitfalls for present scanner signals.

    pitfalls : existing blueprint pitfalls (list).
    signals  : scan.json["platform_pitfall_signals"] — list of {signal, evidence_path}.
    catalog  : loaded platform_pitfalls.json — {"pitfalls": [{signal, pitfall}]}.

    Pure (no I/O). Dedup by pitfall id so re-scans are idempotent. Returns a new list.
    """
    result = list(pitfalls or [])
    existing_ids = {p.get("id") for p in result if isinstance(p, dict)}
    by_signal = {}
    for entry in (catalog or {}).get("pitfalls", []):
        sig = entry.get("signal")
        if sig and entry.get("pitfall"):
            by_signal.setdefault(sig, entry["pitfall"])
    for sig in signals or []:
        name = sig.get("signal") if isinstance(sig, dict) else sig
        seed = by_signal.get(name)
        if not seed or seed.get("id") in existing_ids:
            continue
        pitfall = json.loads(json.dumps(seed))  # deep copy
        ev = sig.get("evidence_path") if isinstance(sig, dict) else None
        if ev:
            pitfall["evidence"] = [
                f"{ev} — registered sources are enumerated here; a new file absent "
                f"from this manifest is excluded from the build"
            ]
        result.append(pitfall)
        existing_ids.add(pitfall.get("id"))
    return result


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


def _resolve_owner_to_component(
    owner_slug: str,
    components: list,
    component_name_set: set,
) -> str:
    """Resolve a Wave 1 `owned_by_component` value to a known component name.

    The Data agent emits owner values in several shapes:
      1. Exact component name ("OrderService")
      2. Descriptive string with parenthetical ("common/domain (domainModule)")
      3. Folder slug ("page_settings" — matches component whose location
         ends with `/page_settings`)
      4. Deep sub-folder slug ("common/domain/repository/settings" — walk
         up the path: settings → repository → domain → common, return the
         component whose location ends with the deepest matching ancestor)

    Returns the empty string when no match — caller skips that owner
    rather than fabricating an attribution.
    """
    if not isinstance(owner_slug, str) or not owner_slug.strip():
        return ""
    raw = owner_slug.strip()
    # 1. Exact name match.
    if raw in component_name_set:
        return raw
    # 2. Strip parenthetical, try again.
    stripped = raw.split("(", 1)[0].strip().rstrip(",").strip()
    if stripped and stripped != raw and stripped in component_name_set:
        return stripped
    candidate = (stripped or raw).lstrip("./").rstrip("/")
    if not candidate:
        return ""

    def _match_slug(slug: str) -> str:
        for c in components:
            if not isinstance(c, dict):
                continue
            loc = (c.get("location") or "").rstrip("/")
            if loc and (loc.endswith("/" + slug) or loc == slug):
                return c.get("name", "")
        return ""

    # 3. Exact slug suffix match against component locations.
    hit = _match_slug(candidate)
    if hit:
        return hit
    # 4. Ancestor walk — strip the deepest segment and retry until match.
    parts = candidate.split("/")
    for i in range(len(parts) - 1, 0, -1):
        parent = "/".join(parts[:i])
        if not parent:
            continue
        hit = _match_slug(parent)
        if hit:
            return hit
    return ""


def _derive_persistence_writers(bp: dict) -> None:
    """Populate `persistence_stores[*].writers` from `data_models[*]`.

    Single source of truth for "who writes which store." Both the React
    viewer (DataModelsSection) and the markdown renderer
    (`.claude/rules/data-models.md`) read this field — no client-side
    re-derivation needed, no divergence risk.

    Idempotent: existing `writers` fields are overwritten on each
    finalize so re-running keeps them in sync with current data_models.
    Mutates the blueprint in place.
    """
    stores = bp.get("persistence_stores") or []
    if not isinstance(stores, list) or not stores:
        return
    components = (bp.get("components") or {}).get("components") or []
    components = [c for c in components if isinstance(c, dict) and c.get("name")]
    name_set = {c.get("name") for c in components}
    data_models = bp.get("data_models") or []

    writers_by_store: dict[str, list[str]] = {}
    for m in data_models:
        if not isinstance(m, dict):
            continue
        owner_raw = (m.get("owned_by_component") or "").strip()
        store = (m.get("store") or "").strip()
        if not owner_raw or not store:
            continue
        resolved = _resolve_owner_to_component(owner_raw, components, name_set)
        if not resolved:
            continue
        bucket = writers_by_store.setdefault(store, [])
        if resolved not in bucket:
            bucket.append(resolved)

    # Sort alphabetically inside each bucket for stable, diff-friendly output.
    for s in stores:
        if not isinstance(s, dict):
            continue
        store_name = s.get("name")
        if not store_name:
            continue
        s["writers"] = sorted(writers_by_store.get(store_name, []))


def _reset_reasoning_sections(bp: dict, payloads: list[dict]) -> None:
    """Full-mode redo-safety: clear the Wave-2-regenerated sections that the
    incoming payloads actually carry, so the subsequent merge REPLACES them
    instead of appending.

    Why: `deep_merge` concatenates lists (key_decisions / trade_offs / pitfalls
    have no `name` to dedup on) and refuses to overwrite a non-empty scalar
    (architecture_diagram / executive_summary). Without this, re-running step 5
    (`--from 5`) onto a blueprint_raw that still holds the prior run's Wave-2
    would duplicate the lists and keep a stale diagram/summary.

    Only clears a key when a payload provides it — never blanks a section that
    nothing will repopulate (e.g. a malformed/empty agent file). `communication`
    is intentionally NOT cleared: its patterns dedup by `name`, and Wave 1 owns
    the base array. Caller must gate this to full (non-patch) mode — patch mode
    returns deltas and must preserve unchanged sections.
    """
    present = set()
    for p in payloads:
        present.update(p.keys())
    # Product agent (Wave 2) owns product_model / derived_invariants /
    # unenforced_invariants — same redo-safety as the Design/Risk sections so
    # `--from 5` REPLACES them instead of concatenating (lists) or stale-merging
    # (product_model.entities). domain_invariants is Wave 1 (lives in
    # blueprint_raw) and is intentionally NOT reset here.
    for key in ("decisions", "implementation_guidelines", "pitfalls", "architecture_diagram",
                "product_model", "derived_invariants", "unenforced_invariants"):
        if key in present:
            bp.pop(key, None)
    # Nested: Overview owns meta.executive_summary; keep the rest of meta (Wave-1
    # platforms / architecture_style).
    if any(isinstance(p.get("meta"), dict) and "executive_summary" in p["meta"] for p in payloads):
        if isinstance(bp.get("meta"), dict):
            bp["meta"].pop("executive_summary", None)


def finalize(root: Path, agent_files: list[str] | str | None = None, patch_mode: bool = False):
    """Run the full finalization pipeline.

    `agent_files` may be a single path (legacy) or a list of paths — Wave 2's
    Design/Risk/Overview agents each write their own file and all are merged in
    one call. Merging in a single call keeps step 5 atomic: the blueprint is
    written once, so resume re-runs step 5 from scratch the same way the
    single-agent pipeline did.
    """
    if isinstance(agent_files, str):
        agent_files = [agent_files]
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

    # ── 1. Merge reasoning agent output(s) / patch output ─────────────────
    # Wave 2 may hand us one file (legacy / incremental single-agent) or three
    # (Design / Risk / Overview). Merge them all in this one call so the
    # blueprint is written exactly once — disjoint key ownership means order is
    # irrelevant, and findings are routed per file (only Risk emits them).
    if agent_files:
        _merge = _import_sibling("merge")
        extract_json_from_text = _merge.extract_json_from_text
        deep_merge = _merge.deep_merge

        # Parse every agent file up front (routing findings to the store as we
        # go) so we know which reasoning sections will be regenerated before we
        # touch the base — needed for safe clear-then-merge below.
        payloads = []
        for agent_file in agent_files:
            agent_path = Path(agent_file)
            if not agent_path.exists():
                print(f"  Warning: {agent_file} not found, skipping merge", file=sys.stderr)
                continue
            parsed = extract_json_from_text(agent_path.read_text())
            if not parsed:
                print(f"  Warning: could not parse JSON from {agent_file}", file=sys.stderr)
                continue
            # Findings live in .archie/findings.json, not in the blueprint.
            # Extract and merge id-stably before deep-merging the rest.
            new_findings = parsed.pop("findings", None)
            if isinstance(new_findings, list) and new_findings:
                total = _merge_findings_into_store(archie_dir, new_findings)
                print(f"  Findings store: {total} entries after deep-scan upgrade", file=sys.stderr)
            payloads.append(parsed)

        if payloads:
            # Redo-safety (full mode only): replace, don't append, the Wave-2
            # sections so `--from 5` is idempotent. See _reset_reasoning_sections.
            if not patch_mode:
                _reset_reasoning_sections(bp, payloads)
            for parsed in payloads:
                bp = deep_merge(bp, parsed)

            if patch_mode:
                # In patch mode, write directly to blueprint.json (skip raw)
                (archie_dir / "blueprint.json").write_text(json.dumps(bp, indent=2))
                print("  Patched blueprint.json with incremental reasoning", file=sys.stderr)
            else:
                bp_raw_path.write_text(json.dumps(bp, indent=2))
                print("  Merged reasoning output into blueprint_raw.json", file=sys.stderr)

    # ── 2. Deterministic normalize ─────────────────────────────────────────
    sys.path.insert(0, str(_SCRIPT_DIR))
    from _common import normalize_blueprint  # noqa: E402
    normalize_blueprint(bp)

    # ── 2b. Derive persistence_stores[*].writers ──────────────────────────
    # Walk data_models, resolve each `owned_by_component` slug to a known
    # component name (ancestor-walk algorithm — handles bare names, folder
    # slugs like `page_settings`, descriptive strings with parens, and
    # deeper sub-folder paths like `common/domain/repository/settings`
    # whose closest enclosing component is at `common/domain/repository`).
    # Aggregate unique writer-component names per store and store on
    # `persistence_stores[*].writers` so the renderer + viewers can show
    # "Written by: <component>" without recomputing client-side.
    _derive_persistence_writers(bp)

    # ── Deterministic platform-pitfall seed ───────────────────────────────
    # Inject known platform pitfalls (e.g. legacy-Xcode pbxproj registration)
    # from scanner signals before the blueprint is rendered. Dedup by id keeps
    # re-scans idempotent. Best-effort: never fail finalize over the seed.
    scan_path = archie_dir / "scan.json"
    pp_path = archie_dir / "platform_pitfalls.json"
    if scan_path.exists() and pp_path.exists():
        try:
            _signals = json.loads(scan_path.read_text()).get("platform_pitfall_signals", [])
            _catalog = json.loads(pp_path.read_text())
            bp["pitfalls"] = merge_platform_pitfalls(bp.get("pitfalls", []), _signals, _catalog)
        except Exception as _e:  # pragma: no cover - defensive
            print(f"  Warning: platform-pitfall seed skipped: {_e}", file=sys.stderr)

    # ── C4 enrichment (deterministic, no AI) ─────────────────────────────────
    # Stamp kind/group onto components before the blueprint is written so the
    # viewer's Components section and the C4 diagram both see them. The diagram
    # itself (.archie/c4.json) is generated just after the write. Runs in full
    # + incremental alike; pure function of blueprint + scan.json.
    _c4 = None
    try:
        _c4 = _import_sibling("c4")
        _scan_path = archie_dir / "scan.json"
        _scan = json.loads(_scan_path.read_text()) if _scan_path.exists() else {}
        _c4.enrich_components(bp, _scan)
    except Exception as e:  # never block finalize on diagram generation
        print(f"  C4 enrich skipped: {e}", file=sys.stderr)

    bp_path = archie_dir / "blueprint.json"
    bp_path.write_text(json.dumps(bp, indent=2))

    # c4.json reads the freshly-written enriched blueprint + scan.
    if _c4 is not None:
        try:
            _c4.build_all(root)
            print("  C4 diagram written (.archie/c4.json)", file=sys.stderr)
        except Exception as e:
            print(f"  C4 diagram skipped: {e}", file=sys.stderr)

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

    renderer = _import_sibling("renderer")
    generate_all = renderer.generate_all

    files = generate_all(bp, enforcement_rules=enforcement_rules)
    for rel_path, content in files.items():
        full_path = root / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        # AGENTS.md / CLAUDE.md may coexist with hand-authored content. Route
        # mergeable files through render_mergeable so any user-written section
        # outside Archie's generated block is preserved (mirrors renderer.main()).
        # A straight write_text here was the regression that overwrote curated
        # AGENTS.md files. Everything else is fully Archie-owned → plain write.
        if rel_path in renderer.MERGEABLE_FILES:
            full_path.write_text(renderer.render_mergeable(full_path, content))
        else:
            full_path.write_text(content)
    removed = renderer.cleanup_stale_rule_files(root, files)
    if removed:
        print(f"  Removed {len(removed)} stale rule files", file=sys.stderr)
    print(f"  Rendered {len(files)} files", file=sys.stderr)

    # ── 4. Hooks ───────────────────────────────────────────────────────────
    if not patch_mode:
        install = _import_sibling("install_hooks").install
        install(root)
        print("  Hooks installed", file=sys.stderr)

    # ── 7. Validate (informational) ────────────────────────────────────────
    _validate = _import_sibling("validate")
    check_paths, check_methods, check_pitfalls = _validate.check_paths, _validate.check_methods, _validate.check_pitfalls
    # check_crosslinks measures Wave-2 cross-reference integrity (pitfall→decision,
    # finding→pitfall, trade_off→decision, chain→key_decisions). WARN-only — it is
    # the no-regress signal for the 3-agent split, never a hard gate.
    check_crosslinks = getattr(_validate, "check_crosslinks", None)

    all_errors = []
    checks = [("paths", check_paths), ("methods", check_methods), ("pitfalls", check_pitfalls)]
    if check_crosslinks is not None:
        checks.append(("crosslinks", check_crosslinks))
    for name, fn in checks:
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
        print("Usage: python3 finalize.py /path/to/project [agent1.json agent2.json ...]", file=sys.stderr)
        print("  Or:  python3 finalize.py /path/to/project --patch [agent1.json ...]", file=sys.stderr)
        print("  Or:  python3 finalize.py /path/to/project --normalize-only", file=sys.stderr)
        sys.exit(1)

    project_root = Path(sys.argv[1]).resolve()
    rest = sys.argv[2:]

    if rest and rest[0] == "--normalize-only":
        normalize_only(project_root)
    else:
        patch_mode = False
        if rest and rest[0] == "--patch":
            patch_mode = True
            rest = rest[1:]
        # rest is now zero or more agent output files (one for the legacy /
        # incremental single agent, three for the Design/Risk/Overview split).
        finalize(project_root, rest or None, patch_mode=patch_mode)

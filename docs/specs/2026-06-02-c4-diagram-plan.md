# C4 Architecture Diagram Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a deterministic, script-built C4 diagram (Context / Container / Component) as a second tab next to the existing "Simplified Overview" in the Archie viewer/share.

**Architecture:** A new standalone module `c4.py` reads the enriched blueprint + `scan.json` and writes `.archie/c4.json` (three Mermaid C4 strings, byte-stable). The scanner emits kind-tagged `entrypoints`; `finalize.py` stamps `kind`/`group` onto components and invokes `c4.py` deterministically (no AI, both full + incremental). `upload.py::build_bundle` carries `c4.json` into the bundle, which feeds share (Supabase) and local viewer alike. The React viewer renders the new tab via the already-bundled Mermaid C4 renderer.

**Tech Stack:** Python 3.11 (stdlib only), pytest, React + TypeScript (Vite), Mermaid 11.4.1.

**Design doc:** `docs/specs/2026-06-02-c4-diagram-design.md`
**Branch:** `feature/c4-diagram` (already created)

**Conventions (read before starting):**
- Canonical Python lives in `archie/standalone/*.py`; mirror every change to `npm-package/assets/*.py` and register in `npm-package/bin/archie.mjs`. `python3 scripts/verify_sync.py` must pass before any commit.
- Viewer source is `share/viewer/`; mirrored into `npm-package/assets/viewer/` via `scripts/sync_viewer_assets.sh`.
- Mermaid IDs must be slugs (`[a-z0-9_]`); nodes and edges sorted by key so output is byte-identical across runs.
- No `Date`/random/timestamps in `c4.py` — pure function of inputs.

---

## Task 1: Scanner emits kind-tagged build targets

**Files:**
- Modify: `archie/standalone/scanner.py` (add `detect_build_targets`, near `detect_entry_points` at line 969; add `entrypoints` to the `run_scan` return dict at ~line 1086 next to `"entry_points"`)
- Test: `tests/test_scanner_build_targets.py` (create)

**Step 1: Write the failing test**

```python
"""Scanner emits kind-tagged deployable entrypoints for the C4 Container level."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))
import scanner  # noqa: E402


def _files(*paths):
    return [{"path": p} for p in paths]


def test_build_targets_tags_kind_from_parent_dir():
    files = _files(
        "cmd/server/main.go",
        "cmd/billing-worker/main.go",
        "cmd/jobs/main.go",
        "cmd/benthos-collector/main.go",
        "openmeter/billing/service.go",   # not an entrypoint
    )
    targets = scanner.detect_build_targets(files)
    by_path = {t["path"]: t["kind"] for t in targets}
    assert by_path == {
        "cmd/server/main.go": "service",
        "cmd/billing-worker/main.go": "worker",
        "cmd/jobs/main.go": "cli",
        "cmd/benthos-collector/main.go": "app",
    }


def test_build_targets_is_sorted_for_determinism():
    files = _files("cmd/b/main.go", "cmd/a/main.go")
    targets = scanner.detect_build_targets(files)
    assert [t["path"] for t in targets] == ["cmd/a/main.go", "cmd/b/main.go"]
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scanner_build_targets.py -v`
Expected: FAIL — `AttributeError: module 'scanner' has no attribute 'detect_build_targets'`

**Step 3: Write minimal implementation**

Add after `detect_entry_points` (line 970) in `archie/standalone/scanner.py`:

```python
def _entry_kind(path: str) -> str:
    """Classify a deployable entrypoint by its parent directory name."""
    parts = path.split("/")
    parent = parts[-2].lower() if len(parts) >= 2 else ""
    if "worker" in parent:
        return "worker"
    if parent == "server" or parent.endswith("-service") or parent.endswith("_service") or "service" in parent:
        return "service"
    if parent in ("jobs", "cli") or parent.endswith("-cli"):
        return "cli"
    return "app"


def detect_build_targets(files: list[dict]) -> list[dict]:
    """Deployable units = files whose basename is a known entrypoint, tagged
    with a coarse kind from the parent dir. Sorted by path (byte-stable)."""
    targets = [
        {"path": f["path"], "kind": _entry_kind(f["path"])}
        for f in files
        if f["path"].rsplit("/", 1)[-1] in ENTRY_POINT_NAMES
    ]
    return sorted(targets, key=lambda t: t["path"])
```

In `run_scan` (the `return {` dict at ~line 1077), add a line beside `"entry_points": entry_points,`:

```python
        "entrypoints": detect_build_targets(readable_files),
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_scanner_build_targets.py -v`
Expected: PASS (both tests)

**Step 5: Commit**

```bash
git add archie/standalone/scanner.py tests/test_scanner_build_targets.py
git commit -m "feat(scanner): emit kind-tagged entrypoints for C4 container level"
```

---

## Task 2: c4.py — component enrichment (kind + group)

**Files:**
- Create: `archie/standalone/c4.py`
- Test: `tests/test_c4.py` (create)

**Step 1: Write the failing test**

```python
"""c4.py — deterministic C4 generation from blueprint + scan."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))
import c4  # noqa: E402


def _bp():
    return {
        "meta": {"name": "openmeter"},
        "components": {"components": [
            {"name": "cmd/server", "location": "cmd/server"},
            {"name": "cmd workers", "location": "cmd", "key_files": ["cmd/billing-worker/main.go"]},
            {"name": "openmeter/billing", "location": "openmeter/billing"},
            {"name": "pkg/models", "location": "pkg/models"},
        ]},
        "persistence_stores": ["primary_postgres", "clickhouse_events"],
        "communication": {"integrations": [
            {"service": "Stripe"}, {"service": "PostgreSQL"},
        ]},
    }


def _scan():
    return {"entrypoints": [
        {"path": "cmd/server/main.go", "kind": "service"},
        {"path": "cmd/billing-worker/main.go", "kind": "worker"},
    ]}


def test_enrich_stamps_kind_and_group():
    bp = _bp()
    c4.enrich_components(bp, _scan())
    by_name = {c["name"]: c for c in bp["components"]["components"]}
    # subtree match: server has its own entrypoint, "cmd workers" matches via key_files
    assert by_name["cmd/server"]["kind"] == "service"
    assert by_name["cmd workers"]["kind"] == "worker"
    # no entrypoint under it → lib
    assert by_name["openmeter/billing"]["kind"] == "lib"
    assert by_name["pkg/models"]["kind"] == "lib"
    # group = first path segment
    assert by_name["cmd/server"]["group"] == "cmd"
    assert by_name["openmeter/billing"]["group"] == "openmeter"


def test_enrich_is_idempotent():
    bp = _bp()
    c4.enrich_components(bp, _scan())
    once = [dict(c) for c in bp["components"]["components"]]
    c4.enrich_components(bp, _scan())
    assert bp["components"]["components"] == once
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_c4.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'c4'`

**Step 3: Write minimal implementation**

Create `archie/standalone/c4.py`:

```python
#!/usr/bin/env python3
"""Archie C4 — deterministic C4 diagram generation (no AI).

Reads an enriched blueprint + scan.json, writes .archie/c4.json with three
byte-stable Mermaid C4 strings: context, container, component.

    python3 c4.py /path/to/project        # writes .archie/c4.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


# ── helpers ──────────────────────────────────────────────────────────────────

def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")
    return s or "n"


def _group_of(location: str) -> str:
    loc = (location or "").strip("/")
    return loc.split("/")[0] if loc else "root"


def _components(bp: dict) -> list[dict]:
    comps = bp.get("components", {})
    items = comps.get("components", []) if isinstance(comps, dict) else comps
    return [c for c in items if isinstance(c, dict)]


def _persistence_names(bp: dict) -> list[str]:
    out = []
    for s in bp.get("persistence_stores", []) or []:
        out.append(s if isinstance(s, str) else s.get("name", ""))
    return [s for s in out if s]


def _integrations(bp: dict) -> list[str]:
    out = []
    for i in bp.get("communication", {}).get("integrations", []) or []:
        name = i.get("service") or i.get("name") if isinstance(i, dict) else i
        if name:
            out.append(name)
    return out


def _externals(bp: dict) -> list[str]:
    """Third-party systems = integrations minus our own datastores."""
    stores_norm = {_slug(s) for s in _persistence_names(bp)}
    seen, out = set(), []
    for name in _integrations(bp):
        sl = _slug(name)
        if sl in stores_norm or sl in seen:
            continue
        seen.add(sl)
        out.append(name)
    return sorted(out, key=_slug)


# ── enrichment ─────────────────────────────────────────────────────────────

def enrich_components(bp: dict, scan: dict) -> None:
    """Stamp `kind` and `group` onto each component, in place. Idempotent."""
    entrypoints = scan.get("entrypoints", []) if isinstance(scan, dict) else []
    store_slugs = {_slug(s) for s in _persistence_names(bp)}
    for comp in _components(bp):
        loc = (comp.get("location") or "").strip("/")
        key_files = comp.get("key_files") or []
        # subtree match: any entrypoint at-or-under this component's location/key_files
        matched = []
        for ep in entrypoints:
            p = ep.get("path", "")
            under_loc = loc and (p == loc or p.startswith(loc + "/"))
            in_keyfiles = any(p == kf or p.startswith(str(kf).rstrip("/") + "/") for kf in key_files)
            if under_loc or in_keyfiles:
                matched.append(ep.get("kind", "app"))
        if matched:
            comp["kind"] = sorted(set(matched))[0]
        elif _slug(comp.get("name", "")) in store_slugs or _slug(loc) in store_slugs:
            comp["kind"] = "datastore"
        else:
            comp["kind"] = "lib"
        comp["group"] = _group_of(loc)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_c4.py -v`
Expected: PASS (both tests)

**Step 5: Commit**

```bash
git add archie/standalone/c4.py tests/test_c4.py
git commit -m "feat(c4): component kind+group enrichment (deterministic)"
```

---

## Task 3: c4.py — Context level (C4Context)

**Files:**
- Modify: `archie/standalone/c4.py`
- Test: `tests/test_c4.py`

**Step 1: Add the failing test**

```python
def test_build_context_separates_externals_from_datastores():
    out = c4.build_context(_bp())
    assert out.startswith("C4Context")
    assert 'System(' in out          # the repo itself
    assert 'System_Ext(' in out and "Stripe" in out      # true external
    assert 'SystemDb(' in out and "primary_postgres" in out  # datastore
    assert "PostgreSQL" not in out.split("System_Ext")[-1].split("\n")[0]  # PG not an external (it's a store)


def test_build_context_is_byte_stable():
    assert c4.build_context(_bp()) == c4.build_context(_bp())
```

**Step 2: Run** `python -m pytest tests/test_c4.py -k context -v` → FAIL (`no attribute 'build_context'`)

**Step 3: Implement** (append to `c4.py`):

```python
def build_context(bp: dict) -> str:
    name = bp.get("meta", {}).get("name") or "System"
    sys_id = _slug(name)
    lines = ["C4Context", f"title System Context — {name}", f'System({sys_id}, "{name}", "This system")']
    rels = []
    for ext in _externals(bp):
        eid = _slug(ext)
        lines.append(f'System_Ext({eid}, "{ext}", "External system")')
        rels.append(f'Rel({sys_id}, {eid}, "uses")')
    for store in sorted(_persistence_names(bp), key=_slug):
        sid = _slug(store)
        lines.append(f'SystemDb({sid}, "{store}", "Datastore")')
        rels.append(f'Rel({sys_id}, {sid}, "reads/writes")')
    return "\n".join(lines + sorted(rels))
```

**Step 4: Run** `python -m pytest tests/test_c4.py -v` → PASS

**Step 5: Commit**

```bash
git add archie/standalone/c4.py tests/test_c4.py
git commit -m "feat(c4): Context level (C4Context)"
```

---

## Task 4: c4.py — Container level (C4Container, entrypoint-driven)

**Files:**
- Modify: `archie/standalone/c4.py`
- Test: `tests/test_c4.py`

**Step 1: Add the failing test**

```python
def test_build_container_nodes_are_entrypoints():
    out = c4.build_container(_bp(), _scan())
    assert out.startswith("C4Container")
    # one Container per real binary, named from the entrypoint dir
    assert "server" in out and "billing-worker" in out
    assert 'ContainerDb(' in out and "primary_postgres" in out
    assert 'System_Ext(' in out and "Stripe" in out
    assert 'System_Boundary(' in out  # grouped by `group`


def test_build_container_byte_stable():
    assert c4.build_container(_bp(), _scan()) == c4.build_container(_bp(), _scan())
```

**Step 2: Run** `-k container` → FAIL

**Step 3: Implement** (append). The binary's display name = entrypoint parent dir; group = first path segment:

```python
def _binary_name(path: str) -> str:
    parts = path.split("/")
    return parts[-2] if len(parts) >= 2 else parts[0]


def build_container(bp: dict, scan: dict) -> str:
    name = bp.get("meta", {}).get("name") or "System"
    lines = ["C4Container", f"title Containers — {name}"]
    rels = []
    entrypoints = sorted(
        (scan.get("entrypoints", []) if isinstance(scan, dict) else []),
        key=lambda e: e.get("path", ""),
    )
    # group binaries into System_Boundary by first path segment
    groups: dict[str, list[dict]] = {}
    for ep in entrypoints:
        groups.setdefault(_group_of(ep.get("path", "")), []).append(ep)
    for grp in sorted(groups):
        lines.append(f'System_Boundary(b_{_slug(grp)}, "{grp}") {{')
        for ep in groups[grp]:
            bid = _slug(ep.get("path", ""))
            bn = _binary_name(ep.get("path", ""))
            lines.append(f'  Container({bid}, "{bn}", "{ep.get("kind", "app")}")')
        lines.append("}")
    # datastores + externals at top level
    for store in sorted(_persistence_names(bp), key=_slug):
        lines.append(f'ContainerDb({_slug(store)}, "{store}", "Datastore")')
    for ext in _externals(bp):
        lines.append(f'System_Ext({_slug(ext)}, "{ext}", "External system")')
    # best-effort edges: every binary touches every datastore/external is too noisy;
    # v1 draws binary→datastore only when a single binary exists, else omit (nodes are
    # exact, edges are best-effort). Keep deterministic + minimal.
    return "\n".join(lines + sorted(rels))
```

> NOTE: v1 keeps Container edges minimal/empty (nodes are the exact, valuable part; cross-binary edge inference is deferred). This is intentional — log it, do not silently imply full edges.

**Step 4: Run** `python -m pytest tests/test_c4.py -v` → PASS

**Step 5: Commit**

```bash
git add archie/standalone/c4.py tests/test_c4.py
git commit -m "feat(c4): Container level (entrypoint-driven C4Container)"
```

---

## Task 5: c4.py — Component level + build_all + CLI

**Files:**
- Modify: `archie/standalone/c4.py`
- Test: `tests/test_c4.py`

**Step 1: Add the failing test**

```python
def test_build_component_uses_depends_on_and_groups():
    bp = _bp()
    bp["components"]["components"][2]["depends_on"] = ["pkg/models"]
    c4.enrich_components(bp, _scan())
    out = c4.build_component(bp)
    assert out.startswith("C4Component")
    assert 'Component(' in out
    assert 'Rel(' in out  # billing depends_on models
    assert 'Container_Boundary(' in out  # grouped


def test_build_all_writes_three_levels(tmp_path):
    a = tmp_path / ".archie"
    a.mkdir()
    import json as _j
    (a / "blueprint.json").write_text(_j.dumps(_bp()))
    (a / "scan.json").write_text(_j.dumps(_scan()))
    c4.build_all(tmp_path)
    data = _j.loads((a / "c4.json").read_text())
    assert set(data) == {"context", "container", "component"}
    assert data["context"].startswith("C4Context")
    # build_all also persisted kind/group back onto blueprint.json
    bp = _j.loads((a / "blueprint.json").read_text())
    assert all("kind" in c and "group" in c for c in bp["components"]["components"])
```

**Step 2: Run** → FAIL

**Step 3: Implement** (append):

```python
def build_component(bp: dict) -> str:
    name = bp.get("meta", {}).get("name") or "System"
    comps = [c for c in _components(bp) if c.get("kind") != "datastore"]
    by_name = {c.get("name"): c for c in comps}
    lines = ["C4Component", f"title Components — {name}"]
    rels = []
    groups: dict[str, list[dict]] = {}
    for c in comps:
        groups.setdefault(c.get("group") or _group_of(c.get("location", "")), []).append(c)
    for grp in sorted(groups):
        lines.append(f'Container_Boundary(bc_{_slug(grp)}, "{grp}") {{')
        for c in sorted(groups[grp], key=lambda x: _slug(x.get("name", ""))):
            cid = _slug(c.get("name", ""))
            resp = (c.get("responsibility") or c.get("kind") or "").replace('"', "'")[:60]
            lines.append(f'  Component({cid}, "{c.get("name","")}", "{resp}")')
        lines.append("}")
    for c in comps:
        src = _slug(c.get("name", ""))
        for dep in sorted(c.get("depends_on", []) or []):
            if dep in by_name:
                rels.append(f'Rel({src}, {_slug(dep)}, "depends on")')
    return "\n".join(lines + sorted(set(rels)))


def build_all(project_root: Path) -> dict:
    archie = Path(project_root) / ".archie"
    bp = json.loads((archie / "blueprint.json").read_text())
    scan_path = archie / "scan.json"
    scan = json.loads(scan_path.read_text()) if scan_path.exists() else {}
    enrich_components(bp, scan)
    (archie / "blueprint.json").write_text(json.dumps(bp, indent=2))
    c4 = {
        "context": build_context(bp),
        "container": build_container(bp, scan),
        "component": build_component(bp),
    }
    (archie / "c4.json").write_text(json.dumps(c4, indent=2))
    return c4


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: c4.py /path/to/project", file=sys.stderr)
        return 2
    build_all(Path(argv[0]).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

**Step 4: Run** `python -m pytest tests/test_c4.py -v` → PASS (all)

**Step 5: Commit**

```bash
git add archie/standalone/c4.py tests/test_c4.py
git commit -m "feat(c4): Component level + build_all + CLI"
```

---

## Task 6: Wire c4 into finalize (enrich + write c4.json)

**Files:**
- Modify: `archie/standalone/finalize.py` (around lines 328–331: after `_derive_persistence_writers(bp)`, before the blueprint write)
- Test: `tests/test_finalize_c4.py` (create)

**Step 1: Write the failing test**

```python
"""finalize wires c4.build_all: blueprint gains kind/group, c4.json is written."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))
import finalize as F  # noqa: E402


def test_finalize_writes_c4_and_enriches(tmp_path):
    a = tmp_path / ".archie"
    a.mkdir()
    (a / "scan.json").write_text(json.dumps(
        {"entrypoints": [{"path": "cmd/server/main.go", "kind": "service"}]}))
    (a / "blueprint_raw.json").write_text(json.dumps({
        "meta": {"name": "demo"},
        "components": {"components": [{"name": "cmd/server", "location": "cmd/server"}]},
        "persistence_stores": ["pg"],
        "communication": {"patterns": []},
    }))
    F.finalize(tmp_path, [])  # no agent files; just normalize+render+c4

    bp = json.loads((a / "blueprint.json").read_text())
    comp = bp["components"]["components"][0]
    assert comp["kind"] == "service" and comp["group"] == "cmd"
    c4 = json.loads((a / "c4.json").read_text())
    assert c4["context"].startswith("C4Context")
```

**Step 2: Run** `python -m pytest tests/test_finalize_c4.py -v` → FAIL (no `c4.json`, no `kind`)

**Step 3: Implement**

In `archie/standalone/finalize.py`, immediately after `_derive_persistence_writers(bp)` (line 328) and before `bp_path = archie_dir / "blueprint.json"` (line 330), insert:

```python
    # ── C4 enrichment + diagram generation (deterministic, no AI) ────────────
    # Stamp kind/group onto components, then emit .archie/c4.json (Context /
    # Container / Component Mermaid strings) for the viewer's C4 tab. Runs in
    # full + incremental alike; pure function of blueprint + scan.json.
    try:
        _c4 = _import_sibling("c4")
        _scan_path = archie_dir / "scan.json"
        _scan = json.loads(_scan_path.read_text()) if _scan_path.exists() else {}
        _c4.enrich_components(bp, _scan)
    except Exception as e:  # never block finalize on diagram generation
        print(f"  C4 enrich skipped: {e}", file=sys.stderr)
        _scan = {}
```

Then after the blueprint write (`bp_path.write_text(...)`, line 331), insert:

```python
    # c4.json reads the freshly-written enriched blueprint + scan.
    try:
        _c4.build_all(root)
        print("  C4 diagram written (.archie/c4.json)", file=sys.stderr)
    except Exception as e:
        print(f"  C4 diagram skipped: {e}", file=sys.stderr)
```

> `build_all` re-reads + re-writes blueprint.json (harmless, idempotent — enrich already ran). Acceptable for v1 clarity; if perf matters, refactor `build_all` to accept an in-memory `bp` later.

**Step 4: Run** `python -m pytest tests/test_finalize_c4.py -v` → PASS

**Step 5: Commit**

```bash
git add archie/standalone/finalize.py tests/test_finalize_c4.py
git commit -m "feat(finalize): enrich components + generate c4.json"
```

---

## Task 7: Carry c4.json into the bundle (share + local)

**Files:**
- Modify: `archie/standalone/upload.py::build_bundle` (after the findings block, ~line 190)
- Test: `tests/test_upload_c4.py` (create)

**Step 1: Write the failing test**

```python
"""build_bundle carries .archie/c4.json into bundle['c4'] (share + local viewer)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))
import upload  # noqa: E402


def _min_archie(tmp_path):
    a = tmp_path / ".archie"
    a.mkdir()
    (a / "blueprint.json").write_text(json.dumps({"meta": {"name": "x"}}))
    return a


def test_bundle_includes_c4_when_present(tmp_path):
    a = _min_archie(tmp_path)
    (a / "c4.json").write_text(json.dumps({"context": "C4Context\n", "container": "", "component": ""}))
    bundle = upload.build_bundle(tmp_path)
    assert bundle["c4"]["context"].startswith("C4Context")


def test_bundle_omits_c4_when_absent(tmp_path):
    _min_archie(tmp_path)
    bundle = upload.build_bundle(tmp_path)
    assert "c4" not in bundle
```

**Step 2: Run** → FAIL

**Step 3: Implement** — in `build_bundle`, after the findings block (line 190), before the semantic-duplications block (line 192):

```python
    # C4 diagrams (Context/Container/Component Mermaid). Deterministic, script-
    # built. Optional — old bundles without it make the viewer hide the C4 tab.
    c4 = _read_json(archie_dir / "c4.json")
    if isinstance(c4, dict):
        bundle["c4"] = c4
```

**Step 4: Run** `python -m pytest tests/test_upload_c4.py -v` → PASS

**Step 5: Commit**

```bash
git add archie/standalone/upload.py tests/test_upload_c4.py
git commit -m "feat(share): carry c4.json into the bundle (share + local viewer)"
```

---

## Task 8: Sync Python assets

**Files:**
- Create: `npm-package/assets/c4.py` (copy of `archie/standalone/c4.py`)
- Modify: `npm-package/assets/scanner.py`, `npm-package/assets/finalize.py`, `npm-package/assets/upload.py` (mirror the canonical edits)
- Modify: `npm-package/bin/archie.mjs` (add `"c4.py"` to the script copy list)

**Step 1: Mirror the files**

```bash
cp archie/standalone/c4.py npm-package/assets/c4.py
cp archie/standalone/scanner.py npm-package/assets/scanner.py
cp archie/standalone/finalize.py npm-package/assets/finalize.py
cp archie/standalone/upload.py npm-package/assets/upload.py
```

**Step 2: Register c4.py in archie.mjs**

In `npm-package/bin/archie.mjs`, find the `for (const script of [ ... ]` array and add `"c4.py",` (keep alphabetical if the list is).

**Step 3: Run the sync checker**

Run: `python3 scripts/verify_sync.py`
Expected: prints success, exit 0. If it reports `c4.py` missing from the archie.mjs list or an asset mismatch, fix and re-run.

**Step 4: Run full Python test suite**

Run: `python -m pytest tests/ -v`
Expected: all PASS (new + existing — esp. `test_connector_contract.py`).

**Step 5: Commit**

```bash
git add npm-package/assets/c4.py npm-package/assets/scanner.py npm-package/assets/finalize.py npm-package/assets/upload.py npm-package/bin/archie.mjs
git commit -m "chore(sync): mirror c4.py + scanner/finalize/upload to npm assets"
```

---

## Task 9: Viewer — Bundle type + C4 tab

**Files:**
- Modify: `share/viewer/src/lib/api.ts` (`interface Bundle`, ~line 14)
- Modify: `share/viewer/src/pages/ReportPage.tsx` (derive `c4` near line 114; replace the diagram `<section id="diagram">` body at 815–833 with a tab strip)
- Test: `share/viewer/src/pages/ReportPage.c4.test.tsx` (create — if the viewer has a test runner; otherwise verify manually in Step 4)

**Step 1: Add the C4 type**

In `api.ts`, add to `interface Bundle`:

```typescript
  c4?: { context?: string; container?: string; component?: string }
```

**Step 2: Derive c4 + render tabs in ReportPage**

Near line 114 (after `const diagram = ...`):

```typescript
  const c4 = bundle?.c4
  const c4Levels = ([
    ['container', 'Container', 'Deployable units, datastores, and external systems'],
    ['context', 'Context', 'The system and the external systems it talks to'],
    ['component', 'Component', 'Internal modules and their dependencies'],
  ] as const).filter(([k]) => typeof c4?.[k] === 'string' && c4![k]!.trim().length > 0)
  const hasC4 = c4Levels.length > 0
```

Add view state near the other `useState` hooks:

```typescript
  const [diagramTab, setDiagramTab] = useState<'overview' | 'c4'>('overview')
  const [c4Level, setC4Level] = useState<'context' | 'container' | 'component'>('container')
```

Replace the body of `<section id="diagram">` (lines ~816–833) so the existing caption + `<MermaidDiagram chart={diagram} />` sit under an "Simplified Overview" tab, and add a "C4 Model" tab (only when `hasC4`) containing an inner Context/Container/Component segmented control that renders `<MermaidDiagram chart={c4![c4Level]!} />` with the matching caption. Use the same tab/segmented-control styling already used for the local VIEW toggle (lines ~412–430) for visual consistency. Default tab = `overview`; if `c4Level` isn't in `c4Levels`, fall back to the first available level.

**Step 3: Type-check + build**

Run: `cd share/viewer && npm run build`
Expected: build succeeds, no TS errors.

**Step 4: Manual verification**

Run the local viewer against a project that has `.archie/c4.json`:
```bash
python3 archie/standalone/viewer.py /Users/hamutarto/DEV/gbr/openmeter
```
Confirm: "Simplified Overview" tab unchanged + default; "C4 Model" tab appears, the inner toggle switches Context/Container/Component, each renders a valid C4 diagram. Then load a project WITHOUT `c4.json` and confirm the C4 tab is hidden and the page is otherwise unchanged.

**Step 5: Commit**

```bash
git add share/viewer/src/lib/api.ts share/viewer/src/pages/ReportPage.tsx
git commit -m "feat(viewer): C4 Model tab with Context/Container/Component toggle"
```

---

## Task 10: Sync viewer assets + final verification

**Files:**
- Modify: `npm-package/assets/viewer/*` (built viewer mirror)

**Step 1: Sync the built viewer into npm assets**

Run: `bash scripts/sync_viewer_assets.sh`
(Confirms `check_viewer_source_mirror` in verify_sync stays green.)

**Step 2: Full sync + test gate**

Run:
```bash
python3 scripts/verify_sync.py && python -m pytest tests/ -v
```
Expected: verify_sync exit 0; all tests pass.

**Step 3: End-to-end on a real repo**

Regenerate `.archie/c4.json` deterministically and confirm byte-stability:
```bash
python3 archie/standalone/c4.py /Users/hamutarto/DEV/gbr/openmeter
cp /Users/hamutarto/DEV/gbr/openmeter/.archie/c4.json /tmp/c4-a.json
python3 archie/standalone/c4.py /Users/hamutarto/DEV/gbr/openmeter
diff /tmp/c4-a.json /Users/hamutarto/DEV/gbr/openmeter/.archie/c4.json && echo "BYTE-STABLE"
```
Expected: `BYTE-STABLE` (no diff). Spot-check the three Mermaid strings render in the viewer.

**Step 4: Commit**

```bash
git add npm-package/assets/viewer
git commit -m "chore(sync): mirror built viewer with C4 tab into npm assets"
```

**Step 5: Open PR** (only when the user asks to ship)

Target `feature/c4-diagram` → `main`. PR body: summarize the deterministic C4 generation, the second tab, "no Supabase change (verified)", and that the Simplified Overview is unchanged.

---

## Notes & deferred work (log, don't silently skip)

- **Container edges are minimal in v1** (Task 4): nodes (binaries, datastores, externals) are exact; cross-binary→datastore/external edge inference from `integration_point` is deferred. Surface this in the PR so it reads as a deliberate v1 boundary, not an omission.
- **Entrypoint coverage** is `ENTRY_POINT_NAMES`-based (Go `main.go`, Python `__main__.py`, etc.). `package.json` `bin`/Dockerfile-service detection is a future enhancement; until then unconventional stacks get a thinner Container level (Context + Component still render fully).
- **Multi-CLI:** nothing here touches connectors or workflow prompts — `c4.py` is standalone and deterministic, so Claude Code and Codex are unaffected by construction. No per-CLI verification needed beyond the standard test gate.
- **Supabase:** no change (verified: `upload/index.ts` stores arbitrary bundle keys, 5 MB cap, `blueprint` GET returns full blob).

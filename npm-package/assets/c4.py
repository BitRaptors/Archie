#!/usr/bin/env python3
"""Archie C4 — deterministic C4 diagram generation (no AI).

Reads an enriched blueprint + scan.json, writes .archie/c4.json with three
byte-stable Mermaid C4 strings: context, container, component.

    python3 c4.py /path/to/project        # writes .archie/c4.json

Three data sources, each used where it is strongest:
  - kind   (app/service/worker/cli/lib/datastore) <- scanner entrypoints +
           persistence_stores. Answers "is it deployable?".
  - group  (cmd / openmeter / api / pkg ...)      <- first path segment.
           Answers "what layer?". Drives System_Boundary grouping.
  - Container level is driven by scanner entrypoints (the real binaries);
    Component level by the components + depends_on; Context needs neither.
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
        name = (i.get("service") or i.get("name")) if isinstance(i, dict) else i
        if name:
            out.append(name)
    return out


# Datastore/message-bus names that show up in `integrations` but are our own
# infrastructure, not third-party systems. Their canonical nodes come from
# `persistence_stores`; we drop the integration duplicate so the Context level
# does not double-count them as external systems.
DATASTORE_HINTS = (
    "postgres", "mysql", "mariadb", "clickhouse", "redis", "kafka", "mongo",
    "sqlite", "dynamodb", "cassandra", "elasticsearch", "opensearch",
    "rabbitmq", "memcached", "cockroach", "watermill",
)


def _is_datastore_name(name: str) -> bool:
    sl = _slug(name)
    return any(h in sl for h in DATASTORE_HINTS)


def _externals(bp: dict) -> list[str]:
    """Third-party systems = integrations minus our own datastores/buses.

    Two filters because integration names rarely match persistence_store names
    textually (e.g. integration "PostgreSQL" vs store "primary_postgres"):
    (1) slug equality with a known store, (2) a datastore/bus keyword hint.
    """
    stores_norm = {_slug(s) for s in _persistence_names(bp)}
    seen, out = set(), []
    for name in _integrations(bp):
        sl = _slug(name)
        if sl in stores_norm or _is_datastore_name(name) or sl in seen:
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
        # key_files are the more specific signal: a component at location `cmd`
        # subtree-matches every cmd/* binary, but its key_files name the one it
        # actually owns. Prefer key_files matches; fall back to location subtree.
        kf_kinds, loc_kinds = [], []
        for ep in entrypoints:
            p = ep.get("path", "")
            in_keyfiles = any(
                p == kf or p.startswith(str(kf).rstrip("/") + "/") for kf in key_files
            )
            under_loc = bool(loc) and (p == loc or p.startswith(loc + "/"))
            if in_keyfiles:
                kf_kinds.append(ep.get("kind", "app"))
            elif under_loc:
                loc_kinds.append(ep.get("kind", "app"))
        matched = kf_kinds or loc_kinds
        if matched:
            comp["kind"] = sorted(set(matched))[0]
        elif _slug(comp.get("name", "")) in store_slugs or _slug(loc) in store_slugs:
            comp["kind"] = "datastore"
        else:
            comp["kind"] = "lib"
        comp["group"] = _group_of(loc)


# ── Context level ──────────────────────────────────────────────────────────

def _system_name(bp: dict, name: str | None) -> str:
    return name or bp.get("meta", {}).get("name") or "System"


def build_context(bp: dict, name: str | None = None) -> str:
    name = _system_name(bp, name)
    sys_id = _slug(name)
    lines = [
        "C4Context",
        f"title System Context — {name}",
        f'System({sys_id}, "{name}", "This system")',
    ]
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


# ── Container level (entrypoint-driven) ──────────────────────────────────────

def _binary_name(path: str) -> str:
    parts = path.split("/")
    return parts[-2] if len(parts) >= 2 else parts[0]


def _path_related(a: str, b: str) -> bool:
    """True when two component paths overlap (equal / ancestor / descendant)."""
    a, b = a.strip("/"), b.strip("/")
    if not a or not b:
        return False
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def _anchor_component(ep_path: str, components: list[dict]) -> dict | None:
    """The component a binary belongs to: longest `location` that prefixes the
    entrypoint path, or a component naming it in key_files."""
    best, best_len = None, -1
    for c in components:
        loc = (c.get("location") or "").strip("/")
        if loc and (ep_path == loc or ep_path.startswith(loc + "/")) and len(loc) > best_len:
            best, best_len = c, len(loc)
        for kf in c.get("key_files") or []:
            if ep_path == kf or ep_path.startswith(str(kf).rstrip("/") + "/"):
                if best_len < 0:
                    best, best_len = c, 0
    return best


def _store_writers(bp: dict) -> dict[str, list[str]]:
    """Map persistence store name -> writer component names (when present)."""
    out: dict[str, list[str]] = {}
    for s in bp.get("persistence_stores", []) or []:
        if isinstance(s, dict) and s.get("name"):
            out[s["name"]] = [w for w in (s.get("writers") or []) if w]
    return out


def build_container(bp: dict, scan: dict, name: str | None = None) -> str:
    name = _system_name(bp, name)
    rels: list[str] = []
    entrypoints = sorted(
        (scan.get("entrypoints", []) if isinstance(scan, dict) else []),
        key=lambda e: e.get("path", ""),
    )
    stores = sorted(_persistence_names(bp), key=_slug)
    externals = _externals(bp)
    # Node-less guard: a C4 diagram with only a title fails to render. Signal the
    # viewer (which filters empty strings) to hide this level.
    if not entrypoints and not stores and not externals:
        return ""

    components = _components(bp)
    writers = _store_writers(bp)

    lines = ["C4Container", f"title Containers — {name}"]
    groups: dict[str, list[dict]] = {}
    for ep in entrypoints:
        groups.setdefault(_group_of(ep.get("path", "")), []).append(ep)
    for grp in sorted(groups):
        lines.append(f'System_Boundary(b_{_slug(grp)}, "{grp}") {{')
        for ep in groups[grp]:
            p = ep.get("path", "")
            lines.append(f'  Container({_slug(p)}, "{_binary_name(p)}", "{ep.get("kind", "app")}")')
        lines.append("}")
    for store in stores:
        lines.append(f'ContainerDb({_slug(store)}, "{store}", "Datastore")')
    for ext in externals:
        lines.append(f'System_Ext({_slug(ext)}, "{ext}", "External system")')

    # Edges: binary -> datastore, derived from the binary's anchor-component
    # dependencies vs each store's writers (path-prefix match). Wiring-based, so
    # partial — a binary that delegates persistence via DI may show no edge.
    for ep in entrypoints:
        anchor = _anchor_component(ep.get("path", ""), components)
        if not anchor:
            continue
        deps = list(anchor.get("depends_on") or []) + [anchor.get("name", ""), anchor.get("location", "")]
        for store, ws in writers.items():
            if any(_path_related(d, w) for d in deps for w in ws):
                rels.append(f'Rel({_slug(ep.get("path", ""))}, {_slug(store)}, "writes")')
    return "\n".join(lines + sorted(set(rels)))


# ── Component level ─────────────────────────────────────────────────────────

def build_component(bp: dict, name: str | None = None) -> str:
    name = _system_name(bp, name)
    comps = [c for c in _components(bp) if c.get("kind") != "datastore"]
    if not comps:  # node-less guard (see build_container)
        return ""
    by_name = {c.get("name"): c for c in comps}
    lines = ["C4Component", f"title Components — {name}"]
    rels: list[str] = []
    groups: dict[str, list[dict]] = {}
    for c in comps:
        grp = c.get("group") or _group_of(c.get("location", ""))
        groups.setdefault(grp, []).append(c)
    for grp in sorted(groups):
        lines.append(f'Container_Boundary(bc_{_slug(grp)}, "{grp}") {{')
        for c in sorted(groups[grp], key=lambda x: _slug(x.get("name", ""))):
            cid = _slug(c.get("name", ""))
            resp = (c.get("responsibility") or c.get("kind") or "").replace('"', "'")[:60]
            lines.append(f'  Component({cid}, "{c.get("name", "")}", "{resp}")')
        lines.append("}")
    for c in comps:
        src = _slug(c.get("name", ""))
        for dep in sorted(c.get("depends_on", []) or []):
            if dep in by_name:
                rels.append(f'Rel({src}, {_slug(dep)}, "depends on")')
    return "\n".join(lines + sorted(set(rels)))


# ── orchestration ────────────────────────────────────────────────────────────

def build_all(project_root: Path) -> dict:
    archie = Path(project_root) / ".archie"
    bp = json.loads((archie / "blueprint.json").read_text())
    scan_path = archie / "scan.json"
    scan = json.loads(scan_path.read_text()) if scan_path.exists() else {}
    enrich_components(bp, scan)
    (archie / "blueprint.json").write_text(json.dumps(bp, indent=2))
    name = Path(project_root).resolve().name
    out = {
        "context": build_context(bp, name),
        "container": build_container(bp, scan, name),
        "component": build_component(bp, name),
    }
    (archie / "c4.json").write_text(json.dumps(out, indent=2))
    return out


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: c4.py /path/to/project", file=sys.stderr)
        return 2
    build_all(Path(argv[0]).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

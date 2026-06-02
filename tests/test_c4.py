"""c4.py — deterministic C4 generation from blueprint + scan."""
import json
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


# ── enrichment ────────────────────────────────────────────────────────────

def test_enrich_stamps_kind_and_group():
    bp = _bp()
    c4.enrich_components(bp, _scan())
    by_name = {c["name"]: c for c in bp["components"]["components"]}
    assert by_name["cmd/server"]["kind"] == "service"
    assert by_name["cmd workers"]["kind"] == "worker"   # via key_files subtree match
    assert by_name["openmeter/billing"]["kind"] == "lib"
    assert by_name["pkg/models"]["kind"] == "lib"
    assert by_name["cmd/server"]["group"] == "cmd"
    assert by_name["openmeter/billing"]["group"] == "openmeter"


def test_enrich_is_idempotent():
    bp = _bp()
    c4.enrich_components(bp, _scan())
    once = [dict(c) for c in bp["components"]["components"]]
    c4.enrich_components(bp, _scan())
    assert bp["components"]["components"] == once


# ── Context level ──────────────────────────────────────────────────────────

def test_build_context_separates_externals_from_datastores():
    out = c4.build_context(_bp())
    assert out.startswith("C4Context")
    assert "System(" in out
    assert "System_Ext(" in out and "Stripe" in out
    assert "SystemDb(" in out and "primary_postgres" in out
    # PostgreSQL is a store, not an external → must not appear as System_Ext
    ext_lines = [ln for ln in out.splitlines() if ln.startswith("System_Ext(")]
    assert not any("PostgreSQL" in ln for ln in ext_lines)


def test_build_context_is_byte_stable():
    assert c4.build_context(_bp()) == c4.build_context(_bp())


# ── Container level ─────────────────────────────────────────────────────────

def test_build_container_nodes_are_entrypoints():
    out = c4.build_container(_bp(), _scan())
    assert out.startswith("C4Container")
    assert "server" in out and "billing-worker" in out
    assert "ContainerDb(" in out and "primary_postgres" in out
    assert "System_Ext(" in out and "Stripe" in out
    assert "System_Boundary(" in out


def test_build_container_byte_stable():
    assert c4.build_container(_bp(), _scan()) == c4.build_container(_bp(), _scan())


def test_build_container_draws_binary_to_datastore_edges():
    # cmd/server's anchor component depends on a writer of postgres → edge.
    bp = _bp()
    bp["components"]["components"][0]["depends_on"] = ["internal/billing"]
    bp["persistence_stores"] = [{"name": "primary_postgres", "writers": ["internal/billing"]}]
    bp["components"]["components"].append({"name": "internal/billing", "location": "internal/billing"})
    c4.enrich_components(bp, _scan())
    out = c4.build_container(bp, _scan())
    assert 'Rel(cmd_server_main_go, primary_postgres, "writes")' in out


def test_container_edges_from_dir_graph_reachability():
    # Ground truth: cmd/server transitively reaches internal/billing (a postgres
    # writer) through the real import graph, even with no direct depends_on.
    bp = _bp()
    bp["persistence_stores"] = [{"name": "primary_postgres", "writers": ["internal/billing"]}]
    bp["components"]["components"].append({"name": "internal/billing", "location": "internal/billing"})
    c4.enrich_components(bp, _scan())
    dg = {"cmd/server": {"internal/api"}, "internal/api": {"internal/billing"}, "internal/billing": set()}
    out = c4.build_container(bp, _scan(), None, dg)
    assert 'Rel(cmd_server_main_go, primary_postgres, "writes")' in out


def test_component_edges_from_dir_graph():
    # dir graph edges aggregate to group-level edges.
    bp = _bp()
    c4.enrich_components(bp, _scan())
    dg = {"openmeter/billing/charges": {"pkg/models"}, "pkg/models": set()}
    out = c4.build_component(bp, None, dg)
    assert 'Rel(openmeter, pkg, "depends on")' in out


def test_build_container_empty_when_no_nodes():
    # No entrypoints, no stores, no externals → node-less → "" (viewer hides it).
    empty = {"meta": {}, "components": {"components": []},
             "persistence_stores": [], "communication": {"integrations": []}}
    assert c4.build_container(empty, {"entrypoints": []}) == ""


def test_build_component_empty_when_no_components():
    empty = {"meta": {}, "components": {"components": []}}
    assert c4.build_component(empty) == ""


# ── Component level ─────────────────────────────────────────────────────────

def test_build_component_collapses_to_groups():
    # Component level = folder-group nodes + group edges (fallback via depends_on).
    bp = _bp()
    bp["components"]["components"][2]["depends_on"] = ["pkg/models"]  # openmeter/billing -> pkg/models
    c4.enrich_components(bp, _scan())
    out = c4.build_component(bp)
    assert out.startswith("C4Component")
    # group nodes, not per-module nodes
    assert 'Component(openmeter,' in out and 'Component(pkg,' in out
    assert 'Component(openmeter_billing,' not in out
    # group-level edge
    assert 'Rel(openmeter, pkg, "depends on")' in out


# ── build_all + CLI ─────────────────────────────────────────────────────────

def test_build_all_writes_three_levels(tmp_path):
    a = tmp_path / ".archie"
    a.mkdir()
    (a / "blueprint.json").write_text(json.dumps(_bp()))
    (a / "scan.json").write_text(json.dumps(_scan()))
    c4.build_all(tmp_path)
    data = json.loads((a / "c4.json").read_text())
    assert set(data) == {"context", "container", "component"}
    assert data["context"].startswith("C4Context")
    bp = json.loads((a / "blueprint.json").read_text())
    assert all("kind" in c and "group" in c for c in bp["components"]["components"])

"""Tests for the deterministic Mermaid diagram generator.

Diagram is rendered from the structured blueprint without any AI call.
These tests cover the contract: which nodes appear, which edges connect
them, what gets clustered, what gets capped, what gets elided.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_DIAGRAM_PATH = Path(__file__).resolve().parents[1] / "archie" / "standalone" / "diagram.py"
_spec = importlib.util.spec_from_file_location("_archie_diagram_under_test", _DIAGRAM_PATH)
diagram = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(diagram)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Empty / degenerate
# ---------------------------------------------------------------------------

def test_empty_blueprint_returns_empty_string():
    assert diagram.generate({}) == ""


def test_blueprint_with_no_components_returns_empty():
    assert diagram.generate({"components": {"components": []}}) == ""
    assert diagram.generate({"components": {}}) == ""
    assert diagram.generate({"data_models": [{"name": "X"}]}) == ""


def test_components_without_name_are_skipped():
    bp = {"components": {"components": [{"location": "a/"}, {"name": "Real"}]}}
    out = diagram.generate(bp)
    assert "graph TD" in out
    assert "Real" in out


# ---------------------------------------------------------------------------
# Nodes and edges
# ---------------------------------------------------------------------------

def test_single_component_renders_node_no_edges():
    bp = {"components": {"components": [{"name": "Solo", "platform": "backend"}]}}
    out = diagram.generate(bp)
    assert "graph TD" in out
    assert "Solo" in out
    assert "-->" not in out
    # Single platform → no subgraph wrapping
    assert "subgraph" not in out


def test_depends_on_renders_edges():
    bp = {"components": {"components": [
        {"name": "A", "depends_on": ["B", "C"]},
        {"name": "B", "depends_on": ["C"]},
        {"name": "C"},
    ]}}
    out = diagram.generate(bp)
    assert "A --> B" in out
    assert "A --> C" in out
    assert "B --> C" in out


def test_depends_on_filters_out_external_libs():
    """Dependencies on non-component names (3rd-party libs) get dropped."""
    bp = {"components": {"components": [
        {"name": "A", "depends_on": ["B", "react", "lodash"]},
        {"name": "B"},
    ]}}
    out = diagram.generate(bp)
    assert "A --> B" in out
    assert "react" not in out
    assert "lodash" not in out


def test_self_referential_depends_on_dropped():
    bp = {"components": {"components": [{"name": "A", "depends_on": ["A", "B"]}, {"name": "B"}]}}
    out = diagram.generate(bp)
    assert "A --> B" in out
    # No A→A self-loop
    assert "A --> A" not in out


def test_duplicate_edges_collapsed():
    bp = {"components": {"components": [
        {"name": "A", "depends_on": ["B", "B"]},
        {"name": "B"},
    ]}}
    out = diagram.generate(bp)
    assert out.count("A --> B") == 1


# ---------------------------------------------------------------------------
# Subgraph clustering by platform
# ---------------------------------------------------------------------------

def test_single_platform_no_subgraphs():
    bp = {"components": {"components": [
        {"name": "A", "platform": "backend"},
        {"name": "B", "platform": "backend"},
    ]}}
    out = diagram.generate(bp)
    assert "subgraph" not in out


def test_multi_platform_renders_subgraphs():
    bp = {"components": {"components": [
        {"name": "Api", "platform": "backend"},
        {"name": "Web", "platform": "frontend"},
        {"name": "Shared", "platform": "shared"},
    ]}}
    out = diagram.generate(bp)
    assert "subgraph" in out
    assert out.count("subgraph") == 3
    # Count whole-line 'end' closers (not the substring inside 'backend'/'Frontend')
    end_lines = sum(1 for line in out.split("\n") if line.strip() == "end")
    assert end_lines == 3
    # Labels render with human-readable names
    assert '"Backend"' in out
    assert '"Frontend"' in out


def test_missing_platform_falls_into_shared_bucket():
    bp = {"components": {"components": [
        {"name": "Api", "platform": "backend"},
        {"name": "Util"},
    ]}}
    out = diagram.generate(bp)
    assert "subgraph" in out
    assert "Util" in out


# ---------------------------------------------------------------------------
# External integrations
# ---------------------------------------------------------------------------

def test_integration_renders_pill_and_attaches_to_component():
    bp = {
        "components": {"components": [
            {"name": "PaymentService", "location": "backend/services/payment"}
        ]},
        "communication": {"integrations": [
            {"service": "Stripe", "integration_point": "backend/services/payment/charge.py"}
        ]},
    }
    out = diagram.generate(bp)
    assert "ext_Stripe([" in out
    assert "PaymentService -.->|integrates| ext_Stripe" in out


def test_integration_without_resolvable_path_still_renders_pill():
    bp = {
        "components": {"components": [{"name": "App", "location": "src/"}]},
        "communication": {"integrations": [
            {"service": "Sentry", "integration_point": "unknown/path.py"}
        ]},
    }
    out = diagram.generate(bp)
    assert "ext_Sentry([" in out
    # No attaching edge when the path doesn't resolve
    assert "|integrates| ext_Sentry" not in out


def test_duplicate_integration_services_collapsed():
    bp = {
        "components": {"components": [{"name": "App", "location": "src/"}]},
        "communication": {"integrations": [
            {"service": "Firebase", "integration_point": "src/auth.py"},
            {"service": "Firebase", "integration_point": "src/db.py"},
        ]},
    }
    out = diagram.generate(bp)
    assert out.count("ext_Firebase([") == 1


# ---------------------------------------------------------------------------
# Persistence layer
# ---------------------------------------------------------------------------

def test_persistence_stores_render_as_cylinders():
    bp = {
        "components": {"components": [{"name": "Api"}]},
        "persistence_stores": [
            {"name": "primary_postgres", "engine": "PostgreSQL 15"}
        ],
    }
    out = diagram.generate(bp)
    assert "store_primary_postgres[(" in out


def test_data_model_owner_to_store_edge():
    bp = {
        "components": {"components": [{"name": "OrderService"}]},
        "persistence_stores": [{"name": "primary_pg"}],
        "data_models": [{
            "name": "Order",
            "owned_by_component": "OrderService",
            "store": "primary_pg",
        }],
    }
    out = diagram.generate(bp)
    assert "OrderService ==>|persists| store_primary_pg" in out


def test_persistence_edges_deduped_per_owner_store_pair():
    """Multiple models owned by the same component pointing at the same
    store should produce a single arrow, not one per model."""
    bp = {
        "components": {"components": [{"name": "OrderService"}]},
        "persistence_stores": [{"name": "primary_pg"}],
        "data_models": [
            {"name": "Order", "owned_by_component": "OrderService", "store": "primary_pg"},
            {"name": "Refund", "owned_by_component": "OrderService", "store": "primary_pg"},
            {"name": "Payment", "owned_by_component": "OrderService", "store": "primary_pg"},
        ],
    }
    out = diagram.generate(bp)
    assert out.count("OrderService ==>|persists| store_primary_pg") == 1


def test_data_model_skipped_when_owner_unknown():
    bp = {
        "components": {"components": [{"name": "RealService"}]},
        "persistence_stores": [{"name": "pg"}],
        "data_models": [
            {"name": "Order", "owned_by_component": "MissingService", "store": "pg"}
        ],
    }
    out = diagram.generate(bp)
    assert "MissingService" not in out
    assert "|persists|" not in out


def test_data_model_skipped_when_store_unknown():
    bp = {
        "components": {"components": [{"name": "Svc"}]},
        "persistence_stores": [{"name": "real_pg"}],
        "data_models": [
            {"name": "Order", "owned_by_component": "Svc", "store": "missing_store"}
        ],
    }
    out = diagram.generate(bp)
    assert "|persists|" not in out


# ---------------------------------------------------------------------------
# Top-N cap on huge repos
# ---------------------------------------------------------------------------

def test_top_n_cap_engages_above_threshold():
    """31 components — only the top 15 by edge degree should render, plus
    a single 'X hidden' note."""
    comps = [{"name": f"C{i:02d}"} for i in range(31)]
    # Make C00 highly connected (referenced by 20 others) so it ranks first
    for i in range(1, 21):
        comps[i]["depends_on"] = ["C00"]
    bp = {"components": {"components": comps}}
    out = diagram.generate(bp)
    # C00 must be present (top-ranked by inbound count)
    assert "C00" in out
    # Hidden-count note must appear
    assert "16 more components hidden" in out
    # Only 15 component nodes should be rendered (count node declarations
    # excluding the hidden-count note shape).
    node_count = sum(1 for line in out.split("\n") if line.strip().startswith(("C", "n_C")) and "[\"" in line)
    assert node_count <= 15


def test_top_n_cap_not_engaged_under_threshold():
    bp = {"components": {"components": [{"name": f"C{i}"} for i in range(10)]}}
    out = diagram.generate(bp)
    assert "hidden" not in out


# ---------------------------------------------------------------------------
# Backward-compat — legacy blueprints without data_models/persistence_stores
# ---------------------------------------------------------------------------

def test_legacy_blueprint_without_persistence_renders_fine():
    bp = {"components": {"components": [
        {"name": "A", "platform": "backend", "depends_on": ["B"]},
        {"name": "B", "platform": "backend"},
    ]}}
    out = diagram.generate(bp)
    assert "graph TD" in out
    assert "A --> B" in out
    # Nothing persistence-related rendered
    assert "store_" not in out
    assert "|persists|" not in out


# ---------------------------------------------------------------------------
# Node ID safety — special chars in component names mustn't break Mermaid
# ---------------------------------------------------------------------------

def test_special_chars_in_names_sanitized():
    bp = {"components": {"components": [
        {"name": "page-login/fragment", "depends_on": ["util.helpers"]},
        {"name": "util.helpers"},
    ]}}
    out = diagram.generate(bp)
    # No spaces / slashes / dots in node IDs (those break Mermaid parsing)
    for line in out.split("\n"):
        # crude: scan lines that look like edge declarations
        if "-->" in line:
            lhs, _, rhs = line.partition("-->")
            for token in (lhs.strip(), rhs.strip()):
                assert "/" not in token and " " not in token.split("[")[0]


def test_names_starting_with_digit_get_letter_prefix():
    bp = {"components": {"components": [{"name": "2fa-checker"}]}}
    out = diagram.generate(bp)
    assert "n_2fa_checker" in out


def test_quotes_in_labels_escaped():
    """Mermaid label parsing breaks on unescaped double quotes."""
    bp = {"components": {"components": [{"name": 'X"quoted"'}]}}
    out = diagram.generate(bp)
    # Generated label should use single quotes inside the double-quoted label.
    assert "X'quoted'" in out


# ---------------------------------------------------------------------------
# Resolver tolerance — Wave 1 emits depends_on / owned_by_component in
# several shapes (bare names, folder slugs, descriptive strings with paren).
# ---------------------------------------------------------------------------

def test_depends_on_folder_slug_resolves_to_component():
    """When depends_on holds a folder slug like `page_settings`, it
    resolves to the component whose location ends with that slug."""
    bp = {"components": {"components": [
        {"name": "Application Bootstrap", "location": "app/src/main/java/com/x",
         "depends_on": ["page_settings"]},
        {"name": "Settings Page", "location": "app/src/main/java/com/x/page_settings"},
    ]}}
    out = diagram.generate(bp)
    assert "Application_Bootstrap --> Settings_Page" in out


def test_depends_on_descriptive_string_with_paren_resolves():
    """When depends_on holds `common/domain (domainModule)`, the
    parenthetical is stripped and the path resolves to a component."""
    bp = {"components": {"components": [
        {"name": "Boot", "location": "app",
         "depends_on": ["common/domain (domainModule, SHARED_DATA)"]},
        {"name": "Domain", "location": "app/common/domain"},
    ]}}
    out = diagram.generate(bp)
    assert "Boot --> Domain" in out


def test_owned_by_component_folder_slug_resolves():
    """data_models[*].owned_by_component holding a folder slug resolves
    to the matching component and renders the persists edge."""
    bp = {
        "components": {"components": [
            {"name": "Settings Page",
             "location": "app/src/main/java/com/x/page_settings"},
        ]},
        "persistence_stores": [{"name": "shared_prefs"}],
        "data_models": [{
            "name": "SettingsRepo",
            "owned_by_component": "page_settings",
            "store": "shared_prefs",
        }],
    }
    out = diagram.generate(bp)
    assert "Settings_Page ==>|persists| store_shared_prefs" in out


def test_unresolvable_dependency_silently_dropped():
    """Free-form prose with no component anchor (e.g. 3rd-party lib refs)
    is dropped, not rendered as a dangling edge."""
    bp = {"components": {"components": [
        {"name": "X", "depends_on": ["hu.bitraptors RaptorSdk (private SDK)"]},
    ]}}
    out = diagram.generate(bp)
    assert "X" in out
    assert "-->" not in out


# ---------------------------------------------------------------------------
# Determinism — same blueprint produces byte-identical output
# ---------------------------------------------------------------------------

def test_deterministic_output():
    bp = {
        "components": {"components": [
            {"name": "B", "platform": "backend"},
            {"name": "A", "platform": "backend", "depends_on": ["B"]},
            {"name": "C", "platform": "frontend"},
        ]},
        "persistence_stores": [
            {"name": "redis"},
            {"name": "postgres"},
        ],
        "communication": {"integrations": [
            {"service": "Zeta", "integration_point": ""},
            {"service": "Alpha", "integration_point": ""},
        ]},
    }
    a = diagram.generate(bp)
    b = diagram.generate(bp)
    assert a == b

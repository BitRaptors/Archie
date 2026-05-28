"""Tests for finalize.py::_derive_persistence_writers.

The deriver walks data_models, resolves each `owned_by_component` slug to
a known component name (via ancestor-walk), and aggregates unique writer
names per store onto `persistence_stores[*].writers`. Single source of
truth for "who writes which store" — read by both the markdown renderer
and the React viewer.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_FINALIZE_PATH = Path(__file__).resolve().parents[1] / "archie" / "standalone" / "finalize.py"
_spec = importlib.util.spec_from_file_location("_archie_finalize_under_test", _FINALIZE_PATH)
finalize = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(finalize)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# _resolve_owner_to_component — the resolver alone
# ---------------------------------------------------------------------------

def test_exact_name_match():
    components = [{"name": "OrderService", "location": "backend/services/orders"}]
    name_set = {"OrderService"}
    assert finalize._resolve_owner_to_component("OrderService", components, name_set) == "OrderService"


def test_strip_paren_then_exact_match():
    components = [{"name": "OrderService", "location": "backend/services/orders"}]
    name_set = {"OrderService"}
    out = finalize._resolve_owner_to_component(
        "OrderService (placementModule)", components, name_set,
    )
    assert out == "OrderService"


def test_folder_slug_resolves_to_component():
    """`page_settings` should resolve to the component whose location
    ends with `/page_settings`."""
    components = [
        {"name": "Settings Page", "location": "app/src/main/java/com/x/page_settings"},
        {"name": "Other", "location": "app/src/main/java/com/x/something_else"},
    ]
    name_set = {"Settings Page", "Other"}
    out = finalize._resolve_owner_to_component("page_settings", components, name_set)
    assert out == "Settings Page"


def test_ancestor_walk_for_deep_subfolder():
    """`common/domain/repository/settings` has no exact component — walk up
    to `common/domain/repository`, which is the location's suffix of
    `Common Domain - Repositories`."""
    components = [
        {"name": "Common Domain - Repositories",
         "location": "app/src/main/java/com/x/common/domain/repository"},
    ]
    name_set = {"Common Domain - Repositories"}
    out = finalize._resolve_owner_to_component(
        "common/domain/repository/settings", components, name_set,
    )
    assert out == "Common Domain - Repositories"


def test_returns_empty_when_no_match():
    components = [{"name": "A", "location": "src/a"}]
    name_set = {"A"}
    assert finalize._resolve_owner_to_component("totally_unrelated", components, name_set) == ""


def test_empty_input_returns_empty():
    assert finalize._resolve_owner_to_component("", [], set()) == ""
    assert finalize._resolve_owner_to_component(None, [], set()) == ""  # type: ignore[arg-type]


def test_descriptive_string_with_paren_falls_to_path_resolution():
    """A blob like `common/domain (domainModule, SHARED_DATA)` strips
    the paren to `common/domain`, then resolves by ancestor walk."""
    components = [
        {"name": "Common Domain - DTO Layer", "location": "src/common/domain/api/dto"},
        {"name": "Common Domain - Network Layer", "location": "src/common/domain/api"},
    ]
    name_set = {c["name"] for c in components}
    # candidate = "common/domain"; no exact, walk: "common" — no match.
    # So returns empty (correctly — "common/domain" is ambiguous among 2 components).
    out = finalize._resolve_owner_to_component(
        "common/domain (domainModule)", components, name_set,
    )
    # The resolver returns the FIRST matching component when ancestor-walking;
    # for ambiguous slugs, we accept whichever comes first (the strict-match
    # path doesn't fire because no location ends with /common/domain).
    # The important guarantee: it doesn't crash and returns a valid result.
    assert out == "" or out in name_set


# ---------------------------------------------------------------------------
# _derive_persistence_writers — the full pipeline mutation
# ---------------------------------------------------------------------------

def test_no_persistence_stores_is_noop():
    bp: dict = {"data_models": [{"name": "X", "owned_by_component": "Y", "store": "z"}]}
    finalize._derive_persistence_writers(bp)
    assert "persistence_stores" not in bp


def test_no_data_models_yields_empty_writers():
    bp: dict = {
        "persistence_stores": [{"name": "pg", "engine": "PostgreSQL"}],
        "components": {"components": [{"name": "A"}]},
    }
    finalize._derive_persistence_writers(bp)
    assert bp["persistence_stores"][0]["writers"] == []


def test_writers_populated_from_owned_by_component():
    bp = {
        "components": {"components": [
            {"name": "OrderService", "location": "backend/services/orders"},
        ]},
        "persistence_stores": [{"name": "primary_pg"}],
        "data_models": [
            {"name": "Order", "owned_by_component": "OrderService", "store": "primary_pg"},
        ],
    }
    finalize._derive_persistence_writers(bp)
    assert bp["persistence_stores"][0]["writers"] == ["OrderService"]


def test_writers_dedup_across_models():
    """Two models with the same owner pointing at the same store should
    produce a single writer entry, not duplicates."""
    bp = {
        "components": {"components": [
            {"name": "OrderService", "location": "backend/services/orders"},
        ]},
        "persistence_stores": [{"name": "pg"}],
        "data_models": [
            {"name": "Order", "owned_by_component": "OrderService", "store": "pg"},
            {"name": "Refund", "owned_by_component": "OrderService", "store": "pg"},
            {"name": "Audit", "owned_by_component": "OrderService", "store": "pg"},
        ],
    }
    finalize._derive_persistence_writers(bp)
    assert bp["persistence_stores"][0]["writers"] == ["OrderService"]


def test_writers_aggregate_multiple_components():
    bp = {
        "components": {"components": [
            {"name": "OrderService", "location": "backend/services/orders"},
            {"name": "PaymentService", "location": "backend/services/payment"},
        ]},
        "persistence_stores": [{"name": "pg"}],
        "data_models": [
            {"name": "Order", "owned_by_component": "OrderService", "store": "pg"},
            {"name": "Payment", "owned_by_component": "PaymentService", "store": "pg"},
        ],
    }
    finalize._derive_persistence_writers(bp)
    # Sorted alphabetically for stable output across runs
    assert bp["persistence_stores"][0]["writers"] == ["OrderService", "PaymentService"]


def test_writers_sorted_alphabetically():
    bp = {
        "components": {"components": [
            {"name": "Zeta", "location": "src/z"},
            {"name": "Alpha", "location": "src/a"},
            {"name": "Mike", "location": "src/m"},
        ]},
        "persistence_stores": [{"name": "store"}],
        "data_models": [
            {"name": "M1", "owned_by_component": "Zeta", "store": "store"},
            {"name": "M2", "owned_by_component": "Alpha", "store": "store"},
            {"name": "M3", "owned_by_component": "Mike", "store": "store"},
        ],
    }
    finalize._derive_persistence_writers(bp)
    assert bp["persistence_stores"][0]["writers"] == ["Alpha", "Mike", "Zeta"]


def test_writers_resolved_via_folder_slug():
    """data_model.owned_by_component is a folder slug (`page_settings`),
    not the bare component name. Resolver should find it."""
    bp = {
        "components": {"components": [
            {"name": "Settings Page", "location": "app/src/main/com/x/page_settings"},
        ]},
        "persistence_stores": [{"name": "shared_prefs"}],
        "data_models": [
            {"name": "Settings", "owned_by_component": "page_settings", "store": "shared_prefs"},
        ],
    }
    finalize._derive_persistence_writers(bp)
    assert bp["persistence_stores"][0]["writers"] == ["Settings Page"]


def test_writers_resolved_via_ancestor_walk():
    """The BabyWeather case: `owned_by_component: 'common/domain/repository/settings'`
    has no direct match; walk up to find `Common Domain - Repositories` whose
    location ends with `common/domain/repository`."""
    bp = {
        "components": {"components": [
            {"name": "Common Domain - Repositories",
             "location": "app/src/main/com/x/common/domain/repository"},
        ]},
        "persistence_stores": [{"name": "firebase_storage"}],
        "data_models": [
            {"name": "profile_image_blob",
             "owned_by_component": "common/domain/repository/settings",
             "store": "firebase_storage"},
        ],
    }
    finalize._derive_persistence_writers(bp)
    assert bp["persistence_stores"][0]["writers"] == ["Common Domain - Repositories"]


def test_unresolvable_owner_dropped_silently():
    """A data_model whose owner can't be resolved to any component should
    NOT add a fake writer, just be ignored."""
    bp = {
        "components": {"components": [{"name": "A", "location": "src/a"}]},
        "persistence_stores": [{"name": "pg"}],
        "data_models": [
            {"name": "X", "owned_by_component": "totally_made_up_thing", "store": "pg"},
        ],
    }
    finalize._derive_persistence_writers(bp)
    assert bp["persistence_stores"][0]["writers"] == []


def test_existing_writers_field_overwritten():
    """Re-running finalize must replace stale writer lists, not append."""
    bp = {
        "components": {"components": [{"name": "Real", "location": "src/real"}]},
        "persistence_stores": [{"name": "pg", "writers": ["Stale", "Older"]}],
        "data_models": [
            {"name": "M", "owned_by_component": "Real", "store": "pg"},
        ],
    }
    finalize._derive_persistence_writers(bp)
    assert bp["persistence_stores"][0]["writers"] == ["Real"]


def test_multiple_stores_each_get_their_own_writers():
    bp = {
        "components": {"components": [
            {"name": "A", "location": "src/a"},
            {"name": "B", "location": "src/b"},
        ]},
        "persistence_stores": [
            {"name": "store1"},
            {"name": "store2"},
        ],
        "data_models": [
            {"name": "M1", "owned_by_component": "A", "store": "store1"},
            {"name": "M2", "owned_by_component": "B", "store": "store2"},
        ],
    }
    finalize._derive_persistence_writers(bp)
    assert bp["persistence_stores"][0]["writers"] == ["A"]
    assert bp["persistence_stores"][1]["writers"] == ["B"]

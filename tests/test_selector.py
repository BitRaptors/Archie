import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "archie" / "standalone"))
import selector as sel

BP = {
  "domain_invariants": [{"id": "inv-1", "enforced_at": ["billing/usage.py:88", "billing/"]}],
  "decisions": {"key_decisions": [{"title": "d1", "forced_by": "core/router.py"}]},
  "persistence_stores": [{"name": "pg", "location": "db/models.py"}],
  "data_models": [{"name": "Cart", "location": "db/models.py"}],
}

def test_invariant_specialist_selected_on_cited_file():
    out = sel.select_specialists(BP, ["billing/usage.py"])
    assert "invariant-integrity" in out["specialists"]
    # reason format: "cites domain_invariant inv-1[,inv-2,...]"
    # Split on whitespace+comma so "inv-1" does not falsely match "inv-10".
    reason_str = out["reason"]["invariant-integrity"]
    ids_in_reason = reason_str.replace("cites domain_invariant ", "").split(",")
    assert "inv-1" in ids_in_reason, (
        f"Expected 'inv-1' as an exact id in reason, got: {reason_str!r}"
    )

def test_data_lifecycle_selected_on_store_file():
    out = sel.select_specialists(BP, ["db/models.py"])
    assert "data-lifecycle" in out["specialists"]

def test_no_touch_returns_empty():
    assert sel.select_specialists(BP, ["README.md"])["specialists"] == []

def test_short_anchor_does_not_substring_match_unrelated_file():
    bp = {"domain_invariants": [{"id": "inv-x", "enforced_at": ["db/"]}],
          "decisions": {"key_decisions": []}, "persistence_stores": [], "data_models": []}
    out = sel.select_specialists(bp, ["services/redis_db_client.py"])
    assert out["specialists"] == []


def test_hit_does_not_match_interior_segment():
    """Anchor 'src/api/' must NOT match a file under 'vendor/src/api/'."""
    bp = {"domain_invariants": [{"id": "inv-api", "enforced_at": ["src/api/"]}],
          "decisions": {"key_decisions": []}, "persistence_stores": [], "data_models": []}
    out = sel.select_specialists(bp, ["vendor/src/api/x.py"])
    assert out["specialists"] == [], f"Expected no specialist but got {out['specialists']}"


def test_multiple_invariants_all_surface():
    """When two invariants both match the changed files, both ids appear in the reason."""
    bp = {
        "domain_invariants": [
            {"id": "inv-A", "enforced_at": ["billing/"]},
            {"id": "inv-B", "enforced_at": ["billing/usage.py"]},
        ],
        "decisions": {"key_decisions": []},
        "persistence_stores": [],
        "data_models": [],
    }
    out = sel.select_specialists(bp, ["billing/usage.py"])
    assert "invariant-integrity" in out["specialists"]
    reason_str = out["reason"]["invariant-integrity"]
    assert "inv-A" in reason_str, f"inv-A missing from reason: {reason_str}"
    assert "inv-B" in reason_str, f"inv-B missing from reason: {reason_str}"


def test_touched_context_selects_intersecting_invariant():
    """An invariant enforced_at a changed file → returned in invariants; a decision
    whose forced_by matches → returned in decisions. Non-touched items are excluded."""
    bp = {
        "domain_invariants": [
            {"id": "inv-hit", "invariant": "tenant scope", "enforced_at": ["billing/usage.py:88"]},
            {"id": "inv-miss", "invariant": "unrelated", "enforced_at": ["other/thing.py"]},
        ],
        "decisions": {"key_decisions": [
            {"title": "d-hit", "forced_by": "core/router.py"},
            {"title": "d-miss", "forced_by": "misc/other.py"},
        ]},
    }
    ctx = sel.touched_context(bp, ["billing/usage.py", "core/router.py"])
    inv_ids = {i["id"] for i in ctx["invariants"]}
    dec_titles = {d["title"] for d in ctx["decisions"]}
    assert inv_ids == {"inv-hit"}
    assert dec_titles == {"d-hit"}


def test_touched_context_empty_when_nothing_touched():
    ctx = sel.touched_context(BP, ["README.md"])
    assert ctx["invariants"] == []
    assert ctx["decisions"] == []


def test_touched_context_skips_overridden_invariant():
    """A ratified/staged override retires the law — the review engine must not
    keep enforcing it even though the entry stays in domain_invariants and its
    anchor still matches a changed file. A live sibling still surfaces."""
    bp = {
        "domain_invariants": [
            {"id": "inv-dead", "invariant": "retired", "enforced_at": ["billing/usage.py"],
             "status": "overridden"},
            {"id": "inv-staged", "invariant": "pending ratify", "enforced_at": ["billing/usage.py"],
             "status": "override_staged"},
            {"id": "inv-live", "invariant": "still enforced", "enforced_at": ["billing/usage.py"]},
        ],
        "decisions": {"key_decisions": []},
    }
    ctx = sel.touched_context(bp, ["billing/usage.py"])
    inv_ids = {i["id"] for i in ctx["invariants"]}
    assert inv_ids == {"inv-live"}


def test_select_specialists_skips_overridden_invariant():
    bp = {
        "domain_invariants": [
            {"id": "inv-dead", "enforced_at": ["billing/usage.py"], "status": "overridden"},
        ],
        "decisions": {"key_decisions": []}, "persistence_stores": [], "data_models": [],
    }
    out = sel.select_specialists(bp, ["billing/usage.py"])
    assert out["specialists"] == []


# --- parallel/duplicated-tree tolerance (worker <-> new_worker) ---

def test_duplicated_tree_routes_invariant():
    """An invariant anchored in worker/ must route for a change in the duplicate
    new_worker/ that shares the same path tail."""
    bp = {"domain_invariants": [{"id": "inv-dup", "enforced_at": ["worker/main.py:757"]}],
          "decisions": {"key_decisions": []}, "persistence_stores": [], "data_models": []}
    assert "invariant-integrity" in sel.select_specialists(bp, ["new_worker/main.py"])["specialists"]
    # deep tails work too
    bp2 = {"domain_invariants": [{"id": "inv-dup2",
            "enforced_at": ["worker/lib/supabase/supabase_client.py:1058"]}],
           "decisions": {"key_decisions": []}, "persistence_stores": [], "data_models": []}
    ctx = sel.touched_context(bp2, ["new_worker/lib/supabase/supabase_client.py"])
    assert {i["id"] for i in ctx["invariants"]} == {"inv-dup2"}


def test_unrelated_roots_do_not_parallel_match():
    """Same filename under UNRELATED top dirs must NOT match (billing vs other)."""
    bp = {"domain_invariants": [{"id": "inv-x", "enforced_at": ["billing/usage.py:88"]}],
          "decisions": {"key_decisions": []}, "persistence_stores": [], "data_models": []}
    assert sel.select_specialists(bp, ["other/usage.py"])["specialists"] == []


def test_parallel_tolerance_ignores_directory_anchors():
    """Directory anchors (src/api/) keep their strict semantics — no tail-matching."""
    bp = {"domain_invariants": [{"id": "inv-api", "enforced_at": ["src/api/"]}],
          "decisions": {"key_decisions": []}, "persistence_stores": [], "data_models": []}
    assert sel.select_specialists(bp, ["new_src/api/x.py"])["specialists"] == []


def test_related_roots_helper():
    assert sel._related_roots("worker", "new_worker")      # suffix
    assert sel._related_roots("api", "api_v2")             # prefix
    assert not sel._related_roots("billing", "other")
    assert not sel._related_roots("src", "vendor")

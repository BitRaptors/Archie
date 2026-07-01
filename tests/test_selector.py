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
    assert "inv-1" in out["reason"]["invariant-integrity"]

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

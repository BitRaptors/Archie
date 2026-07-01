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

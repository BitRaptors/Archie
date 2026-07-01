import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import reachability as r  # noqa: E402

GRAPH = {"a.py": ["b"], "b.py": ["c"], "c.py": [], "d.py": ["a"]}

def test_direct_and_transitive_consumers():
    got = set(r.consumers(GRAPH, "c.py"))
    assert got == {"b.py", "a.py", "d.py"}

def test_leaf_change_has_no_consumers():
    assert r.consumers(GRAPH, "d.py") == []

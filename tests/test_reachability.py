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


def test_same_basename_not_conflated():
    """app/util.py and lib/util.py should not share consumers when imports are path-ish.

    If the import string contains a slash (path-ish), the resolver should distinguish
    between app/util.py and lib/util.py.  main.py imports 'app/util' -> should appear
    in consumers('app/util.py') but NOT in consumers('lib/util.py').
    """
    graph = {
        "app/util.py": [],
        "lib/util.py": [],
        "main.py": ["app/util"],  # path-ish import -> resolves to app/util.py
    }
    app_consumers = set(r.consumers(graph, "app/util.py"))
    lib_consumers = set(r.consumers(graph, "lib/util.py"))
    assert "main.py" in app_consumers, "main.py should be a consumer of app/util.py"
    assert "main.py" not in lib_consumers, (
        "main.py incorrectly counted as consumer of lib/util.py (basename collision)"
    )


def test_consumers_terminates_on_cycle():
    """Cyclic import graph must not cause infinite loop."""
    graph = {
        "a.py": ["b"],
        "b.py": ["a"],
    }
    result = r.consumers(graph, "a.py")
    # Should terminate and include b.py (which imports a)
    assert isinstance(result, list)
    assert "b.py" in result

import importlib.util
from pathlib import Path

_SPEC = Path(__file__).resolve().parents[1] / "archie" / "standalone" / "link_store.py"
_mod = importlib.util.spec_from_file_location("link_store", _SPEC)
link_store = importlib.util.module_from_spec(_mod)
_mod.loader.exec_module(link_store)


def test_archie_home_uses_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ARCHIE_HOME", str(tmp_path / "home"))
    assert link_store.archie_home() == tmp_path / "home"


def test_project_store_path(monkeypatch, tmp_path):
    monkeypatch.setenv("ARCHIE_HOME", str(tmp_path / "home"))
    assert link_store.project_store("abc") == tmp_path / "home" / "projects" / "abc"


def test_link_file_round_trip(tmp_path):
    data = {"schema_version": 1, "project_id": "p1", "mode": "detached"}
    link_store.write_link_file(tmp_path, data)
    assert (tmp_path / link_store.LINK_FILENAME).exists()
    assert link_store.read_link_file(tmp_path) == data


def test_read_link_file_absent(tmp_path):
    assert link_store.read_link_file(tmp_path) is None


def test_exposure_defaults_when_absent(tmp_path):
    exp = link_store.read_exposure(tmp_path)
    assert exp["categories"]["rules"] is True
    assert exp["overrides"] == {}
    exp["categories"]["rules"] = False
    assert link_store.read_exposure(tmp_path)["categories"]["rules"] is True


def test_exposure_round_trip(tmp_path):
    exp = link_store.read_exposure(tmp_path)
    exp["categories"]["folder_context"] = False
    link_store.write_exposure(tmp_path, exp)
    assert link_store.read_exposure(tmp_path)["categories"]["folder_context"] is False


def test_placements_round_trip(tmp_path):
    assert link_store.read_placements(tmp_path) == []
    items = [{"path": ".archie", "kind": "dir", "strategy": "symlink"}]
    link_store.write_placements(tmp_path, items)
    assert link_store.read_placements(tmp_path) == items

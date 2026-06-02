# tests/benchmark/test_store.py
import json
from archie.benchmark import store


def test_offline_fallback_when_env_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    out = tmp_path / "nested" / "results.json"
    res = store.store_results({"name": "x"}, [{"arm": "treatment"}], out)
    assert res["mode"] == "offline"
    saved = json.loads(out.read_text())
    assert saved["run"]["name"] == "x"
    assert saved["samples"][0]["arm"] == "treatment"


def test_online_write_posts_run_then_samples(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "secret")
    calls = []

    def fake_poster(url, key, table, rows):
        calls.append((table, rows))
        if table == "benchmark_runs":
            return [{"id": "run-123"}]
        return rows

    res = store.store_results({"name": "x"}, [{"arm": "treatment"}, {"arm": "control"}],
                              tmp_path / "r.json", _poster=fake_poster)
    assert res["mode"] == "online"
    assert res["run_id"] == "run-123"
    assert calls[0][0] == "benchmark_runs"
    assert calls[1][0] == "benchmark_samples"
    # run_id stamped onto every sample row
    assert all(r["run_id"] == "run-123" for r in calls[1][1])

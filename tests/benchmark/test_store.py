# tests/benchmark/test_store.py
import json

import pytest

from archie.benchmark import store


@pytest.fixture(autouse=True)
def _isolate_secrets(tmp_path, monkeypatch):
    """Keep tests independent of a developer's real .archie-bench/secrets.env."""
    monkeypatch.setattr(store, "SECRETS_PATH", tmp_path / "no-secrets.env")


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


def test_offline_fallback_on_post_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "secret")

    def failing_poster(url, key, table, rows):
        raise OSError("connection refused")

    out = tmp_path / "results.json"
    res = store.store_results({"name": "x"}, [{"arm": "control"}], out,
                              _poster=failing_poster)
    assert res["mode"] == "offline-fallback"
    assert "connection refused" in res["error"]
    assert json.loads(out.read_text())["run"]["name"] == "x"


def test_secrets_file_autoload(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    secrets = tmp_path / "secrets.env"
    secrets.write_text(
        "# comment\n"
        "SUPABASE_URL=https://real.supabase.co\n"
        "SUPABASE_SERVICE_KEY='sk-real'\n"
    )
    monkeypatch.setattr(store, "SECRETS_PATH", secrets)
    assert store._env() == ("https://real.supabase.co", "sk-real")


def test_secrets_file_placeholders_ignored(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    secrets = tmp_path / "secrets.env"
    secrets.write_text(
        "SUPABASE_URL=https://REPLACE-WITH-PROJECT-REF.supabase.co\n"
        "SUPABASE_SERVICE_KEY=REPLACE-WITH-SERVICE-ROLE-KEY\n"
    )
    monkeypatch.setattr(store, "SECRETS_PATH", secrets)
    assert store._env() == (None, None)


def test_env_vars_take_precedence_over_secrets_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://env.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "sk-env")
    secrets = tmp_path / "secrets.env"
    secrets.write_text(
        "SUPABASE_URL=https://file.supabase.co\nSUPABASE_SERVICE_KEY=sk-file\n"
    )
    monkeypatch.setattr(store, "SECRETS_PATH", secrets)
    assert store._env() == ("https://env.supabase.co", "sk-env")


def test_verify_reports_missing_credentials(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    res = store.verify()
    assert res["ok"] is False
    assert res["checks"][0][0] == "credentials"
    assert res["checks"][0][1] is False


def test_verify_probe_roundtrip(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "secret")
    calls = []

    def fake_requester(url, key, table, *, method="POST", body=None, query=""):
        calls.append((method, table, query))
        if method == "POST" and table == "benchmark_runs":
            return [{"id": "probe-1"}]
        return []

    res = store.verify(_requester=fake_requester)
    assert res["ok"] is True
    assert ("POST", "benchmark_samples", "") in calls
    assert ("DELETE", "benchmark_runs", "?id=eq.probe-1") in calls


def test_verify_fails_on_insert_error(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "secret")

    def fake_requester(url, key, table, *, method="POST", body=None, query=""):
        raise OSError("relation benchmark_runs does not exist")

    res = store.verify(_requester=fake_requester)
    assert res["ok"] is False
    assert any(name == "insert benchmark_runs" and not ok for name, ok, _ in res["checks"])

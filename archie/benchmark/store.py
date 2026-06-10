# archie/benchmark/store.py
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Default location of the gitignored credentials file (see secrets.env.example).
SECRETS_PATH = Path(".archie-bench/secrets.env")


def _load_secrets(path: Path | None = None):
    """Populate SUPABASE_* env vars from the secrets file when not already set.

    Template placeholders (REPLACE-WITH-...) are ignored so an unfilled copy
    behaves exactly like a missing file. Never overrides real env vars.
    """
    path = path or SECRETS_PATH  # module attr resolved at call time (testable)
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY") and value \
                and "REPLACE-WITH" not in value and not os.environ.get(key):
            os.environ[key] = value


def _env():
    _load_secrets()
    return os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY")


def _request(url, key, table, *, method="POST", body=None, query=""):
    req = urllib.request.Request(
        f"{url}/rest/v1/{table}{query}",
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else None


def _post(url, key, table, rows):
    return _request(url, key, table, body=rows)


def _write_offline(run_row, sample_rows, offline_path):
    path = Path(offline_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"run": run_row, "samples": sample_rows}, indent=2))
    return str(path)


def store_results(run_row, sample_rows, offline_path, _poster=None):
    url, key = _env()
    if not url or not key:
        return {"mode": "offline", "path": _write_offline(run_row, sample_rows, offline_path)}

    poster = _poster or _post
    try:
        created = poster(url, key, "benchmark_runs", [run_row])
        run_id = created[0]["id"]
        for r in sample_rows:
            r["run_id"] = run_id
        poster(url, key, "benchmark_samples", sample_rows)
        return {"mode": "online", "run_id": run_id}
    except Exception as e:  # never lose results over a storage error
        detail = getattr(e, "reason", None) or e
        if isinstance(e, urllib.error.HTTPError):
            try:
                detail = f"HTTP {e.code}: {e.read().decode('utf-8')[:200]}"
            except Exception:
                detail = f"HTTP {e.code}"
        print(f"  Supabase write failed ({detail}) — falling back to offline store.",
              file=sys.stderr)
        return {
            "mode": "offline-fallback",
            "error": str(detail),
            "path": _write_offline(run_row, sample_rows, offline_path),
        }


def verify(_requester=None):
    """Connection self-test for `python3 -m archie.benchmark verify`.

    Checks credentials, reachability, and that both tables accept a
    service-role insert (probe row inserted then deleted). Returns
    {"ok": bool, "checks": [(name, ok, detail), ...]}.
    """
    requester = _requester or _request
    checks = []

    url, key = _env()
    creds_ok = bool(url and key)
    if creds_ok:
        detail = url
    else:
        missing = [n for n, v in (("SUPABASE_URL", url), ("SUPABASE_SERVICE_KEY", key)) if not v]
        detail = f"{' + '.join(missing)} not set (env or .archie-bench/secrets.env)"
    checks.append(("credentials", creds_ok, detail))
    if not creds_ok:
        return {"ok": False, "checks": checks}

    probe_id = None
    try:
        created = requester(url, key, "benchmark_runs",
                            body=[{"name": "verify-probe", "repo_name": "verify"}])
        probe_id = created[0]["id"]
        checks.append(("insert benchmark_runs", True, probe_id))
    except Exception as e:
        checks.append(("insert benchmark_runs", False, str(e)))
        return {"ok": False, "checks": checks}

    try:
        requester(url, key, "benchmark_samples",
                  body=[{"run_id": probe_id, "arm": "control", "repetition": 0}])
        checks.append(("insert benchmark_samples", True, ""))
    except Exception as e:
        checks.append(("insert benchmark_samples", False, str(e)))

    try:
        # Cascade removes the probe sample with the run.
        requester(url, key, "benchmark_runs", method="DELETE", query=f"?id=eq.{probe_id}")
        checks.append(("cleanup probe", True, ""))
    except Exception as e:
        checks.append(("cleanup probe", False, f"delete probe {probe_id} manually: {e}"))

    return {"ok": all(ok for _, ok, _ in checks), "checks": checks}

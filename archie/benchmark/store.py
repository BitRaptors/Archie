# archie/benchmark/store.py
import json
import os
import urllib.request
from pathlib import Path


def _env():
    return os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY")


def _post(url, key, table, rows):
    data = json.dumps(rows).encode("utf-8")
    req = urllib.request.Request(
        f"{url}/rest/v1/{table}",
        data=data,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def store_results(run_row, sample_rows, offline_path, _poster=None):
    url, key = _env()
    if not url or not key:
        path = Path(offline_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"run": run_row, "samples": sample_rows}, indent=2))
        return {"mode": "offline", "path": str(path)}

    poster = _poster or _post
    created = poster(url, key, "benchmark_runs", [run_row])
    run_id = created[0]["id"]
    for r in sample_rows:
        r["run_id"] = run_id
    poster(url, key, "benchmark_samples", sample_rows)
    return {"mode": "online", "run_id": run_id}

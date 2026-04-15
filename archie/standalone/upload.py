#!/usr/bin/env python3
"""Archie share — upload blueprint bundle for sharing.

Run: python3 upload.py /path/to/project
Reads from .archie/: blueprint.json (required), health.json, scan.json, rules.json,
                     proposed_rules.json, scan_report.md (all optional).
Prints: shareable URL on success, warning on failure.

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

UPLOAD_URL = os.environ.get(
    "ARCHIE_UPLOAD_URL",
    "https://chlmyhkjnirrcrjdsvrc.supabase.co/functions/v1/upload",
)
PROD_VIEWER_URL = "https://archie-viewer.vercel.app"


def _detect_viewer_url() -> str:
    """Resolve the viewer host. Precedence:
    1. ARCHIE_VIEWER_URL env var (explicit override)
    2. Production default
    """
    override = os.environ.get("ARCHIE_VIEWER_URL")
    if override:
        return override.rstrip("/")

    return PROD_VIEWER_URL


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        return path.read_text()
    except OSError:
        return None


TOP_N_HIGH_CC = 20
TOP_N_DUPLICATES = 10


def _strip_scan_meta(scan: dict) -> dict:
    return {
        "total_files": len(scan.get("file_tree", [])),
        "frameworks": [
            {"name": s.get("name", ""), "version": s.get("version", "")}
            for s in (scan.get("framework_signals") or [])
        ],
        "frontend_ratio": scan.get("frontend_ratio", 0),
        "subprojects": [
            {"name": s.get("name", ""), "type": s.get("type", "")}
            for s in (scan.get("subprojects") or [])
        ],
        "dependency_count": len(scan.get("dependencies") or []),
    }


def _strip_health(health: dict) -> dict:
    functions = health.get("functions") or []
    # Rank by mass (cc*sqrt(sloc)) when present; fall back to cc for older
    # health.json that predates the mass field.
    top_cc = sorted(
        functions,
        key=lambda f: (f.get("mass") or f.get("cc", 0)),
        reverse=True,
    )[:TOP_N_HIGH_CC]

    duplicates = health.get("duplicates") or []
    top_dupes = sorted(duplicates, key=lambda d: d.get("lines", 0), reverse=True)[:TOP_N_DUPLICATES]

    return {
        "erosion": health.get("erosion"),
        "gini": health.get("gini"),
        "top20_share": health.get("top20_share"),
        "verbosity": health.get("verbosity"),
        "total_functions": health.get("total_functions"),
        "high_cc_functions": health.get("high_cc_functions"),
        "total_loc": health.get("total_loc"),
        "duplicate_lines": health.get("duplicate_lines"),
        "cc_distribution": health.get("cc_distribution"),
        "mass": health.get("mass"),
        "top_high_cc": [
            {
                "path": f.get("path"),
                "name": f.get("name"),
                "cc": f.get("cc"),
                "sloc": f.get("sloc"),
                "line": f.get("line"),
                "mass": f.get("mass"),
            }
            for f in top_cc
        ],
        "top_duplicates": [
            {
                "lines": d.get("lines"),
                "locations": d.get("locations") or d.get("files") or [],
            }
            for d in top_dupes
        ],
    }


def build_bundle(project_root: Path) -> dict:
    archie_dir = project_root / ".archie"

    blueprint = _read_json(archie_dir / "blueprint.json")
    if blueprint is None:
        print("Error: .archie/blueprint.json not found. Run /archie-scan first.", file=sys.stderr)
        sys.exit(1)

    bundle: dict = {"blueprint": blueprint}

    health = _read_json(archie_dir / "health.json")
    if health:
        bundle["health"] = _strip_health(health)
    else:
        history = _read_json(archie_dir / "health_history.json")
        if isinstance(history, list) and history:
            latest = history[-1]
            bundle["health"] = {
                "erosion": latest.get("erosion"),
                "gini": latest.get("gini"),
                "top20_share": latest.get("top20_share"),
                "verbosity": latest.get("verbosity"),
                "total_loc": latest.get("total_loc"),
                "total_functions": None,
                "high_cc_functions": None,
                "duplicate_lines": None,
                "top_high_cc": [],
                "top_duplicates": [],
                "_source": "history_fallback",
            }

    scan = _read_json(archie_dir / "scan.json")
    if scan:
        bundle["scan_meta"] = _strip_scan_meta(scan)

    rules = _read_json(archie_dir / "rules.json")
    if rules:
        bundle["rules_adopted"] = rules

    proposed = _read_json(archie_dir / "proposed_rules.json")
    if proposed:
        bundle["rules_proposed"] = proposed

    scan_report = _read_text(archie_dir / "scan_report.md")
    if scan_report:
        bundle["scan_report"] = scan_report

    return bundle


def upload(bundle: dict) -> str | None:
    data = json.dumps(bundle).encode("utf-8")

    req = urllib.request.Request(
        UPLOAD_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            token = result.get("token")
            if not token:
                return None
            return f"{_detect_viewer_url()}/r/{token}"
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"Upload failed (HTTP {e.code}): {body}", file=sys.stderr)
        return None
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        print(f"Upload failed: {e}", file=sys.stderr)
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 upload.py /path/to/project", file=sys.stderr)
        sys.exit(1)

    project_root = Path(sys.argv[1]).resolve()
    bundle = build_bundle(project_root)

    print("Uploading blueprint...", file=sys.stderr)
    url = upload(bundle)

    if url:
        print(f"\nShareable URL: {url}", file=sys.stderr)
        print(url)
    else:
        print("\nUpload failed. Your blueprint is still at .archie/blueprint.json", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

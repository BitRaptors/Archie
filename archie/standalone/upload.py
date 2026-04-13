#!/usr/bin/env python3
"""Archie share — upload blueprint bundle for sharing.

Run: python3 upload.py /path/to/project
Reads: .archie/blueprint.json, .archie/health.json (optional), .archie/scan.json (optional),
       .archie/rules.json (optional), .archie/proposed_rules.json (optional)
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


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


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
    return {
        "erosion": health.get("erosion"),
        "gini": health.get("gini"),
        "top20_share": health.get("top20_share"),
        "verbosity": health.get("verbosity"),
        "total_functions": health.get("total_functions"),
        "high_cc_functions": health.get("high_cc_functions"),
        "total_loc": health.get("total_loc"),
        "duplicate_lines": health.get("duplicate_lines"),
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

    scan = _read_json(archie_dir / "scan.json")
    if scan:
        bundle["scan_meta"] = _strip_scan_meta(scan)

    rules = _read_json(archie_dir / "rules.json")
    if rules:
        bundle["rules_adopted"] = rules

    proposed = _read_json(archie_dir / "proposed_rules.json")
    if proposed:
        bundle["rules_proposed"] = proposed

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
            return result.get("url")
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

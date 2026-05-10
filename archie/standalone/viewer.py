#!/usr/bin/env python3
"""Archie local viewer — serves the share/viewer/ React app + /api/bundle.

Run: python3 viewer.py /path/to/repo [--port PORT] [--no-open] [--api-only]

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import argparse
import http.server
import json
import socket
import sys
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from upload import build_bundle  # noqa: E402

DEFAULT_PORT = 5847

# Directory names skipped when scanning the project tree. Shared by
# /api/generated-files and (later) the folder CLAUDE.md browser endpoint —
# kept at module scope so both endpoints stay in sync.
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".archie", "venv",
              ".venv", "dist", "build", ".next", ".nuxt", "coverage",
              ".pytest_cache", ".mypy_cache"}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return ""


def _collect_generated_files(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for name in ("CLAUDE.md", "AGENTS.md"):
        p = root / name
        if p.exists():
            files[name] = _read_text(p)
    rules_dir = root / ".claude" / "rules"
    if rules_dir.is_dir():
        for f in sorted(rules_dir.rglob("*")):
            if f.is_file():
                files[str(f.relative_to(root))] = _read_text(f)
    return files


def _collect_folder_claude_mds(root: Path) -> dict[str, str]:
    result = {}
    for claude_md in root.rglob("CLAUDE.md"):
        if any(part in _SKIP_DIRS for part in claude_md.parts):
            continue
        rel = str(claude_md.relative_to(root))
        if rel == "CLAUDE.md":
            continue  # root CLAUDE.md is in /api/generated-files
        result[rel] = _read_text(claude_md)
    return result


def _intent_layer_status(root: Path) -> dict:
    folders = _collect_folder_claude_mds(root)
    count = len(folders)
    state_path = root / ".archie" / "intent_layer_state.json"
    marker_exists = False
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
            processed = state.get("processed", [])
            marker_exists = isinstance(processed, list) and len(processed) > 0
        except (json.JSONDecodeError, OSError):
            pass
    return {"exists": count > 0 or marker_exists, "count": count}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _port_available(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", port))
        return True
    except OSError:
        return False


def _make_handler(root: Path, dist_dir: Path | None):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(dist_dir) if dist_dir else None, **kwargs)

        def log_message(self, fmt, *args):  # quiet by default
            pass

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/api/bundle":
                self._serve_bundle(root)
                return
            if parsed.path == "/api/generated-files":
                self._serve_json(_collect_generated_files(root))
                return
            if parsed.path == "/api/intent-layer-status":
                self._serve_json(_intent_layer_status(root))
                return
            if parsed.path == "/api/folder-claude-mds":
                self._serve_json(_collect_folder_claude_mds(root))
                return
            # Unknown /api/* paths must 404 — never fall through to the SPA so
            # client fetches see a real error instead of HTML masquerading as JSON.
            if parsed.path.startswith("/api/"):
                self._send_error(404, "Not found")
                return
            if dist_dir is None:
                self._send_error(404, "Static disabled (--api-only)")
                return
            # SPA fallback: rewrite unknown non-asset paths to index.html
            if "." not in Path(parsed.path).name and parsed.path != "/":
                self.path = "/index.html"
            super().do_GET()

        def _serve_bundle(self, root: Path):
            try:
                bundle = build_bundle(root)
            except SystemExit:
                self._send_error(404, "blueprint.json missing")
                return
            except Exception as e:  # malformed blueprint.json, IO errors, etc.
                self._send_error(500, f"build_bundle failed: {e}")
                return
            # Wrap in the canonical ReportResponse envelope so LocalPage.tsx can
            # consume the same shape as CoverPage.tsx / ReportPage.tsx (defined
            # by share/viewer/src/lib/api.ts). created_at mirrors the scan
            # timestamp from blueprint.meta.scanned_at — same field
            # upload._build_enterprise_bundle uses — so the viewer renders a
            # real date instead of "Invalid Date".
            created_at = ""
            if isinstance(bundle, dict):
                blueprint = bundle.get("blueprint")
                if isinstance(blueprint, dict):
                    meta = blueprint.get("meta")
                    if isinstance(meta, dict):
                        scanned_at = meta.get("scanned_at")
                        if isinstance(scanned_at, str):
                            created_at = scanned_at
            self._serve_json({"bundle": bundle, "created_at": created_at})

        def _serve_json(self, data):
            body = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_error(self, code: int, msg: str):
            body = json.dumps({"error": msg}).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def build_app(root: Path, *, port: int = 0, api_only: bool = False) -> http.server.ThreadingHTTPServer:
    # If api_only is set, never serve static files. Otherwise, serve the
    # React dist/ if it exists; if it does not, fall through to API-only mode
    # silently — main() is responsible for the user-facing dist preflight so
    # build_app stays testable without a real dist build.
    candidate_dist = root / ".archie" / "viewer" / "dist"
    if api_only or not (candidate_dist / "index.html").exists():
        dist_dir = None
    else:
        dist_dir = candidate_dist
    handler = _make_handler(root, dist_dir)
    return http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)


def _summarize(root: Path) -> str:
    archie = root / ".archie"
    bp = archie / "blueprint.json"
    findings = archie / "findings.json"
    rules = archie / "rules.json"
    parts = []
    if bp.exists():
        parts.append("1 blueprint")
    try:
        f_data = json.loads(findings.read_text())
        # findings.json may be either {"findings": [...]} or a bare list
        items = f_data.get("findings", []) if isinstance(f_data, dict) else f_data
        if isinstance(items, list):
            active = [x for x in items if isinstance(x, dict) and x.get("status", "active") == "active"]
            parts.append(f"{len(active)} findings")
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    try:
        r_data = json.loads(rules.read_text())
        rule_list = r_data.get("rules", []) if isinstance(r_data, dict) else r_data
        if isinstance(rule_list, list):
            parts.append(f"{len(rule_list)} rules adopted")
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return ", ".join(parts) if parts else "no data yet"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archie local viewer.")
    parser.add_argument("project_root", help="Path to the project to inspect")
    parser.add_argument("--port", type=int, default=None, help="Port (default 5847, falls back to free)")
    parser.add_argument("--no-open", action="store_true", help="Do not auto-open the browser")
    parser.add_argument("--api-only", action="store_true", help="Serve only /api/bundle (no static)")
    args = parser.parse_args(argv)

    root = Path(args.project_root).resolve()
    bp = root / ".archie" / "blueprint.json"
    if not bp.exists():
        print(
            "Error: .archie/blueprint.json not found. "
            "Run /archie-scan or /archie-deep-scan first.",
            file=sys.stderr,
        )
        return 1

    if not args.api_only:
        dist_index = root / ".archie" / "viewer" / "dist" / "index.html"
        if not dist_index.exists():
            print(
                "Error: .archie/viewer/dist/ not found. "
                "Run `npx @bitraptors/archie` to set up the viewer.",
                file=sys.stderr,
            )
            return 1

    if args.port is not None:
        port = args.port
    else:
        port = DEFAULT_PORT if _port_available(DEFAULT_PORT) else _free_port()

    server = build_app(root, port=port, api_only=args.api_only)
    print("Starting Archie viewer…")
    print(f"Bundle: {_summarize(root)}")
    url = f"http://localhost:{port}/local"
    print(f"Listening on http://localhost:{port}")
    if not args.no_open and not args.api_only:
        try:
            webbrowser.open(url)
            print("Opening browser…")
        except Exception:
            pass
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Archie blueprint viewer — zero-dep local HTML inspector.

Run: python3 viewer.py /path/to/repo [--port PORT]
Opens a browser showing only Archie-generated output.

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import http.server
import json
import re
import socket
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent))
from _common import _load_json  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".archie", "venv",
              ".venv", "dist", "build", ".next", ".nuxt", "coverage",
              ".pytest_cache", ".mypy_cache"}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return ""


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _collect_folder_claude_mds(root: Path) -> dict[str, str]:
    result = {}
    for claude_md in root.rglob("CLAUDE.md"):
        if any(part in _SKIP_DIRS for part in claude_md.parts):
            continue
        rel = str(claude_md.relative_to(root))
        if rel == "CLAUDE.md":
            continue  # skip root — shown in generated-files tab
        result[rel] = _read_text(claude_md)
    return result


def _collect_generated_files(root: Path) -> dict[str, str]:
    """Collect only files that Archie generated."""
    files: dict[str, str] = {}
    # Root output files
    for name in ("CLAUDE.md", "AGENTS.md"):
        p = root / name
        if p.exists():
            files[name] = _read_text(p)
    # Rule files
    rules_dir = root / ".claude" / "rules"
    if rules_dir.is_dir():
        for f in sorted(rules_dir.rglob("*")):
            if f.is_file():
                files[str(f.relative_to(root))] = _read_text(f)
    return files


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

class ArchieHandler(http.server.BaseHTTPRequestHandler):
    """Routes requests to API endpoints or serves the HTML page."""

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        root: Path = self.server.root  # type: ignore[attr-defined]
        archie_dir = root / ".archie"

        if path == "/api/blueprint":
            self._send_json(_load_json(archie_dir / "blueprint.json"))

        elif path == "/api/rules":
            self._send_json(_load_json(archie_dir / "rules.json"))

        elif path == "/api/health":
            # Read full health data saved by scan/deep-scan
            data = _load_json(archie_dir / "health.json")
            if not data:
                # Fallback to history summary (no functions/waste detail)
                history = _load_json(archie_dir / "health_history.json")
                # Handle both formats: plain list or {"history": [...]}
                if isinstance(history, dict):
                    history = history.get("history", [])
                if isinstance(history, list) and history:
                    data = history[-1]
            self._send_json(data or {})

        elif path == "/api/health-history":
            data = _load_json(archie_dir / "health_history.json")
            # Handle both formats: plain list or {"history": [...]}
            if isinstance(data, dict):
                data = data.get("history", [])
            if not isinstance(data, list):
                data = []
            self._send_json(data)

        elif path == "/api/scan-reports":
            reports = []
            if archie_dir.is_dir():
                # Primary: scan_history/ directory (one file per scan)
                history_dir = archie_dir / "scan_history"
                if history_dir.is_dir():
                    for f in sorted(history_dir.glob("*.md"), reverse=True):
                        name = f"scan_history/{f.name}"
                        # New format: scan_NNN_YYYY-MM-DDTHHMM.md
                        m = re.search(r"(\d{4}-\d{2}-\d{2})T(\d{2})(\d{2})", f.name)
                        if m:
                            date_str = f"{m.group(1)} {m.group(2)}:{m.group(3)} UTC"
                        else:
                            # Old format: scan_NNN_YYYY-MM-DD.md
                            m = re.search(r"(\d{4}-\d{2}-\d{2})", f.name)
                            date_str = m.group(1) if m else ""
                        reports.append({"filename": name, "date": date_str})
                # Legacy: scan_report_*.md in .archie/ (older format)
                if not reports:
                    for f in sorted(archie_dir.glob("scan_report_*.md"), reverse=True):
                        name = f.name
                        m = re.search(r"scan_report_(\d{4}-\d{2}-\d{2})\.md$", name)
                        date_str = m.group(1) if m else ""
                        reports.append({"filename": name, "date": date_str})
                # Fallback: scan_report.md (no history dir, no dated files)
                if not reports:
                    sr = archie_dir / "scan_report.md"
                    if sr.exists():
                        content = _read_text(sr)
                        dm = re.search(r"(\d{4}-\d{2}-\d{2})", content)
                        date_str = dm.group(1) if dm else ""
                        reports.append({"filename": "scan_report.md", "date": date_str})
            self._send_json(reports)

        elif path.startswith("/api/scan-report/"):
            filename = path[len("/api/scan-report/"):]
            # Validate filename to prevent path traversal
            if not re.match(r"^(scan_history/)?scan[\w_\-]*\.md$", filename) or ".." in filename or "\\" in filename:
                self._send_error(400, "Invalid filename")
                return
            report_path = archie_dir / filename
            if not report_path.exists():
                self._send_error(404, "Report not found")
                return
            content = _read_text(report_path)
            self._send_json({"filename": filename, "content": content})

        elif path == "/api/drift":
            self._send_json(_load_json(archie_dir / "drift_report.json"))

        elif path == "/api/generated-files":
            self._send_json(_collect_generated_files(root))

        elif path == "/api/folder-claude-mds":
            self._send_json(_collect_folder_claude_mds(root))

        elif path == "/api/ignored-rules":
            self._send_json(_load_json(archie_dir / "ignored_rules.json"))

        elif path == "/api/proposed-rules":
            self._send_json(_load_json(archie_dir / "proposed_rules.json"))

        elif path == "/api/dependency-graph":
            self._send_json(_load_json(archie_dir / "dependency_graph.json"))

        else:
            # Static file serving (React dist) with SPA fallback
            self._serve_static(path)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        root: Path = self.server.root  # type: ignore[attr-defined]

        if path == "/api/rules":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                data = json.loads(body)
            except (ValueError, json.JSONDecodeError):
                self._send_error(400, "Invalid JSON")
                return

            if not isinstance(data, dict) or "rules" not in data or not isinstance(data["rules"], list):
                self._send_error(400, "Body must have a 'rules' key with an array value")
                return

            rules_path = root / ".archie" / "rules.json"
            rules_path.parent.mkdir(parents=True, exist_ok=True)
            rules_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            self._send_json({"ok": True})

        elif path == "/api/share":
            try:
                upload_script = Path(__file__).parent / "upload.py"
                if not upload_script.exists():
                    self._send_error(500, "upload.py not found")
                    return

                import importlib.util
                spec = importlib.util.spec_from_file_location("upload", str(upload_script))
                upload_mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(upload_mod)

                bundle = upload_mod.build_bundle(root)
                result = upload_mod.upload(bundle)
                self._send_json({"ok": True, "url": result})
            except Exception as e:
                self._send_error(500, str(e))
        else:
            self._send_error(404, "Not found")

    def _send_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
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

    def _serve_static(self, url_path: str):
        """Serve files from viewer_dist/, falling back to index.html for SPA routing."""
        dist_dir: Path = self.server.dist_dir  # type: ignore

        if url_path == "/" or url_path == "":
            file_path = dist_dir / "index.html"
        else:
            relative = url_path.lstrip("/")
            file_path = dist_dir / relative

        try:
            file_path = file_path.resolve()
            if not str(file_path).startswith(str(dist_dir.resolve())):
                self._send_error(403, "Forbidden")
                return
        except (ValueError, OSError):
            self._send_error(400, "Bad path")
            return

        if not file_path.is_file():
            file_path = dist_dir / "index.html"

        if not file_path.is_file():
            self._send_error(404, "Viewer dist not found. Run: cd share/viewer && npm run build")
            return

        content = file_path.read_bytes()
        content_type = self._guess_type(file_path.name)

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        if "/assets/" in url_path:
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.end_headers()
        self.wfile.write(content)

    @staticmethod
    def _guess_type(filename: str) -> str:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return {
            "html": "text/html; charset=utf-8",
            "js": "application/javascript; charset=utf-8",
            "css": "text/css; charset=utf-8",
            "json": "application/json; charset=utf-8",
            "svg": "image/svg+xml",
            "png": "image/png",
            "ico": "image/x-icon",
            "woff": "font/woff",
            "woff2": "font/woff2",
        }.get(ext, "application/octet-stream")


# ---------------------------------------------------------------------------
# HTML_PAGE removed — viewer now serves pre-built React dist from viewer_dist/
# ---------------------------------------------------------------------------

HTML_PAGE = None  # Removed — viewer now serves pre-built React dist from viewer_dist/

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 viewer.py /path/to/repo [--port PORT]", file=sys.stderr)
        sys.exit(1)

    root = Path(sys.argv[1]).resolve()
    if not root.is_dir():
        print(f"Error: {root} is not a directory", file=sys.stderr)
        sys.exit(1)

    port = None
    for i, arg in enumerate(sys.argv[2:], 2):
        if arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
            break

    if port is None:
        port = _find_free_port()

    try:
        server = http.server.HTTPServer(("localhost", port), ArchieHandler)
    except OSError as e:
        print(f"Error: Could not start server on port {port} ({e})", file=sys.stderr)
        print("Try a different port: python3 viewer.py /path/to/repo --port 8888", file=sys.stderr)
        sys.exit(1)
    server.root = root  # type: ignore[attr-defined]
    server.dist_dir = Path(__file__).parent / "viewer_dist"  # type: ignore

    url = f"http://localhost:{port}"
    print(f"Archie Viewer: {url}", file=sys.stderr)
    print(f"Project: {root}", file=sys.stderr)
    print("Press Ctrl+C to stop.", file=sys.stderr)

    threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        server.shutdown()

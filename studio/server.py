#!/usr/bin/env python3
"""Archie Studio — local 3-tab app: PRD reader + embedded archie-viewer.

Run: python3 studio/server.py /path/to/project [--prd docs/prd] [--port 5848] [--no-open]

Zero dependencies beyond Python 3.9+ stdlib. Internal experiment — lives only
in the Archie repo, never shipped via npm. Inherits all viewer API endpoints
by subclassing the handler from archie/standalone/viewer.py.
"""
from __future__ import annotations

import argparse
import http.server
import json
import sys
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "archie" / "standalone"))
import viewer  # noqa: E402

DEFAULT_PORT = 5848  # viewer uses 5847; keep both runnable side by side
DIST_DIR = Path(__file__).resolve().parent / "frontend" / "dist"
PRD_DEFAULT_CANDIDATES = ("docs/prd", "prd")


def resolve_prd_root(root: Path, prd_arg: str | None) -> Path | None:
    if prd_arg:
        candidate = (root / prd_arg).resolve()
        return candidate if candidate.is_dir() else None
    for rel in PRD_DEFAULT_CANDIDATES:
        candidate = root / rel
        if candidate.is_dir():
            return candidate.resolve()
    return None


def build_prd_tree(prd_root: Path) -> list[dict]:
    def walk(d: Path) -> list[dict]:
        entries = []
        for child in sorted(d.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            if child.name.startswith("."):
                continue  # .obsidian, .trash, etc.
            if child.is_symlink():
                continue  # cycles would ELOOP; linked .md would 404 on fetch
            if child.is_dir():
                children = walk(child)
                if children:
                    entries.append({
                        "type": "dir", "name": child.name,
                        "path": str(child.relative_to(prd_root)),
                        "children": children,
                    })
            elif child.suffix.lower() == ".md":
                entries.append({
                    "type": "file", "name": child.name,
                    "path": str(child.relative_to(prd_root)),
                })
        return entries
    return walk(prd_root)


def read_prd_file(prd_root: Path, rel: str) -> str | None:
    """Content of a .md file under prd_root, or None (missing/outside/non-md)."""
    prd_root = prd_root.resolve()  # guard fails spuriously on unresolved paths
    try:
        # resolve() inside the guard: pathological names (embedded null bytes)
        # raise ValueError there too, not just in relative_to.
        target = (prd_root / rel).resolve()
        target.relative_to(prd_root)
    except ValueError:
        return None  # traversal outside the PRD root, or unresolvable name
    if target.suffix.lower() != ".md" or not target.is_file():
        return None
    try:
        return target.read_text(errors="replace")
    except OSError:
        return None  # permission denied / vanished between check and read


class _FsError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _list_dirs(path_param: str) -> dict:
    """Directory listing for the project picker: subdirs of path_param (or $HOME)."""
    base = Path(path_param).expanduser() if path_param else Path.home()
    try:
        base = base.resolve()
    except (ValueError, OSError):
        raise _FsError("Invalid path", 400)
    if not base.is_dir():
        raise _FsError(f"Not a directory: {base}", 404)
    try:
        children = sorted(base.iterdir(), key=lambda p: p.name.lower())
    except PermissionError:
        raise _FsError(f"Permission denied: {base}", 403)
    dirs = []
    for child in children:
        if child.name.startswith("."):
            continue
        try:
            if not child.is_dir():
                continue
            dirs.append({
                "name": child.name,
                "path": str(child),
                "has_archie": (child / ".archie").is_dir(),
                "has_prd": any((child / rel).is_dir() for rel in PRD_DEFAULT_CANDIDATES),
            })
        except OSError:
            continue  # unreadable entry — skip, keep the rest of the listing
    parent = str(base.parent) if base.parent != base else None
    return {"path": str(base), "parent": parent, "dirs": dirs}


def _project_info(state: dict) -> dict:
    root = state["root"]
    prd_root = state["prd_root"]
    return {
        "root": str(root) if root else None,
        "prd_root": str(prd_root) if prd_root else None,
        "name": root.name if root else None,
    }


def _set_project(server: http.server.ThreadingHTTPServer, root: Path) -> None:
    """Swap the live handler class to serve a newly selected project.

    ThreadingHTTPServer instantiates RequestHandlerClass per request, so
    replacing the class takes effect on the next request — no restart needed.
    """
    prd_root = resolve_prd_root(root, server.studio_prd_arg)
    server.studio_state = {"root": root, "prd_root": prd_root}
    server.RequestHandlerClass = _make_studio_handler(root, prd_root, server.studio_dist_dir)


def _make_studio_handler(root: Path | None, prd_root: Path | None, dist_dir: Path | None):
    # Base needs a Path even in picker mode (no project yet); a nonexistent
    # placeholder is safe because do_GET/do_POST below intercept every /api/*
    # before the viewer handlers can touch it.
    Base = viewer._make_handler(root if root is not None else Path("/archie-studio-no-project"), dist_dir)

    class StudioHandler(Base):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/api/project":
                self._serve_json(_project_info(self.server.studio_state))
                return
            if parsed.path == "/api/fs/list":
                path_param = (parse_qs(parsed.query).get("path") or [""])[0]
                try:
                    self._serve_json(_list_dirs(path_param))
                except _FsError as e:
                    self._send_error(e.status_code, str(e))
                return
            if root is None and parsed.path.startswith("/api/"):
                self._send_error(404, "No project selected")
                return
            if parsed.path == "/api/prd/tree":
                if prd_root is None:
                    self._serve_json({"prd_root": None, "tree": []})
                else:
                    self._serve_json({"prd_root": str(prd_root),
                                      "tree": build_prd_tree(prd_root)})
                return
            if parsed.path == "/api/prd/file":
                if prd_root is None:
                    self._send_error(404, "No PRD folder configured")
                    return
                rel = (parse_qs(parsed.query).get("path") or [""])[0]
                if not rel:
                    self._send_error(400, "Missing ?path= query parameter")
                    return
                content = read_prd_file(prd_root, rel)
                if content is None:
                    self._send_error(404, "PRD file not found: " + rel)
                    return
                self._serve_json({"path": rel, "content": content})
                return
            super().do_GET()

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path == "/api/project":
                try:
                    length = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(length))
                except (ValueError, json.JSONDecodeError):
                    self._send_error(400, "Invalid JSON body")
                    return
                raw = body.get("path") if isinstance(body, dict) else None
                if not isinstance(raw, str) or not raw.strip():
                    self._send_error(400, "path must be a non-empty string")
                    return
                try:
                    new_root = Path(raw).expanduser().resolve()
                except (ValueError, OSError):
                    self._send_error(400, "Invalid path")
                    return
                if not new_root.is_dir():
                    self._send_error(404, f"Not a directory: {new_root}")
                    return
                _set_project(self.server, new_root)
                self._serve_json(_project_info(self.server.studio_state))
                return
            if root is None:
                self._send_error(404, "No project selected")
                return
            super().do_POST()

    return StudioHandler


def build_studio_app(root: Path | None, prd_root: Path | None, *, port: int = 0,
                     dist_dir: Path | None = None,
                     prd_arg: str | None = None) -> http.server.ThreadingHTTPServer:
    if dist_dir is not None and not (dist_dir / "index.html").exists():
        dist_dir = None  # API-only; main() owns the user-facing preflight
    handler = _make_studio_handler(root, prd_root, dist_dir)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    server.studio_state = {"root": root, "prd_root": prd_root}
    server.studio_dist_dir = dist_dir
    server.studio_prd_arg = prd_arg
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archie Studio local app.")
    parser.add_argument("project_root", nargs="?", default=None,
                        help="Path to the project to open (omit to pick a "
                             "folder in the browser)")
    parser.add_argument("--prd", default=None,
                        help="PRD folder relative to the project root "
                             "(default: docs/prd, then prd)")
    parser.add_argument("--port", type=int, default=None,
                        help=f"Port (default {DEFAULT_PORT}, falls back to free)")
    parser.add_argument("--no-open", action="store_true",
                        help="Do not auto-open the browser")
    args = parser.parse_args(argv)

    root = None
    prd_root = None
    if args.project_root is not None:
        root = Path(args.project_root).resolve()
        if not root.is_dir():
            print(f"Error: not a directory: {root}", file=sys.stderr)
            return 1
        prd_root = resolve_prd_root(root, args.prd)
        if prd_root is None:
            where = args.prd or " or ".join(PRD_DEFAULT_CANDIDATES)
            print(f"Note: no PRD folder found ({where}). The Product tab will "
                  "show an empty state.", file=sys.stderr)

    if not (DIST_DIR / "index.html").exists():
        print("Error: studio/frontend/dist/ not found. "
              "Build it first: cd studio/frontend && npm install && npm run build",
              file=sys.stderr)
        return 1

    if args.port is not None:
        port = args.port
    elif viewer._port_available(DEFAULT_PORT):
        port = DEFAULT_PORT
    else:
        port = viewer._free_port()

    server = build_studio_app(root, prd_root, port=port, dist_dir=DIST_DIR,
                              prd_arg=args.prd)
    print("Starting Archie Studio…")
    if root is None:
        print("Project: (none — pick a folder in the browser)")
    else:
        print(f"Project: {root}")
        print(f"PRD folder: {prd_root if prd_root else '(none found)'}")
    url = f"http://localhost:{port}/"
    print(f"Listening on {url}")
    if not args.no_open:
        try:
            webbrowser.open(url)
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

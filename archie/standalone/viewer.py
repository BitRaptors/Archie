#!/usr/bin/env python3
"""Archie local viewer — serves the share/viewer/ React app + /api/bundle.

Run: python3 viewer.py /path/to/repo [--port PORT] [--no-open] [--api-only]

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import argparse
import http.server
import json
import os
import socket
import subprocess
import sys
import threading
import time
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


def _collect_exposure_data(root: Path) -> dict:
    """Per-file visibility state for the viewer. Repo mode -> empty/inert.

    Lists only the gateable generated MARKDOWN (intent-layer per-folder CLAUDE.md
    and blueprint .claude/rules/*.md), grouped by category. Infrastructure
    (.archie) is excluded — it is never gated.
    """
    import linker
    import link_store
    st = linker.status(root)
    out = {"mode": st["mode"], "categories": {}, "overrides": {}, "placements": []}
    if st["mode"] != "detached" or not st.get("store"):
        return out
    store = Path(st["store"])
    exposure = link_store.read_exposure(store)
    out["categories"] = exposure.get("categories", {})
    out["overrides"] = exposure.get("overrides", {})
    for p in st["placements"]:
        category = p.get("category") or linker._category_of(p["path"])
        if category == "infrastructure":
            continue
        out["placements"].append({
            "path": p["path"], "kind": p["kind"], "exposed": p["exposed"],
            "category": category,
        })
    return out


def _apply_exposure_action(root: Path, body: dict) -> dict:
    """Toggle a category or per-path override, then reconcile the working tree."""
    import linker
    import link_store
    st = linker.status(root)
    if st["mode"] != "detached" or not st.get("store"):
        return {"mode": st["mode"], "categories": {}, "overrides": {}, "placements": []}
    store = Path(st["store"])
    exposure = link_store.read_exposure(store)
    target = body.get("target")
    key = body.get("key")
    value = bool(body.get("value"))
    if target == "category" and key in exposure.get("categories", {}):
        exposure["categories"][key] = value
    elif target == "path" and isinstance(key, str):
        exposure.setdefault("overrides", {})[key] = value
    else:
        raise ValueError("invalid exposure target/key")
    link_store.write_exposure(store, exposure)
    linker.reconcile(root)
    return _collect_exposure_data(root)


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


ALLOWED_SEVERITY_CLASSES = {
    "decision_violation", "pitfall_triggered", "tradeoff_undermined",
    "pattern_divergence", "mechanical_violation",
}


class _RuleActionError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _read_rules_file(path: Path) -> dict:
    if not path.exists():
        return {"rules": []}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {"rules": []}
    if isinstance(data, dict):
        return data
    return {"rules": data if isinstance(data, list) else []}


def _atomic_write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    os.replace(tmp, path)


def _spawn_subprocess_silent(argv: list[str]) -> None:
    try:
        subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, FileNotFoundError):
        pass


def _apply_rule_action(root: Path, action: str, rule_id: str, patch: dict) -> None:
    archie = root / ".archie"
    rules_path = archie / "rules.json"
    proposed_path = archie / "proposed_rules.json"
    ignored_path = archie / "ignored_rules.json"

    def find_and_pop(data: dict, rid: str):
        rules = data.get("rules", [])
        for i, r in enumerate(rules):
            if r.get("id") == rid:
                return rules.pop(i)
        return None

    if action == "adopt":
        proposed = _read_rules_file(proposed_path)
        rule = find_and_pop(proposed, rule_id)
        if rule is None:
            raise _RuleActionError(f"rule_id {rule_id} not in proposed_rules.json", 409)
        rule["source"] = "scan-adopted"
        rules = _read_rules_file(rules_path)
        rules.setdefault("rules", []).append(rule)
        _atomic_write_json(rules_path, rules)
        _atomic_write_json(proposed_path, proposed)
    elif action == "reject":
        proposed = _read_rules_file(proposed_path)
        rule = find_and_pop(proposed, rule_id)
        if rule is None:
            raise _RuleActionError(f"rule_id {rule_id} not in proposed_rules.json", 409)
        ignored = _read_rules_file(ignored_path)
        ignored.setdefault("rules", []).append(rule)
        _atomic_write_json(ignored_path, ignored)
        _atomic_write_json(proposed_path, proposed)
    elif action == "disable":
        rules = _read_rules_file(rules_path)
        rule = find_and_pop(rules, rule_id)
        if rule is None:
            raise _RuleActionError(f"rule_id {rule_id} not in rules.json", 409)
        ignored = _read_rules_file(ignored_path)
        ignored.setdefault("rules", []).append(rule)
        _atomic_write_json(ignored_path, ignored)
        _atomic_write_json(rules_path, rules)
    elif action == "enable":
        ignored = _read_rules_file(ignored_path)
        rule = find_and_pop(ignored, rule_id)
        if rule is None:
            raise _RuleActionError(f"rule_id {rule_id} not in ignored_rules.json", 409)
        rules = _read_rules_file(rules_path)
        rules.setdefault("rules", []).append(rule)
        _atomic_write_json(rules_path, rules)
        _atomic_write_json(ignored_path, ignored)
    elif action == "edit":
        if not isinstance(patch, dict):
            raise _RuleActionError("patch must be an object", 400)
        if "severity_class" in patch and patch["severity_class"] not in ALLOWED_SEVERITY_CLASSES:
            raise _RuleActionError(
                f"invalid severity_class — allowed: {sorted(ALLOWED_SEVERITY_CLASSES)}", 400,
            )
        for path in (rules_path, ignored_path):
            data = _read_rules_file(path)
            for rule in data.get("rules", []):
                if rule.get("id") == rule_id:
                    for key in ("description", "why", "example", "severity_class"):
                        if key in patch and isinstance(patch[key], str):
                            rule[key] = patch[key]
                    _atomic_write_json(path, data)
                    return
        raise _RuleActionError(f"rule_id {rule_id} not found in rules or ignored", 404)


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
            if parsed.path == "/api/ignored-rules":
                self._serve_json(_read_rules_file(root / ".archie" / "ignored_rules.json"))
                return
            if parsed.path == "/api/exposure":
                self._serve_json(_collect_exposure_data(root))
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

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path not in ("/api/rules", "/api/exposure"):
                self._send_error(404, "Not found")
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                body = json.loads(raw)
            except (ValueError, json.JSONDecodeError):
                self._send_error(400, "Invalid JSON body")
                return
            if parsed.path == "/api/exposure":
                try:
                    self._serve_json(_apply_exposure_action(root, body))
                except ValueError as e:
                    self._send_error(400, str(e))
                except Exception as e:
                    self._send_error(500, f"Exposure update failed: {e}")
                return
            action = body.get("action")
            rule_id = body.get("rule_id")
            if action not in {"adopt", "reject", "disable", "enable", "edit"}:
                self._send_error(400, f"Unknown action: {action}")
                return
            if not isinstance(rule_id, str):
                self._send_error(400, "rule_id must be a string")
                return
            try:
                _apply_rule_action(root, action, rule_id, body.get("patch") or {})
            except _RuleActionError as e:
                self._send_error(e.status_code, str(e))
                return
            except Exception as e:
                self._send_error(500, f"Rule action failed: {e}")
                return
            _spawn_subprocess_silent(["python3", str(root / ".archie" / "rule_index.py"), "build", str(root)])
            _spawn_subprocess_silent(["python3", str(root / ".archie" / "renderer.py"), str(root)])
            self._serve_json({"ok": True})

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


def _start_reload_watcher(watch_dir: Path, poll_seconds: float = 1.0) -> None:
    """Background thread: re-exec the process when any .py in watch_dir changes.

    Solves a real trap: `npx @bitraptors/archie` replaces viewer.py on disk while
    a long-running Python process keeps the old code in memory, leading to
    silent API-version mismatches (V2 endpoints returning 404 even though the
    new viewer.py has them). Polling-only watcher — zero deps, ~25 stat calls
    per second is negligible. os.execv replaces the current process with a
    fresh interpreter; the same listening port is freed and rebound on restart.
    """
    try:
        initial = {p.name: p.stat().st_mtime for p in watch_dir.glob("*.py")}
    except OSError:
        return  # watch_dir gone — skip silently

    def watcher() -> None:
        nonlocal initial
        while True:
            time.sleep(poll_seconds)
            try:
                current = {p.name: p.stat().st_mtime for p in watch_dir.glob("*.py")}
            except OSError:
                continue
            changed = [n for n, m in current.items() if initial.get(n) != m]
            added = [n for n in current if n not in initial]
            removed = [n for n in initial if n not in current]
            if not (changed or added or removed):
                continue
            tags = changed + [f"+{n}" for n in added] + [f"-{n}" for n in removed]
            print(f"[reload] {', '.join(tags)} changed — restarting…", file=sys.stderr)
            try:
                os.execv(sys.executable, [sys.executable, *sys.argv])
            except OSError as e:
                print(f"[reload] os.execv failed: {e}", file=sys.stderr)
                initial = current  # avoid infinite retry storm

    t = threading.Thread(target=watcher, daemon=True, name="archie-reload")
    t.start()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archie local viewer.")
    parser.add_argument("project_root", help="Path to the project to inspect")
    parser.add_argument("--port", type=int, default=None, help="Port (default 5847, falls back to free)")
    parser.add_argument("--no-open", action="store_true", help="Do not auto-open the browser")
    parser.add_argument("--api-only", action="store_true", help="Serve only /api/bundle (no static)")
    parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload watcher (default: on)")
    args = parser.parse_args(argv)

    root = Path(args.project_root).resolve()
    # Don't preflight blueprint.json — the React app shows a friendly
    # empty-state when /api/bundle returns 404. Forcing the user to run a
    # scan BEFORE they can open the viewer chrome was a hostile UX:
    # `npx @bitraptors/archie` installs the viewer but data only arrives
    # after a deep scan, so the first launch on a fresh project would
    # error out from the CLI without ever opening the browser.
    bp = root / ".archie" / "blueprint.json"
    if not bp.exists():
        print(
            "Note: .archie/blueprint.json not found yet. The viewer will "
            "still launch — run /archie-deep-scan to "
            "populate it. The /api/bundle endpoint will return 404 until "
            "data exists; the React app surfaces this as an empty state.",
            file=sys.stderr,
        )

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
    if not args.no_reload:
        _start_reload_watcher(Path(__file__).resolve().parent)
        print("Auto-reload: on (--no-reload to disable)")
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

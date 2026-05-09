# Unify /archie-viewer with share/viewer/ — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace `archie/standalone/viewer.py` (2067-LOC zero-dep Python HTML SPA) with a small Python sidecar that serves the existing `share/viewer/` React app. V1 ships render parity with the share viewer's detail page; V2 features can diverge under the same React codebase.

**Architecture:** Python sidecar serves `.archie/viewer/dist/` (built React app) plus one JSON endpoint `GET /api/bundle` that reuses `upload.build_bundle()`. React app gains a `/local` route that fetches `/api/bundle` and renders `ReportPage`. Build happens at install time via `npx @bitraptors/archie`, cached with a version marker.

**Tech Stack:** Python 3.9+ stdlib (HTTP server), React 18 + Vite + TypeScript (existing share viewer), Node 18+ for install-time build, pytest for Python tests.

**Branch:** `feature/unify-viewer-scan` (already created).

**Reference design:** `docs/plans/2026-05-09-unify-viewer-scan-design.md`.

---

## Phase A — Python sidecar

### Task A1: Set up viewer test scaffolding

**Files:**
- Create: `tests/test_viewer.py`
- Read: `archie/standalone/upload.py` (specifically `build_bundle`)

**Step 1: Write the failing test**

```python
# tests/test_viewer.py
"""Tests for the Archie local viewer sidecar."""
from __future__ import annotations

import json
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture
def project_with_blueprint(tmp_path: Path) -> Path:
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    (archie_dir / "blueprint.json").write_text(json.dumps({
        "meta": {"scan_count": 1},
        "components": {"components": [{"name": "x", "location": "src/x"}]},
    }))
    return tmp_path


def test_bundle_endpoint_returns_blueprint(project_with_blueprint: Path):
    from viewer import build_app
    port = _free_port()
    app = build_app(project_with_blueprint, port=port)
    server_thread = threading.Thread(target=app.serve_forever, daemon=True)
    server_thread.start()
    try:
        time.sleep(0.05)
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/bundle", timeout=2)
        body = json.loads(resp.read())
        assert "blueprint" in body
        assert body["blueprint"]["components"]["components"][0]["name"] == "x"
    finally:
        app.shutdown()
```

**Step 2: Run to verify it fails**

```bash
python -m pytest tests/test_viewer.py::test_bundle_endpoint_returns_blueprint -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'viewer'` or `cannot import name 'build_app'`.

**Step 3: Commit**

```bash
git add tests/test_viewer.py
git commit -m "test(viewer): scaffold sidecar bundle-endpoint test"
```

---

### Task A2: Implement the sidecar with /api/bundle

**Files:**
- Replace: `archie/standalone/viewer.py` (delete the existing 2067 LOC, write a fresh ~150 LOC version)

**Step 1: Write the new viewer.py**

```python
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
import threading
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from upload import build_bundle  # noqa: E402

DEFAULT_PORT = 5847


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
            body = json.dumps({"bundle": bundle, "created_at": ""}).encode("utf-8")
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
    dist_dir = None if api_only else (root / ".archie" / "viewer" / "dist")
    if not api_only and (dist_dir is None or not (dist_dir / "index.html").exists()):
        print(
            "Error: .archie/viewer/dist/ not found. "
            "Run `npx @bitraptors/archie` to set up the viewer.",
            file=sys.stderr,
        )
        raise SystemExit(1)
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
        active = [x for x in f_data.get("findings", []) if x.get("status", "active") == "active"]
        parts.append(f"{len(active)} findings")
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    try:
        r_data = json.loads(rules.read_text())
        parts.append(f"{len(r_data.get('rules', []))} rules adopted")
    except (FileNotFoundError, json.JSONDecodeError):
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
```

**Step 2: Run the test from Task A1**

```bash
python -m pytest tests/test_viewer.py::test_bundle_endpoint_returns_blueprint -v
```

Expected: PASS.

**Step 3: Commit**

```bash
git add archie/standalone/viewer.py
git commit -m "feat(viewer): replace inline-HTML viewer with React-app sidecar"
```

---

### Task A3: Test static SPA fallback + 404

**Files:**
- Modify: `tests/test_viewer.py`

**Step 1: Add tests**

```python
def test_404_for_unknown_api_path(project_with_blueprint: Path, tmp_path: Path):
    # Create a fake dist/ so build_app accepts the project
    dist = project_with_blueprint / ".archie" / "viewer" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html>local</html>")
    from viewer import build_app
    port = _free_port()
    app = build_app(project_with_blueprint, port=port)
    threading.Thread(target=app.serve_forever, daemon=True).start()
    try:
        time.sleep(0.05)
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/nonexistent", timeout=2)
        assert exc.value.code == 404
    finally:
        app.shutdown()


def test_spa_fallback_serves_index_html(project_with_blueprint: Path):
    dist = project_with_blueprint / ".archie" / "viewer" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html>local</html>")
    from viewer import build_app
    port = _free_port()
    app = build_app(project_with_blueprint, port=port)
    threading.Thread(target=app.serve_forever, daemon=True).start()
    try:
        time.sleep(0.05)
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/local", timeout=2)
        assert b"<html>local</html>" in resp.read()
    finally:
        app.shutdown()


def test_api_only_skips_static(project_with_blueprint: Path):
    from viewer import build_app
    port = _free_port()
    app = build_app(project_with_blueprint, port=port, api_only=True)
    threading.Thread(target=app.serve_forever, daemon=True).start()
    try:
        time.sleep(0.05)
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
        assert exc.value.code == 404
        # Bundle endpoint still works
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/bundle", timeout=2)
        assert resp.status == 200
    finally:
        app.shutdown()
```

**Step 2: Run all viewer tests**

```bash
python -m pytest tests/test_viewer.py -v
```

Expected: 4 PASS.

**Step 3: Commit**

```bash
git add tests/test_viewer.py
git commit -m "test(viewer): cover static fallback, 404, and --api-only"
```

---

### Task A4: Test preflight check (missing blueprint)

**Files:**
- Modify: `tests/test_viewer.py`

**Step 1: Write test**

```python
def test_main_exits_when_blueprint_missing(tmp_path: Path, capsys):
    from viewer import main
    rc = main([str(tmp_path)])
    assert rc == 1
    captured = capsys.readouterr()
    assert "blueprint.json not found" in captured.err
```

**Step 2: Run**

```bash
python -m pytest tests/test_viewer.py::test_main_exits_when_blueprint_missing -v
```

Expected: PASS (already implemented in A2).

**Step 3: Commit**

```bash
git add tests/test_viewer.py
git commit -m "test(viewer): preflight check exits cleanly when no blueprint"
```

---

### Task A5: Manual smoke against a real project

**Files:** None modified.

**Step 1: Build a stub dist/ in a real Archie project**

```bash
mkdir -p /tmp/archie-smoke/.archie/viewer/dist
echo '<!doctype html><html><body>stub</body></html>' > /tmp/archie-smoke/.archie/viewer/dist/index.html
cp $PWD/.archie/blueprint.json /tmp/archie-smoke/.archie/blueprint.json 2>/dev/null \
  || echo '{"meta":{"scan_count":1}}' > /tmp/archie-smoke/.archie/blueprint.json
```

**Step 2: Run viewer**

```bash
python3 archie/standalone/viewer.py /tmp/archie-smoke --no-open --port 5847 &
SERVER_PID=$!
sleep 1
curl -s http://localhost:5847/api/bundle | head -c 200
curl -s http://localhost:5847/local | head -c 200
kill $SERVER_PID
```

Expected: bundle JSON with `blueprint` key; `/local` returns the stub HTML.

**Step 3: No commit** — purely diagnostic.

---

## Phase B — React app changes

### Task B1: Add bundle prop to ReportPage

**Files:**
- Modify: `share/viewer/src/pages/ReportPage.tsx` lines 20-44

**Step 1: Refactor signature**

Change the component header from:

```tsx
export default function ReportPage() {
  const { token } = useParams<{ token: string }>()
  const [bundle, setBundle] = useState<Bundle | null>(null)
  const [createdAt, setCreatedAt] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  // ...
  useEffect(() => {
    if (!token) return
    fetchReport(token)
      .then((r) => {
        setBundle(r.bundle)
        setCreatedAt(r.created_at)
      })
      .catch((e) => setError(e.message))
  }, [token])
```

to:

```tsx
interface ReportPageProps {
  bundle?: Bundle
  createdAt?: string
}

export default function ReportPage({ bundle: bundleProp, createdAt: createdAtProp }: ReportPageProps = {}) {
  const { token } = useParams<{ token: string }>()
  const [bundle, setBundle] = useState<Bundle | null>(bundleProp ?? null)
  const [createdAt, setCreatedAt] = useState<string | null>(createdAtProp ?? null)
  const [error, setError] = useState<string | null>(null)
  // ...
  useEffect(() => {
    if (bundleProp) return  // local mode: bundle already provided, skip fetch
    if (!token) return
    fetchReport(token)
      .then((r) => {
        setBundle(r.bundle)
        setCreatedAt(r.created_at)
      })
      .catch((e) => setError(e.message))
  }, [token, bundleProp])
```

**Step 2: Type-check**

```bash
cd share/viewer && npx tsc -b --noEmit
```

Expected: no errors.

**Step 3: Smoke-test the share-mode unchanged behavior**

```bash
cd share/viewer && npm run dev &
DEV_PID=$!
sleep 3
# Visit http://localhost:5173/r/SOME_TOKEN/details — should fetch as before
curl -s http://localhost:5173/ | grep -c '<div id="root">'
kill $DEV_PID
```

Expected: existing share routes still load (the curl is a smoke; visual check is the real proof — open the URL in a browser).

**Step 4: Commit**

```bash
git add share/viewer/src/pages/ReportPage.tsx
git commit -m "refactor(viewer): ReportPage accepts optional bundle prop"
```

---

### Task B2: Add LocalPage component

**Files:**
- Create: `share/viewer/src/pages/LocalPage.tsx`

**Step 1: Write the component**

```tsx
import { useEffect, useState } from 'react'
import ReportPage from './ReportPage'
import type { Bundle } from '@/lib/api'

export default function LocalPage() {
  const [bundle, setBundle] = useState<Bundle | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/bundle')
      .then((r) => {
        if (!r.ok) throw new Error(`Local bundle fetch failed (HTTP ${r.status}). Is /archie-scan run?`)
        return r.json()
      })
      .then((j) => setBundle(j.bundle))
      .catch((e) => setError(e.message))
  }, [])

  if (error) {
    return (
      <div className="p-8 max-w-2xl mx-auto">
        <h1 className="text-2xl font-semibold mb-2">Local viewer</h1>
        <p className="text-red-600">{error}</p>
      </div>
    )
  }
  if (!bundle) return <div className="p-8">Loading local bundle…</div>
  return <ReportPage bundle={bundle} />
}
```

**Step 2: Type-check**

```bash
cd share/viewer && npx tsc -b --noEmit
```

Expected: no errors.

**Step 3: Commit**

```bash
git add share/viewer/src/pages/LocalPage.tsx
git commit -m "feat(viewer): add LocalPage that fetches /api/bundle"
```

---

### Task B3: Register /local route

**Files:**
- Modify: `share/viewer/src/main.tsx` lines 7-22

**Step 1: Add the route**

Add the import and the `<Route>` element:

```tsx
import LocalPage from './pages/LocalPage'
// ...
<Routes>
  <Route path="/" element={<HomePage />} />
  <Route path="/local" element={<LocalPage />} />
  <Route path="/r/:token" element={<CoverPage />} />
  <Route path="/r/:token/details" element={<ReportPage />} />
  <Route path="*" element={<NotFoundPage />} />
</Routes>
```

**Step 2: Type-check + dev smoke**

```bash
cd share/viewer && npx tsc -b --noEmit
```

Expected: no errors.

Manually: in one terminal, `python3 archie/standalone/viewer.py "$PWD" --api-only --port 5847 --no-open`. In another, `cd share/viewer && npm run dev` with a `vite.config.ts` proxy to `http://127.0.0.1:5847`. Visit `http://localhost:5173/local`.

**Step 3: Add the dev proxy if missing**

Check `share/viewer/vite.config.ts` for an existing proxy. If absent, add:

```ts
server: {
  proxy: {
    '/api': 'http://127.0.0.1:5847',
  },
},
```

**Step 4: Commit**

```bash
git add share/viewer/src/main.tsx share/viewer/vite.config.ts
git commit -m "feat(viewer): register /local route and dev proxy to sidecar"
```

---

### Task B4: Verify production build

**Files:** None modified.

**Step 1: Build**

```bash
cd share/viewer && npm run build
```

Expected: `dist/` regenerated, no TypeScript errors, no Vite warnings about unresolved imports.

**Step 2: Manual smoke via the built bundle**

```bash
mkdir -p /tmp/archie-smoke/.archie/viewer
cp -r share/viewer/dist /tmp/archie-smoke/.archie/viewer/dist
echo '{"meta":{"scan_count":1},"components":{"components":[]}}' \
  > /tmp/archie-smoke/.archie/blueprint.json
python3 archie/standalone/viewer.py /tmp/archie-smoke --port 5847
# Browser opens to http://localhost:5847/local — should render the (sparse) detail page
```

Expected: page renders without crash. Empty/sparse sections OK.

**Step 3: No commit** — diagnostic.

---

## Phase C — Install pipeline

### Task C1: Mirror share/viewer/ source into npm-package/assets/viewer/

**Files:**
- Create: `npm-package/assets/viewer/` (directory mirror)
- Create: `scripts/sync_viewer_assets.sh` (helper)

**Step 1: Write the sync helper**

```bash
#!/usr/bin/env bash
# scripts/sync_viewer_assets.sh
# Mirror share/viewer/ build inputs into npm-package/assets/viewer/.
# node_modules/ and dist/ are excluded — they're built at install time.
set -euo pipefail

SRC="share/viewer"
DST="npm-package/assets/viewer"

rm -rf "$DST"
mkdir -p "$DST"

# Copy source + configs only
for item in src public package.json package-lock.json vite.config.ts \
            tsconfig.json tsconfig.node.json tailwind.config.js \
            postcss.config.js index.html; do
  if [ -e "$SRC/$item" ]; then
    cp -r "$SRC/$item" "$DST/$item"
  fi
done

echo "Synced share/viewer/ → npm-package/assets/viewer/"
```

```bash
chmod +x scripts/sync_viewer_assets.sh
```

**Step 2: Run the sync**

```bash
./scripts/sync_viewer_assets.sh
ls npm-package/assets/viewer/
du -sh npm-package/assets/viewer/
```

Expected: `package.json`, `package-lock.json`, `src/`, `public/`, `index.html`, vite/tsconfig/tailwind configs. Size ~300 KB.

**Step 3: Verify the asset copy still builds**

```bash
cd npm-package/assets/viewer && npm ci && npm run build && ls dist/
```

Expected: clean build, `dist/index.html` and `dist/assets/*` present.

**Step 4: Clean up before commit**

```bash
rm -rf npm-package/assets/viewer/node_modules npm-package/assets/viewer/dist
```

**Step 5: Commit**

```bash
git add scripts/sync_viewer_assets.sh npm-package/assets/viewer/
git commit -m "chore(viewer): mirror share/viewer/ source into npm-package/assets"
```

---

### Task C2: archie.mjs copies viewer/ into target

**Files:**
- Modify: `npm-package/bin/archie.mjs` after section 3 ("Copy standalone Python scripts", around line 116)

**Step 1: Add the copy block**

After the platform_rules.json copy (after line 126), insert:

```js
// 3e. Copy share/viewer/ source into target's .archie/viewer/ for install-time build.
function cpDirSync(src, dest) {
  mkdirSync(dest, { recursive: true });
  for (const entry of readdirSync(src, { withFileTypes: true })) {
    const s = join(src, entry.name);
    const d = join(dest, entry.name);
    if (entry.isDirectory()) {
      cpDirSync(s, d);
    } else {
      writeFileSync(d, readFileSync(s));
    }
  }
}

const viewerSrc = join(ASSETS, "viewer");
const viewerDest = join(archieDir, "viewer");
if (existsSync(viewerSrc)) {
  rmSync(viewerDest, { recursive: true, force: true });
  cpDirSync(viewerSrc, viewerDest);
  console.log(`  ${GREEN}✓${RESET} .archie/viewer/ (React source)`);
}
```

**Step 2: Smoke**

```bash
rm -rf /tmp/archie-test
mkdir /tmp/archie-test
node npm-package/bin/archie.mjs /tmp/archie-test
ls /tmp/archie-test/.archie/viewer/
```

Expected: viewer source mirrored into target.

**Step 3: Commit**

```bash
git add npm-package/bin/archie.mjs
git commit -m "feat(install): copy share/viewer source into target .archie/viewer"
```

---

### Task C3: archie.mjs runs npm ci + vite build with streaming output

**Files:**
- Modify: `npm-package/bin/archie.mjs`

**Step 1: Add `import { spawnSync } from "child_process";` to the top imports**

Replace the existing import:

```js
import { execSync } from "child_process";
```

with:

```js
import { execSync, spawnSync } from "child_process";
```

**Step 2: Add the build helper near the top of the file (after the constants block)**

```js
function readPackageVersion() {
  try {
    const pkg = JSON.parse(readFileSync(join(__dirname, "..", "package.json"), "utf8"));
    return pkg.version || "0.0.0";
  } catch { return "0.0.0"; }
}

function streamPrefix(prefix, stream) {
  let buffer = "";
  return (chunk) => {
    buffer += chunk.toString();
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (line.length) stream.write(`${prefix} ${line}\n`);
    }
  };
}

function runWithPrefix(prefix, cmd, args, opts) {
  const result = spawnSync(cmd, args, { ...opts, stdio: "pipe", encoding: "buffer" });
  const onOut = streamPrefix(prefix, process.stdout);
  const onErr = streamPrefix(prefix, process.stderr);
  if (result.stdout) onOut(result.stdout);
  if (result.stderr) onErr(result.stderr);
  return result.status === 0;
}

function buildLocalViewer(viewerDir, packageVersion) {
  const marker = join(viewerDir, "dist", ".archie-version");
  if (existsSync(marker)) {
    const cached = readFileSync(marker, "utf8").trim();
    if (cached === packageVersion) {
      console.log(`  ${GREEN}✓${RESET} Local viewer up to date (v${packageVersion}) — skipping build`);
      return true;
    }
  }

  console.log("");
  console.log(`${BOLD}  Local viewer setup${RESET} ${DIM}(one-time, ~45s)${RESET}`);
  console.log(`  ${DIM}Installs React deps and builds the UI. Cached by version.${RESET}`);
  console.log("");

  const startedAt = Date.now();

  console.log(`  ${CYAN}→${RESET} Installing dependencies (npm ci)`);
  if (!runWithPrefix(`${DIM}[npm]${RESET}`, "npm", ["ci", "--silent"], { cwd: viewerDir })) {
    console.error("");
    console.error(`  ${BOLD}npm ci failed.${RESET} Common causes:`);
    console.error("    - No internet / corporate proxy blocking npm registry");
    console.error("    - Old node (<18). Run `node --version`.");
    console.error("    - npm misconfigured. Run `npm ping`.");
    return false;
  }

  console.log(`  ${CYAN}→${RESET} Building viewer bundle (vite build)`);
  if (!runWithPrefix(`${DIM}[vite]${RESET}`, "npm", ["run", "build", "--silent"], { cwd: viewerDir })) {
    console.error("");
    console.error(`  ${BOLD}vite build failed.${RESET} See output above.`);
    return false;
  }

  console.log(`  ${CYAN}→${RESET} Cleaning up build dependencies`);
  rmSync(join(viewerDir, "node_modules"), { recursive: true, force: true });

  console.log(`  ${CYAN}→${RESET} Writing version marker`);
  writeFileSync(marker, packageVersion);

  const elapsed = ((Date.now() - startedAt) / 1000).toFixed(0);
  console.log("");
  console.log(`  ${GREEN}✓${RESET} Local viewer built in ${elapsed}s`);
  return true;
}
```

**Step 3: Invoke after the viewer copy block (Task C2)**

After the `console.log(\`  \${GREEN}✓\${RESET} .archie/viewer/ (React source)\`);` line, add:

```js
const ok = buildLocalViewer(viewerDest, readPackageVersion());
if (!ok) {
  console.error("");
  console.error("  ⚠ Local viewer build failed. /archie-viewer will not work.");
  console.error("  ⚠ Other Archie features still work. Re-run `npx @bitraptors/archie`");
  console.error("    after fixing the npm/node issue above.");
  // Don't process.exit(1) — preserve the rest of the install (scripts, hooks)
}
```

**Step 4: Smoke**

```bash
rm -rf /tmp/archie-test
mkdir /tmp/archie-test
node npm-package/bin/archie.mjs /tmp/archie-test
ls /tmp/archie-test/.archie/viewer/dist/
cat /tmp/archie-test/.archie/viewer/dist/.archie-version
```

Expected: `dist/index.html` exists, `dist/.archie-version` matches `npm-package/package.json` version, no `node_modules/`.

Run again immediately:

```bash
node npm-package/bin/archie.mjs /tmp/archie-test
```

Expected: skip-build line, no second build.

**Step 5: Commit**

```bash
git add npm-package/bin/archie.mjs
git commit -m "feat(install): build local viewer at install time with progress streaming"
```

---

### Task C4: Node version preflight

**Files:**
- Modify: `npm-package/bin/archie.mjs` near the top (after the imports + constants, before any work)

**Step 1: Add the check**

```js
const MIN_NODE_MAJOR = 18;
const nodeMajor = parseInt(process.versions.node.split(".")[0], 10);
if (nodeMajor < MIN_NODE_MAJOR) {
  console.error(`Archie requires Node ${MIN_NODE_MAJOR}+. You're on ${process.versions.node}.`);
  process.exit(1);
}
```

**Step 2: Smoke**

```bash
node --version  # check current
node npm-package/bin/archie.mjs --help 2>&1 | head -1
```

Expected: install proceeds (assuming node ≥ 18).

**Step 3: Commit**

```bash
git add npm-package/bin/archie.mjs
git commit -m "feat(install): preflight node 18+ before viewer build"
```

---

## Phase D — Sync, docs, cleanup

### Task D1: Sync new viewer.py to npm-package/assets/

**Files:**
- Copy: `archie/standalone/viewer.py` → `npm-package/assets/viewer.py`

**Step 1: Copy**

```bash
cp archie/standalone/viewer.py npm-package/assets/viewer.py
```

**Step 2: Verify sync**

```bash
python3 scripts/verify_sync.py
```

Expected: clean for the .py file. May still warn about `npm-package/assets/viewer/` directory until D2.

**Step 3: Commit**

```bash
git add npm-package/assets/viewer.py
git commit -m "chore(sync): mirror new viewer.py to npm-package/assets"
```

---

### Task D2: Update verify_sync.py to handle viewer/ directory

**Files:**
- Modify: `scripts/verify_sync.py`

**Step 1: Add a check for the viewer source mirror**

After the existing checks, add a function that verifies `npm-package/assets/viewer/` mirrors `share/viewer/` (excluding `node_modules` and `dist`).

```python
def check_viewer_source_mirror(errors: list[str]) -> None:
    src = ROOT / "share" / "viewer"
    dst = ROOT / "npm-package" / "assets" / "viewer"
    if not src.is_dir():
        return
    if not dst.is_dir():
        errors.append("npm-package/assets/viewer/ missing — run scripts/sync_viewer_assets.sh")
        return
    EXPECTED = ["package.json", "package-lock.json", "vite.config.ts", "tsconfig.json",
                "tailwind.config.js", "postcss.config.js", "index.html"]
    for name in EXPECTED:
        s = src / name
        d = dst / name
        if s.exists() and not d.exists():
            errors.append(f"npm-package/assets/viewer/{name} missing (exists in share/viewer/)")
        elif s.exists() and d.exists() and s.read_bytes() != d.read_bytes():
            errors.append(f"share/viewer/{name} != npm-package/assets/viewer/{name} — run scripts/sync_viewer_assets.sh")
    # Source tree shape match
    src_files = sorted(p.relative_to(src).as_posix() for p in (src / "src").rglob("*") if p.is_file())
    dst_files = sorted(p.relative_to(dst).as_posix() for p in (dst / "src").rglob("*") if p.is_file()) if (dst / "src").is_dir() else []
    if src_files != dst_files:
        only_src = set(src_files) - set(dst_files)
        only_dst = set(dst_files) - set(src_files)
        if only_src:
            errors.append(f"share/viewer/{{ {','.join(sorted(only_src))} }} missing from asset mirror")
        if only_dst:
            errors.append(f"asset mirror has stale files: {','.join(sorted(only_dst))}")
```

Wire it into the main check function alongside the existing checks.

**Step 2: Run**

```bash
python3 scripts/verify_sync.py
```

Expected: clean.

**Step 3: Commit**

```bash
git add scripts/verify_sync.py
git commit -m "chore(sync): teach verify_sync.py about the viewer source mirror"
```

---

### Task D3: Update slash command docs

**Files:**
- Modify: `.claude/commands/archie-viewer.md`
- Copy: → `npm-package/assets/archie-viewer.md`

**Step 1: Rewrite the prerequisites section**

```markdown
# Archie Viewer — Blueprint Inspector

Open the blueprint viewer in your browser to inspect generated artifacts.

**Prerequisites:** Requires `.archie/viewer.py` and a built `.archie/viewer/dist/`. If either is missing, tell the user to run `npx @bitraptors/archie` first.

The viewer renders the same React UI the share flow uses (`archie-viewer.vercel.app`). It works against whatever data exists — even after just `/archie-scan`, you'll see health scores, findings, rules, and the architecture diagram. Sections that need deep-scan data (full component graph, decision chain) render sparse.

## Launch

```bash
python3 .archie/viewer.py "$PWD"
```

The viewer auto-opens in your default browser at `http://localhost:5847/local`. Press Ctrl+C to stop.

Optional flags: `--no-open` (suppress browser), `--api-only` (JSON endpoint only, for contributors running `vite dev` separately).
```

**Step 2: Mirror to npm-package/assets/**

```bash
cp .claude/commands/archie-viewer.md npm-package/assets/archie-viewer.md
```

**Step 3: Verify sync**

```bash
python3 scripts/verify_sync.py
```

Expected: clean.

**Step 4: Commit**

```bash
git add .claude/commands/archie-viewer.md npm-package/assets/archie-viewer.md
git commit -m "docs(viewer): update slash command for the React-app sidecar"
```

---

### Task D4: Run full test suite

**Files:** None modified.

**Step 1: Run pytest**

```bash
python -m pytest tests/ -v
```

Expected: all green, including the four `test_viewer.py` tests.

**Step 2: Run sync verifier**

```bash
python3 scripts/verify_sync.py
```

Expected: clean.

**Step 3: Build React in CI shape**

```bash
cd npm-package/assets/viewer && npm ci && npm run build
ls dist/
cd -
rm -rf npm-package/assets/viewer/node_modules npm-package/assets/viewer/dist
```

Expected: clean build.

**Step 4: No commit** — diagnostic.

---

### Task D5: End-to-end smoke in fresh project

**Files:** None modified.

**Step 1: Fresh install**

```bash
rm -rf /tmp/archie-e2e
mkdir /tmp/archie-e2e
cd /tmp/archie-e2e
git init -q
echo '{"meta":{"scan_count":1},"components":{"components":[]}}' > /tmp/archie-e2e/.archie-bp-stub
node $OLDPWD/npm-package/bin/archie.mjs /tmp/archie-e2e
mkdir -p .archie
cp /tmp/archie-e2e/.archie-bp-stub .archie/blueprint.json
ls .archie/viewer/dist/
python3 .archie/viewer.py "$PWD" --no-open --port 5848 &
SERVER_PID=$!
sleep 1
curl -s http://localhost:5848/api/bundle | python3 -m json.tool | head -20
curl -s http://localhost:5848/local | head -c 200
kill $SERVER_PID
cd $OLDPWD
```

Expected: install succeeds, `dist/` is populated, bundle endpoint returns JSON, `/local` returns HTML.

**Step 2: No commit** — diagnostic.

---

### Task D6: Run /archie-viewer manually against BabyWeather.Android

**Files:** None modified.

**Step 1:** From the user's BabyWeather.Android project (per memory: it's the canonical test repo), run:

```bash
npx /path/to/this/repo/npm-package/bin/archie.mjs .
# Then in Claude Code:
/archie-viewer
```

Expected: install completes, `/archie-viewer` opens browser, ReportPage renders the BabyWeather blueprint with all sections populated.

**Step 2: No commit** — manual sign-off.

---

## Phase E — Ship

### Task E1: Open the PR

**Files:** None modified.

**Step 1: Push the branch**

```bash
git push -u origin feature/unify-viewer-scan
```

**Step 2: Open the PR**

```bash
gh pr create --title "feat(viewer): unify /archie-viewer with share/viewer/ React app" \
  --body "$(cat <<'EOF'
## Summary

- Replace `archie/standalone/viewer.py` (2067-LOC zero-dep Python HTML SPA) with a small Python sidecar that serves the existing `share/viewer/` React app.
- One source of truth for the UI: the Vercel-hosted share viewer and the local `/archie-viewer` render the same React components.
- Local mode lands on a new `/local` route that fetches `/api/bundle` from the sidecar (which reuses `upload.build_bundle()` — the same bundle shape the share flow uploads).
- Build happens at install time via `npx @bitraptors/archie`, cached with a version marker. No prebuilt assets shipped in npm-package.

## What ships in V1

Render parity with the share viewer's detail page: architecture diagram, health, components, decisions, trade-offs, pitfalls, rules, findings, communications, integrations, technology, deployment.

## What gets dropped (return in V2 if wanted)

- Files browser (.claude/rules/* + AGENTS.md viewer)
- Folder CLAUDE.md browser
- Dependency graph (vis-network)
- Inline rule editor (POST /api/rules — already covered by the /archie-scan adoption flow)

## Diff size

- Removed: ~2067 LOC from `viewer.py` (the inline HTML SPA).
- Added: ~150 LOC new sidecar, ~40 LOC LocalPage, ~10 LOC ReportPage prop refactor, ~80 LOC archie.mjs install-time build, ~80 LOC tests, mirrored React source in `npm-package/assets/viewer/` (~300 KB tracked in git).

## Test plan

- [ ] `python -m pytest tests/ -v` (all green incl. new test_viewer.py)
- [ ] `python3 scripts/verify_sync.py` (clean)
- [ ] `cd npm-package/assets/viewer && npm ci && npm run build` (clean)
- [ ] `npx ./npm-package/bin/archie.mjs /tmp/empty` (install + build complete, marker written)
- [ ] `/archie-viewer` against BabyWeather.Android (full render, mermaid diagram, findings)
- [ ] Vercel deploy preview at `archie-viewer.vercel.app/r/:token/details` unchanged

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

**Step 3:** Wait for CI (`npm run build` step), address any failures, request review.

---

## Decisions reference

See `docs/plans/2026-05-09-unify-viewer-scan-design.md` for the locked design choices and risk register.

## Total task count

- Phase A (Python sidecar): 5 tasks
- Phase B (React): 4 tasks
- Phase C (install pipeline): 4 tasks
- Phase D (sync, docs, cleanup): 6 tasks
- Phase E (ship): 1 task

**19 tasks total. Frequent commits — one per task except diagnostic-only smoke tasks.**

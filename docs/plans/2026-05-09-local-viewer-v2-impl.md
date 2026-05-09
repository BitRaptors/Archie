# Local Viewer V2 — Unified Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bring back three previously-dropped V1 features (inline rule editor, folder CLAUDE.md browser, generated files browser) as local-only additions to the React viewer. Share viewer's `archie-viewer.vercel.app/r/:token/details` route stays bundle-identical.

**Architecture:** `LocalPage` becomes a 3-tab shell; rule editor is inline on `ReportPage` via `LocalEditContext`; new tabs lazy-load components from `share/viewer/src/components/local/`.

**Tech stack:** Same as V1 — Python 3.9+ stdlib (HTTP), React 18 + Vite + TypeScript, pytest.

**Branch:** `feature/unify-viewer-scan` (continuation of V1, no separate branch). All commits land here.

**Reference design:** `docs/plans/2026-05-09-local-viewer-v2-design.md`.

---

## Iteration 1 — Tabbed shell + shared primitives + Generated Files

### Task V2-1.1: Add `Toast`, `TreeNav`, `MarkdownPane` shared primitives

**Files:**
- Create: `share/viewer/src/components/local/Toast.tsx`
- Create: `share/viewer/src/components/local/TreeNav.tsx`
- Create: `share/viewer/src/components/local/MarkdownPane.tsx`

**Step 1: Implement primitives**

`MarkdownPane.tsx` (~30 LOC):
- Props: `{ content: string }`
- Wraps `ReactMarkdown` + `remarkGfm` + `rehypeHighlight` (already used by ReportPage). Tailwind `prose prose-invert prose-sm max-w-none` style. Imports `'highlight.js/styles/atom-one-dark.min.css'`.

`TreeNav.tsx` (~50 LOC):
- Props: `{ paths: string[], selected: string | null, onSelect: (path: string) => void }`
- Groups paths by directory prefix. Renders an unordered tree where directory names are non-clickable headers and files are clickable buttons. Highlights the `selected` entry with `bg-teal-900` (matches existing palette).

`Toast.tsx` (~25 LOC):
- Props: `{ message: string | null, onDismiss: () => void }`
- Fixed bottom-right, `bg-papaya-700/90 text-ink-900 px-4 py-2 rounded shadow-lg`. Auto-dismisses after 2s via `setTimeout`. Returns null when `message` is null.

**Step 2: Type-check**

```bash
cd share/viewer && npx tsc -b --noEmit
```

Expected: clean.

**Step 3: Commit**

```bash
git add share/viewer/src/components/local/
git commit -m "feat(viewer-v2): add MarkdownPane, TreeNav, Toast primitives"
```

---

### Task V2-1.2: Refactor `LocalPage` into a 3-tab shell

**Files:**
- Modify: `share/viewer/src/pages/LocalPage.tsx`

**Step 1: Extend LocalPage**

Replace the current LocalPage body with a tabbed layout. Use plain state for the active tab — no router changes (keeps the URL stable). Tabs:

```tsx
type Tab = 'report' | 'generated' | 'folders'

const [tab, setTab] = useState<Tab>('report')
const GeneratedFilesBrowser = lazy(() => import('@/components/local/GeneratedFilesBrowser'))
const FolderClaudeMdsBrowser = lazy(() => import('@/components/local/FolderClaudeMdsBrowser'))
```

Tab bar at the top (text buttons styled to match the viewer palette — `text-papaya-300`/`text-papaya-100` for inactive/active). Below it, a `<Suspense fallback={<div className="p-8">Loading…</div>}>` wraps the active tab's content.

The "Report" tab body must wrap `ReportPage` in a `LocalEditContext.Provider` even though the value is null until iteration 3 lands the editor — keeping the wrapper avoids touching LocalPage again later.

**Step 2: Create the (placeholder) context**

Create `share/viewer/src/components/local/context/LocalEditContext.tsx`:

```tsx
import { createContext } from 'react'

export interface LocalEditCtx {
  toggleRule: (id: string, action: 'adopt' | 'reject' | 'disable' | 'enable') => Promise<void>
  editRule: (id: string, patch: Record<string, string>) => Promise<void>
}

export const LocalEditContext = createContext<LocalEditCtx | null>(null)
```

LocalPage wraps with `<LocalEditContext.Provider value={null}>` initially. iteration 3 fills in the implementation.

**Step 3: Type-check**

```bash
cd share/viewer && npx tsc -b --noEmit
```

Expected: zero errors. The lazy imports point to files that don't exist yet — TypeScript only warns at runtime, not compile time. To avoid noisy errors, create empty stub files at `share/viewer/src/components/local/GeneratedFilesBrowser.tsx` and `FolderClaudeMdsBrowser.tsx` that just `export default function() { return null }`. They'll be implemented in tasks 1.3 and 2.3.

**Step 4: Commit**

```bash
git add share/viewer/src/pages/LocalPage.tsx share/viewer/src/components/local/
git commit -m "feat(viewer-v2): LocalPage is a 3-tab shell with LocalEditContext"
```

---

### Task V2-1.3: Backend `GET /api/generated-files`

**Files:**
- Modify: `archie/standalone/viewer.py`
- Modify: `tests/test_viewer.py`

**Step 1: Add helper + endpoint**

In `viewer.py`, restore the `_collect_generated_files` helper from the deleted V1 viewer.py code (visible in git history at `archie/standalone/viewer.py@27dbf4019~1`):

```python
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
```

Then in the handler's `do_GET`, add a new branch:

```python
if parsed.path == "/api/generated-files":
    self._serve_json(_collect_generated_files(root))
    return
```

Where `_serve_json` is a small helper extracted from the existing `_serve_bundle` pattern (status 200 + content-type + body bytes). If `_serve_json` doesn't already exist as a method, create it:

```python
def _serve_json(self, data):
    body = json.dumps(data).encode("utf-8")
    self.send_response(200)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)
```

**Step 2: Add test**

Append to `tests/test_viewer.py`:

```python
def test_generated_files_endpoint(project_with_blueprint: Path):
    # Stub generated outputs in the tmpdir
    (project_with_blueprint / "CLAUDE.md").write_text("# root claude")
    (project_with_blueprint / "AGENTS.md").write_text("# agents")
    rules = project_with_blueprint / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "enforcement.md").write_text("# enforcement")
    (rules / "topic-x.md").write_text("# topic x")

    from viewer import build_app
    port = _free_port()
    app = build_app(project_with_blueprint, port=port, api_only=True)
    threading.Thread(target=app.serve_forever, daemon=True).start()
    try:
        time.sleep(0.05)
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/generated-files", timeout=2)
        body = json.loads(resp.read())
        assert "CLAUDE.md" in body
        assert "AGENTS.md" in body
        assert ".claude/rules/enforcement.md" in body
        assert ".claude/rules/topic-x.md" in body
        assert body["CLAUDE.md"] == "# root claude"
    finally:
        app.shutdown()
```

**Step 3: Run + commit**

```bash
python -m pytest tests/test_viewer.py -v
# 6 passed
git add archie/standalone/viewer.py tests/test_viewer.py
git commit -m "feat(viewer-v2): GET /api/generated-files endpoint + test"
```

---

### Task V2-1.4: Frontend `GeneratedFilesBrowser`

**Files:**
- Replace stub: `share/viewer/src/components/local/GeneratedFilesBrowser.tsx`

**Step 1: Implement**

```tsx
import { useEffect, useState } from 'react'
import MarkdownPane from './MarkdownPane'
import TreeNav from './TreeNav'

export default function GeneratedFilesBrowser() {
  const [files, setFiles] = useState<Record<string, string> | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/generated-files')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data) => {
        setFiles(data)
        const first = Object.keys(data)[0]
        if (first) setSelected(first)
      })
      .catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="p-8 text-red-400">Failed to load generated files: {error}</div>
  if (!files) return <div className="p-8">Loading…</div>
  if (Object.keys(files).length === 0)
    return <div className="p-8 text-papaya-300">No generated files yet — run /archie-scan first.</div>

  return (
    <div className="flex h-full">
      <aside className="w-72 border-r border-ink-800 overflow-y-auto p-4">
        <TreeNav paths={Object.keys(files)} selected={selected} onSelect={setSelected} />
      </aside>
      <main className="flex-1 overflow-y-auto p-8">
        {selected && <MarkdownPane content={files[selected]} />}
      </main>
    </div>
  )
}
```

**Step 2: tsc + commit**

```bash
cd share/viewer && npx tsc -b --noEmit
git add share/viewer/src/components/local/GeneratedFilesBrowser.tsx
git commit -m "feat(viewer-v2): GeneratedFilesBrowser with tree+markdown"
```

---

### Task V2-1.5: Iteration 1 verification

**Files:** none modified.

**Step 1: Build the bundle and verify**

```bash
cd share/viewer && npm run build
# Confirm /local route still loads, new tabs render, Generated tab shows files
```

**Step 2: Sync the asset mirror + verify**

```bash
./scripts/sync_viewer_assets.sh
python3 scripts/verify_sync.py
```

Both must pass. Commit any byte changes the sync produced:

```bash
git add npm-package/assets/viewer/
git commit -m "chore(sync): refresh asset mirror after V2 iteration 1"
```

**Step 3: Smoke against the Archie repo's own .archie/**

```bash
# Ensure Archie repo has its own .archie/blueprint.json (rerun /archie-scan if missing)
python3 archie/standalone/viewer.py "$PWD" --no-open --port 5854 &
PID=$!
sleep 0.6
curl -s http://localhost:5854/api/generated-files | python3 -m json.tool | head -10
kill $PID; wait
```

Expected: returns CLAUDE.md, AGENTS.md, .claude/rules/*.md from the Archie repo itself.

---

## Iteration 2 — Folder CLAUDE.md browser + Intent Layer CTA

### Task V2-2.1: Backend `GET /api/intent-layer-status` + `GET /api/folder-claude-mds`

**Files:**
- Modify: `archie/standalone/viewer.py`
- Modify: `tests/test_viewer.py`

**Step 1: Add helpers + endpoints**

Restore `_collect_folder_claude_mds` from V1 git history (~15 LOC):

```python
def _collect_folder_claude_mds(root: Path) -> dict[str, str]:
    result = {}
    for claude_md in root.rglob("CLAUDE.md"):
        if any(part in _SKIP_DIRS for part in claude_md.parts):
            continue
        rel = str(claude_md.relative_to(root))
        if rel == "CLAUDE.md":
            continue  # root CLAUDE.md is shown in /api/generated-files
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
```

Two new branches in `do_GET`:

```python
if parsed.path == "/api/intent-layer-status":
    self._serve_json(_intent_layer_status(root))
    return
if parsed.path == "/api/folder-claude-mds":
    self._serve_json(_collect_folder_claude_mds(root))
    return
```

**Step 2: Tests**

Append to `tests/test_viewer.py` — three tests covering the (no marker / no files / both / either) matrix:

```python
def test_intent_layer_status_empty(project_with_blueprint: Path):
    from viewer import build_app
    port = _free_port()
    app = build_app(project_with_blueprint, port=port, api_only=True)
    threading.Thread(target=app.serve_forever, daemon=True).start()
    try:
        time.sleep(0.05)
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/intent-layer-status", timeout=2)
        body = json.loads(resp.read())
        assert body == {"exists": False, "count": 0}
    finally:
        app.shutdown()


def test_intent_layer_status_with_files(project_with_blueprint: Path):
    folder = project_with_blueprint / "src" / "x"
    folder.mkdir(parents=True)
    (folder / "CLAUDE.md").write_text("# x context")
    from viewer import build_app
    port = _free_port()
    app = build_app(project_with_blueprint, port=port, api_only=True)
    threading.Thread(target=app.serve_forever, daemon=True).start()
    try:
        time.sleep(0.05)
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/intent-layer-status", timeout=2)
        body = json.loads(resp.read())
        assert body == {"exists": True, "count": 1}
        resp2 = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/folder-claude-mds", timeout=2)
        body2 = json.loads(resp2.read())
        assert "src/x/CLAUDE.md" in body2
        assert body2["src/x/CLAUDE.md"] == "# x context"
    finally:
        app.shutdown()


def test_intent_layer_status_marker_only(project_with_blueprint: Path):
    state = project_with_blueprint / ".archie" / "intent_layer_state.json"
    state.write_text(json.dumps({"processed": ["src/foo"]}))
    from viewer import build_app
    port = _free_port()
    app = build_app(project_with_blueprint, port=port, api_only=True)
    threading.Thread(target=app.serve_forever, daemon=True).start()
    try:
        time.sleep(0.05)
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/intent-layer-status", timeout=2)
        body = json.loads(resp.read())
        assert body == {"exists": True, "count": 0}
    finally:
        app.shutdown()
```

**Step 3: Run + commit**

```bash
python -m pytest tests/test_viewer.py -v
# 9 passed
git add archie/standalone/viewer.py tests/test_viewer.py
git commit -m "feat(viewer-v2): /api/intent-layer-status + /api/folder-claude-mds"
```

---

### Task V2-2.2: Frontend `IntentLayerEmptyState`

**Files:**
- Create: `share/viewer/src/components/local/IntentLayerEmptyState.tsx`

**Step 1: Implement**

```tsx
interface Props { count: number }

export default function IntentLayerEmptyState({ count }: Props) {
  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="bg-ink-900/50 border border-ink-700 rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-3">📁 Per-folder context not yet generated</h2>
        <p className="text-papaya-200 mb-4">
          Archie can write a CLAUDE.md into each meaningful directory of your repo,
          giving AI agents directory-level architectural context (what this layer
          does, what it depends on, what to avoid here). Without this, agents only
          see the root CLAUDE.md.
        </p>
        <p className="text-papaya-200 mb-2 font-semibold">Two ways to generate:</p>
        <ul className="list-none space-y-3 mb-4">
          <li>
            <code className="text-tangerine-300">/archie-deep-scan</code>
            <p className="text-papaya-300 text-sm ml-4">
              Runs the intent layer as Phase 7. Full baseline, ~15-20 min.
            </p>
          </li>
          <li>
            <code className="text-tangerine-300">/archie-intent-layer prepare</code>
            <span className="text-papaya-300"> &amp;&amp; </span>
            <code className="text-tangerine-300">/archie-intent-layer next-ready</code>
            <p className="text-papaya-300 text-sm ml-4">
              Incremental, resumable across sessions. Run next-ready until the queue is empty.
            </p>
          </li>
        </ul>
        <p className="text-papaya-400 text-sm">
          Detected: {count} per-folder CLAUDE.md file{count === 1 ? '' : 's'} outside the repo root.
        </p>
      </div>
    </div>
  )
}
```

**Step 2: tsc + commit**

```bash
cd share/viewer && npx tsc -b --noEmit
git add share/viewer/src/components/local/IntentLayerEmptyState.tsx
git commit -m "feat(viewer-v2): IntentLayerEmptyState CTA component"
```

---

### Task V2-2.3: Frontend `FolderClaudeMdsBrowser`

**Files:**
- Replace stub: `share/viewer/src/components/local/FolderClaudeMdsBrowser.tsx`

**Step 1: Implement**

```tsx
import { useEffect, useState } from 'react'
import MarkdownPane from './MarkdownPane'
import TreeNav from './TreeNav'
import IntentLayerEmptyState from './IntentLayerEmptyState'

export default function FolderClaudeMdsBrowser() {
  const [status, setStatus] = useState<{ exists: boolean; count: number } | null>(null)
  const [files, setFiles] = useState<Record<string, string> | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/intent-layer-status')
      .then((r) => r.json())
      .then((s: { exists: boolean; count: number }) => {
        setStatus(s)
        if (s.exists) {
          return fetch('/api/folder-claude-mds')
            .then((r) => r.json())
            .then((data: Record<string, string>) => {
              setFiles(data)
              const first = Object.keys(data)[0]
              if (first) setSelected(first)
            })
        }
      })
      .catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="p-8 text-red-400">Failed to load: {error}</div>
  if (!status) return <div className="p-8">Loading…</div>
  if (!status.exists) return <IntentLayerEmptyState count={status.count} />
  if (!files) return <div className="p-8">Loading folders…</div>

  return (
    <div className="flex h-full">
      <aside className="w-72 border-r border-ink-800 overflow-y-auto p-4">
        <TreeNav paths={Object.keys(files)} selected={selected} onSelect={setSelected} />
      </aside>
      <main className="flex-1 overflow-y-auto p-8">
        {selected && <MarkdownPane content={files[selected]} />}
      </main>
    </div>
  )
}
```

**Step 2: tsc + commit**

```bash
cd share/viewer && npx tsc -b --noEmit
git add share/viewer/src/components/local/FolderClaudeMdsBrowser.tsx
git commit -m "feat(viewer-v2): FolderClaudeMdsBrowser with empty-state branch"
```

---

### Task V2-2.4: Iteration 2 verification

```bash
cd share/viewer && npm run build
./scripts/sync_viewer_assets.sh
python3 scripts/verify_sync.py
git add npm-package/assets/viewer/
git commit -m "chore(sync): refresh asset mirror after V2 iteration 2"
```

Smoke: launch viewer.py against `/Users/hamutarto/DEV/BitRaptors/BabyWeather.Android` (which has per-folder CLAUDE.mds — confirmed earlier) → Folders tab should populate. Then launch against a project without intent layer → CTA should render.

---

## Iteration 3 — Inline rule editor

### Task V2-3.1: Backend `POST /api/rules` skeleton

**Files:**
- Modify: `archie/standalone/viewer.py`

**Step 1: Add `do_POST` handler**

Inside the `Handler` class, add `do_POST`:

```python
def do_POST(self):
    parsed = urlparse(self.path)
    if parsed.path != "/api/rules":
        self._send_error(404, "Not found")
        return
    try:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        body = json.loads(raw)
    except (ValueError, json.JSONDecodeError):
        self._send_error(400, "Invalid JSON body")
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
    # Fire-and-forget refresh subprocesses
    _spawn_subprocess_silent(["python3", str(root / ".archie" / "rule_index.py"), "build", str(root)])
    _spawn_subprocess_silent(["python3", str(root / ".archie" / "renderer.py"), str(root)])
    self._serve_json({"ok": True})
```

**Step 2: Add `_RuleActionError` + `_apply_rule_action` + `_spawn_subprocess_silent` at module scope**

```python
import subprocess

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


def _spawn_subprocess_silent(argv: list[str]) -> None:
    try:
        subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, FileNotFoundError):
        pass  # fire-and-forget — failures don't block the user
```

Top-of-file imports: add `import os` and `import subprocess`.

**Step 2: Sanity check**

```bash
python3 -m pytest tests/test_viewer.py -v
# Existing tests should still pass; no new tests yet — that's V2-3.2
```

**Step 3: Commit**

```bash
git add archie/standalone/viewer.py
git commit -m "feat(viewer-v2): POST /api/rules with 5 atomic actions"
```

---

### Task V2-3.2: Backend tests for all 5 actions + failure modes

**Files:**
- Modify: `tests/test_viewer.py`

**Step 1: Add fixture + tests**

```python
import urllib.error


@pytest.fixture
def project_with_rules(tmp_path: Path) -> Path:
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    (archie_dir / "blueprint.json").write_text(json.dumps({"meta": {}}))
    (archie_dir / "rules.json").write_text(json.dumps({"rules": [
        {"id": "r1", "description": "active", "severity_class": "pattern_divergence"},
    ]}))
    (archie_dir / "proposed_rules.json").write_text(json.dumps({"rules": [
        {"id": "p1", "description": "proposed", "severity_class": "pattern_divergence"},
    ]}))
    (archie_dir / "ignored_rules.json").write_text(json.dumps({"rules": [
        {"id": "i1", "description": "ignored", "severity_class": "pattern_divergence"},
    ]}))
    return tmp_path


def _post_rule(port: int, action: str, rule_id: str, patch: dict | None = None) -> int:
    body = {"action": action, "rule_id": rule_id}
    if patch is not None:
        body["patch"] = patch
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/rules",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=2)
        return resp.status
    except urllib.error.HTTPError as e:
        return e.code


def test_rule_adopt_moves_proposed_to_active(project_with_rules: Path):
    from viewer import build_app
    port = _free_port()
    app = build_app(project_with_rules, port=port, api_only=True)
    threading.Thread(target=app.serve_forever, daemon=True).start()
    try:
        time.sleep(0.05)
        assert _post_rule(port, "adopt", "p1") == 200
        rules = json.loads((project_with_rules / ".archie" / "rules.json").read_text())
        proposed = json.loads((project_with_rules / ".archie" / "proposed_rules.json").read_text())
        assert any(r["id"] == "p1" and r.get("source") == "scan-adopted" for r in rules["rules"])
        assert all(r["id"] != "p1" for r in proposed["rules"])
    finally:
        app.shutdown()


# Repeat the harness for: reject, disable, enable, edit (with valid + invalid severity_class)
# and the failure cases: unknown rule_id (409), unknown action (400), invalid JSON body (400).
```

Mirror that pattern for `reject`, `disable`, `enable`, plus:

```python
def test_rule_edit_with_invalid_severity_returns_400(project_with_rules: Path):
    # ... bring up server ...
    code = _post_rule(port, "edit", "r1", patch={"severity_class": "bogus"})
    assert code == 400


def test_rule_unknown_id_returns_409(project_with_rules: Path):
    # ... bring up server ...
    code = _post_rule(port, "adopt", "does-not-exist")
    assert code == 409


def test_rule_unknown_action_returns_400(project_with_rules: Path):
    code = _post_rule(port, "delete", "r1")
    assert code == 400
```

**Step 2: Run + commit**

```bash
python -m pytest tests/test_viewer.py -v
# All passing; should be ~14 tests now
git add tests/test_viewer.py
git commit -m "test(viewer-v2): cover all 5 rule actions and failure modes"
```

---

### Task V2-3.3: Frontend `RuleControls` (lazy)

**Files:**
- Create: `share/viewer/src/components/local/RuleControls.tsx`
- Create: `share/viewer/src/components/local/RuleEditModal.tsx`

**Step 1: Implement RuleControls**

```tsx
import { useState } from 'react'
import RuleEditModal from './RuleEditModal'

interface Props {
  rule: { id: string; description?: string; why?: string; example?: string; severity_class?: string }
  state: 'active' | 'proposed' | 'ignored'
  onAction: (action: 'adopt' | 'reject' | 'disable' | 'enable') => Promise<void>
  onEdit: (patch: Record<string, string>) => Promise<void>
}

export default function RuleControls({ rule, state, onAction, onEdit }: Props) {
  const [editing, setEditing] = useState(false)
  return (
    <div className="flex gap-2 ml-auto">
      {state === 'proposed' && (
        <>
          <button onClick={() => onAction('adopt')} className="text-tangerine-300 hover:text-tangerine-200" title="Adopt">✓</button>
          <button onClick={() => onAction('reject')} className="text-papaya-400 hover:text-papaya-200" title="Reject">✕</button>
        </>
      )}
      {state === 'active' && (
        <>
          <button onClick={() => setEditing(true)} className="text-papaya-300 hover:text-papaya-100" title="Edit">✎</button>
          <button onClick={() => onAction('disable')} className="text-papaya-400 hover:text-papaya-200" title="Disable">🔒</button>
        </>
      )}
      {state === 'ignored' && (
        <button onClick={() => onAction('enable')} className="text-tangerine-300 hover:text-tangerine-200" title="Enable">🔓</button>
      )}
      {editing && (
        <RuleEditModal
          rule={rule}
          onSave={(patch) => onEdit(patch).finally(() => setEditing(false))}
          onCancel={() => setEditing(false)}
        />
      )}
    </div>
  )
}
```

**Step 2: Implement RuleEditModal**

```tsx
import { useState } from 'react'

const SEVERITIES = ['decision_violation', 'pitfall_triggered', 'tradeoff_undermined', 'pattern_divergence', 'mechanical_violation']

interface Props {
  rule: { description?: string; why?: string; example?: string; severity_class?: string }
  onSave: (patch: Record<string, string>) => Promise<void>
  onCancel: () => void
}

export default function RuleEditModal({ rule, onSave, onCancel }: Props) {
  const [description, setDescription] = useState(rule.description || '')
  const [why, setWhy] = useState(rule.why || '')
  const [example, setExample] = useState(rule.example || '')
  const [severity, setSeverity] = useState(rule.severity_class || 'pattern_divergence')

  return (
    <div className="fixed inset-0 bg-ink-950/80 flex items-center justify-center z-50">
      <div className="bg-ink-900 border border-ink-700 rounded-lg p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto">
        <h3 className="text-lg font-semibold mb-4">Edit rule</h3>
        <label className="block mb-2 text-sm text-papaya-300">Description</label>
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} className="w-full bg-ink-800 border border-ink-700 rounded px-3 py-2 mb-3 text-papaya-100" rows={2} />
        <label className="block mb-2 text-sm text-papaya-300">Why</label>
        <textarea value={why} onChange={(e) => setWhy(e.target.value)} className="w-full bg-ink-800 border border-ink-700 rounded px-3 py-2 mb-3 text-papaya-100" rows={4} />
        <label className="block mb-2 text-sm text-papaya-300">Example</label>
        <textarea value={example} onChange={(e) => setExample(e.target.value)} className="w-full bg-ink-800 border border-ink-700 rounded px-3 py-2 mb-3 text-papaya-100 font-mono text-sm" rows={4} />
        <label className="block mb-2 text-sm text-papaya-300">Severity class</label>
        <select value={severity} onChange={(e) => setSeverity(e.target.value)} className="w-full bg-ink-800 border border-ink-700 rounded px-3 py-2 mb-4 text-papaya-100">
          {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <div className="flex gap-3 justify-end">
          <button onClick={onCancel} className="px-4 py-2 text-papaya-300 hover:text-papaya-100">Cancel</button>
          <button onClick={() => onSave({ description, why, example, severity_class: severity })} className="px-4 py-2 bg-tangerine-600 text-ink-900 rounded hover:bg-tangerine-500">Save</button>
        </div>
      </div>
    </div>
  )
}
```

**Step 3: tsc + commit**

```bash
cd share/viewer && npx tsc -b --noEmit
git add share/viewer/src/components/local/RuleControls.tsx share/viewer/src/components/local/RuleEditModal.tsx
git commit -m "feat(viewer-v2): RuleControls + RuleEditModal lazy components"
```

---

### Task V2-3.4: Wire LocalEditContext + Toast in LocalPage

**Files:**
- Modify: `share/viewer/src/pages/LocalPage.tsx`

**Step 1: Replace the `null` provider with a real implementation**

```tsx
import Toast from '@/components/local/Toast'
import { LocalEditContext, type LocalEditCtx } from '@/components/local/context/LocalEditContext'

// inside LocalPage, alongside existing useState calls:
const [toast, setToast] = useState<string | null>(null)
const [bundleVersion, setBundleVersion] = useState(0)  // re-fetch trigger

const ctx: LocalEditCtx = {
  toggleRule: async (id, action) => {
    const res = await fetch('/api/rules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, rule_id: id }),
    })
    if (!res.ok) {
      const { error } = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
      setToast(`Failed: ${error}`)
      return
    }
    setToast(`Rule ${id} ${action}d.`)
    setBundleVersion((v) => v + 1)
  },
  editRule: async (id, patch) => {
    const res = await fetch('/api/rules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'edit', rule_id: id, patch }),
    })
    if (!res.ok) {
      const { error } = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
      setToast(`Failed: ${error}`)
      return
    }
    setToast(`Rule ${id} updated.`)
    setBundleVersion((v) => v + 1)
  },
}

// modify the bundle-fetch useEffect to depend on bundleVersion:
useEffect(() => {
  fetch('/api/bundle').then(...).then((j) => setBundle(j.bundle))
}, [bundleVersion])

// in the report tab body:
<LocalEditContext.Provider value={ctx}>
  <ReportPage bundle={bundle} />
</LocalEditContext.Provider>

// at the bottom of LocalPage's render:
<Toast message={toast} onDismiss={() => setToast(null)} />
```

**Step 2: tsc + commit**

```bash
cd share/viewer && npx tsc -b --noEmit
git add share/viewer/src/pages/LocalPage.tsx
git commit -m "feat(viewer-v2): wire LocalEditContext + bundle re-fetch + Toast"
```

---

### Task V2-3.5: ReportPage renders RuleControls when context is set

**Files:**
- Modify: `share/viewer/src/pages/ReportPage.tsx` (or `share/viewer/src/components/ReportSections.tsx` if rule rendering lives there — read first)

**Step 1: Read where rules render**

```bash
grep -n 'rule\|Rule' share/viewer/src/pages/ReportPage.tsx share/viewer/src/components/ReportSections.tsx | head -40
```

Identify the exact JSX blocks where each rule card is rendered: Architecture Rules, Enforcement Rules (adopted), Development Rules, Infrastructure Rules, Proposed Enforcement Rules. The plan owner (you) should expect 4-5 rule card sites to inject `<RuleControls>` into.

**Step 2: Add the context check + lazy import + per-site injection**

In whichever file renders rule cards, near the top:

```tsx
import { lazy, Suspense, useContext } from 'react'
import { LocalEditContext } from '@/components/local/context/LocalEditContext'

const RuleControls = lazy(() => import('@/components/local/RuleControls'))
```

Inside each rule card render, append:

```tsx
{(() => {
  const ctx = useContext(LocalEditContext)
  if (!ctx) return null
  return (
    <Suspense fallback={null}>
      <RuleControls
        rule={rule}
        state="active"  // or "proposed" or "ignored" depending on the card
        onAction={(action) => ctx.toggleRule(rule.id, action)}
        onEdit={(patch) => ctx.editRule(rule.id, patch)}
      />
    </Suspense>
  )
})()}
```

(If hooks-in-loops linting complains, refactor by hoisting `useContext` to the section's outer component.)

For sections that don't have a clean "ignored" rendering today, this iteration adds one: under the "Enforcement Rules" section, after the adopted list, add an "Ignored Rules" subsection that pulls from `bundle.rules_ignored` (or fetches `/api/ignored-rules` — pick whichever is simplest given the share-viewer's bundle shape).

**Note for the implementer:** if `ignored_rules.json` is not currently in the share viewer's `Bundle` interface, you have two options:
1. Add `rules_ignored?: { rules: any[] }` to `share/viewer/src/lib/api.ts` Bundle interface AND have the viewer.py sidecar populate it via `build_bundle`. Cleaner — single fetch.
2. Have RuleControls / the Enforcement Rules section fetch `/api/ignored-rules` separately. Simpler — touches no shared types.

Recommend option 2 for V2 to keep the share-mode bundle shape unchanged. Add a `GET /api/ignored-rules` endpoint to `viewer.py` that just `_serve_json(_read_rules_file(archie / "ignored_rules.json"))`.

**Step 3: Add `/api/ignored-rules` endpoint**

In `archie/standalone/viewer.py do_GET`:

```python
if parsed.path == "/api/ignored-rules":
    self._serve_json(_read_rules_file(root / ".archie" / "ignored_rules.json"))
    return
```

**Step 4: tsc + commit**

```bash
cd share/viewer && npx tsc -b --noEmit
git add share/viewer/src/pages/ReportPage.tsx share/viewer/src/components/ReportSections.tsx archie/standalone/viewer.py
git commit -m "feat(viewer-v2): inline RuleControls on rule cards + /api/ignored-rules"
```

---

### Task V2-3.6: Iteration 3 verification — including bundle separation invariant

**Step 1: Verify share-mode bundle stays clean**

```bash
cd share/viewer && npm run build
# Then grep the share-built JS chunks:
grep -l 'RuleControls\|RuleEditModal' dist/assets/*.js
# Expected: ONLY in the lazy-load chunks, NOT in index-*.js.
# If RuleControls names appear in index-*.js, something is statically importing local/.
# Trace and fix.
```

**Step 2: Sync + commit asset mirror**

```bash
./scripts/sync_viewer_assets.sh
python3 scripts/verify_sync.py
git add npm-package/assets/viewer/
git commit -m "chore(sync): refresh asset mirror after V2 iteration 3"
```

**Step 3: End-to-end smoke against BabyWeather.Android**

```bash
BW=/Users/hamutarto/DEV/BitRaptors/BabyWeather.Android
node npm-package/bin/archie.mjs $BW
python3 $BW/.archie/viewer.py $BW --port 5855 --no-open &
PID=$!
sleep 1
# Test happy path: adopt then disable then enable a real proposed rule
curl -s http://localhost:5855/api/bundle | python3 -c "
import json, sys, urllib.request
d = json.load(sys.stdin)
proposed = d['bundle'].get('rules_proposed', {}).get('rules', [])
if proposed:
  pid = proposed[0]['id']
  print('proposed rule:', pid)
  req = urllib.request.Request(
    'http://localhost:5855/api/rules',
    data=json.dumps({'action': 'adopt', 'rule_id': pid}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST',
  )
  print('adopt response:', urllib.request.urlopen(req, timeout=2).read())
"
kill $PID; wait
```

Verify the rule actually moved in `.archie/rules.json` and is gone from `proposed_rules.json`.

**Step 4: Manual UI smoke**

Launch `python3 .archie/viewer.py "$PWD"` (the Archie repo itself), open the local viewer in a browser, click adopt/reject/disable/enable on real rules, watch toasts fire and the rule list reconcile.

If everything green: V2 ships.

---

## Total task count

- **Iteration 1** — 5 tasks (1.1 primitives, 1.2 shell, 1.3 backend, 1.4 frontend, 1.5 verify)
- **Iteration 2** — 4 tasks (2.1 backend + tests, 2.2 empty state, 2.3 frontend, 2.4 verify)
- **Iteration 3** — 6 tasks (3.1 backend skeleton, 3.2 backend tests, 3.3 lazy components, 3.4 wire context, 3.5 ReportPage injection, 3.6 verify)

**15 tasks total. Frequent commits — one per task plus a sync-asset-mirror commit at each iteration's verification step.**

## Decisions reference

See `docs/plans/2026-05-09-local-viewer-v2-design.md` for the locked design choices, risk register, and bundle-separation invariant.

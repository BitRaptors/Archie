#!/usr/bin/env python3
"""Archie intent layer — AI-generated per-folder CLAUDE.md via bottom-up DAG.

Analyzes source code folder-by-folder (leaves first, then parents with child context)
to generate architectural descriptions: purpose, patterns, anti-patterns, code examples.

Subcommands:
  prepare        — Build folder DAG and processing plan
  next-ready     — Given done folders, return folders ready to process
  suggest-batches — Group ready folders into efficient subagent batches
  prompt         — Generate intent layer prompt for folder(s)
  merge          — Create/patch CLAUDE.md files with generated content
  inject-scoped  — Project blueprint scoped patterns/guidelines into per-folder
                   CLAUDE.md (component root only) for path-based hard filtering
  extract-guardrails — Scan per-folder CLAUDE.md for maintainer-curated
                   anti-pattern bullets, strip Archie's own marker blocks,
                   write .archie/maintainer_guardrails.json for Wave 2 §11

Run:
  python3 intent_layer.py prepare /path/to/repo [--only-folders folder1,folder2,...]
  python3 intent_layer.py next-ready /path/to/repo [done1 done2 ...]
  python3 intent_layer.py suggest-batches /path/to/repo [ready1 ready2 ...]
  python3 intent_layer.py prompt /path/to/repo --folder src/lib
  python3 intent_layer.py prompt /path/to/repo --folders src/api/routes,src/api/middleware
  python3 intent_layer.py merge /path/to/repo
  python3 intent_layer.py inject-scoped /path/to/repo

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import hashlib
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import _load_json, IgnoreMatcher  # noqa: E402


def _get_components(blueprint: dict) -> list[dict]:
    """Extract component list from blueprint."""
    raw = blueprint.get("components", {})
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get("components", [])
    return []


def _find_component_for_dir(directory: str, components: list[dict]) -> dict | None:
    """Find the best matching component for a directory."""
    best = None
    best_len = -1
    for comp in components:
        loc = (comp.get("location") or comp.get("path") or "").rstrip("/")
        if not loc:
            continue
        if directory == loc or directory.startswith(loc + "/"):
            if len(loc) > best_len:
                best = comp
                best_len = len(loc)
    return best


# ---------------------------------------------------------------------------
# Enrichment-level skip lists
# ---------------------------------------------------------------------------

# Directories to skip during enrichment (generated/data/config-only folders)
_SKIP_ENRICHMENT_DIRS = {
    "output", "data", "dist", "build", ".build", "DerivedData",
    "public", "static", "assets",
    "migrations", "fixtures", "seeds", "__snapshots__",
    "coverage", ".nyc_output",
}

# Extensions to skip when reading file content
_SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".woff", ".woff2", ".ttf", ".eot",
    ".lock", ".map", ".min.js", ".min.css",
    ".pyc", ".pyo", ".class", ".o", ".so", ".dylib",
    ".zip", ".tar", ".gz", ".br",
    ".pdf", ".doc", ".docx",
    ".db", ".sqlite", ".sqlite3",
}

MAX_FILE_SIZE = 15_000  # chars — safety valve for monster files only


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return slug or "project"


def _make_intent_run_id(root: Path) -> str:
    seed = f"{root.resolve()}::{time.time_ns()}".encode("utf-8")
    return hashlib.sha1(seed).hexdigest()[:12]


def _is_source_file(file_path: str) -> bool:
    """Check if a file should be read for enrichment."""
    name = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
    _, _, ext = name.rpartition(".")
    if ext and f".{ext}" in _SKIP_EXTENSIONS:
        return False
    return True


def _should_skip_dir(directory: str) -> bool:
    """Check if any path segment matches the enrichment skip list."""
    parts = directory.split("/")
    return any(part in _SKIP_ENRICHMENT_DIRS for part in parts)


# ---------------------------------------------------------------------------
# prepare — build folder DAG
# ---------------------------------------------------------------------------

def cmd_prepare(root: Path, only_folders: list[str] | None = None):
    """Build folder DAG for bottom-up enrichment."""
    scan = _load_json(root / ".archie" / "scan.json")
    files = scan.get("file_tree", [])

    # Collect directories that have source files. Files tagged by .archiebulk
    # as generated/bulk content (ent codegen, protobuf stubs, minified JS, etc.)
    # don't need folder-level CLAUDE.md guidance — an agent editing a dir that
    # contains ONLY generated code isn't writing architecture, it's running a
    # codegen tool. Filter them here so the DAG only covers hand-authored code.
    dir_files: dict[str, list[str]] = defaultdict(list)
    for f in files:
        p = f.get("path", "")
        if "/" in p:
            parent = str(Path(p).parent)
        else:
            continue  # skip root files
        if f.get("bulk"):
            continue  # bulk-tagged files are inventory-only — no enrichment target
        dir_files[parent].append(p)

    # Filter: skip only enrichment-irrelevant directories (build, dist, etc.)
    # Any folder with at least 1 hand-authored file qualifies — wherever we
    # write code by hand, we need a CLAUDE.md.  Safety valve: depth > 8 with
    # exactly 1 file is noise.
    qualifying = []
    for d, flist in sorted(dir_files.items()):
        if not flist:
            continue
        if _should_skip_dir(d):
            continue
        depth = d.count("/") + 1
        if depth > 8 and len(flist) == 1:
            continue
        qualifying.append(d)

    qualifying_set = set(qualifying)

    # Structural qualification: intermediate directories that have qualifying
    # children but no direct source files still deserve a CLAUDE.md that
    # describes the purpose and responsibility of that layer.
    # Use a work-queue so newly promoted ancestors are also processed.
    promote_queue = list(qualifying)
    while promote_queue:
        d = promote_queue.pop()
        p = Path(d).parent
        while str(p) != "." and str(p) != p.root:
            ancestor = str(p)
            if ancestor in qualifying_set:
                break  # already qualified
            if _should_skip_dir(ancestor):
                break
            # This ancestor has qualifying descendants — promote it
            qualifying.append(ancestor)
            qualifying_set.add(ancestor)
            promote_queue.append(ancestor)
            if ancestor not in dir_files:
                dir_files[ancestor] = []  # structural folder, no direct files
            p = p.parent

    # Calculate folder content sizes from file system
    folder_sizes: dict[str, int] = {}
    for d in qualifying:
        total = 0
        for fp in dir_files[d]:
            if _is_source_file(fp):
                try:
                    total += min((root / fp).stat().st_size, MAX_FILE_SIZE)
                except OSError:
                    pass
        folder_sizes[d] = total

    # Build parent→children map: find closest qualifying ancestor for each folder
    folder_children: dict[str, list[str]] = {d: [] for d in qualifying}
    for d in qualifying:
        # Walk up the path to find the closest qualifying ancestor
        p = Path(d).parent
        while str(p) != "." and str(p) != p.root:
            ancestor = str(p)
            if ancestor in qualifying_set:
                folder_children[ancestor].append(d)
                break
            p = p.parent

    leaves = sorted(d for d in qualifying if not folder_children[d])
    # Roots: folders whose closest qualifying ancestor doesn't exist
    roots = []
    for d in qualifying:
        p = Path(d).parent
        is_root = True
        while str(p) != "." and str(p) != p.root:
            if str(p) in qualifying_set:
                is_root = False
                break
            p = p.parent
        if is_root:
            roots.append(d)
    roots = sorted(roots)

    # Mark structural folders (no direct source files, only qualifying children)
    structural_set = {d for d in qualifying if not dir_files.get(d)}

    plan = {
        "version": 2,
        "run_id": _make_intent_run_id(root),
        "project_slug": _slugify(root.name),
        "folders": {
            d: {
                "children": sorted(folder_children[d]),
                "depth": d.count("/") + 1,
                "size_chars": folder_sizes.get(d, 0),
                **({"structural": True} if d in structural_set else {}),
            }
            for d in qualifying
        },
        "leaves": leaves,
        "roots": roots,
    }

    # Incremental mode: mark only affected folders + parent chain as dirty
    if only_folders:
        dirty = set()
        for f in only_folders:
            # Add the folder itself
            if f in qualifying_set:
                dirty.add(f)
            # Add all qualifying ancestors
            parts = Path(f).parts
            for i in range(1, len(parts)):
                ancestor = str(Path(*parts[:i]))
                if ancestor in qualifying_set:
                    dirty.add(ancestor)
        plan["dirty_folders"] = sorted(dirty)
        print(f"Incremental: {len(dirty)} dirty folders (of {len(qualifying)} total)", file=sys.stderr)

    # Save
    archie_dir = root / ".archie"
    archie_dir.mkdir(exist_ok=True)
    out_path = archie_dir / "enrich_batches.json"
    out_path.write_text(json.dumps(plan, indent=2))

    print(f"Enrichment DAG: {len(qualifying)} folders, {len(leaves)} leaves, {len(roots)} roots", file=sys.stderr)
    print(f"Saved to: {out_path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# State tracking — persistent done list
# ---------------------------------------------------------------------------

_STATE_FILE = "enrich_state.json"


@contextmanager
def _state_lock(root: Path):
    lock_path = root / ".archie" / "enrich_state.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lock_path, "w")
    try:
        try:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass
        yield
    finally:
        try:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except (ImportError, OSError):
            pass
        fh.close()


def _load_state(root: Path) -> dict:
    """Load enrichment state (done folders, wave count)."""
    state_path = root / ".archie" / _STATE_FILE
    if state_path.exists():
        try:
            data = json.loads(state_path.read_text())
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"done": [], "wave": 0}


def _save_state(root: Path, state: dict):
    """Save state atomically — write to temp file then rename."""
    archie_dir = root / ".archie"
    archie_dir.mkdir(parents=True, exist_ok=True)
    state_path = archie_dir / _STATE_FILE
    tmp = state_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    os.replace(tmp, state_path)


def cmd_mark_done(root: Path, folders: list[str]):
    """Mark folders as done in persistent state."""
    with _state_lock(root):
        state = _load_state(root)
        done_set = set(state.get("done", []))
        added = 0
        for f in folders:
            if f not in done_set:
                done_set.add(f)
                added += 1
        state["done"] = sorted(done_set)
        state["wave"] = int(state.get("wave", 0) or 0) + 1
        _save_state(root, state)
        print(f"Marked {added} folders done (total: {len(done_set)}, wave {state['wave']})", file=sys.stderr)


def cmd_reset_state(root: Path):
    """Reset enrichment state for a fresh run.

    Deletes:
    - `.archie/enrich_state.json` (done list + wave counter)
    - `.archie/enrichments/` directory contents (per-batch enrichment JSONs)

    Removing the enrichments directory keeps the fresh-start path in the
    slash commands from needing `rm -rf` (which is not in the default
    Claude Code permission allowlist) — wiping state is this function's
    job, regardless of which files back it.
    """
    state_path = root / ".archie" / _STATE_FILE
    if state_path.exists():
        state_path.unlink()
    enrichments_dir = root / ".archie" / "enrichments"
    if enrichments_dir.is_dir():
        import shutil
        shutil.rmtree(enrichments_dir)
    print("Enrichment state reset (enrich_state.json + enrichments/ directory)", file=sys.stderr)


# ---------------------------------------------------------------------------
# Deep scan state tracking
# ---------------------------------------------------------------------------

_DEEP_SCAN_STATE_FILE = "deep_scan_state.json"


def _config_path(root: Path) -> Path:
    return root / ".archie" / "archie_config.json"


def cmd_scan_config(root: Path, action: str):
    """Manage .archie/archie_config.json — the persisted scope + monorepo metadata.

    Actions:
      read       — print existing config JSON to stdout, exit 1 if missing
      write      — stdin JSON merged into config; requires schema_version, scope, monorepo_type
      validate   — exit 0 if config matches reality, 1 if drift or missing

    Config shape:
      {
        "schema_version": 1,
        "scope": "single" | "whole" | "per-package" | "hybrid",
        "workspaces": ["apps/webui", ...],
        "monorepo_type": "bun-workspaces" | ... | "none",
        "reconfigured_at": "ISO-8601 UTC"
      }
    """
    path = _config_path(root)
    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            existing = {}

    if action == "read":
        if not path.exists():
            print(f"No scan-config at {path}", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(existing, indent=2))
        return

    if action == "write":
        try:
            payload = json.loads(sys.stdin.read())
        except json.JSONDecodeError as e:
            print(f"Invalid JSON on stdin: {e}", file=sys.stderr)
            sys.exit(1)

        if not isinstance(payload, dict):
            print("Config must be a JSON object", file=sys.stderr)
            sys.exit(1)

        allowed_scopes = {"single", "whole", "per-package", "hybrid"}
        scope = payload.get("scope")
        if scope not in allowed_scopes:
            print(f"scope must be one of {sorted(allowed_scopes)}", file=sys.stderr)
            sys.exit(1)

        workspaces = payload.get("workspaces")
        if workspaces is None:
            workspaces = existing.get("workspaces", [])
        if not isinstance(workspaces, list):
            print("workspaces must be an array", file=sys.stderr)
            sys.exit(1)
        if scope in ("per-package", "hybrid") and len(workspaces) == 0:
            print(f"scope={scope} requires non-empty workspaces[]", file=sys.stderr)
            sys.exit(1)

        monorepo_type = payload.get("monorepo_type", existing.get("monorepo_type", "none"))
        if not isinstance(monorepo_type, str):
            print("monorepo_type must be a string", file=sys.stderr)
            sys.exit(1)

        # Merge preserving unknown keys (forward-compat)
        from datetime import datetime, timezone
        merged = {**existing}
        merged.update(payload)
        merged["schema_version"] = 1
        merged["scope"] = scope
        merged["workspaces"] = list(workspaces)
        merged["monorepo_type"] = monorepo_type
        merged["reconfigured_at"] = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(merged, indent=2) + "\n")
        tmp.replace(path)
        print(json.dumps(merged, indent=2))
        return

    if action == "validate":
        if not path.exists():
            print(f"No scan-config at {path}", file=sys.stderr)
            sys.exit(1)

        scope = existing.get("scope")
        if scope not in {"single", "whole", "per-package", "hybrid"}:
            print(f"Invalid scope in config: {scope}", file=sys.stderr)
            sys.exit(1)

        # Check each listed workspace exists
        missing = []
        for ws in existing.get("workspaces", []):
            if not (root / ws).is_dir():
                missing.append(ws)
        if missing:
            print(
                "Workspace drift detected — the following workspaces no longer exist:\n  "
                + "\n  ".join(missing)
                + "\nRun the command with --reconfigure to rebuild the scope config.",
                file=sys.stderr,
            )
            sys.exit(1)
        return

    print(f"Unknown scan-config action: {action}", file=sys.stderr)
    sys.exit(1)


# --- Test snapshots (safe repeated single-step re-runs) ---------------------
# Static installed .archie/ entries that pipeline steps never mutate — excluded
# from test snapshots (re-copying them is wasteful and restoring code is wrong).
_SNAPSHOT_ARCHIE_SKIP = {
    ".test_snapshots", "__pycache__", "workflow", "viewer", "_install_pkg", "hooks",
}
# Generated artifacts OUTSIDE .archie/ that a step mutates AND that are gitignored
# (so git can't restore them — the snapshot must). Paths relative to project root.
_SNAPSHOT_OUTSIDE = [".claude/hooks", ".claude/settings.local.json", ".codex/hooks.json"]
# Generated but git-TRACKED — restore via git, not the snapshot (don't duplicate git).
_SNAPSHOT_GIT_DEFERRED = ["CLAUDE.md", "AGENTS.md", ".claude/rules", "per-folder CLAUDE.md"]


def _snapshot_archie_entries(archie_dir: Path) -> list[Path]:
    """Mutable .archie/ top-level entries to capture (skips static tooling)."""
    if not archie_dir.is_dir():
        return []
    out = []
    for p in sorted(archie_dir.iterdir()):
        if p.name in _SNAPSHOT_ARCHIE_SKIP or p.suffix == ".py":
            continue
        out.append(p)
    return out


def _valid_snapshot_label(label: str | None) -> bool:
    return bool(label) and label not in (".", "..") and all(
        c.isalnum() or c in "._-" for c in label
    )


def cmd_deep_scan_state(root: Path, action: str, step: int | None = None, label: str | None = None):
    """Manage deep scan state for resume capability.

    Actions:
      init            — reset state for fresh run
      complete-step N — mark step N as completed
      read            — print current state as JSON to stdout
      check-prereqs N — validate artifacts exist for step N; also warns (stderr)
                        when the ledger shows step N-1 was never completed, or a
                        prereq artifact predates this run (stale-input signal)
      snapshot <label>   — capture all mutable pipeline state into
                           .archie/.test_snapshots/<label>/ (for safe repeated
                           single-step re-runs via --from N). Git-tracked
                           generated docs/rules are NOT captured — restore those
                           via git (the command prints how).
      restore <label>    — restore a snapshot (exact within captured scope)
      list-snapshots     — list available snapshots as JSON
      save-context    — stdin JSON merged into state["run_context"]; stores
                        shell-recoverable state (scope, intent_layer, scan_mode,
                        project_root, workspaces, monorepo_type, start_step)
                        so /compact + --continue can rehydrate without relying
                        on the orchestrator's in-context memory.
      save-baseline   — stash the current git SHA + scan mode (existing)
      detect-changes  — emit incremental mode + changed files (existing)

    State file shape:
      {
        "completed_steps": [1, 2, …],
        "last_completed": N,
        "status": "in_progress" | "completed" | "none",
        "started_at": ISO,
        "run_context": {              # present after save-context call
          "scope": "whole|per-package|hybrid|single",
          "intent_layer": "yes|no",
          "scan_mode": "full|incremental",
          "project_root": "/abs/path",
          "workspaces": ["apps/…"],
          "monorepo_type": "…",
          "start_step": 1
        }
      }
    """
    state_path = root / ".archie" / _DEEP_SCAN_STATE_FILE

    def _load_state() -> dict:
        try:
            data = json.loads(state_path.read_text())
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
        return {"completed_steps": [], "last_completed": 0, "status": "none"}

    if action == "init":
        from datetime import datetime, timezone
        state = {
            "completed_steps": [],
            "last_completed": 0,
            "status": "in_progress",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "run_context": {},
        }
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2))
        print("Deep scan state initialized", file=sys.stderr)

    elif action == "complete-step":
        if step is None:
            print("Error: step number required", file=sys.stderr)
            sys.exit(1)
        state = _load_state()
        state.setdefault("completed_steps", [])
        if step not in state["completed_steps"]:
            state["completed_steps"].append(step)
            state["completed_steps"].sort()
        state["last_completed"] = step
        state["status"] = "completed" if step == 9 else "in_progress"
        state_path.write_text(json.dumps(state, indent=2))

        # Also mark the matching telemetry step as finished — captures an
        # accurate completed_at NOW, before any /compact pause can shift the
        # mark-auto-close baseline. Idempotent: finish_step is a no-op if the
        # step is already closed.
        _STEP_NAMES = {
            1: "scan", 2: "read", 3: "wave1", 4: "merge",
            5: "wave2_synthesis", 6: "rule_synthesis",
            7: "intent_layer", 8: "cleanup", 9: "finalize",
        }
        step_name = _STEP_NAMES.get(step)
        if step_name:
            try:
                import sys as _sys
                _sys.path.insert(0, str(Path(__file__).parent))
                import telemetry as _telem
                _telem.finish_step(root, step_name)
            except Exception as exc:
                # Telemetry is informational; never block the pipeline.
                print(f"telemetry finish skipped for step {step} ({step_name}): {exc}", file=sys.stderr)

        print(f"Step {step} completed", file=sys.stderr)

    elif action == "save-context":
        try:
            payload = json.loads(sys.stdin.read())
        except json.JSONDecodeError as e:
            print(f"Invalid JSON on stdin: {e}", file=sys.stderr)
            sys.exit(1)
        if not isinstance(payload, dict):
            print("save-context expects a JSON object on stdin", file=sys.stderr)
            sys.exit(1)
        state = _load_state()
        context = state.get("run_context") or {}
        if not isinstance(context, dict):
            context = {}
        # Merge (new values win); drop keys set explicitly to null
        for k, v in payload.items():
            if v is None:
                context.pop(k, None)
            else:
                context[k] = v
        state["run_context"] = context
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2))
        print(f"Run context saved: {sorted(context.keys())}", file=sys.stderr)

    elif action == "save-run-context":
        # Shell-friendly alternative to save-context: accepts the canonical
        # deep-scan run-context fields as CLI flags so callers don't have to
        # build JSON in bash (which would require inline python for the
        # workspaces array). Reads workspaces from --workspaces-file as a
        # newline-separated list.
        #
        # NOTE: `project_root` is intentionally NOT a persisted field. The
        # Resume Prelude always rehydrates PROJECT_ROOT="$PWD" — the slash
        # command invocation contract requires the agent to be at the repo
        # root anyway (state lives in <root>/.archie/deep_scan_state.json,
        # so you can't find the state from anywhere else). Storing the
        # absolute path would leak machine-specific info (e.g. /Users/foo/)
        # into committable state files. The flag is accepted + silently
        # discarded for backward-compat with older slash-command prose
        # that still passes --project-root.
        fields: dict[str, str | None] = {
            "scope": None,
            "intent_layer": None,
            "scan_mode": None,
            "monorepo_type": None,
            "start_step": None,
            "depth": None,
        }
        workspaces_from_stdin = False
        # CLI layout: [script, "deep-scan-state", <root>, "save-run-context", ...flags...]
        # So flags start at sys.argv[4].
        argv = sys.argv[4:]
        i = 0
        while i < len(argv):
            a = argv[i]
            if a == "--workspaces-from-stdin":
                workspaces_from_stdin = True
                i += 1
                continue
            if a.startswith("--"):
                key = a[2:].replace("-", "_")
                # Silently accept (and drop) --project-root so callers on
                # older slash-command prose don't error out.
                if key == "project_root" and i + 1 < len(argv):
                    i += 2
                    continue
                if key in fields and i + 1 < len(argv):
                    fields[key] = argv[i + 1]
                    i += 2
                    continue
            i += 1
        payload: dict = {}
        for k in ("scope", "intent_layer", "scan_mode", "monorepo_type", "depth"):
            v = fields[k]
            if v is not None:
                payload[k] = v
        if fields["start_step"] is not None:
            try:
                payload["start_step"] = int(fields["start_step"])
            except ValueError:
                payload["start_step"] = fields["start_step"]
        if workspaces_from_stdin:
            raw = sys.stdin.read()
            payload["workspaces"] = [line for line in raw.splitlines() if line.strip()]
        state = _load_state()
        context = state.get("run_context") or {}
        if not isinstance(context, dict):
            context = {}
        for k, v in payload.items():
            context[k] = v
        # Defensive cleanup: if an older version of Archie wrote a machine-
        # specific project_root into this file, scrub it now so the state
        # becomes committable.
        context.pop("project_root", None)
        state["run_context"] = context
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2))
        print(f"Run context saved: {sorted(context.keys())}", file=sys.stderr)

    elif action == "read":
        if state_path.exists():
            print(state_path.read_text())
        else:
            print(json.dumps({
                "completed_steps": [], "last_completed": 0,
                "status": "none", "run_context": {},
            }))

    elif action == "check-prereqs":
        if step is None:
            print("Error: step number required", file=sys.stderr)
            sys.exit(1)
        prereqs = {
            1: [],
            2: [".archie/scan.json"],
            3: [".archie/scan.json"],
            4: [],
            5: [".archie/blueprint_raw.json"],
            6: [".archie/blueprint.json"],
            7: [".archie/blueprint.json", ".archie/scan.json"],
            8: [],
            9: [".archie/blueprint.json"],
        }
        # Ledger cross-check (general, all steps): --from N trusts artifact
        # existence only. Consult the ledger we already maintain and make a
        # skipped/never-completed upstream step impossible to miss. Warnings go
        # to stderr so the JSON stdout contract is untouched; never blocking
        # (--from is an explicit override).
        state = _load_state()
        last = state.get("last_completed", 0) or 0
        if isinstance(step, int) and last < step - 1:
            gap = f"{last + 1}" if last + 1 == step - 1 else f"{last + 1}-{step - 1}"
            print(
                f"⚠️  --from {step}: ledger last_completed={last} — step(s) {gap} were "
                f"never completed in this run. Upstream artifacts may be stale or "
                f"inconsistent. Proceeding anyway (explicit override).",
                file=sys.stderr,
            )
        started = state.get("started_at")
        if started:
            try:
                from datetime import datetime
                started_ts = datetime.fromisoformat(started).timestamp()
                for p in prereqs.get(step, []):
                    fp = root / p
                    if fp.exists() and fp.stat().st_mtime < started_ts:
                        print(
                            f"⚠️  prereq {p} predates this run (started_at={started}) "
                            f"— likely stale input.",
                            file=sys.stderr,
                        )
            except (ValueError, OSError):
                pass

        missing = [p for p in prereqs.get(step, []) if not (root / p).exists()]
        if missing:
            print(json.dumps({"ok": False, "missing": missing, "step": step}))
            sys.exit(1)
        else:
            print(json.dumps({"ok": True, "step": step}))
    elif action in ("snapshot", "restore"):
        import shutil
        archie_dir = root / ".archie"
        if not _valid_snapshot_label(label):
            print("Error: snapshot label required (alphanumerics, '.', '-', '_' only)", file=sys.stderr)
            sys.exit(1)
        snap_root = archie_dir / ".test_snapshots" / label

        if action == "snapshot":
            if snap_root.exists():
                shutil.rmtree(snap_root)
            (snap_root / "archie").mkdir(parents=True)
            for p in _snapshot_archie_entries(archie_dir):
                dest = snap_root / "archie" / p.name
                if p.is_dir():
                    shutil.copytree(p, dest)
                else:
                    shutil.copy2(p, dest)
            captured_outside = []
            for rel in _SNAPSHOT_OUTSIDE:
                src = root / rel
                if not src.exists():
                    continue
                dest = snap_root / "outside" / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                if src.is_dir():
                    shutil.copytree(src, dest)
                else:
                    shutil.copy2(src, dest)
                captured_outside.append(rel)
            import subprocess
            try:
                sha = subprocess.run(
                    ["git", "-C", str(root), "rev-parse", "HEAD"],
                    capture_output=True, text=True, timeout=5,
                ).stdout.strip()
            except Exception:
                sha = ""
            from datetime import datetime, timezone
            manifest = {
                "label": label,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "archie_entries": [p.name for p in _snapshot_archie_entries(archie_dir)],
                "outside": captured_outside,
                "git_deferred": _SNAPSHOT_GIT_DEFERRED,
                "git_sha": sha,
            }
            (snap_root / "manifest.json").write_text(json.dumps(manifest, indent=2))
            print(f"Snapshot '{label}' captured ({len(manifest['archie_entries'])} .archie entries, "
                  f"{len(captured_outside)} outside files).", file=sys.stderr)
            print("Note: generated docs/rules are git-tracked and NOT in the snapshot — "
                  "restore those with git (see `restore` output).", file=sys.stderr)

        else:  # restore
            if not snap_root.is_dir():
                print(f"Error: no snapshot '{label}' under .archie/.test_snapshots/", file=sys.stderr)
                sys.exit(1)
            # 1. Clear current in-scope .archie state so files created since the
            #    snapshot are undone (exact restore within captured scope). The
            #    snapshot dir itself is in the skip set, so it survives.
            for p in _snapshot_archie_entries(archie_dir):
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
            # 2. Copy the snapshot's .archie state back.
            snap_archie = snap_root / "archie"
            if snap_archie.is_dir():
                for p in sorted(snap_archie.iterdir()):
                    dest = archie_dir / p.name
                    if p.is_dir():
                        shutil.copytree(p, dest)
                    else:
                        shutil.copy2(p, dest)
            # 3. Restore captured outside files (remove current, copy back).
            try:
                manifest = json.loads((snap_root / "manifest.json").read_text())
            except (OSError, json.JSONDecodeError):
                manifest = {"outside": []}
            for rel in manifest.get("outside", []):
                cur = root / rel
                if cur.is_dir():
                    shutil.rmtree(cur, ignore_errors=True)
                elif cur.exists():
                    cur.unlink()
                src = snap_root / "outside" / rel
                if src.exists():
                    cur.parent.mkdir(parents=True, exist_ok=True)
                    if src.is_dir():
                        shutil.copytree(src, cur)
                    else:
                        shutil.copy2(src, cur)
            print(f"Snapshot '{label}' restored.", file=sys.stderr)
            print("Generated docs/rules are git-tracked (not snapshotted). To reset them too:",
                  file=sys.stderr)
            print("  git checkout -- CLAUDE.md AGENTS.md .claude/rules", file=sys.stderr)
            print("  (plus any per-folder CLAUDE.md the Intent Layer regenerated)", file=sys.stderr)

    elif action == "list-snapshots":
        snaps_dir = root / ".archie" / ".test_snapshots"
        items = []
        if snaps_dir.is_dir():
            for d in sorted(snaps_dir.iterdir()):
                if not d.is_dir():
                    continue
                created = ""
                try:
                    created = json.loads((d / "manifest.json").read_text()).get("created_at", "")
                except (OSError, json.JSONDecodeError):
                    pass
                items.append({"label": d.name, "created_at": created})
        print(json.dumps({"snapshots": items}, indent=2))

    elif action == "save-baseline":
        import subprocess
        try:
            sha = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
        except Exception:
            sha = ""
        from datetime import datetime, timezone
        marker = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "commit_sha": sha,
            "mode": sys.argv[4] if len(sys.argv) > 4 else "full",
        }
        marker_path = root / ".archie" / "last_deep_scan.json"
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(json.dumps(marker, indent=2), encoding="utf-8")
        print(f"Baseline saved: {sha[:8] if sha else 'no-git'}", file=sys.stderr)

    elif action == "detect-changes":
        import subprocess
        marker_path = root / ".archie" / "last_deep_scan.json"
        if not marker_path.exists():
            print(json.dumps({"mode": "full", "reason": "no previous deep scan"}))
            return
        try:
            marker = json.loads(marker_path.read_text())
        except (json.JSONDecodeError, OSError):
            print(json.dumps({"mode": "full", "reason": "corrupt baseline marker"}))
            return
        sha = marker.get("commit_sha", "")
        if not sha:
            print(json.dumps({"mode": "full", "reason": "no commit SHA in marker"}))
            return
        # Check if SHA still exists in repo
        try:
            check = subprocess.run(
                ["git", "-C", str(root), "cat-file", "-t", sha],
                capture_output=True, text=True, timeout=5,
            )
            if check.returncode != 0:
                print(json.dumps({"mode": "full", "reason": f"baseline commit {sha[:8]} no longer in repo"}))
                return
        except Exception:
            print(json.dumps({"mode": "full", "reason": "git check failed"}))
            return
        # Get changed files
        try:
            result = subprocess.run(
                ["git", "-C", str(root), "diff", "--name-only", sha + "..HEAD"],
                capture_output=True, text=True, timeout=10,
            )
            changed = [f for f in result.stdout.strip().split("\n") if f]
        except Exception:
            print(json.dumps({"mode": "full", "reason": "git diff failed"}))
            return
        # Honor .archieignore/.gitignore. git diff lists tracked files even
        # when they're .archieignore'd (git doesn't know that file), so
        # vendored/generated paths would otherwise count toward the
        # incremental threshold AND get read by the Risk agent's recency
        # sweep. Best-effort: a broken ignore file must not kill detection.
        try:
            matcher = IgnoreMatcher(root)
            changed = [
                f for f in changed
                if not matcher.is_ignored(f.replace(os.sep, "/"))
            ]
        except Exception:
            pass
        # Count total files
        scan = _load_json(root / ".archie" / "scan.json")
        total = len(scan.get("file_tree", []))
        ratio = len(changed) / max(total, 1)
        # Thresholds
        if len(changed) > 30 or ratio > 0.20:
            mode = "full"
            reason = f"{len(changed)} files changed ({ratio:.0%}), exceeds threshold"
        elif len(changed) == 0:
            mode = "incremental"
            reason = "no files changed since last deep scan"
        else:
            mode = "incremental"
            reason = f"{len(changed)} files changed ({ratio:.0%})"
        # Compute affected folders (every ancestor of every changed file)
        affected_folders = set()
        for f in changed:
            parts = Path(f).parts
            for i in range(1, len(parts)):
                affected_folders.add(str(Path(*parts[:i])))
        print(json.dumps({
            "mode": mode,
            "reason": reason,
            "changed_files": changed,
            "changed_count": len(changed),
            "total_files": total,
            "ratio": round(ratio, 4),
            "affected_folders": sorted(affected_folders),
        }))

    else:
        print(f"Unknown action: {action}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# next-ready — DAG scheduler
# ---------------------------------------------------------------------------

def cmd_next_ready(root: Path, done_folders: list[str]):
    """Given completed folders, return folders whose children are ALL done.

    If no done_folders are passed as CLI args, reads from persistent state file.
    """
    plan = _load_json(root / ".archie" / "enrich_batches.json")
    folders = plan.get("folders", {})

    # Use persistent state if no explicit done list
    if not done_folders:
        state = _load_state(root)
        done_folders = state.get("done", [])

    done_set = set(done_folders)

    ready = []
    for folder, info in folders.items():
        if folder in done_set:
            continue
        children = info.get("children", [])
        if all(c in done_set for c in children):
            ready.append(folder)

    # In incremental mode, only return dirty folders
    dirty = set(plan.get("dirty_folders", []))
    if dirty:
        ready = [f for f in ready if f in dirty]

    print(json.dumps(sorted(ready)))


# ---------------------------------------------------------------------------
# suggest-batches — group ready folders for parallel subagent calls
# ---------------------------------------------------------------------------

BATCH_TOKEN_BUDGET = 100_000  # ~400KB chars, conservative for 200K Sonnet context
CHARS_PER_TOKEN = 4
MAX_FOLDERS_PER_BATCH = 5


def cmd_suggest_batches(root: Path, ready_folders: list[str]):
    """Group ready folders into efficient batches for parallel subagent calls."""
    plan = _load_json(root / ".archie" / "enrich_batches.json")
    folders_info = plan.get("folders", {})

    # Group by parent directory (siblings batch well together)
    by_parent: dict[str, list[str]] = defaultdict(list)
    for f in ready_folders:
        parent = str(Path(f).parent)
        by_parent[parent].append(f)

    batches = []
    for parent, siblings in sorted(by_parent.items()):
        current_batch: list[str] = []
        current_size = 0
        for folder in sorted(siblings):
            folder_size = folders_info.get(folder, {}).get("size_chars", 0)
            at_budget = (current_size + folder_size) / CHARS_PER_TOKEN > BATCH_TOKEN_BUDGET
            at_max = len(current_batch) >= MAX_FOLDERS_PER_BATCH
            if current_batch and (at_budget or at_max):
                batches.append(current_batch)
                current_batch = []
                current_size = 0
            current_batch.append(folder)
            current_size += folder_size
        if current_batch:
            batches.append(current_batch)

    result = [{"id": f"w{i}", "folders": b} for i, b in enumerate(batches)]

    # Summary to stderr
    total_folders = sum(len(b["folders"]) for b in result)
    print(f"Batches: {len(result)} batches, {total_folders} folders total", file=sys.stderr)
    for b in result:
        preview = ", ".join(b["folders"][:3])
        if len(b["folders"]) > 3:
            preview += f", ... (+{len(b['folders']) - 3} more)"
        print(f"  {b['id']}: {len(b['folders'])} folders ({preview})", file=sys.stderr)

    print(json.dumps(result))


# ---------------------------------------------------------------------------
# prompt — generate enrichment prompt for folder(s)
# ---------------------------------------------------------------------------

def _read_file_content(root: Path, rel_path: str) -> str:
    """Read a source file. Truncates only if over MAX_FILE_SIZE."""
    try:
        full = root / rel_path
        if not full.exists() or not full.is_file():
            return ""
        text = full.read_text(errors="replace")
        if len(text) > MAX_FILE_SIZE:
            text = text[:MAX_FILE_SIZE] + "\n... (truncated)"
        return text
    except (OSError, UnicodeDecodeError):
        return ""


def _inject_child_summaries(prompt_parts: list[str], folder: str, child_summaries_dir: str, plan: dict):
    """Inject rich child summaries into the prompt for a folder."""
    child_dir = Path(child_summaries_dir)
    if not child_dir.is_dir():
        return

    # Get this folder's children from the DAG
    folder_info = plan.get("folders", {}).get(folder, {})
    child_folders = set(folder_info.get("children", []))
    if not child_folders:
        return

    # Scan enrichment files for matching children
    for child_file in sorted(child_dir.iterdir()):
        if not child_file.name.endswith(".json"):
            continue
        try:
            child_data = json.loads(child_file.read_text())
            for child_path, child_info in child_data.items():
                if child_path not in child_folders:
                    continue
                prompt_parts.append(f"### Child: `{child_path}`")
                if child_info.get("purpose"):
                    prompt_parts.append(f"**Purpose:** {child_info['purpose']}")
                patterns = child_info.get("patterns", [])
                if patterns:
                    names = [p["name"] for p in patterns if isinstance(p, dict) and p.get("name")]
                    if names:
                        prompt_parts.append(f"**Patterns:** {', '.join(names)}")
                decisions = child_info.get("decisions", [])
                if decisions:
                    decs = [d["decision"] for d in decisions if isinstance(d, dict) and d.get("decision")]
                    if decs:
                        prompt_parts.append(f"**Decisions:** {'; '.join(decs)}")
                anti = child_info.get("anti_patterns", [])
                if anti:
                    prompt_parts.append(f"**Anti-patterns:** {'; '.join(anti[:5])}")
                guides = child_info.get("key_file_guides", [])
                if guides:
                    files = [g["file"] for g in guides if isinstance(g, dict) and g.get("file")]
                    if files:
                        prompt_parts.append(f"**Key files:** {', '.join(files)}")
                prompt_parts.append("")
        except (json.JSONDecodeError, OSError):
            pass


def cmd_prompt(root: Path, folders: list[str], child_summaries_dir: str | None = None):
    """Generate enrichment prompt for one or more folders, output to stdout."""
    plan = _load_json(root / ".archie" / "enrich_batches.json")
    blueprint = _load_json(root / ".archie" / "blueprint.json")
    scan = _load_json(root / ".archie" / "scan.json")
    components = _get_components(blueprint)

    # Build file index
    files_by_dir: dict[str, list[str]] = defaultdict(list)
    for f in scan.get("file_tree", []):
        p = f.get("path", "")
        if "/" in p:
            parent = str(Path(p).parent)
            files_by_dir[parent].append(p)

    # Build prompt
    prompt_parts = []
    prompt_parts.append("## Folder Architecture Description")
    prompt_parts.append("")
    prompt_parts.append("Describe each folder's architecture so an AI coding agent can write correct code here without reading every file first.")
    prompt_parts.append("Answer: What is this folder? What does it contain? How is code structured here? What patterns must new code follow? What would break if done wrong?")
    prompt_parts.append("")
    prompt_parts.append("Be specific: reference actual function names, actual file names, actual patterns you see in the code.")
    prompt_parts.append("")
    prompt_parts.append("For each folder, return a JSON object with these fields:")
    prompt_parts.append("- purpose: 1-2 sentence summary — what this folder does, its role in the system, its primary constraint")
    prompt_parts.append("- patterns: list of {name, description, example} — max 7. Architectural patterns that MUST be followed when adding code here. Each mechanically verifiable.")
    prompt_parts.append("- key_file_guides: list of {file, role, watch_for} — max 8. Per-file role and foot-guns")
    prompt_parts.append("- anti_patterns: list of strings — max 5. Things that would break the architecture if done here")
    prompt_parts.append("- decisions: list of {decision, rationale} — max 3. Why the code is structured this way")
    prompt_parts.append("- code_examples: list of {scenario, code} — max 1. The SINGLE most representative code pattern. Use actual imports.")
    prompt_parts.append("")
    prompt_parts.append("## Line Budget")
    prompt_parts.append("")
    prompt_parts.append("~80 lines per folder. Every CLAUDE.md is loaded into Claude's context window — bloated files waste tokens.")
    prompt_parts.append("Density over completeness. One precise sentence beats three vague ones.")
    prompt_parts.append("Prioritize: purpose > patterns > key_files > anti_patterns > decisions > code_example.")
    prompt_parts.append("Omit any field where you have nothing code-grounded to say — empty arrays are fine.")
    prompt_parts.append("")
    prompt_parts.append("## Rules")
    prompt_parts.append("")
    prompt_parts.append("1. Derive patterns from ACTUAL code — not generic best practices")
    prompt_parts.append("2. Every pattern must be mechanically verifiable by a code reviewer")
    prompt_parts.append("3. Reference ONLY files provided below. If you cannot ground a claim in code you see, skip it")
    prompt_parts.append("4. If child folder summaries are provided, add cross-cutting insights — don't repeat what children cover")
    prompt_parts.append("5. If this folder already has a CLAUDE.md with manual notes, incorporate those insights — don't discard them")
    prompt_parts.append("")
    prompt_parts.append("### Structural (no-code) folders")
    prompt_parts.append("")
    prompt_parts.append("Some folders have no direct source files — they are organisational folders whose children contain the actual code.")
    prompt_parts.append("For these, describe the folder's **role and responsibility in the architecture**: what domain/layer it owns, how its children relate, and what a developer should know before navigating into it.")
    prompt_parts.append("Do NOT just list children. Synthesise: 'sdk is the public API surface for weather data — its sub-packages split by transport (HTTP, gRPC) and domain (forecast, alerts)'.")
    prompt_parts.append("")
    prompt_parts.append("Return a JSON object with folder paths as keys:")
    prompt_parts.append('{"folder/path": {purpose, patterns, key_file_guides, ...}, ...}')
    prompt_parts.append("")
    prompt_parts.append("---")
    prompt_parts.append("")

    # Detect which folders are structural
    plan_folders = plan.get("folders", {})

    for folder in folders:
        is_structural = plan_folders.get(folder, {}).get("structural", False)
        label = f"## Folder: {folder}"
        if is_structural:
            label += "  *(structural — no direct source files)*"
        prompt_parts.append(label)
        prompt_parts.append("")

        # Component context
        comp = _find_component_for_dir(folder, components)
        if comp:
            prompt_parts.append(f"**Component:** {comp.get('name', '')} — {comp.get('responsibility', '')}")
            deps = comp.get("depends_on", [])
            if deps:
                prompt_parts.append(f"**Depends on:** {', '.join(deps)}")
            exposes = comp.get("exposes_to", [])
            if exposes:
                prompt_parts.append(f"**Exposes to:** {', '.join(exposes)}")
            # Key interfaces from blueprint
            interfaces = comp.get("key_interfaces", [])
            if interfaces:
                iface_parts = []
                for iface in interfaces:
                    if isinstance(iface, dict) and iface.get("name"):
                        methods = iface.get("methods", [])
                        desc = iface.get("description", "")
                        entry = f"{iface['name']}"
                        if desc:
                            entry += f": {desc}"
                        if methods:
                            entry += f" — methods: {', '.join(methods)}"
                        iface_parts.append(entry)
                if iface_parts:
                    prompt_parts.append(f"**Key Interfaces:** {'; '.join(iface_parts)}")
            prompt_parts.append("")

        # Import graph context
        import_graph = scan.get("import_graph", {})
        if import_graph:
            imports_from: set[str] = set()
            imported_by: set[str] = set()
            for file_path, imports in import_graph.items():
                file_dir = str(Path(file_path).parent)
                is_in_dir = (file_dir == folder or file_dir.startswith(folder + "/"))
                if is_in_dir:
                    for imp in imports:
                        if "/" in imp or "." in imp:
                            parts = imp.replace(".", "/").split("/")
                            if len(parts) >= 2:
                                imp_dir = "/".join(parts[:2])
                                if not imp_dir.startswith(folder):
                                    imports_from.add(imp_dir)
                else:
                    for imp in imports:
                        if folder in imp.replace(".", "/"):
                            imported_by.add(file_dir)
            if imports_from:
                prompt_parts.append(f"**Imports from:** {', '.join(sorted(imports_from))}")
            if imported_by:
                prompt_parts.append(f"**Imported by:** {', '.join(sorted(imported_by))}")

        # Child summaries — DAG-aware: only inject actual children
        if child_summaries_dir:
            _inject_child_summaries(prompt_parts, folder, child_summaries_dir, plan)

        if is_structural:
            # Structural folder: list children only, no source files to read
            children = plan_folders.get(folder, {}).get("children", [])
            if children:
                prompt_parts.append(f"**Sub-folders:** {', '.join(sorted(children))}")
            prompt_parts.append("")
            prompt_parts.append("*This folder contains no direct source files. Describe its architectural role based on its children's summaries above.*")
            prompt_parts.append("")
        else:
            # Read ALL source files
            folder_files = files_by_dir.get(folder, [])
            source_files = [fp for fp in sorted(folder_files) if _is_source_file(fp)]

            prompt_parts.append(f"**All files:** {', '.join(Path(f).name for f in sorted(folder_files))}")
            prompt_parts.append("")

            for fp in source_files:
                content = _read_file_content(root, fp)
                if content:
                    fname = fp.rsplit("/", 1)[-1] if "/" in fp else fp
                    prompt_parts.append(f"### {fname}")
                    prompt_parts.append(f"```")
                    prompt_parts.append(content)
                    prompt_parts.append("```")
                    prompt_parts.append("")

        prompt_parts.append("---")
        prompt_parts.append("")

    print("\n".join(prompt_parts))


# ---------------------------------------------------------------------------
# merge — patch CLAUDE.md files with enrichment data
# ---------------------------------------------------------------------------

_AI_START = "<!-- archie:ai-start -->"
_AI_END = "<!-- archie:ai-end -->"
_SCOPED_START = "<!-- archie:scoped-start -->"
_SCOPED_END = "<!-- archie:scoped-end -->"


_MAX_CLAUDE_MD_LINES = 100  # budget per folder — density over completeness


def _render_enrichment_section(data: dict) -> str:
    """Render enrichment JSON into concise markdown.

    Budget: ~80-100 lines. Density over completeness.
    Removed: 'contains' (redundant with purpose), 'key_imports' (noise).
    Code examples: max 1.
    """
    lines = []
    lines.append(_AI_START)
    lines.append("")

    # Purpose
    purpose = data.get("purpose", "")
    if purpose:
        lines.append(f"> {purpose}")
        lines.append("")

    # Patterns (compact — name + description on one line)
    patterns = data.get("patterns", [])
    if patterns:
        lines.append("## Patterns")
        lines.append("")
        for p in patterns[:7]:  # max 7 patterns
            if isinstance(p, dict):
                desc = p.get("description", "")
                ex = p.get("example", "")
                line = f"**{p.get('name', '')}** — {desc}"
                if ex:
                    line += f" (`{ex}`)"
                lines.append(line)
            elif isinstance(p, str):
                lines.append(f"- {p}")
        lines.append("")

    # Key File Guides (compact table)
    guides = data.get("key_file_guides", [])
    if guides:
        lines.append("## Key Files")
        lines.append("")
        lines.append("| File | Role | Watch For |")
        lines.append("|------|------|-----------|")
        for g in guides[:8]:  # max 8 files
            if isinstance(g, dict):
                lines.append(f"| `{g.get('file', '')}` | {g.get('role', '')} | {g.get('watch_for', '')} |")
        lines.append("")

    # Anti-Patterns (max 5)
    anti = data.get("anti_patterns", [])
    if anti:
        lines.append("## Anti-Patterns")
        lines.append("")
        for a in anti[:5]:
            lines.append(f"- {a}")
        lines.append("")

    # Decisions (max 3, compact)
    decisions = data.get("decisions", [])
    if decisions:
        lines.append("## Decisions")
        lines.append("")
        for dec in decisions[:3]:
            if isinstance(dec, dict):
                lines.append(f"- **{dec.get('decision', '')}** — {dec.get('rationale', '')}")
            elif isinstance(dec, str):
                lines.append(f"- {dec}")
        lines.append("")

    # Code Example (max 1, most representative)
    examples = data.get("code_examples", [])
    if examples:
        ex = examples[0]
        if isinstance(ex, dict):
            code = ex.get("code", "")
            if code:
                lines.append(f"## Example: {ex.get('scenario', '')}")
                lines.append("")
                lines.append("```")
                # Truncate long examples
                code_lines = code.split("\n")
                if len(code_lines) > 15:
                    code_lines = code_lines[:15] + ["// ..."]
                lines.append("\n".join(code_lines))
                lines.append("```")
                lines.append("")

    lines.append(_AI_END)
    return "\n".join(lines)


def _extract_enrichment_json(text: str) -> dict | None:
    """Extract enrichment JSON from agent output text.

    Handles:
    - Plain JSON
    - JSON inside code fences
    - Claude Code NDJSON conversation envelopes
    - Multiple JSON blocks (one per folder) that need merging
    - Common AI escape issues (\\$, nested quotes)
    """
    def _fix_escapes(s: str) -> str:
        return s.replace("\\$", "$")

    def _try_parse(s: str) -> dict | None:
        for attempt in (s, _fix_escapes(s)):
            try:
                obj = json.loads(attempt)
                if isinstance(obj, dict):
                    return obj
            except (json.JSONDecodeError, ValueError):
                pass
        return None

    # 1. Try direct parse
    result = _try_parse(text)
    if result is not None:
        return result

    # 2. Try unwrapping NDJSON conversation envelope
    if text.lstrip().startswith(("{\"parentUuid\"", "{\"isSidechain\"")):
        content_parts = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("type") != "assistant":
                continue
            for block in record.get("message", {}).get("content", []):
                if isinstance(block, dict) and block.get("type") == "text":
                    content_parts.append(block["text"])
        if content_parts:
            text = "\n".join(content_parts)
            result = _try_parse(text)
            if result is not None:
                return result

    # 3. Extract from code fences — merge multiple blocks
    fences = list(re.finditer(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL))
    if fences:
        merged = {}
        for match in fences:
            block = match.group(1).strip()
            if block.startswith("{"):
                parsed = _try_parse(block)
                if parsed:
                    merged.update(parsed)
        if merged:
            return merged

    # 4. String-aware brace-matching — find all top-level JSON objects and merge
    merged = {}
    i = 0
    limit = len(text)
    attempts = 0
    while i < limit and attempts < 50:
        if text[i] != '{':
            i += 1
            continue
        attempts += 1
        # Walk forward, skip braces inside quoted strings
        depth = 0
        j = i
        in_string = False
        while j < limit:
            ch = text[j]
            if in_string:
                if ch == '\\':
                    j += 2
                    continue
                if ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        parsed = _try_parse(text[i:j + 1])
                        if parsed:
                            if "parentUuid" not in parsed and "isSidechain" not in parsed:
                                merged.update(parsed)
                        break
            j += 1
        i = j + 1 if j < limit else limit

    return merged if merged else None


def cmd_save_enrichment(root: Path, name: str, input_file: str):
    """Extract enrichment JSON from agent output and save to enrichments dir.

    Also marks the extracted folders as done in the state file.
    """
    enrichments_dir = root / ".archie" / "enrichments"
    enrichments_dir.mkdir(parents=True, exist_ok=True)

    text = Path(input_file).read_text() if input_file != "-" else sys.stdin.read()
    data = _extract_enrichment_json(text)

    if not data:
        print(f"Error: could not extract JSON from {input_file}", file=sys.stderr)
        sys.exit(1)

    # Filter: only keep entries that look like folder enrichments (have 'purpose' key)
    clean = {}
    for key, val in data.items():
        if isinstance(val, dict) and ("purpose" in val or "patterns" in val or "contains" in val):
            clean[key] = val

    if not clean:
        # Fallback: keep all dict entries
        clean = {k: v for k, v in data.items() if isinstance(v, dict)}

    plan = _load_json(root / ".archie" / "enrich_batches.json")
    known_folders = set((plan.get("folders") or {}).keys())
    foreign = sorted(k for k in clean if k not in known_folders)
    if foreign:
        print(
            "Error: enrichment payload contains folders outside the current DAG: "
            + ", ".join(foreign[:5])
            + (" ..." if len(foreign) > 5 else ""),
            file=sys.stderr,
        )
        sys.exit(1)

    out_path = enrichments_dir / f"{name}.json"
    out_path.write_text(json.dumps(clean, indent=2))
    print(f"Saved {len(clean)} folders to {out_path}", file=sys.stderr)

    cmd_mark_done(root, list(clean.keys()))

    return clean


def _externalize_folder_md(root: Path, folder_path: str) -> None:
    """Relocate a freshly-written per-folder CLAUDE.md to the external store.

    No-op in repo mode (the common case). Never raises — externalize must
    never break the enrichment merge.
    """
    try:
        _here = str(Path(__file__).resolve().parent)
        if _here not in sys.path:
            sys.path.insert(0, _here)
        import linker  # standalone sibling
        linker.externalize_folder_file(root, f"{folder_path}/CLAUDE.md")
    except Exception:
        pass


def cmd_merge(root: Path):
    """Patch existing CLAUDE.md files with enrichment data."""
    enrichments_dir = root / ".archie" / "enrichments"
    if not enrichments_dir.is_dir():
        print("Error: .archie/enrichments/ not found. Run enrichment first.", file=sys.stderr)
        sys.exit(1)

    # Load all enrichment JSONs (use robust extraction in case of raw agent output)
    all_enrichments: dict[str, dict] = {}
    for json_file in sorted(enrichments_dir.iterdir()):
        if not json_file.name.endswith(".json"):
            continue
        try:
            text = json_file.read_text()
            data = _extract_enrichment_json(text)
            if data:
                all_enrichments.update(data)
            else:
                print(f"  Warning: could not extract JSON from {json_file}", file=sys.stderr)
        except OSError as e:
            print(f"  Warning: could not read {json_file}: {e}", file=sys.stderr)

    if not all_enrichments:
        print("No enrichment data found.", file=sys.stderr)
        sys.exit(1)

    patched = 0
    created = 0
    skipped_missing = 0
    for folder_path, enrichment_data in sorted(all_enrichments.items()):
        # Defensive: skip enrichments whose folder no longer exists on disk.
        # Happens after resume if the repo was restructured between runs, or
        # when finalize-partial ingests orphan /tmp enrichments for folders
        # that never landed anywhere real.
        folder_abs = root / folder_path
        if not folder_abs.is_dir():
            skipped_missing += 1
            continue

        claude_md_path = folder_abs / "CLAUDE.md"
        ai_section = _render_enrichment_section(enrichment_data)
        dir_name = folder_path.rsplit("/", 1)[-1] if "/" in folder_path else folder_path

        if claude_md_path.exists():
            content = claude_md_path.read_text()

            if _AI_START in content and _AI_END in content:
                # Has archie markers — replace archie section, keep everything else
                pattern = re.compile(
                    re.escape(_AI_START) + r".*?" + re.escape(_AI_END),
                    re.DOTALL,
                )
                content = pattern.sub(ai_section, content)
            else:
                # No archie markers — existing manual/Claude Code content.
                # Extract the non-archie content, prepend it to archie section.
                existing = content.strip()
                # Remove any old footer
                footer = "---\n*Auto-generated by Archie.*"
                existing = existing.replace(footer, "").strip()
                # Remove old header if it's just the dir name
                if existing.startswith(f"# {dir_name}"):
                    existing = existing[len(f"# {dir_name}"):].strip()

                if existing:
                    # Merge: keep existing content as a "Manual notes" block,
                    # but truncate if combined would exceed budget
                    existing_lines = existing.split("\n")
                    ai_lines = ai_section.split("\n")
                    budget_for_existing = max(20, _MAX_CLAUDE_MD_LINES - len(ai_lines) - 5)
                    if len(existing_lines) > budget_for_existing:
                        existing_lines = existing_lines[:budget_for_existing]
                        existing_lines.append("<!-- truncated to fit line budget -->")
                    content = f"# {dir_name}\n\n" + "\n".join(existing_lines) + "\n\n" + ai_section + "\n"
                else:
                    content = f"# {dir_name}\n\n{ai_section}\n"

            # Enforce total line budget
            total_lines = content.split("\n")
            if len(total_lines) > _MAX_CLAUDE_MD_LINES + 20:  # 20 line grace
                # Trim from the end (before the AI_END marker)
                content = "\n".join(total_lines[:_MAX_CLAUDE_MD_LINES + 20])
                if _AI_END not in content:
                    content += f"\n{_AI_END}\n"

            claude_md_path.write_text(content)
            patched += 1
        else:
            # Folder exists (we verified above), but no CLAUDE.md yet — create it.
            content = f"# {dir_name}\n\n{ai_section}\n"
            claude_md_path.write_text(content)
            created += 1

        # Detached mode: relocate the freshly-written per-folder file to the
        # external store and replace it with a managed link. No-op in repo mode.
        _externalize_folder_md(root, folder_path)

    summary = f"Enrichment merge: {patched} patched, {created} created"
    if skipped_missing:
        summary += f", {skipped_missing} skipped (folder no longer exists)"
    print(summary, file=sys.stderr)


# ---------------------------------------------------------------------------
# inject-scoped — project blueprint scoped patterns/guidelines into per-folder
# CLAUDE.md so Claude Code's per-folder autoloading filters them at the loader
# level (hard filter), not via agent self-discipline (soft filter). Items with
# scope=[] (repo-wide) are NOT injected — they already live in global rules.md.
# ---------------------------------------------------------------------------

def _str_list(val) -> list[str]:
    """Coerce a value to a list of non-empty strings."""
    if isinstance(val, list):
        return [s for s in val if isinstance(s, str) and s.strip()]
    if isinstance(val, str) and val.strip():
        return [val]
    return []


def _render_scoped_guideline(gl: dict) -> list[str]:
    """Render one implementation_guideline as compact scoped markdown."""
    cap = gl.get("capability", "")
    if not cap:
        return []
    cat = gl.get("category", "")
    heading = f"#### {cap}" + (f" [{cat}]" if cat else "")
    out = [heading]
    if gl.get("pattern_description"):
        out.append(f"Pattern: {gl['pattern_description']}")
    libs = gl.get("libraries") or []
    if libs:
        out.append(f"Libraries: {', '.join(f'`{l}`' for l in libs)}")
    key_files = gl.get("key_files") or []
    if key_files:
        out.append(f"Key files: {', '.join(f'`{f}`' for f in key_files)}")
    if gl.get("usage_example"):
        out.append(f"Example: `{gl['usage_example']}`")
    if gl.get("applicable_when"):
        out.append(f"**Applicable when:** {gl['applicable_when']}")
    do_not = _str_list(gl.get("do_not_apply_when"))
    if do_not:
        out.append("**Do NOT apply when:**")
        for d in do_not:
            out.append(f"  - {d}")
    out.append("")
    return out


def _render_scoped_pattern(pat: dict) -> list[str]:
    """Render one communication.patterns entry as compact scoped markdown."""
    name = pat.get("name", "")
    if not name:
        return []
    out = [f"#### {name}"]
    if pat.get("when_to_use"):
        out.append(f"- **When:** {pat['when_to_use']}")
    if pat.get("how_it_works"):
        out.append(f"- **How:** {pat['how_it_works']}")
    if pat.get("applicable_when"):
        out.append(f"- **Applicable when:** {pat['applicable_when']}")
    do_not = _str_list(pat.get("do_not_apply_when"))
    if do_not:
        out.append("- **Do NOT apply when:**")
        for d in do_not:
            out.append(f"  - {d}")
    out.append("")
    return out


def _render_scoped_section_from_items(
    component_name: str,
    in_scope_igs: list[dict],
    in_scope_patterns: list[dict],
    in_scope_models: list[dict] | None = None,
) -> str:
    """Render the marker-bracketed scoped section for a component, given
    pre-resolved item lists.

    Caller is responsible for resolving scope values to components first
    (via ``_resolve_scope_value`` + aggregation). Returns the empty string
    when all three lists are empty — signal to caller to leave the file alone.

    ``in_scope_models`` is optional for backward compatibility; pass the list
    of ``data_models`` entries whose ``owned_by_component`` resolved to this
    component to render a per-folder "Data Models owned here" subsection.
    """
    in_scope_models = in_scope_models or []
    if not in_scope_igs and not in_scope_patterns and not in_scope_models:
        return ""

    lines = [_SCOPED_START, ""]
    lines.append("## Scoped Architecture Rules")
    lines.append("")
    lines.append(f"*From blueprint — these rules are scoped to the `{component_name}` component.*")
    lines.append("")

    if in_scope_igs:
        lines.append("### Implementation Guidelines")
        lines.append("")
        for gl in in_scope_igs:
            lines.extend(_render_scoped_guideline(gl))

    if in_scope_patterns:
        lines.append("### Communication Patterns")
        lines.append("")
        for pat in in_scope_patterns:
            lines.extend(_render_scoped_pattern(pat))

    if in_scope_models:
        lines.append("### Data Models owned here")
        lines.append("")
        for m in in_scope_models:
            if not isinstance(m, dict) or not m.get("name"):
                continue
            name = m.get("name", "")
            loc = m.get("location", "")
            kind = m.get("kind", "")
            head = f"- **`{name}`**"
            if kind:
                head += f" *({kind})*"
            if loc:
                head += f" — `{loc}`"
            lines.append(head)
            lifecycle = m.get("lifecycle") or {}
            if isinstance(lifecycle, dict):
                # Read new {prose, example} shape, fall back to legacy strings.
                for label, key in (
                    ("How to modify", "how_to_modify"),
                    ("How to read", "how_to_read"),
                ):
                    raw = lifecycle.get(key)
                    if isinstance(raw, dict):
                        prose = raw.get("prose") or ""
                    elif isinstance(raw, str):
                        prose = raw
                    else:
                        prose = ""
                    if prose:
                        lines.append(f"  - *{label}:* {prose}")
        lines.append("")

    lines.append(_SCOPED_END)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Lenient scope resolver — maps scope identifiers (component name, class name,
# Koin module val) to a component name. Wave 2 in the wild prefers concrete
# code symbols over component descriptors ("NetworkDatasourceImpl" rather
# than "Domain and Data Layer"); the resolver handles both so the agent's
# choice doesn't break hard-filter delivery.
# ---------------------------------------------------------------------------

# Source-file extensions whose contents we scan for symbol declarations.
_RESOLVER_SOURCE_EXTS = {
    ".kt", ".kts", ".java", ".scala",
    ".py",
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".swift",
    ".go", ".rs",
    ".rb", ".cs", ".php",
}

# Top-level type declarations.
_DECL_RE = re.compile(
    r"\b(?:class|interface|object|enum|trait|struct|protocol|record)\s+([A-Z][A-Za-z0-9_]*)\b"
)
# Koin / Spring / similar val-module declarations.
_VAL_MODULE_RE = re.compile(
    r"\bval\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*module\b"
)


def _build_symbol_index(root: Path, skip_dirs: set[str]) -> dict[str, str]:
    """Walk source files once and index identifier -> first-seen rel path.

    First-match wins for ambiguous names. Skip lists prevent walking into
    .archie/, .claude/, build/, node_modules/ and similar.
    """
    index: dict[str, str] = {}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in _RESOLVER_SOURCE_EXTS:
            continue
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if any(part in skip_dirs for part in rel.parts):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel_str = str(rel)
        for m in _DECL_RE.finditer(content):
            index.setdefault(m.group(1), rel_str)
        for m in _VAL_MODULE_RE.finditer(content):
            index.setdefault(m.group(1), rel_str)
    return index


# Demotion threshold — if a pattern's resolved scope spans >= this fraction
# of all blueprint components, it's effectively repo-wide. Repo-wide patterns
# already live in global rules.md (loaded for every edit), so fanning them
# out into every per-folder CLAUDE.md just duplicates the same text. Tune by
# editing this constant; set to 1.0 to disable demotion entirely.
_REPO_WIDE_DEMOTE_RATIO = 0.5


def _resolve_scope_value(
    value: str,
    components: list[dict],
    comp_by_name: dict[str, dict],
    symbol_index: dict[str, str],
) -> str | None:
    """Map a scope identifier to a component name, or None if unresolvable.

    Resolution chain (first hit wins):
      1. Exact match against ``components.components[].name`` (literal mode —
         backwards compat with strict-mode blueprints).
      2. Symbol index hit (class / interface / object / val module) → look up
         the matching file's directory in the components list.
      3. Otherwise unresolvable; caller drops it.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    # 1. Direct name match.
    if value in comp_by_name:
        return value
    # 2. Symbol index → file → component.
    rel = symbol_index.get(value)
    if rel:
        parent = str(Path(rel).parent)
        comp = _find_component_for_dir(parent, components)
        if comp and comp.get("name"):
            return comp["name"]
    return None


def _patch_scoped_section(content: str, scoped_section: str) -> str:
    """Insert/replace the scoped section in a CLAUDE.md body.

    If markers exist, replace between them. Otherwise append after any AI
    section, or to the end. If scoped_section is empty, REMOVE any existing
    scoped block (so that re-running after scope shrinks cleans up stale
    blocks).
    """
    has_markers = _SCOPED_START in content and _SCOPED_END in content
    if not scoped_section:
        if not has_markers:
            return content
        # Strip the existing block (and any trailing whitespace it leaves).
        pattern = re.compile(
            r"\n*" + re.escape(_SCOPED_START) + r".*?" + re.escape(_SCOPED_END) + r"\n*",
            re.DOTALL,
        )
        return pattern.sub("\n", content).rstrip() + "\n"

    if has_markers:
        pattern = re.compile(
            re.escape(_SCOPED_START) + r".*?" + re.escape(_SCOPED_END),
            re.DOTALL,
        )
        return pattern.sub(scoped_section, content)

    # Append: prefer to land after the AI section if present, else at end.
    if _AI_END in content:
        return content.replace(_AI_END, _AI_END + "\n\n" + scoped_section, 1)
    return content.rstrip() + "\n\n" + scoped_section + "\n"


def cmd_inject_scoped(root: Path):
    """Project blueprint scoped patterns into per-folder CLAUDE.md.

    Two-pass:
      1. Build a symbol index of source files (one walk over the repo) and
         resolve every scope value through the resolver chain (component
         name -> class/interface/object -> Koin val module). Aggregate per
         component name.
      2. For every component, render and inject (or clear) its scoped block.
         Re-runs replace marker-bracketed blocks in place; scope-shrink
         clears stale blocks; the AI section is preserved.

    Lenient by design: Wave 2 in the wild often emits class names rather
    than literal component names. The resolver maps either form back to a
    component, so the hard-filter delivery fires regardless of which
    identifier style the agent picks.
    """
    blueprint = _load_json(root / ".archie" / "blueprint.json")
    if not blueprint:
        print("Error: .archie/blueprint.json not found or empty.", file=sys.stderr)
        sys.exit(1)

    components = _get_components(blueprint)
    if not components:
        print("No components in blueprint — nothing to project.", file=sys.stderr)
        return

    comp_by_name = {c["name"]: c for c in components if isinstance(c, dict) and c.get("name")}

    # Pass 1 — walk source tree once, index symbol declarations.
    symbol_index = _build_symbol_index(root, _GUARDRAIL_SKIP_DIRS)

    # Pass 1b — resolve every scope value, aggregate items per target
    # component. A pattern with scope spanning multiple components lands a
    # copy of itself in each component's bucket; the per-component renderer
    # takes care of de-duping (a pattern is only added once per bucket
    # because we coalesce target-component sets).
    component_to_igs: dict[str, list[dict]] = {}
    component_to_patterns: dict[str, list[dict]] = {}
    unresolved: list[tuple[str, str, str]] = []  # (kind, item_name, scope_value)
    demoted: list[tuple[str, str, int]] = []  # (kind, item_name, resolved_count)

    total_components = max(1, sum(
        1 for c in components if isinstance(c, dict) and c.get("name") and (c.get("location") or c.get("path"))
    ))
    demote_threshold = max(2, int(total_components * _REPO_WIDE_DEMOTE_RATIO))

    def _aggregate(item, kind, scope_values):
        """Resolve, then keep/demote/drop based on coverage threshold."""
        targets: set[str] = set()
        for s in scope_values:
            cn = _resolve_scope_value(s, components, comp_by_name, symbol_index)
            if cn:
                targets.add(cn)
            else:
                unresolved.append((kind, item.get("capability") or item.get("name") or "?", s))
        # Demotion: if the pattern resolves to too many components, treat it
        # as repo-wide (the global rule file already carries it via inline
        # scope text). Skip per-folder injection to avoid mass duplication.
        if len(targets) >= demote_threshold:
            demoted.append((kind, item.get("capability") or item.get("name") or "?", len(targets)))
            return None
        return targets

    for ig in blueprint.get("implementation_guidelines") or []:
        if not isinstance(ig, dict) or not ig.get("capability"):
            continue
        targets = _aggregate(ig, "guideline", _str_list(ig.get("scope")))
        if targets is None:
            continue
        for cn in targets:
            component_to_igs.setdefault(cn, []).append(ig)

    for pat in (blueprint.get("communication") or {}).get("patterns") or []:
        if not isinstance(pat, dict) or not pat.get("name"):
            continue
        targets = _aggregate(pat, "pattern", _str_list(pat.get("scope")))
        if targets is None:
            continue
        for cn in targets:
            component_to_patterns.setdefault(cn, []).append(pat)

    # Data models — single-component ownership via owned_by_component (set
    # by the Wave 1 Data agent). No full scope resolver needed; this is a
    # direct name lookup against components. Models with no owner stay in
    # the root topic file (.claude/rules/data-models.md) only.
    component_to_models: dict[str, list[dict]] = {}
    for m in blueprint.get("data_models") or []:
        if not isinstance(m, dict) or not m.get("name"):
            continue
        owner = m.get("owned_by_component") or ""
        if owner and owner in comp_by_name:
            component_to_models.setdefault(owner, []).append(m)

    # Pass 2 — for every component, write or clear its scoped block. We
    # iterate ALL components (not just the ones that received items) so
    # that scope-shrink across runs cleans up stale blocks.
    injected = 0
    cleared = 0
    skipped_missing = 0
    for comp in components:
        if not isinstance(comp, dict):
            continue
        name = comp.get("name") or ""
        location = (comp.get("location") or comp.get("path") or "").strip().rstrip("/")
        if not name or not location:
            continue

        folder_abs = root / location
        if not folder_abs.is_dir():
            skipped_missing += 1
            continue

        claude_md_path = folder_abs / "CLAUDE.md"
        igs = component_to_igs.get(name, [])
        pats = component_to_patterns.get(name, [])
        models = component_to_models.get(name, [])
        scoped_section = _render_scoped_section_from_items(name, igs, pats, models)

        if claude_md_path.exists():
            old = claude_md_path.read_text()
            new = _patch_scoped_section(old, scoped_section)
            if new != old:
                claude_md_path.write_text(new)
                if scoped_section:
                    injected += 1
                else:
                    cleared += 1
        elif scoped_section:
            # Folder has no CLAUDE.md (intent_layer didn't cover it) but the
            # blueprint says scoped rules apply here. Create a minimal file
            # so the rules land somewhere — without it, the hard filter has
            # no delivery.
            dir_name = location.rsplit("/", 1)[-1] if "/" in location else location
            claude_md_path.write_text(f"# {dir_name}\n\n{scoped_section}\n")
            injected += 1

    summary = f"Scoped injection: {injected} updated, {cleared} cleared (no longer scoped)"
    if skipped_missing:
        summary += f", {skipped_missing} skipped (component location does not exist)"
    print(summary, file=sys.stderr)

    if demoted:
        # Patterns that fanned out across >=50% of components: too broad to be
        # called "scoped." They live in global rules.md instead, where they
        # already render with inline scope text.
        names = ", ".join(f"{name!r} ({count} comps)" for _, name, count in demoted[:5])
        more = f" (+{len(demoted) - 5} more)" if len(demoted) > 5 else ""
        print(
            f"  ({len(demoted)} pattern(s) demoted to repo-wide because they "
            f"span >= {demote_threshold} of {total_components} components: "
            f"{names}{more})",
            file=sys.stderr,
        )

    if unresolved:
        # Group by scope value so users can see the most common offenders
        # without scrolling through every (kind, item) pair.
        by_value: dict[str, int] = {}
        for _, _, value in unresolved:
            by_value[value] = by_value.get(value, 0) + 1
        top = sorted(by_value.items(), key=lambda kv: -kv[1])
        print(
            f"  ({len(unresolved)} scope values could not be resolved to a component; "
            f"top offenders: {', '.join(f'{v!r}×{n}' for v, n in top[:5])})",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# extract-maintainer-guardrails — scan per-folder CLAUDE.md for human-curated
# anti-patterns. Strips Archie's own marker blocks (ai + scoped) deterministically
# so the output only carries maintainer prose. Wave 2 §11 reads the resulting
# JSON instead of LLM-globbing CLAUDE.md, eliminating the self-amplification
# class of failure (Archie's previous output cannot feed back into itself).
# ---------------------------------------------------------------------------

# Directories to skip when scanning for CLAUDE.md files
_GUARDRAIL_SKIP_DIRS = {
    ".archie", ".claude", "node_modules", ".venv", ".git",
    "vendor", "dist", "build", "target", ".next", ".nuxt",
    "__pycache__",
}

# Regex matching common anti-pattern section headings: "## Anti-Patterns",
# "## Anti-pattern", "## Anti Patterns", "## anti-patterns", etc.
_ANTI_HEADING_RE = re.compile(
    r"^\s*#{2,4}\s+anti[-\s]?patterns?\s*$", re.IGNORECASE
)
_NEXT_HEADING_RE = re.compile(r"^\s*#{2,4}\s+\S")
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.+?)\s*$")


def _strip_archie_blocks(content: str) -> str:
    """Remove Archie's own marker blocks (AI + scoped) from CLAUDE.md content.

    Anything between ``<!-- archie:ai-* -->`` or ``<!-- archie:scoped-* -->``
    is Archie's output, not maintainer prose, and must not feed back into
    Wave 2's compound-learning loop.
    """
    for start, end in ((_AI_START, _AI_END), (_SCOPED_START, _SCOPED_END)):
        pattern = re.compile(
            re.escape(start) + r".*?" + re.escape(end),
            re.DOTALL,
        )
        content = pattern.sub("", content)
    return content


def _extract_anti_pattern_bullets(content: str) -> list[str]:
    """Return the bullet items under any ## Anti-Patterns section.

    Handles single or multiple anti-pattern sections per file. Stops at the
    next section heading (any ## or deeper).
    """
    items: list[str] = []
    in_section = False
    for raw_line in content.splitlines():
        if _ANTI_HEADING_RE.match(raw_line):
            in_section = True
            continue
        if in_section and _NEXT_HEADING_RE.match(raw_line):
            in_section = False
            continue
        if not in_section:
            continue
        m = _BULLET_RE.match(raw_line)
        if m:
            text = m.group(1).strip()
            if text:
                items.append(text)
    return items


def _is_skipped_path(rel_path: Path) -> bool:
    """True if this folder is under a skip-list ancestor."""
    return any(part in _GUARDRAIL_SKIP_DIRS for part in rel_path.parts)


def cmd_extract_guardrails(root: Path):
    """Write maintainer guardrails to .archie/maintainer_guardrails.json.

    Wave 2 §11 reads this file rather than globbing CLAUDE.md directly, so
    the compound-learning loop sees only deterministically-cleaned input
    and cannot pick up Archie's own previous output.
    """
    out_path = root / ".archie" / "maintainer_guardrails.json"
    guardrails: list[dict] = []

    for path in sorted(root.rglob("CLAUDE.md")):
        rel = path.relative_to(root)
        # Skip the repo-root CLAUDE.md (Archie generates that one entirely;
        # there's no maintainer Anti-Patterns layer there).
        if rel == Path("CLAUDE.md"):
            continue
        if _is_skipped_path(rel.parent):
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        cleaned = _strip_archie_blocks(raw)
        items = _extract_anti_pattern_bullets(cleaned)
        if items:
            guardrails.append({
                "source": str(rel),
                "items": items,
            })

    payload = {
        "version": 1,
        "guardrails": guardrails,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2))
    print(
        f"Maintainer guardrails: {len(guardrails)} CLAUDE.md files contributed "
        f"({sum(len(g['items']) for g in guardrails)} bullets total) "
        f"-> {out_path.relative_to(root)}",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# inspect subcommand
# ---------------------------------------------------------------------------

def cmd_inspect(root: Path, filename: str, query: str | None = None, as_list: bool = False):
    """Print human-readable summary (stderr) + raw JSON (stdout) for .archie/ files.

    When ``as_list`` is True and the resolved query value is a JSON array,
    prints each element on its own line (raw string for string elements,
    compact JSON for non-string elements). Non-list values print normally.
    Used by shell callers that want to iterate a list without pulling in
    jq or inline python.
    """
    filepath = root / ".archie" / filename
    if not filepath.exists():
        print(f"Error: {filename} not found in .archie/", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(filepath.read_text())
    except (json.JSONDecodeError, ValueError):
        print(f"Error: {filename} contains invalid JSON", file=sys.stderr)
        sys.exit(1)

    # --query mode: extract and print value only
    if query:
        # Parse query: .key.subkey or .key|length
        has_length = query.endswith("|length")
        path = query[:-len("|length")] if has_length else query
        parts = [p for p in path.split(".") if p]

        obj = data
        for p in parts:
            if isinstance(obj, dict) and p in obj:
                obj = obj[p]
            else:
                # Key not found — return null, not error
                print("null")
                return

        if has_length:
            if isinstance(obj, (list, dict)):
                print(len(obj))
            else:
                print(f"Error: value is not a list or dict", file=sys.stderr)
                sys.exit(1)
        elif as_list:
            if isinstance(obj, list):
                for item in obj:
                    if isinstance(item, str):
                        print(item)
                    else:
                        print(json.dumps(item))
            elif isinstance(obj, str):
                print(obj)
            elif obj is None:
                pass  # empty output — matches "no items"
            else:
                print(json.dumps(obj))
        else:
            print(json.dumps(obj) if isinstance(obj, (dict, list)) else obj)
        return

    # Summary mode: file-specific summary to stderr, full JSON to stdout
    basename = filename.lower()
    if basename == "scan.json" and isinstance(data, dict):
        fc = data.get("total_files", "?")
        fr = data.get("frontend_ratio", "?")
        fw = len(data.get("frameworks", []))
        print(f"Scan: {fc} files, frontend_ratio={fr}, {fw} frameworks", file=sys.stderr)
    elif basename == "blueprint.json" and isinstance(data, dict):
        comps = data.get("components", [])
        if isinstance(comps, dict):
            comps = comps.get("components", [])
        nc = len(comps) if isinstance(comps, list) else 0
        nd = len(data.get("decisions", []))
        np = len(data.get("pitfalls", []))
        style = data.get("meta", {}).get("architecture_style", "")
        summary = f"Blueprint: {nc} components, {nd} decisions, {np} pitfalls"
        if style:
            summary += f", style={style}"
        print(summary, file=sys.stderr)
    elif basename == "dependency_graph.json" and isinstance(data, dict):
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        cycles = data.get("cycles", [])
        # top 3 by in-degree
        in_deg: dict[str, int] = {}
        for e in edges:
            t = e.get("to", "")
            in_deg[t] = in_deg.get(t, 0) + 1
        top3 = sorted(in_deg, key=lambda k: in_deg[k], reverse=True)[:3]
        summary = f"Graph: {len(nodes)} nodes, {len(edges)} edges, {len(cycles)} cycles"
        if top3:
            summary += f" | top in-degree: {', '.join(top3)}"
        print(summary, file=sys.stderr)
    elif basename == "health.json" and isinstance(data, dict):
        e = data.get("erosion_index", "?")
        g = data.get("gini", "?")
        v = data.get("verbosity", "?")
        loc = data.get("total_loc", "?")
        print(f"Health: erosion={e}, gini={g}, verbosity={v}, loc={loc}", file=sys.stderr)
    elif basename == "health_history.json":
        entries = data if isinstance(data, list) else data.get("history", data)
        count = len(entries) if isinstance(entries, (list, dict)) else "?"
        print(f"History: {count} entries", file=sys.stderr)
    else:
        # Generic summary
        if isinstance(data, list):
            print(f"{filename}: {len(data)} items", file=sys.stderr)
        elif isinstance(data, dict):
            keys = ", ".join(list(data.keys())[:10])
            print(f"{filename}: {len(data)} keys: {keys}", file=sys.stderr)

    print(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage:", file=sys.stderr)
        print("  python3 intent_layer.py prepare /path/to/repo [--only-folders folder1,folder2,...]", file=sys.stderr)
        print("  python3 intent_layer.py next-ready /path/to/repo [done1 done2 ...]", file=sys.stderr)
        print("  python3 intent_layer.py suggest-batches /path/to/repo [ready1 ready2 ...]", file=sys.stderr)
        print("  python3 intent_layer.py prompt /path/to/repo --folder <path>", file=sys.stderr)
        print("  python3 intent_layer.py prompt /path/to/repo --folders <p1>,<p2>", file=sys.stderr)
        print("  python3 intent_layer.py save-enrichment /path/to/repo <name> <input.json>", file=sys.stderr)
        print("  python3 intent_layer.py mark-done /path/to/repo <folder1> [folder2 ...]", file=sys.stderr)
        print("  python3 intent_layer.py reset-state /path/to/repo", file=sys.stderr)
        print("  python3 intent_layer.py merge /path/to/repo", file=sys.stderr)
        print("  python3 intent_layer.py deep-scan-state /path/to/repo <init|complete-step|read|check-prereqs|save-context|save-baseline|detect-changes|snapshot|restore|list-snapshots> [step|label]", file=sys.stderr)
        print("  python3 intent_layer.py scan-config /path/to/repo <read|write|validate>  (write reads JSON from stdin)", file=sys.stderr)
        print("  python3 intent_layer.py inspect /path/to/repo <filename> [--query .key.path]", file=sys.stderr)
        sys.exit(1)

    subcmd = sys.argv[1]
    root = Path(sys.argv[2]).resolve()

    if subcmd == "prepare":
        only = None
        for i, arg in enumerate(sys.argv[3:], 3):
            if arg == "--only-folders" and i + 1 < len(sys.argv):
                only = sys.argv[i + 1].split(",")
                break
        cmd_prepare(root, only_folders=only)
    elif subcmd == "next-ready":
        done = sys.argv[3:] if len(sys.argv) > 3 else []
        cmd_next_ready(root, done)
    elif subcmd == "suggest-batches":
        ready = sys.argv[3:] if len(sys.argv) > 3 else []
        # For large DAGs (hundreds of ready folders), passing paths through
        # bash argv is fragile — shell word-splitting, ARG_MAX limits, and
        # unquoted variable expansion all fail in ways that produce a silent
        # empty argv. When argv has no folders and stdin isn't a TTY, read a
        # JSON array from stdin instead (the canonical output of next-ready).
        if not ready and not sys.stdin.isatty():
            raw = sys.stdin.read().strip()
            if raw:
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError as e:
                    print(f"suggest-batches: stdin is not valid JSON: {e}", file=sys.stderr)
                    sys.exit(2)
                if not isinstance(parsed, list):
                    print(f"suggest-batches: stdin JSON must be an array of folder paths, got {type(parsed).__name__}", file=sys.stderr)
                    sys.exit(2)
                ready = [str(x) for x in parsed]
        cmd_suggest_batches(root, ready)
    elif subcmd == "save-enrichment":
        if len(sys.argv) < 5:
            print("Usage: save-enrichment /path/to/repo <name> <input.json|->", file=sys.stderr)
            sys.exit(1)
        cmd_save_enrichment(root, sys.argv[3], sys.argv[4])
    elif subcmd == "mark-done":
        folders = sys.argv[3:] if len(sys.argv) > 3 else []
        cmd_mark_done(root, folders)
    elif subcmd == "reset-state":
        cmd_reset_state(root)
    elif subcmd == "prompt":
        # Parse --folder, --folders, or positional batch_id
        child_dir = None
        if "--child-summaries" in sys.argv:
            idx = sys.argv.index("--child-summaries")
            if idx + 1 < len(sys.argv):
                child_dir = sys.argv[idx + 1]

        if "--folder" in sys.argv:
            idx = sys.argv.index("--folder")
            if idx + 1 < len(sys.argv):
                cmd_prompt(root, [sys.argv[idx + 1]], child_dir)
            else:
                print("Error: --folder requires a path", file=sys.stderr)
                sys.exit(1)
        elif "--folders" in sys.argv:
            idx = sys.argv.index("--folders")
            if idx + 1 < len(sys.argv):
                folder_list = sys.argv[idx + 1].split(",")
                cmd_prompt(root, folder_list, child_dir)
            else:
                print("Error: --folders requires comma-separated paths", file=sys.stderr)
                sys.exit(1)
        elif len(sys.argv) > 3 and not sys.argv[3].startswith("--"):
            # Legacy batch_id support — look up in suggest-batches output or v1 format
            batch_id = sys.argv[3]
            plan = _load_json(root / ".archie" / "enrich_batches.json")
            # v1 format (depth_levels)
            batch = None
            for dl in plan.get("depth_levels", []):
                for b in dl.get("batches", []):
                    if b["id"] == batch_id:
                        batch = b
                        break
                if batch:
                    break
            if batch:
                cmd_prompt(root, batch["folders"], child_dir)
            else:
                print(f"Error: batch '{batch_id}' not found", file=sys.stderr)
                sys.exit(1)
        else:
            print("Error: prompt requires --folder, --folders, or batch_id", file=sys.stderr)
            sys.exit(1)
    elif subcmd == "deep-scan-state":
        action = sys.argv[3] if len(sys.argv) > 3 else ""
        step_arg = None
        raw_arg = sys.argv[4] if len(sys.argv) > 4 else None
        if raw_arg is not None:
            try:
                step_arg = int(raw_arg)
            except ValueError:
                step_arg = None
        # raw_arg carries the string form (snapshot/restore label); step_arg
        # the int form (complete-step / check-prereqs N).
        cmd_deep_scan_state(root, action, step_arg, label=raw_arg)
    elif subcmd == "scan-config":
        action = sys.argv[3] if len(sys.argv) > 3 else ""
        if action not in {"read", "write", "validate"}:
            print("Usage: scan-config /path/to/repo <read|write|validate>", file=sys.stderr)
            sys.exit(1)
        cmd_scan_config(root, action)
    elif subcmd == "merge":
        cmd_merge(root)
    elif subcmd == "inject-scoped":
        cmd_inject_scoped(root)
    elif subcmd == "extract-guardrails":
        cmd_extract_guardrails(root)
    elif subcmd == "inspect":
        if len(sys.argv) < 4:
            print("Usage: inspect /path/to/repo <filename> [--query .key.path] [--list]", file=sys.stderr)
            sys.exit(1)
        fname = sys.argv[3]
        q = None
        if "--query" in sys.argv:
            qi = sys.argv.index("--query")
            if qi + 1 < len(sys.argv):
                q = sys.argv[qi + 1]
        as_list = "--list" in sys.argv
        cmd_inspect(root, fname, q, as_list=as_list)
    else:
        print(f"Error: unknown subcommand '{subcmd}'", file=sys.stderr)
        sys.exit(1)

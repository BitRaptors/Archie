#!/usr/bin/env python3
"""Archie standalone sync — the Living Blueprint change ledger (Phase 1).

PHASE 1 — PRODUCE OUTPUT ONLY. `record` writes a versioned change file under
`.archie/changes/` capturing the diff plus the agent's harvested intent claims, each
classified `eligible` (would fold into the blueprint in Phase 2) or `staged`
(provisional). It writes NOTHING to blueprint.json or any CLAUDE.md — folding is Phase 2.

The intent payload is supplied by the in-session agent (via /archie-sync), which either
PROVIDES context it already holds or BUILDS it from `git diff`. This script is pure,
deterministic glue: it reads the diff, validates + classifies the claims, and records
them. No model calls, zero dependencies beyond Python 3.9+ stdlib.

Usage:
  python3 sync.py record /path/to/repo [--input payload.json] [--agent claude|codex] [--since <ref>]
  python3 sync.py list   /path/to/repo [--json]

Payload (JSON, from --input or stdin) — a list of claims, or {"claims": [...]}:
  { "type": "decision|rule|pitfall|guideline",
    "title": "short title",
    "rationale": "the why",
    "evidence_files": ["path/touched/by/the/change.kt"],
    "confidence": "low|medium|high",
    "reconstructed": false }

Output to stdout: a one-line JSON summary (detect-changes style).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent

# A claim is a STATEMENT about what the code now is. Descriptive kinds are the
# default (keep the blueprint snapshot current); advisory kinds are an optional
# side-output, emitted only when a change genuinely establishes one.
_DESCRIPTIVE_KINDS = {"behavior", "structure", "dataflow", "data", "tech", "reference"}
_ADVISORY_KINDS = {"decision", "pitfall", "rule", "guideline"}
_VALID_KINDS = _DESCRIPTIVE_KINDS | _ADVISORY_KINDS
_VALID_CONFIDENCE = {"low", "medium", "high"}
_CHANGES_DIR = "changes"


# ---------------------------------------------------------------------------
# small helpers (mirror existing stack conventions)
# ---------------------------------------------------------------------------

def _now_iso_short() -> str:
    """Match finalize.py's finding timestamp format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M")


def _slugify(value: str) -> str:
    """Mirror intent_layer._slugify."""
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return slug or "claim"


def _git(root: Path, *args: str) -> str:
    """Run a git command in `root`, return stripped stdout ('' on any failure)."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    except Exception:
        return ""


def _ancestors(changed: list[str]) -> list[str]:
    """Every ancestor folder of every changed file (mirrors detect-changes)."""
    folders: set[str] = set()
    for f in changed:
        parts = Path(f).parts
        for i in range(1, len(parts)):
            folders.add(str(Path(*parts[:i])))
    return sorted(folders)


# ---------------------------------------------------------------------------
# diff acquisition — reuse detect-changes; fall back to a direct git diff so the
# command is always testable even before a deep-scan baseline exists.
# ---------------------------------------------------------------------------

def _detect_changes(root: Path) -> dict:
    """Call `intent_layer.py deep-scan-state <root> detect-changes` and parse JSON."""
    intent_layer = _SCRIPT_DIR / "intent_layer.py"
    if not intent_layer.exists():
        return {"mode": "full", "reason": "intent_layer.py not found"}
    try:
        result = subprocess.run(
            [sys.executable, str(intent_layer), "deep-scan-state", str(root), "detect-changes"],
            capture_output=True, text=True, timeout=30,
        )
        return json.loads(result.stdout.strip() or "{}")
    except Exception as e:
        return {"mode": "full", "reason": f"detect-changes failed: {e}"}


# Tooling / VCS dirs that are never "the change" (mirrors refresh.py SKIP_DIRS).
# Keeps the ledger from recording its own .archie/ output or editor/CLI scaffolding.
_SKIP_PREFIXES = (".git/", ".archie/", ".claude/", ".codex/", ".agents/")


def _skipped(path: str) -> bool:
    return any(path == p.rstrip("/") or path.startswith(p) for p in _SKIP_PREFIXES)


def _worktree_changes(root: Path) -> list[str]:
    """Uncommitted changes — tracked modifications AND untracked files.

    This is the design's "+ working-tree state": the agent harvests intent while the
    work is still uncommitted, so the change to capture is in the working tree, not in
    any commit. We use clean path-listing commands (not `status --porcelain`, whose
    fixed-column format breaks once the surrounding shell strips leading whitespace):
      - tracked, modified/staged/deleted vs HEAD: `git diff --name-only HEAD`
      - untracked (respecting .gitignore):        `git ls-files --others --exclude-standard`
    Tooling/VCS dirs are filtered out.
    """
    tracked = _git(root, "diff", "--name-only", "HEAD")
    untracked = _git(root, "ls-files", "--others", "--exclude-standard")
    files = []
    for out in (tracked, untracked):
        for f in out.split("\n"):
            f = f.strip()
            if f and not _skipped(f):
                files.append(f)
    return files


def _committed_since(root: Path, ref: str) -> list[str]:
    out = _git(root, "diff", "--name-only", f"{ref}..HEAD")
    return [f for f in out.split("\n") if f and not _skipped(f)]


def _resolve_diff(root: Path, since: str | None) -> dict:
    """Return {mode, changed_files, affected_folders, ratio} or {too_large:True,...}.

    The change to capture = uncommitted working-tree changes UNION the committed delta
    since the baseline. A stale/huge committed baseline (the "too large" guard) is
    IGNORED when there is current work in the tree — we record the work in front of us.
    We only bail with `too_large` when there is nothing uncommitted AND the committed
    delta is too large to evolve piecemeal.
    """
    dc = _detect_changes(root)
    mode = dc.get("mode")
    reason = dc.get("reason", "")
    threshold_full = mode == "full" and "exceeds threshold" in reason

    worktree = _worktree_changes(root)

    if since:
        committed = _committed_since(root, since)
    elif mode == "incremental" and dc.get("changed_files") is not None:
        committed = [f for f in dc.get("changed_files", []) if not _skipped(f)]
    elif threshold_full:
        committed = []  # stale/huge committed baseline — capture current work instead
    else:
        # No baseline: fall back to the last commit so there's something to review.
        committed = _committed_since(root, "HEAD~1") if not worktree else []

    changed = sorted(set(worktree) | set(committed))

    if not changed and threshold_full:
        return {"too_large": True, "reason": reason}

    return {
        "mode": "incremental",
        "changed_files": changed,
        "affected_folders": _ancestors(changed),
        "ratio": dc.get("ratio", 0.0) if mode == "incremental" else 0.0,
    }


# ---------------------------------------------------------------------------
# claim validation + classification
# ---------------------------------------------------------------------------

def _read_payload(input_file: str | None) -> list[dict]:
    raw = Path(input_file).read_text() if input_file else sys.stdin.read()
    raw = raw.strip()
    if not raw:
        return []
    data = json.loads(raw)
    if isinstance(data, list):
        claims = data
    elif isinstance(data, dict):
        claims = data.get("claims") or data.get("intent_updates") or []
    else:
        raise ValueError("payload must be a JSON list or object")
    if not isinstance(claims, list):
        raise ValueError("`claims` must be a list")
    return claims


def _validate_claim(claim: object, idx: int) -> dict:
    if not isinstance(claim, dict):
        raise ValueError(f"claim #{idx} is not an object")
    kind = claim.get("kind") or claim.get("type") or claim.get("section")
    if kind not in _VALID_KINDS:
        raise ValueError(f"claim #{idx}: kind must be one of {sorted(_VALID_KINDS)}, got {kind!r}")
    statement = (claim.get("statement") or claim.get("title") or "").strip()
    if not statement:
        raise ValueError(f"claim #{idx}: missing statement")
    confidence = claim.get("confidence", "low")
    if confidence not in _VALID_CONFIDENCE:
        raise ValueError(f"claim #{idx}: confidence must be one of {sorted(_VALID_CONFIDENCE)}")
    evidence = claim.get("evidence_files", [])
    if not isinstance(evidence, list):
        raise ValueError(f"claim #{idx}: evidence_files must be a list")
    return {
        "kind": kind,
        "statement": statement,
        "evidence_files": [str(e) for e in evidence],
        "confidence": confidence,
        "reconstructed": bool(claim.get("reconstructed", False)),
    }


def _evidence_in_diff(evidence_files: list[str], changed_files: list[str], affected: list[str]) -> bool:
    changed_set = set(changed_files)
    for ev in evidence_files:
        if ev in changed_set:
            return True
        if any(ev == f or ev.startswith(f + "/") for f in affected):
            return True
    return False


def _classify(claim: dict, changed_files: list[str], affected: list[str]) -> str:
    """eligible = confident + non-reconstructed + evidenced inside the diff; else staged."""
    if claim["reconstructed"]:
        return "staged"
    if claim["confidence"] not in ("medium", "high"):
        return "staged"
    if not _evidence_in_diff(claim["evidence_files"], changed_files, affected):
        return "staged"
    return "eligible"


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------

def _changes_dir(root: Path) -> Path:
    return root / ".archie" / _CHANGES_DIR


def _next_version(changes_dir: Path) -> int:
    if not changes_dir.is_dir():
        return 1
    existing = [f for f in changes_dir.iterdir()
                if f.name.startswith("change_") and f.name.endswith(".json")]
    return len(existing) + 1


def _unique_change_path(changes_dir: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base = changes_dir / f"change_{ts}.json"
    if not base.exists():
        return base
    i = 2
    while True:
        candidate = changes_dir / f"change_{ts}_{i}.json"
        if not candidate.exists():
            return candidate
        i += 1


def cmd_record(root: Path, input_file: str | None, agent: str, since: str | None) -> int:
    # 1. Read + validate the payload BEFORE touching disk (reject malformed wholesale).
    try:
        raw_claims = _read_payload(input_file)
        claims = [_validate_claim(c, i) for i, c in enumerate(raw_claims)]
    except (ValueError, json.JSONDecodeError, OSError) as e:
        print(json.dumps({"ok": False, "error": f"invalid payload: {e}"}))
        return 1

    # 2. Resolve the diff (reuse detect-changes; respect the too-large guard).
    diff = _resolve_diff(root, since)
    if diff.get("too_large"):
        print(json.dumps({
            "ok": False, "mode": "full",
            "reason": f"delta too large — run /archie-deep-scan ({diff['reason']})",
        }))
        return 0

    changed_files = diff["changed_files"]
    affected = diff["affected_folders"]

    # 3. Classify each claim (Phase 1: classify only, never fold).
    out_claims = []
    for c in claims:
        status = _classify(c, changed_files, affected)
        out_claims.append({
            "id": f"{c['kind']}:{_slugify(c['statement'])[:60]}",
            "kind": c["kind"],
            "status": status,
            "statement": c["statement"],
            "evidence_files": c["evidence_files"],
            "confidence": c["confidence"],
            "reconstructed": c["reconstructed"],
        })

    # 4. Provenance (reuse the save-baseline git pattern).
    sha = _git(root, "rev-parse", "HEAD")
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    record = {
        "version": None,  # filled below
        "id": f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{sha[:7] or 'nogit'}",
        "folded": False,  # Phase 1 never folds
        "provenance": {
            "created_at": _now_iso_short(),
            "git_head": sha,
            "branch": branch,
            "agent": agent,
            "reconstructed": any(c["reconstructed"] for c in claims),
        },
        "diff": {
            "mode": diff["mode"],
            "changed_files": changed_files,
            "affected_folders": affected,
            "ratio": diff["ratio"],
        },
        "claims": out_claims,
    }

    # 5. Write the versioned change file + latest.json (mirror drift._save_snapshot).
    changes_dir = _changes_dir(root)
    changes_dir.mkdir(parents=True, exist_ok=True)
    record["version"] = _next_version(changes_dir)
    path = _unique_change_path(changes_dir)
    path.write_text(json.dumps(record, indent=2))
    (changes_dir / "latest.json").write_text(json.dumps(record, indent=2))

    eligible = sum(1 for c in out_claims if c["status"] == "eligible")
    staged = sum(1 for c in out_claims if c["status"] == "staged")
    print(json.dumps({
        "ok": True,
        "id": record["id"],
        "version": record["version"],
        "branch": branch,
        "folded": False,
        "eligible": eligible,
        "staged": staged,
        "changed_count": len(changed_files),
        "path": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
    }))
    return 0


def cmd_list(root: Path, as_json: bool) -> int:
    changes_dir = _changes_dir(root)
    if not changes_dir.is_dir():
        print("No change ledger found (.archie/changes/).", file=sys.stderr)
        if as_json:
            print(json.dumps([]))
        return 0
    files = sorted(
        [f for f in changes_dir.iterdir()
         if f.name.startswith("change_") and f.name.endswith(".json")],
        key=lambda f: f.name,
    )
    entries = []
    for f in files:
        try:
            data = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        claims = data.get("claims", [])
        entries.append({
            "file": f.name,
            "version": data.get("version"),
            "created_at": data.get("provenance", {}).get("created_at", ""),
            "branch": data.get("provenance", {}).get("branch", ""),
            "folded": data.get("folded", False),
            "eligible": sum(1 for c in claims if c.get("status") == "eligible"),
            "staged": sum(1 for c in claims if c.get("status") == "staged"),
            "id": data.get("id", ""),
        })

    if not entries:
        print("No change records yet.", file=sys.stderr)
    else:
        print(f"\nChange ledger ({len(entries)} records):\n", file=sys.stderr)
        for e in entries:
            print(
                f"  v{e['version']:<3} {e['created_at']:<16} {e['branch']:<24} "
                f"eligible={e['eligible']} staged={e['staged']}  {e['file']}",
                file=sys.stderr,
            )
        print("", file=sys.stderr)
    print(json.dumps(entries, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Phase 2 — fold plumbing (the AI fold itself is done by the /archie-sync agent;
# these are the deterministic bookends: scope resolution + apply/re-render/validate)
# ---------------------------------------------------------------------------

# claim kind -> the descriptive blueprint section(s) the agent reconciles.
# Descriptive kinds (the default) keep the snapshot current; advisory kinds are
# optional. `rule` is the only kind that edits rules.json instead of blueprint.json.
_KIND_TARGET = {
    # descriptive — the snapshot of what the code IS
    "behavior":  {"sections": ["components", "communication"]},
    "structure": {"sections": ["components"]},
    "dataflow":  {"sections": ["communication", "architecture_diagram"]},
    "data":      {"sections": ["data_models", "persistence_stores", "data_overview"]},
    "tech":      {"sections": ["technology"]},
    "reference": {"sections": ["quick_reference"]},
    # advisory — optional side-output
    "decision":  {"sections": ["decisions"]},
    "pitfall":   {"sections": ["pitfalls"], "also": ".archie/findings.json"},
    "guideline": {"sections": ["implementation_guidelines"]},
    "rule":      {"sections": [], "edit_file": ".archie/rules.json"},
}


def _newest_change(root: Path) -> Path | None:
    changes_dir = _changes_dir(root)
    if not changes_dir.is_dir():
        return None
    files = sorted(
        [f for f in changes_dir.iterdir()
         if f.name.startswith("change_") and f.name.endswith(".json")],
        key=lambda f: f.name,
    )
    return files[-1] if files else None


def _load_change(root: Path, change_file: str | None):
    """Return (path, data). Defaults to the newest change_*.json (NOT latest.json,
    so marking folded updates the real record)."""
    if change_file:
        p = Path(change_file)
        if not p.is_absolute():
            p = root / change_file
    else:
        p = _newest_change(root)
    if not p or not p.exists():
        return None, None
    try:
        return p, json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return p, None


def _persist_change(root: Path, path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2))
    newest = _newest_change(root)
    if newest and newest.name == path.name:
        (_changes_dir(root) / "latest.json").write_text(json.dumps(data, indent=2))


def _load_enforcement_rules(archie: Path) -> list:
    """Mirror finalize.py's enforcement-rule loading for the render step."""
    rules = []
    for fname, src in (("rules.json", "project"), ("platform_rules.json", "platform")):
        p = archie / fname
        if not p.exists():
            continue
        try:
            d = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        items = d if isinstance(d, list) else d.get("rules", [])
        if isinstance(items, list):
            for r in items:
                if isinstance(r, dict):
                    r.setdefault("_archie_source", src)
                    rules.append(r)
    return rules


def cmd_fold_context(root: Path, change_file: str | None) -> int:
    """Resolve scope for the eligible claims: which blueprint section / rules.json
    each claim edits, plus the per-folder CLAUDE.md in scope. Hands the agent a
    bounded edit target list (never the whole blueprint) and stores a guardrail
    snapshot for fold-apply. Deterministic."""
    path, data = _load_change(root, change_file)
    if data is None:
        print(json.dumps({"ok": False, "error": "no change record found"}))
        return 1
    eligible = [c for c in data.get("claims", []) if c.get("status") == "eligible"]
    archie = root / ".archie"
    bp_path = archie / "blueprint.json"
    bp = {}
    if bp_path.exists():
        try:
            bp = json.loads(bp_path.read_text())
        except (OSError, json.JSONDecodeError):
            bp = {}

    targets = []
    for c in eligible:
        kind = c.get("kind") or c.get("section")
        spec = _KIND_TARGET.get(kind, {"sections": []})
        targets.append({
            "claim_id": c.get("id"),
            "kind": kind,
            "advisory": kind in _ADVISORY_KINDS,
            "statement": c.get("statement") or c.get("title"),
            "evidence_files": c.get("evidence_files", []),
            "edit_file": spec.get("edit_file", ".archie/blueprint.json"),
            "blueprint_sections": spec.get("sections", []),
            "also_update": spec.get("also"),
        })

    affected = data.get("diff", {}).get("affected_folders", [])
    intent_files = []
    for folder in affected:
        cf = root / folder / "CLAUDE.md"
        if cf.exists():
            intent_files.append(str(cf.relative_to(root)))

    # Persist a guardrail snapshot so fold-apply can refuse a render that dropped
    # a whole top-level section.
    data["fold_guardrail"] = {"blueprint_top_level_keys": sorted(bp.keys())}
    _persist_change(root, path, data)

    print(json.dumps({
        "ok": True,
        "change_file": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
        "eligible_count": len(eligible),
        "targets": targets,
        "intent_files": intent_files,
        "instructions": (
            "RECONCILE each statement into the snapshot — do not just append. For each "
            "target: read ONLY the named blueprint_sections (the descriptive snapshot of "
            "what the code IS) and the evidence files, then pick ONE op: NO-OP (already "
            "accurately described — common), UPDATE (described but now wrong — correct in "
            "place), ADD (new), REMOVE (code dropped it). Descriptive kinds "
            "(behavior/structure/dataflow/data/tech/reference) are the point; advisory "
            "kinds (decision/pitfall/rule) only when genuinely warranted. Edit "
            "blueprint.json (source of truth); rule -> rules.json; pitfall -> also "
            "findings.json. Then reconcile the DESCRIPTIVE section of each touched "
            "per-folder CLAUDE.md in `intent_files` (direct edit — these are the folder "
            "snapshots). Finally run: sync.py fold-apply ."
        ),
    }, indent=2))
    return 0


def cmd_fold_apply(root: Path, change_file: str | None) -> int:
    """After the agent edited blueprint.json / rules.json: validate the guardrail,
    re-render root docs from the edited blueprint, propagate to the intent layer,
    and mark the record folded. Deterministic plumbing."""
    path, data = _load_change(root, change_file)
    if data is None:
        print(json.dumps({"ok": False, "error": "no change record found"}))
        return 1
    archie = root / ".archie"
    bp_path = archie / "blueprint.json"
    if not bp_path.exists():
        print(json.dumps({"ok": False, "error": "no blueprint.json"}))
        return 1
    try:
        bp = json.loads(bp_path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"ok": False, "error": f"blueprint.json invalid after edit, aborting render: {e}"}))
        return 1

    snapshot = (data.get("fold_guardrail") or {}).get("blueprint_top_level_keys", [])
    missing = [k for k in snapshot if k not in bp]
    if missing:
        print(json.dumps({"ok": False, "error": f"guardrail tripped — blueprint top-level sections dropped: {missing}"}))
        return 1

    sys.path.insert(0, str(_SCRIPT_DIR))
    try:
        from _common import normalize_blueprint  # noqa: E402
        import renderer  # noqa: E402
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"cannot load renderer/_common (blueprint NOT modified): {e}"}))
        return 1
    try:
        import intent_layer  # noqa: E402
        lock = intent_layer._state_lock(root)
    except Exception:
        from contextlib import nullcontext
        lock = nullcontext()

    # Render to memory FIRST (generate_all is pure). Only touch disk once the
    # render succeeded, so a render failure leaves blueprint.json + docs untouched
    # (no half-applied state) and reports a clean JSON error instead of a traceback.
    rendered = []
    try:
        with lock:
            normalize_blueprint(bp)
            enforcement_rules = _load_enforcement_rules(archie)
            files = renderer.generate_all(bp, enforcement_rules=enforcement_rules)
            bp_path.write_text(json.dumps(bp, indent=2))
            for rel, content in files.items():
                full = root / rel
                full.parent.mkdir(parents=True, exist_ok=True)
                if rel in renderer.MERGEABLE_FILES:
                    full.write_text(renderer.render_mergeable(full, content))
                else:
                    full.write_text(content)
                rendered.append(rel)
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"fold-apply render failed (record NOT marked folded): {e}"}))
        return 1

    # NOTE: per-folder CLAUDE.md (the intent-layer folder snapshots) are reconciled
    # DIRECTLY by the agent during the edit step, scoped to the touched folders. We do
    # NOT run a repo-wide inject-scoped here — that backfilled every scoped block and
    # produced churn unrelated to the change. The render above only regenerates the
    # root docs (CLAUDE.md / AGENTS.md / .claude/rules) from the edited blueprint.
    folded = 0
    for c in data.get("claims", []):
        if c.get("status") == "eligible":
            c["status"] = "folded"
            folded += 1
    data["folded"] = True
    _persist_change(root, path, data)

    print(json.dumps({
        "ok": True,
        "folded": folded,
        "rendered_count": len(rendered),
    }))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _usage() -> None:
    print("Usage:", file=sys.stderr)
    print("  python3 sync.py record       /path/to/repo [--input payload.json] [--agent claude|codex] [--since <ref>]", file=sys.stderr)
    print("  python3 sync.py list         /path/to/repo [--json]", file=sys.stderr)
    print("  python3 sync.py fold-context /path/to/repo [--change <file>]   (Phase 2: scope for the agent)", file=sys.stderr)
    print("  python3 sync.py fold-apply   /path/to/repo [--change <file>]   (Phase 2: re-render + propagate + mark folded)", file=sys.stderr)


def _opt(rest: list[str], name: str) -> str | None:
    for i, a in enumerate(rest):
        if a == name and i + 1 < len(rest):
            return rest[i + 1]
    return None


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        _usage()
        return 1
    cmd = argv[1]
    root = Path(argv[2]).resolve()
    rest = argv[3:]

    if cmd == "record":
        input_file = None
        agent = "unknown"
        since = None
        i = 0
        while i < len(rest):
            if rest[i] == "--input" and i + 1 < len(rest):
                input_file = rest[i + 1]; i += 2
            elif rest[i] == "--agent" and i + 1 < len(rest):
                agent = rest[i + 1]; i += 2
            elif rest[i] == "--since" and i + 1 < len(rest):
                since = rest[i + 1]; i += 2
            else:
                i += 1
        return cmd_record(root, input_file, agent, since)

    if cmd == "list":
        return cmd_list(root, "--json" in rest)

    if cmd == "fold-context":
        return cmd_fold_context(root, _opt(rest, "--change"))

    if cmd == "fold-apply":
        return cmd_fold_apply(root, _opt(rest, "--change"))

    _usage()
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

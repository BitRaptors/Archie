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
  python3 sync.py record       /path/to/repo [--input payload.json] [--agent claude|codex] [--since <ref>]
  python3 sync.py list         /path/to/repo [--json]
  python3 sync.py plan-capture /path/to/repo   (stdin: hook envelope with tool_input.plan)
  python3 sync.py plan-list    /path/to/repo
  python3 sync.py plan-consume /path/to/repo
  python3 sync.py churn-bump   /path/to/repo   (stdin: hook envelope with edit tool-call)
  python3 sync.py churn-status /path/to/repo
  python3 sync.py churn-reset  /path/to/repo

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

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent

# Re-export the pure hunk parser from diff_basis so both sync and delivery_review
# share one implementation without pulling in the heavy sync module. Guarded so a
# missing sibling never breaks import of sync.py.
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
from diff_basis import parse_hunk_added_lines  # noqa: E402,F401

# A claim is a STATEMENT about what the code now is. Descriptive kinds are the
# default (keep the blueprint snapshot current); advisory kinds are an optional
# side-output, emitted only when a change genuinely establishes one.
_DESCRIPTIVE_KINDS = {"behavior", "structure", "dataflow", "data", "tech", "reference"}
_ADVISORY_KINDS = {"decision", "pitfall", "rule", "guideline"}
_VALID_KINDS = _DESCRIPTIVE_KINDS | _ADVISORY_KINDS
_VALID_CONFIDENCE = {"low", "medium", "high"}
_CHANGES_DIR = "changes"
_PLANS_DIR = "tmp/plans"           # under .archie/ — durable captured plans
_EDIT_TOOLS = {"Write", "Edit", "MultiEdit", "apply_patch"}
_CHURN_FILE = "tmp/churn.json"     # under .archie/
_DEFAULT_CHURN_FILES = 8
_DEFAULT_CHURN_LINES = 150


def _churn_path(root: Path) -> Path:
    return _archie_dir(root) / _CHURN_FILE


def _load_churn(root: Path) -> dict:
    p = _churn_path(root)
    if p.is_file():
        try:
            d = json.loads(p.read_text())
            if isinstance(d, dict):
                d.setdefault("files", [])
                d.setdefault("edits", 0)
                d.setdefault("lines", 0)
                return d
        except (json.JSONDecodeError, OSError):
            pass
    return {"files": [], "edits": 0, "lines": 0}


def _churn_thresholds(root: Path) -> tuple:
    files_t, lines_t = _DEFAULT_CHURN_FILES, _DEFAULT_CHURN_LINES
    cfg = _archie_dir(root) / "config.json"
    if cfg.is_file():
        try:
            c = json.loads(cfg.read_text())
            if isinstance(c, dict):
                files_t = int(c.get("churn_threshold_files", files_t))
                lines_t = int(c.get("churn_threshold_lines", lines_t))
        except (json.JSONDecodeError, OSError, ValueError, TypeError):
            pass
    return files_t, lines_t


def _churn_summary(root: Path, st: dict) -> dict:
    files_t, lines_t = _churn_thresholds(root)
    nfiles = len(st["files"])
    return {
        "files": nfiles, "edits": st["edits"], "lines": st["lines"],
        "threshold_files": files_t, "threshold_lines": lines_t,
        "crossed": nfiles >= files_t or st["lines"] >= lines_t,
    }


def _archie_dir(root: Path) -> Path:
    return root / ".archie"


def _read_envelope() -> dict:
    """Read a hook tool-call envelope from stdin; tolerate empty/garbage."""
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _safe_branch(root: Path) -> str:
    try:
        return _git(root, "rev-parse", "--abbrev-ref", "HEAD") or "unknown"
    except Exception:
        return "unknown"


import os as _os
import subprocess as _sp


def _branch(root) -> str:
    b = _os.environ.get("ARCHIE_BRANCH") or _os.environ.get("GITHUB_HEAD_REF")
    if b:
        return b
    try:
        out = _sp.run(["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
                      capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def _session_id() -> str:
    return _os.environ.get("CLAUDE_SESSION_ID") or _os.environ.get("ARCHIE_SESSION_ID") or "session"


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
    """eligible = confident + non-reconstructed + evidenced inside the diff; else staged.

    Snapshot-vs-contract (Phase 1): ADVISORY kinds (decision/pitfall/rule/guideline) are
    the *contract* (the law). A code-fold must never silently move the law, or a real
    deviation would be hidden from the PR review — so advisory claims are ALWAYS `staged`
    (recorded + surfaced as proposed amendments), never `eligible`/folded. Only the
    descriptive *mirror* (what the code is now) folds automatically.
    """
    if claim.get("kind") in _ADVISORY_KINDS:
        return "staged"
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

    # 5. Write the versioned change file + latest.json (timestamped snapshot history).
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

# claim kind -> the blueprint section(s) for that kind. Only DESCRIPTIVE kinds fold
# (the mirror); ADVISORY kinds (decision/pitfall/rule/guideline) are always `staged`
# (never folded). The advisory entries below document where a DELIBERATE amendment would
# land — NOT where a code-fold writes (a code-fold writes the mirror only).
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

# Snapshot-vs-contract guardrail (Phase 1): the "contract" (the law) a code-fold must
# never move. The invariant sections + the prescriptive rule sections + the rule files.
# (decisions/pitfalls carry mixed descriptive prose, so they're governed by the
# advisory->staged gate in _classify, not this byte-level fingerprint — which would be
# noisy on them. The sections below are pure law that NO descriptive kind targets.)
_CONTRACT_SECTIONS = (
    "domain_invariants", "derived_invariants", "unenforced_invariants",
    "development_rules", "infrastructure_rules", "architecture_rules",
)
_CONTRACT_FILES = ("rules.json", "platform_rules.json")


def _contract_fingerprint(root: Path, bp: dict) -> str:
    """Stable hash of the contract (invariant sections + rule files); used to refuse a
    fold-apply that moved the law."""
    h = hashlib.sha256()
    h.update(json.dumps({k: bp.get(k) for k in _CONTRACT_SECTIONS},
                        sort_keys=True, ensure_ascii=False).encode("utf-8"))
    for fname in _CONTRACT_FILES:
        p = root / ".archie" / fname
        h.update(b"\x00")
        if p.exists():
            try:
                h.update(p.read_bytes())
            except OSError:
                pass
    return h.hexdigest()


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
    # Advisory claims are the CONTRACT (the law) — a code-fold never writes them. They
    # surface as PROPOSED amendments for a separate, deliberate decision (not folded).
    staged_amendments = [
        {"claim_id": c.get("id"), "kind": c.get("kind") or c.get("section"),
         "statement": c.get("statement") or c.get("title"),
         "evidence_files": c.get("evidence_files", [])}
        for c in data.get("claims", [])
        if (c.get("kind") or c.get("section")) in _ADVISORY_KINDS
    ]
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

    # Intent targets = the LEAF folder(s) that directly contain the changed files —
    # NOT every ancestor. A change's description belongs in the folder snapshot that
    # owns it (e.g. activity_main/CLAUDE.md), not in the top-level app/CLAUDE.md.
    changed = data.get("diff", {}).get("changed_files", [])
    leaf_dirs = sorted({str(Path(f).parent) for f in changed})
    intent_files = []
    for folder in leaf_dirs:
        if folder in (".", ""):
            continue  # root CLAUDE.md is the generated pointer, not a folder snapshot
        cf = root / folder / "CLAUDE.md"
        if cf.exists():
            intent_files.append(str(cf.relative_to(root)))

    # Persist a guardrail snapshot so fold-apply can refuse a render that dropped a whole
    # top-level section OR moved the contract (the law) during a descriptive fold.
    data["fold_guardrail"] = {
        "blueprint_top_level_keys": sorted(bp.keys()),
        "contract_fingerprint": _contract_fingerprint(root, bp),
    }
    _persist_change(root, path, data)

    print(json.dumps({
        "ok": True,
        "change_file": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
        "eligible_count": len(eligible),
        "targets": targets,
        "staged_amendments": staged_amendments,
        "intent_files": intent_files,
        "instructions": (
            "RECONCILE each statement into the snapshot — do not just append. For each "
            "target: read ONLY the named blueprint_sections (the descriptive MIRROR of "
            "what the code IS) and the evidence files, then pick ONE op: NO-OP (already "
            "accurately described — common), UPDATE (described but now wrong — correct in "
            "place), ADD (new), REMOVE (code dropped it). Edit ONLY descriptive mirror "
            "sections of blueprint.json. DO NOT edit the CONTRACT — rules.json, "
            "domain_invariants, derived_invariants, decisions, or pitfalls. Advisory "
            "claims are listed under `staged_amendments` as PROPOSED contract changes; "
            "they must NOT be folded — changing the law is a separate, deliberate step. "
            "Then reconcile the DESCRIPTIVE section of each touched per-folder CLAUDE.md "
            "in `intent_files` (direct edit). Finally run: sync.py fold-apply ."
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

    # Contract awareness (Phase 1): a code-fold reconciles the descriptive MIRROR; the
    # contract (rules.json / invariants) changes only DELIBERATELY. We do NOT block a
    # deliberate rule change — rules legitimately change during real work — but we surface
    # it so the law never moves SILENTLY. Computed BEFORE normalize so normalization can't
    # mask or falsely flag it. (advisory->staged already stops AUTOMATIC contract moves.)
    expected_fp = (data.get("fold_guardrail") or {}).get("contract_fingerprint")
    contract_changed = bool(
        expected_fp is not None and _contract_fingerprint(root, bp) != expected_fp
    )

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
        "contract_changed": contract_changed,
        **({"note": "This fold ALSO changed the contract (rules.json / invariants) — a "
                    "DELIBERATE amendment, not an automatic mirror update. It will be "
                    "reviewed on the PR."} if contract_changed else {}),
    }))
    return 0


# ---------------------------------------------------------------------------
# override-ack — record a user-authorized rule override
# ---------------------------------------------------------------------------

def cmd_override_ack(root: Path, rule_id: str, reason: str) -> int:
    """Record a human-authorized rule override AND apply it to the branch.

    Agent-run ONLY — and only after the user explicitly confirmed crossing the rule
    in conversation. This writes the contract change into the source of truth: the
    rule leaves rules.json, the blueprint invariant is stamped `overridden`, and the
    reason + authorizer + a snapshot of the law text land in overrides.json. The PR
    then carries a real rules diff, the review judges it, and MERGING RATIFIES IT —
    there is no separate ratify step."""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent))
    if not rule_id or not reason:
        print('usage: sync.py override-ack <root> <rule_id> --reason "..."', file=sys.stderr)
        return 1
    import overrides as _ov

    archie = root / ".archie"
    # Capture the grounding invariant ids BEFORE the rule leaves rules.json —
    # rule_aliases reads the rule's own `forced_by` citation.
    ids = {rule_id} | _ov.rule_aliases(root, rule_id)

    law, removed = "", False
    for fname in ("rules.json", "platform_rules.json"):
        rp = archie / fname
        try:
            data = json.loads(rp.read_text())
        except Exception:
            continue
        items = data.get("rules", []) if isinstance(data, dict) else data
        if not isinstance(items, list):
            continue
        hit = next((r for r in items if isinstance(r, dict) and r.get("id") == rule_id), None)
        if hit is None:
            continue
        law = str(hit.get("description", ""))
        kept = [r for r in items if not (isinstance(r, dict) and r.get("id") == rule_id)]
        if isinstance(data, dict):
            data["rules"] = kept
        else:
            data = kept
        try:
            rp.write_text(json.dumps(data, indent=2) + "\n")
            removed = True
        except Exception:
            pass
        break

    e = _ov.ack(root, rule_id, reason, law=law,
                invariant_ids=sorted(ids - {rule_id}))

    # Stamp the blueprint invariant(s) this rule is grounded in, so the rendered
    # product-laws stop stating a retired law as live truth and the review engine
    # stops enforcing it (selector skips `overridden`).
    bp_p = archie / "blueprint.json"
    try:
        bp = json.loads(bp_p.read_text())
        for inv in bp.get("domain_invariants") or []:
            if isinstance(inv, dict) and inv.get("id") in ids:
                inv["status"] = "overridden"
                inv["override"] = {"reason": reason,
                                   "authorized_by": e["authorized_by"],
                                   "branch": e["branch"]}
        bp_p.write_text(json.dumps(bp, indent=2) + "\n")
    except Exception:
        pass

    print(json.dumps({"acked": e["rule_id"], "branch": e["branch"],
                      "by": e["authorized_by"], "rule_removed": removed}))
    return 0


_BASE_BRANCH_FALLBACK = {"main", "master", "develop"}


def _base_branch(root: Path) -> str | None:
    """Resolve the repo's base (merge-target) branch via the remote's HEAD
    symlink. Returns None when there's no remote to ask (e.g. local test
    repos) — the caller falls back to a hardcoded common-name set."""
    ref = _git(root, "symbolic-ref", "refs/remotes/origin/HEAD")
    return ref.rsplit("/", 1)[-1] if ref else None


def _parse_changed_lines(root: Path, base: str) -> dict:
    """Run `git diff -U0 <base> --` and return dict[str, set[int]] of added lines.

    Best-effort: guards the subprocess call and returns {} on any failure.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "diff", "-U0", base, "--"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return {}
        return parse_hunk_added_lines(result.stdout)
    except Exception:
        return {}


def cmd_review(root: Path) -> int:
    """Run the light delivery-review pipeline on the branch delta and print the
    verdict. Non-blocking: ALWAYS returns 0, never raises to the caller."""
    # lazy bare imports (match sync.py's own sibling-import style)
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent))
    try:
        from diff_basis import detect_base, changed_files_result   # noqa
        from sync_review import run_sync_review                     # noqa
        from _common import _load_json                              # noqa

        base = detect_base(root)
        cf = changed_files_result(root, base)
        changed = cf.get("files", [])
        # diff text (bounded) for the prompt
        diff_text = subprocess.run(
            ["git", "-C", str(root), "diff", base, "--"],
            capture_output=True, text=True,
        ).stdout[:200000]
        # changed_lines: added-line numbers per file (best-effort)
        changed_lines = _parse_changed_lines(root, base)
        blueprint = _load_json(root / ".archie" / "blueprint.json") or {}
        scan = _load_json(root / ".archie" / "scan.json") or {}
        import_graph = scan.get("import_graph", {}) if isinstance(scan, dict) else {}
        branch = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True,
        ).stdout.strip() or "HEAD"
        floors = {"behavioral_break": 0.6, "intent_unmet": 0.5,
                  "intent_partial": 0.5, "intent_drift": 0.6}
        out = run_sync_review(str(root), branch, blueprint, import_graph, diff_text,
                              changed, changed_lines, floors)
        if out.get("skipped"):
            print("[archie] delivery review: skipped (nothing relevant changed).")
        else:
            v = out.get("verdict", {})
            ack_note = (f" · {len(out.get('acked', []))} acknowledged override(s)"
                        if out.get("acked") else "")
            print(f"[archie] delivery review — {v.get('intent_completeness', '?')} criteria · "
                  f"{v.get('breaks', 0)} break(s) · {v.get('drift', 0)} drift · "
                  f"{len(out.get('confirmed', []))} finding(s)" + ack_note)
    except Exception as e:
        # non-blocking: never fail the caller
        print(f"[archie] delivery review skipped (error: {e})")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _usage() -> None:
    print("Usage:", file=sys.stderr)
    print("  python3 sync.py record            /path/to/repo [--input payload.json] [--agent claude|codex] [--since <ref>]", file=sys.stderr)
    print("  python3 sync.py list              /path/to/repo [--json]", file=sys.stderr)
    print("  python3 sync.py fold-context      /path/to/repo [--change <file>]   (Phase 2: scope for the agent)", file=sys.stderr)
    print("  python3 sync.py fold-apply        /path/to/repo [--change <file>]   (Phase 2: re-render + propagate + mark folded)", file=sys.stderr)
    print("  python3 sync.py plan-capture      /path/to/repo                     (stdin: hook envelope with tool_input.plan)", file=sys.stderr)
    print("  python3 sync.py plan-list         /path/to/repo", file=sys.stderr)
    print("  python3 sync.py plan-consume      /path/to/repo", file=sys.stderr)
    print("  python3 sync.py churn-bump        /path/to/repo                     (stdin: hook envelope with edit tool-call)", file=sys.stderr)
    print("  python3 sync.py churn-status      /path/to/repo", file=sys.stderr)
    print("  python3 sync.py churn-reset       /path/to/repo", file=sys.stderr)
    print("  python3 sync.py sync-stamp        /path/to/repo                     (record synced code state for the PR drift check)", file=sys.stderr)
    print("  python3 sync.py override-ack      /path/to/repo <rule_id> --reason \"...\"   (record + apply a user-authorized rule retirement onto this branch)", file=sys.stderr)
    print("  python3 sync.py review            /path/to/repo                     (run the delivery review on the branch delta; non-blocking)", file=sys.stderr)
    print("  python3 sync.py write-intent      /path/to/repo  spec.json          (merge branch intent into .archie/intent.json)", file=sys.stderr)
    print("  python3 sync.py capture-intent    /path/to/repo [text]              (append a user-turn event)", file=sys.stderr)
    print("  python3 sync.py imprint           /path/to/repo                     (write a story snapshot for the current branch + session)", file=sys.stderr)
    print("  python3 sync.py story             /path/to/repo [--history|<ts>]    (print current story, history list, or a specific version)", file=sys.stderr)


def _opt(rest: list[str], name: str) -> str | None:
    for i, a in enumerate(rest):
        if a == name and i + 1 < len(rest):
            return rest[i + 1]
    return None


def cmd_plan_capture(root: Path) -> int:
    """Persist the ExitPlanMode plan text as durable intent for /archie-sync.

    Works identically on Claude and Codex — both put plan text in tool_input.plan.
    """
    env = _read_envelope()
    ti = env.get("tool_input", {})
    plan = str(ti.get("plan", "") or "").strip() if isinstance(ti, dict) else ""
    if not plan:
        print(json.dumps({"ok": True, "captured": False}))
        return 0
    plans_dir = _archie_dir(root) / _PLANS_DIR
    plans_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = plans_dir / f"plan_{ts}.md"
    i = 2
    while path.exists():
        path = plans_dir / f"plan_{ts}_{i}.md"
        i += 1
    header = f"<!-- captured {ts} UTC | branch {_safe_branch(root)} -->\n\n"
    path.write_text(header + plan + "\n")
    print(json.dumps({"ok": True, "captured": True, "path": str(path.relative_to(root))}))
    return 0


def cmd_plan_list(root: Path) -> int:
    plans_dir = _archie_dir(root) / _PLANS_DIR
    files = (sorted(str(p.relative_to(root)) for p in plans_dir.glob("plan_*.md"))
             if plans_dir.is_dir() else [])
    print(json.dumps({"ok": True, "plans": files}))
    return 0


def cmd_plan_consume(root: Path) -> int:
    plans_dir = _archie_dir(root) / _PLANS_DIR
    moved = []
    if plans_dir.is_dir():
        consumed = plans_dir / "consumed"
        consumed.mkdir(parents=True, exist_ok=True)
        for p in sorted(plans_dir.glob("plan_*.md")):
            p.replace(consumed / p.name)
            moved.append(p.name)
    print(json.dumps({"ok": True, "consumed": moved}))
    return 0


def cmd_churn_bump(root: Path) -> int:
    env = _read_envelope()
    tool = env.get("tool_name", "")
    if tool not in _EDIT_TOOLS:
        print(json.dumps({"ok": True, "skipped": tool}))
        return 0
    ti = env.get("tool_input", {}) or {}
    fp = (ti.get("file_path") or ti.get("path") or "").strip()
    content = ti.get("content") or ti.get("new_string") or ""
    if not content and isinstance(ti.get("edits"), list):
        content = "\n".join(
            str(e.get("new_string", "")) for e in ti["edits"] if isinstance(e, dict)
        )
    content = str(content)
    st = _load_churn(root)
    if fp and fp not in st["files"]:
        st["files"].append(fp)
    st["edits"] += 1
    st["lines"] += content.count("\n") + (1 if content and not content.endswith("\n") else 0)
    p = _churn_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st))
    print(json.dumps({"ok": True, **_churn_summary(root, st)}))
    return 0


def cmd_churn_status(root: Path) -> int:
    print(json.dumps({"ok": True, **_churn_summary(root, _load_churn(root))}))
    return 0


def cmd_churn_reset(root: Path) -> int:
    try:
        _churn_path(root).unlink()
    except FileNotFoundError:
        pass
    print(json.dumps({"ok": True, "reset": True}))
    return 0


def cmd_sync_stamp(root: Path) -> int:
    """Record the code state this sync reconciled into committed
    `.archie/sync_state.json`, so a later PR can tell whether the branch's code
    moved on without a re-sync. Content-hashed (not commit-pinned), so it survives
    rebases/squashes and works whether the synced changes were committed or not."""
    import datetime
    import os
    script_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(script_dir))
    try:
        from _common import source_fingerprint  # noqa: E402
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"cannot load _common: {e}"}))
        return 1  # signal failure — a silently-skipped stamp must not look like success
    try:
        files = source_fingerprint(root)
        state = {
            "version": 1,
            "synced_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "head": _git(root, "rev-parse", "HEAD") or None,  # forensic only; the check is content-based
            "files": files,
        }
        archie = root / ".archie"
        archie.mkdir(parents=True, exist_ok=True)
        # Atomic write: a crash mid-write must not leave a malformed COMMITTED marker.
        # sort_keys so an unchanged tree serializes identically (no os.walk-order churn).
        target = archie / "sync_state.json"
        tmp = archie / "sync_state.json.tmp"
        try:
            tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
            os.replace(str(tmp), str(target))
        finally:
            if tmp.exists():
                tmp.unlink()  # don't leave a .tmp orphan if os.replace failed
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"stamp failed: {e}"}))
        return 1
    warn = " (no source files fingerprinted — check .archieignore/SKIP_DIRS)" if not files else ""
    print(json.dumps({"ok": True, "stamped": len(files), "warning": warn.strip() or None}))
    return 0


def cmd_write_intent(root, input_file) -> int:
    """Merge a JSON intent spec (from input_file) into .archie/intent.json. Non-crashing:
    a bad payload logs and leaves any existing file untouched. Always returns 0."""
    import sys as _sys
    _p = str(Path(__file__).parent)
    if _p not in _sys.path:
        _sys.path.insert(0, _p)
    from intent import write_committed_intent, INTENT_FILE  # noqa: E402
    if not input_file or not Path(input_file).exists():
        print("[archie] write-intent: no payload file; .archie/intent.json unchanged", file=sys.stderr)
        return 0
    try:
        spec = json.loads(Path(input_file).read_text())
    except Exception as e:
        print(f"[archie] write-intent: bad payload ({e}); .archie/intent.json unchanged", file=sys.stderr)
        return 0
    if not isinstance(spec, dict):
        print("[archie] write-intent: payload not an object; unchanged", file=sys.stderr)
        return 0
    write_committed_intent(root, spec)
    print(f"[archie] intent written to .archie/{INTENT_FILE}")
    return 0


def _intent_imports():
    import sys as _sys
    _pp = str(Path(__file__).parent)
    if _pp not in _sys.path:
        _sys.path.insert(0, _pp)
    import intent_capture
    return intent_capture


def cmd_capture_intent(root, text) -> int:
    ic = _intent_imports()
    ic.record_user_turn(root, text or "")
    print("[archie] intent event captured")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        _usage()
        return 1
    cmd = argv[1]
    # A flag is never a project path: `sync.py record --help` once resolved
    # "--help" as the root and CREATED a ./--help/ directory in the repo.
    if str(argv[2]).startswith("-"):
        _usage()
        return 1
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

    if cmd == "plan-capture":
        return cmd_plan_capture(root)

    if cmd == "plan-list":
        return cmd_plan_list(root)

    if cmd == "plan-consume":
        return cmd_plan_consume(root)

    if cmd == "churn-bump":
        return cmd_churn_bump(root)

    if cmd == "churn-status":
        return cmd_churn_status(root)

    if cmd == "churn-reset":
        return cmd_churn_reset(root)

    if cmd == "sync-stamp":
        return cmd_sync_stamp(root)

    if cmd == "override-ack":
        rid = rest[0] if rest and not rest[0].startswith("--") else ""
        return cmd_override_ack(root, rid, _opt(rest, "--reason") or "")

    if cmd == "review":
        return cmd_review(root)

    if cmd == "write-intent":
        return cmd_write_intent(root, argv[3] if len(argv) > 3 else None)

    if cmd == "capture-intent":
        return cmd_capture_intent(root, argv[3] if len(argv) > 3 else "")

    if cmd == "imprint":
        from datetime import datetime, timezone
        import story_synthesize
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
        p = story_synthesize.imprint(root, _branch(root), _session_id(), ts)
        print(f"[archie] imprinted {p}" if p else "[archie] no sources — nothing imprinted",
              file=sys.stderr)
        sys.exit(0)

    if cmd == "story":
        import story_store
        rest = [a for a in sys.argv[3:] if a != root]
        if "--history" in rest:
            for pth in story_store.list_versions(root, _branch(root)):
                print(pth.stem)
            sys.exit(0)
        if rest:  # a specific timestamp
            parsed = story_store.parse_story_file(
                story_store.story_dir(root, _branch(root)) / f"{rest[0]}.md")
        else:
            parsed = story_store.current_story(root, _branch(root))
        if not parsed:
            print("[archie] no story for this branch", file=sys.stderr); sys.exit(0)
        print(parsed["story"] + "\n")
        for f in parsed["facts"]:
            src = (f.get("from") or {}).get("quote", "")
            print(f"  [{f.get('id')}] {f.get('text')}   (from: {src[:60]})")
        for ng in parsed["non_goals"]:
            print(f"  non-goal: {ng}")
        sys.exit(0)

    _usage()
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

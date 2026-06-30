#!/usr/bin/env python3
"""Archie linker — orchestrates detached-mode presentation of artifacts.

Composes link_store (location/manifests) + link_strategy (OS presentation).
Commands: bind, reconcile, externalize, status, attach, detach.
Zero dependencies beyond Python 3.9+ stdlib.

Model
-----
- `.archie/` is a single ALWAYS-ON directory symlink: infrastructure (tooling,
  hooks, raw JSON the agent never reads directly). Write-through; never gated.
- The generated MARKDOWN the agent actually reads is gated PER FILE:
    * intent-layer per-folder `CLAUDE.md`        -> category "intent_layer"
    * blueprint docs `.claude/rules/**/*.md`     -> category "blueprint"
  Each markdown file is an individually toggleable per-file link. Turning one
  off removes only that file from the working tree (the agent can't read it);
  the content stays in the external store.

This feature exists ONLY in detached mode. In repo mode every function no-ops.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import link_store  # noqa: E402
import link_strategy  # noqa: E402

# The one always-on infrastructure directory link.
INFRA_LINK = ".archie"
INFRA_TARGET = "artifacts/.archie"
INFRASTRUCTURE_PATHS = {INFRA_LINK}

# Directory swept for per-file blueprint markdown.
RULES_DIR = ".claude/rules"

# Legacy marker — older builds appended an "@import" pointer line to CLAUDE.md.
# It was inert (rules reach the agent via the rendered root file + hooks, not an
# import), so bind no longer writes it; detach still strips it for old repos.
_LEGACY_POINTER_MARKER = "archie:detached"

GITIGNORE_BEGIN = "# >>> archie detached (managed) >>>"
GITIGNORE_END = "# <<< archie detached (managed) <<<"
GITIGNORE_ENTRIES = [
    "/.archie",
    "/.claude/rules",
    "**/CLAUDE.md",
    "!/CLAUDE.md",
]


# --------------------------------------------------------------------------- #
# classification
# --------------------------------------------------------------------------- #
def _file_target_and_category(rel_path: str):
    """(store-relative target, category) for a per-file artifact."""
    rel = rel_path.replace("\\", "/")
    if rel.startswith(RULES_DIR + "/"):
        return ("artifacts/" + rel, "blueprint")
    # per-folder CLAUDE.md (anything else externalized is intent-layer context)
    return ("tree/" + rel, "intent_layer")


def _category_of(rel_path: str) -> str:
    if rel_path in INFRASTRUCTURE_PATHS:
        return "infrastructure"
    return _file_target_and_category(rel_path)[1]


def is_exposed(exposure: dict, placement: dict) -> bool:
    """Infrastructure is always exposed; markdown follows override > category."""
    if placement.get("category") == "infrastructure" or placement["path"] in INFRASTRUCTURE_PATHS:
        return True
    overrides = exposure.get("overrides", {})
    if placement["path"] in overrides:
        return bool(overrides[placement["path"]])
    cat = placement.get("category") or _category_of(placement["path"])
    return bool(exposure.get("categories", {}).get(cat, True))


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _ensure_store_skeleton(store: Path) -> None:
    (store / "artifacts" / ".archie").mkdir(parents=True, exist_ok=True)
    (store / "artifacts" / ".claude" / "rules").mkdir(parents=True, exist_ok=True)
    (store / "tree").mkdir(parents=True, exist_ok=True)


def _ensure_gitignore(repo: Path) -> None:
    path = repo / ".gitignore"
    existing = path.read_text() if path.exists() else ""
    if GITIGNORE_BEGIN in existing:
        return
    block = "\n".join([GITIGNORE_BEGIN, *GITIGNORE_ENTRIES, GITIGNORE_END]) + "\n"
    sep = "" if existing.endswith("\n") or existing == "" else "\n"
    path.write_text(existing + sep + block)


def _absorb_existing_dir(link_path: Path, target: Path) -> None:
    """Move a real directory's contents into the store target before linking.

    `.archie/` is a MIXED directory: the npm installer copies tooling (the .py
    scripts, platform_*.json, workflow/) into it before bind runs, and generated
    artifacts land there too. Symlinking the whole dir would otherwise clobber
    the freshly-copied tooling, so we relocate the contents into the store first
    (where they remain reachable through the symlink).
    """
    if not link_path.exists() or link_path.is_symlink() or not link_path.is_dir():
        return
    target.mkdir(parents=True, exist_ok=True)
    for child in link_path.iterdir():
        dest = target / child.name
        if dest.exists():
            if dest.is_dir() and child.is_dir():
                continue
            dest.unlink() if dest.is_file() else shutil.rmtree(dest)
        shutil.move(str(child), str(dest))
    shutil.rmtree(link_path)


def _is_git_tracked(repo: Path, rel_path: str) -> bool:
    """True if rel_path is committed/staged in git. Such files are the user's —
    we never silently relocate them into the store. Non-git repos -> False."""
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "--error-unmatch", rel_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _store_for(repo: Path) -> Path | None:
    info = link_store.read_link_file(repo)
    if not info or info.get("mode") != "detached" or not info.get("project_id"):
        return None
    return link_store.project_store(info["project_id"])


def _file_kind() -> str:
    return "file" if link_strategy.strategy_for("file") == "symlink" else "file_copy"


def _target_of(placement: dict) -> str:
    """Store-relative target, tolerant of old-shape placements without it."""
    t = placement.get("target")
    if t:
        return t
    if placement["path"] in INFRASTRUCTURE_PATHS:
        return INFRA_TARGET
    return _file_target_and_category(placement["path"])[0]


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def bind(repo: Path, project_id: str | None = None) -> dict:
    repo = Path(repo).resolve()
    existing = link_store.read_link_file(repo)
    if existing and existing.get("project_id"):
        project_id = existing["project_id"]
    project_id = project_id or str(uuid.uuid4())

    store = link_store.project_store(project_id)
    _ensure_store_skeleton(store)

    info = {"schema_version": 1, "project_id": project_id, "mode": "detached"}
    link_store.write_link_file(repo, info)

    # The single infrastructure directory link.
    infra_target = store / INFRA_TARGET
    infra_link = repo / INFRA_LINK
    _absorb_existing_dir(infra_link, infra_target)
    strat = link_strategy.create_link(infra_target, infra_link, "dir")

    # PRESERVE existing per-file placements across re-bind (npx --detached runs
    # bind on every install). Only refresh the single infra entry — wiping the
    # registry would orphan every per-file link.
    placements = [p for p in link_store.read_placements(store)
                  if p.get("path") != INFRA_LINK]
    placements.insert(0, {
        "path": INFRA_LINK, "kind": "dir", "strategy": strat,
        "target": INFRA_TARGET, "category": "infrastructure",
    })
    link_store.write_placements(store, placements)

    # Seed exposure defaults if absent.
    link_store.write_exposure(store, link_store.read_exposure(store))

    _ensure_gitignore(repo)

    # Externalize any blueprint markdown that already exists (per-file). Fresh
    # installs have none yet — the renderer externalizes after each render.
    externalize_tree(repo, RULES_DIR)
    return info


def externalize_file(repo: Path, rel_path: str) -> str | None:
    """Relocate a freshly-written generated markdown file into the store and
    replace it with a per-file managed link. No-op in repo mode."""
    repo = Path(repo).resolve()
    store = _store_for(repo)
    if store is None:
        return None

    rel_path = rel_path.replace("\\", "/")
    link_path = repo / rel_path
    target_rel, category = _file_target_and_category(rel_path)
    target = store / target_rel

    if link_strategy.is_managed(link_path, store):
        return None

    # Never relocate a file the user committed to git — leave it as a real,
    # tracked file (no surprise file->symlink swap, no silently-moved content).
    if _is_git_tracked(repo, rel_path):
        return None

    if link_path.exists() and not link_path.is_symlink():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(link_path.read_text())
        link_path.unlink()
    elif not target.exists():
        return None  # nothing to externalize

    strat = link_strategy.create_link(target, link_path, _file_kind())

    placements = link_store.read_placements(store)
    if not any(p["path"] == rel_path for p in placements):
        placements.append({"path": rel_path, "kind": "file", "strategy": strat,
                           "target": target_rel, "category": category})
        link_store.write_placements(store, placements)
    return strat


# Backward-compatible name used by intent_layer.py.
externalize_folder_file = externalize_file


def externalize_tree(repo: Path, base_rel: str) -> list:
    """Externalize every real markdown file under repo/base_rel, per file."""
    repo = Path(repo).resolve()
    store = _store_for(repo)
    if store is None:
        return []
    base = repo / base_rel
    if not base.is_dir() or base.is_symlink():
        return []
    done = []
    for f in sorted(base.rglob("*")):
        if f.is_file() and not f.is_symlink():
            rel = f.relative_to(repo).as_posix()
            if externalize_file(repo, rel):
                done.append(rel)
    return done


def prune_blueprint(repo: Path, keep_rel_paths) -> list:
    """Drop blueprint markdown the renderer no longer produces.

    `keep_rel_paths` is the renderer's authoritative current set of
    `.claude/rules/*` files. Anything in the blueprint group that isn't in it is
    STALE (the renderer dropped it) and is removed from the tree, the store, AND
    the placements registry. A merely *hidden* file is still in keep_rel_paths
    (the renderer produced it; the user only toggled its visibility), so it is
    preserved. No-op in repo mode.
    """
    repo = Path(repo).resolve()
    store = _store_for(repo)
    if store is None:
        return []
    keep = {p.replace("\\", "/") for p in keep_rel_paths}
    placements = link_store.read_placements(store)
    removed, kept = [], []
    for p in placements:
        if p.get("category") == "blueprint" and p["path"] not in keep:
            target = store / _target_of(p)
            link_strategy.remove_managed(repo / p["path"], store,
                                         p.get("strategy", "symlink"), target)
            if target.exists() and not target.is_dir():
                target.unlink()
            removed.append(p["path"])
        else:
            kept.append(p)
    if removed:
        link_store.write_placements(store, kept)
    return removed


def reconcile(repo: Path) -> dict:
    repo = Path(repo).resolve()
    store = _store_for(repo)
    if store is None:
        return {"exposed": [], "hidden": []}
    exposure = link_store.read_exposure(store)
    placements = link_store.read_placements(store)

    exposed, hidden = [], []
    for p in placements:
        rel = p["path"]
        link_path = repo / rel
        target = store / _target_of(p)
        if is_exposed(exposure, p):
            if not link_path.exists():
                kind = "dir" if p["kind"] == "dir" else _file_kind()
                link_strategy.create_link(target, link_path, kind)
            exposed.append(rel)
        else:
            link_strategy.remove_managed(link_path, store, p["strategy"], target)
            hidden.append(rel)
    return {"exposed": exposed, "hidden": hidden}


def status(repo: Path) -> dict:
    repo = Path(repo).resolve()
    info = link_store.read_link_file(repo) or {"mode": "repo"}
    out = {"mode": info.get("mode", "repo"),
           "project_id": info.get("project_id"),
           "store": None, "placements": []}
    store = _store_for(repo)
    if store is None:
        return out
    out["store"] = str(store)
    exposure = link_store.read_exposure(store)
    for p in link_store.read_placements(store):
        out["placements"].append({**p, "exposed": is_exposed(exposure, p)})
    return out


def _strip_block(text: str) -> str:
    if GITIGNORE_BEGIN not in text:
        return text
    out, skip = [], False
    for line in text.splitlines():
        if line.strip() == GITIGNORE_BEGIN:
            skip = True
            continue
        if line.strip() == GITIGNORE_END:
            skip = False
            continue
        if not skip:
            out.append(line)
    return "\n".join(out).rstrip("\n") + "\n"


def detach(repo: Path) -> None:
    repo = Path(repo).resolve()
    store = _store_for(repo)
    if store is None:
        return
    for p in link_store.read_placements(store):
        rel = p["path"]
        link_path = repo / rel
        target = store / _target_of(p)
        link_strategy.remove_managed(link_path, store, p["strategy"], target)
        if link_path.exists():
            continue
        link_path.parent.mkdir(parents=True, exist_ok=True)
        if target.is_dir():
            shutil.copytree(target, link_path)
        elif target.exists():
            shutil.copyfile(target, link_path)

    # Clean the committed footprint.
    (repo / link_store.LINK_FILENAME).unlink(missing_ok=True)
    gi = repo / ".gitignore"
    if gi.exists():
        gi.write_text(_strip_block(gi.read_text()))
    claude = repo / "CLAUDE.md"
    if claude.exists() and _LEGACY_POINTER_MARKER in claude.read_text():
        kept = [ln for ln in claude.read_text().splitlines()
                if _LEGACY_POINTER_MARKER not in ln]
        claude.write_text("\n".join(kept).rstrip("\n") + "\n")


def attach(repo: Path, project_id: str | None = None) -> dict:
    repo = Path(repo).resolve()
    project_id = project_id or str(uuid.uuid4())
    store = link_store.project_store(project_id)
    _ensure_store_skeleton(store)

    # Move the existing .archie/ dir into the store before binding.
    src = repo / INFRA_LINK
    if src.exists() and not src.is_symlink():
        dst = store / INFRA_TARGET
        if dst.exists():
            shutil.rmtree(dst)
        shutil.move(str(src), str(dst))

    # bind re-symlinks .archie and externalizes .claude/rules markdown per-file.
    info = bind(repo, project_id=project_id)

    # Sweep per-folder CLAUDE.md (intent-layer) into the store, per file.
    for claude_md in repo.rglob("CLAUDE.md"):
        rel = claude_md.relative_to(repo).as_posix()
        if rel == "CLAUDE.md" or rel.startswith(".archie") or claude_md.is_symlink():
            continue
        externalize_file(repo, rel)

    reconcile(repo)
    return info


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2:
        print("Usage: linker.py <bind|reconcile|externalize|externalize-tree|"
              "status|attach|detach> <repo> [rel_path]", file=sys.stderr)
        return 1
    cmd, repo = argv[0], Path(argv[1])
    if cmd == "bind":
        print(json.dumps(bind(repo), indent=2))
    elif cmd == "reconcile":
        print(json.dumps(reconcile(repo), indent=2))
    elif cmd == "externalize":
        print(json.dumps({"strategy": externalize_file(repo, argv[2])}))
    elif cmd == "externalize-tree":
        print(json.dumps({"externalized": externalize_tree(repo, argv[2])}))
    elif cmd == "status":
        print(json.dumps(status(repo), indent=2))
    elif cmd == "attach":
        print(json.dumps(attach(repo), indent=2))
    elif cmd == "detach":
        detach(repo)
        print(json.dumps({"ok": True}))
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

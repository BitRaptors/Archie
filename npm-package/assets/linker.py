#!/usr/bin/env python3
"""Archie linker — orchestrates detached-mode presentation of artifacts.

Composes link_store (location/manifests) + link_strategy (OS presentation).
Commands: bind, reconcile, externalize, attach, detach, status.
Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import link_store  # noqa: E402
import link_strategy  # noqa: E402

# (repo-relative link path, store-relative target) for the always-on dir links.
DIR_ARTIFACTS = [
    (".archie", "artifacts/.archie"),
    (".claude/rules", "artifacts/.claude/rules"),
]

IMPORT_LINE = "@.claude/rules/  <!-- archie:detached -->"

GITIGNORE_BEGIN = "# >>> archie detached (managed) >>>"
GITIGNORE_END = "# <<< archie detached (managed) <<<"
GITIGNORE_ENTRIES = [
    "/.archie",
    "/.claude/rules",
    "**/CLAUDE.md",
    "!/CLAUDE.md",
]


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


def _ensure_import_pointer(repo: Path) -> None:
    path = repo / "CLAUDE.md"
    existing = path.read_text() if path.exists() else ""
    if "archie:detached" in existing:
        return
    sep = "" if existing.endswith("\n") or existing == "" else "\n"
    path.write_text(existing + sep + IMPORT_LINE + "\n")


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
                continue  # keep store version of pre-existing subdirs
            dest.unlink() if dest.is_file() else shutil.rmtree(dest)
        shutil.move(str(child), str(dest))
    shutil.rmtree(link_path)


def _store_for(repo: Path) -> Path | None:
    info = link_store.read_link_file(repo)
    if not info or info.get("mode") != "detached" or not info.get("project_id"):
        return None
    return link_store.project_store(info["project_id"])


def _dir_target(store: Path, rel: str) -> Path:
    return store / dict(DIR_ARTIFACTS).get(rel, "artifacts/" + rel)


def _file_kind() -> str:
    return "file" if link_strategy.strategy_for("file") == "symlink" else "file_copy"


# `.archie/` is infrastructure (tooling, hooks, raw JSON the agent never reads
# directly). It is ALWAYS exposed — hiding it would break enforcement/tooling
# and gates nothing the agent actually consumes.
INFRASTRUCTURE_PATHS = {".archie"}


def _category_of(rel_path: str) -> str:
    if rel_path in INFRASTRUCTURE_PATHS:
        return "infrastructure"
    if rel_path == ".claude/rules":
        return "rules"
    if rel_path.endswith("CLAUDE.md"):
        return "folder_context"
    return "rules"


def is_exposed(exposure: dict, rel_path: str) -> bool:
    if rel_path in INFRASTRUCTURE_PATHS:
        return True
    overrides = exposure.get("overrides", {})
    if rel_path in overrides:
        return bool(overrides[rel_path])
    cat = _category_of(rel_path)
    return bool(exposure.get("categories", {}).get(cat, True))


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

    placements = []
    for link_rel, target_rel in DIR_ARTIFACTS:
        target = store / target_rel
        link_path = repo / link_rel
        # Preserve any real-directory contents (e.g. npm-copied tooling) by
        # relocating them into the store before the dir becomes a symlink.
        _absorb_existing_dir(link_path, target)
        strategy = link_strategy.create_link(target, link_path, "dir")
        placements.append({"path": link_rel, "kind": "dir", "strategy": strategy})
    link_store.write_placements(store, placements)

    # Seed exposure defaults if absent.
    link_store.write_exposure(store, link_store.read_exposure(store))

    _ensure_gitignore(repo)
    _ensure_import_pointer(repo)
    return info


def externalize_folder_file(repo: Path, rel_path: str) -> str | None:
    repo = Path(repo).resolve()
    store = _store_for(repo)
    if store is None:
        return None

    link_path = repo / rel_path
    target = store / "tree" / rel_path

    # Already externalized (managed link present) -> no-op.
    if link_strategy.is_managed(link_path, store):
        return None

    if link_path.exists() and not link_path.is_symlink():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(link_path.read_text())
        link_path.unlink()
    elif not target.exists():
        return None  # nothing to externalize

    strategy = link_strategy.create_link(target, link_path, _file_kind())

    placements = link_store.read_placements(store)
    if not any(p["path"] == rel_path for p in placements):
        placements.append({"path": rel_path, "kind": "file", "strategy": strategy})
        link_store.write_placements(store, placements)
    return strategy


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
        target = (store / "tree" / rel) if p["kind"] == "file" else _dir_target(store, rel)
        if is_exposed(exposure, rel):
            if not link_path.exists():
                kind = "dir" if p["kind"] == "dir" else _file_kind()
                link_strategy.create_link(target, link_path, kind)
            exposed.append(rel)
        else:
            link_strategy.remove_managed(link_path, store, p["strategy"])
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
        out["placements"].append({**p, "exposed": is_exposed(exposure, p["path"])})
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
        target = (store / "tree" / rel) if p["kind"] == "file" else _dir_target(store, rel)
        link_strategy.remove_managed(link_path, store, p["strategy"])
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
    if claude.exists():
        kept = [ln for ln in claude.read_text().splitlines()
                if "archie:detached" not in ln]
        claude.write_text("\n".join(kept).rstrip("\n") + "\n")


def attach(repo: Path, project_id: str | None = None) -> dict:
    repo = Path(repo).resolve()
    project_id = project_id or str(uuid.uuid4())
    store = link_store.project_store(project_id)
    _ensure_store_skeleton(store)

    # Move existing in-tree artifacts into the store before binding.
    for link_rel, target_rel in DIR_ARTIFACTS:
        src = repo / link_rel
        dst = store / target_rel
        if src.exists() and not src.is_symlink():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.move(str(src), str(dst))

    folder_files = []
    for claude_md in repo.rglob("CLAUDE.md"):
        rel = claude_md.relative_to(repo).as_posix()
        if rel == "CLAUDE.md" or ".archie" in rel:
            continue
        dst = store / "tree" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(claude_md), str(dst))
        folder_files.append(rel)

    info = bind(repo, project_id=project_id)
    for rel in folder_files:
        strategy = link_strategy.create_link(store / "tree" / rel, repo / rel, _file_kind())
        placements = link_store.read_placements(store)
        if not any(p["path"] == rel for p in placements):
            placements.append({"path": rel, "kind": "file", "strategy": strategy})
            link_store.write_placements(store, placements)
    reconcile(repo)
    return info


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2:
        print("Usage: linker.py <bind|reconcile|externalize|status|attach|detach> "
              "<repo> [rel_path]", file=sys.stderr)
        return 1
    cmd, repo = argv[0], Path(argv[1])
    if cmd == "bind":
        print(json.dumps(bind(repo), indent=2))
    elif cmd == "reconcile":
        print(json.dumps(reconcile(repo), indent=2))
    elif cmd == "externalize":
        print(json.dumps({"strategy": externalize_folder_file(repo, argv[2])}))
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

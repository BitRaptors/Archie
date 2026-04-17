"""Archie LLM Wiki index builder — backlinks and provenance (Pass 2).

Reads the markdown files written by wiki_builder.py, parses markdown links,
inverts them into a backlinks index, then appends a "Referenced by" section
to each page. Also computes SHA256 hashes for provenance.json.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Iterable


# Match [Title](../subdir/slug.md) — relative paths only, .md target, non-empty.
# Does not match external links, anchors, or images.
_LINK_RE = re.compile(r"(?<!\!)\[([^\]]+)\]\((?!https?:)([^)\s#]+\.md)\)")


def extract_links(page: Path) -> list[tuple[str, str]]:
    """Return [(relative_target, link_title), ...] for all relative .md links."""
    text = page.read_text(encoding="utf-8")
    return [(m.group(2), m.group(1)) for m in _LINK_RE.finditer(text)]


def _page_type_from_dir(path_parts: tuple[str, ...]) -> str:
    """Given ('components', 'foo.md') return 'component'. Best-effort singular."""
    if not path_parts:
        return "unknown"
    mapping = {
        "components": "component",
        "decisions": "decision",
        "patterns": "pattern",
        "pitfalls": "pitfall",
        "capabilities": "capability",
    }
    return mapping.get(path_parts[0], "unknown")


def _title_from_page(page: Path) -> str:
    """Return the first-level heading of a page, else filename stem."""
    for line in page.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return page.stem


def build_backlinks(wiki_root: Path) -> dict[str, list[dict]]:
    """Walk the wiki and return {target_rel_path: [{path, title, type}, ...]}.

    Keys and values use wiki-root-relative POSIX paths so the output is stable
    across platforms.
    """
    backlinks: dict[str, list[dict]] = {}
    for page in sorted(wiki_root.rglob("*.md")):
        rel_src = page.relative_to(wiki_root).as_posix()
        # Skip the _meta dir, it's not a real page.
        if rel_src.startswith("_meta/"):
            continue
        src_title = _title_from_page(page)
        src_type = _page_type_from_dir(page.relative_to(wiki_root).parts)
        for relative_target, _link_title in extract_links(page):
            # Resolve relative link against the source page's directory, then
            # re-express relative to wiki_root.
            target_abs = (page.parent / relative_target).resolve()
            try:
                rel_target = target_abs.relative_to(wiki_root.resolve()).as_posix()
            except ValueError:
                continue  # link escapes wiki_root; ignore
            backlinks.setdefault(rel_target, []).append(
                {"path": rel_src, "title": src_title, "type": src_type}
            )
    return backlinks


_REFERENCED_BY_MARKER = "<!-- archie:referenced-by -->"


def _relative_link(src_page: str, target_path: str) -> str:
    """Produce '../decisions/x.md' from two wiki-root-relative posix paths.

    Always produces a path with at least one '../' component — i.e. the link
    goes up to wiki root then down to the target. This matches the convention
    used by wiki_builder.py for all cross-page links.
    """
    src_dir = Path(src_page).parent
    target = Path(target_path)
    # Count how many levels up from the source directory to wiki root.
    depth = len(src_dir.parts) if src_dir != Path(".") else 0
    up = [".."] * depth
    down = list(target.parts)
    return "/".join(up + down)


def inject_referenced_by(wiki_root: Path, backlinks: dict[str, list[dict]]) -> None:
    """Append or refresh a '## Referenced by' section on every page that has backlinks.

    Pages without any backlinks are left unchanged (no empty section).
    Idempotent: re-running with the same backlinks produces byte-identical output.
    """
    for page in sorted(wiki_root.rglob("*.md")):
        rel_src = page.relative_to(wiki_root).as_posix()
        if rel_src.startswith("_meta/"):
            continue
        inbound = backlinks.get(rel_src) or []
        if not inbound:
            # Strip any stale referenced-by block if present (in case links changed).
            _strip_referenced_by(page)
            continue
        body = "\n".join(
            f"- [{ref['title']}]({_relative_link(rel_src, ref['path'])}) ({ref['type']})"
            for ref in sorted(inbound, key=lambda r: (r["type"], r["path"]))
        )
        block = f"\n{_REFERENCED_BY_MARKER}\n## Referenced by\n\n{body}\n"
        content = page.read_text(encoding="utf-8")
        if _REFERENCED_BY_MARKER in content:
            content = _strip_block(content)
        # Ensure single trailing newline before appending.
        content = content.rstrip() + "\n"
        page.write_text(content + block, encoding="utf-8")


def _strip_block(content: str) -> str:
    """Remove everything from the marker onwards (including the marker)."""
    idx = content.find(_REFERENCED_BY_MARKER)
    if idx == -1:
        return content
    return content[:idx].rstrip() + "\n"


def _strip_referenced_by(page: Path) -> None:
    content = page.read_text(encoding="utf-8")
    if _REFERENCED_BY_MARKER not in content:
        return
    page.write_text(_strip_block(content), encoding="utf-8")


def write_provenance(wiki_root: Path, last_refreshed: str) -> None:
    """Walk the wiki and write _meta/provenance.json with SHA256 per page."""
    prov: dict[str, dict] = {}
    for page in sorted(wiki_root.rglob("*.md")):
        rel = page.relative_to(wiki_root).as_posix()
        if rel.startswith("_meta/"):
            continue
        content = page.read_bytes()
        sha = hashlib.sha256(content).hexdigest()
        prov[rel] = {
            "sha256": sha,
            "last_refreshed": last_refreshed,
            "source": "wiki_builder",
        }
    meta = wiki_root / "_meta"
    meta.mkdir(exist_ok=True)
    (meta / "provenance.json").write_text(
        json.dumps(prov, indent=2, sort_keys=True), encoding="utf-8"
    )


def write_backlinks(wiki_root: Path, backlinks: dict[str, list[dict]]) -> None:
    meta = wiki_root / "_meta"
    meta.mkdir(exist_ok=True)
    (meta / "backlinks.json").write_text(
        json.dumps(backlinks, indent=2, sort_keys=True), encoding="utf-8"
    )


def lint(wiki_root: Path, fs_root: Path | None = None) -> list[dict]:
    """Lint the wiki. fs_root is the project root used to validate evidence
    globs; defaults to wiki_root.parent.parent (i.e. the consumer project)."""
    import fnmatch
    fs_root = fs_root or wiki_root.parent.parent
    findings: list[dict] = []
    backlinks = build_backlinks(wiki_root)

    # Orphans.
    for page in sorted(wiki_root.rglob("*.md")):
        rel = page.relative_to(wiki_root).as_posix()
        if rel == "index.md" or rel.startswith("_meta/"):
            continue
        if not backlinks.get(rel):
            findings.append({"kind": "orphan", "page": rel})

    # Broken links.
    for page in sorted(wiki_root.rglob("*.md")):
        rel_src = page.relative_to(wiki_root).as_posix()
        if rel_src.startswith("_meta/"):
            continue
        for relative_target, _title in extract_links(page):
            target = (page.parent / relative_target).resolve()
            if not target.exists():
                findings.append({
                    "kind": "broken_link",
                    "page": rel_src,
                    "target": relative_target,
                })

    # Stale evidence: provenance globs that match zero files under fs_root.
    prov_path = wiki_root / "_meta" / "provenance.json"
    if prov_path.exists():
        prov = json.loads(prov_path.read_text(encoding="utf-8"))
        for page, data in prov.items():
            evidence = data.get("evidence") or []
            if not evidence:
                continue
            # Any glob matching at least one file makes the page fresh.
            matched = False
            for glob in evidence:
                for candidate in fs_root.rglob("*"):
                    if not candidate.is_file():
                        continue
                    try:
                        rel_candidate = candidate.relative_to(fs_root).as_posix()
                    except ValueError:
                        continue
                    if fnmatch.fnmatch(rel_candidate, glob):
                        matched = True
                        break
                if matched:
                    break
            if not matched:
                findings.append({"kind": "stale_evidence", "page": page, "evidence": evidence})

    # Dangling backlinks: stored backlinks whose source page no longer exists.
    bl_path = wiki_root / "_meta" / "backlinks.json"
    if bl_path.exists():
        stored = json.loads(bl_path.read_text(encoding="utf-8"))
        for target, refs in stored.items():
            for ref in refs:
                src_path = wiki_root / ref["path"]
                if not src_path.exists():
                    findings.append({
                        "kind": "dangling_backlink",
                        "page": target,
                        "missing_source": ref["path"],
                    })

    # Contradictions: pitfall claims stems_from X but X.md has no backlink to
    # this pitfall.
    pitfalls_dir = wiki_root / "pitfalls"
    if pitfalls_dir.exists():
        import re as _re
        for page in sorted(pitfalls_dir.glob("*.md")):
            text = page.read_text(encoding="utf-8")
            for match in _re.finditer(
                r"\*\*Stems from:\*\*\s+\[([^\]]+)\]\(([^)]+)\)", text
            ):
                rel_target = match.group(2)
                target_abs = (page.parent / rel_target).resolve()
                try:
                    rel_target_norm = target_abs.relative_to(wiki_root.resolve()).as_posix()
                except ValueError:
                    continue
                src_rel = page.relative_to(wiki_root).as_posix()
                inbound_to_target = backlinks.get(rel_target_norm, [])
                if not any(ref["path"] == src_rel for ref in inbound_to_target):
                    findings.append({
                        "kind": "contradiction",
                        "page": src_rel,
                        "target": rel_target_norm,
                        "message": "pitfall claims stems_from target but target lacks the backlink",
                    })

    return findings

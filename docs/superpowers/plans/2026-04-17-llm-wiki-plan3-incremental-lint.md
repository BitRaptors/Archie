# LLM Wiki — Plan 3: Incremental Update + Lint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/archie-scan` refresh only the wiki pages whose evidence files changed, skip SHA256-unchanged pages, re-run the capabilities agent in scope on affected directories only, and surface wiki lint findings (orphans, broken links, stale evidence, dangling backlinks, contradictions) in `scan_report.md`.

**Architecture:** `wiki_builder.py` gains `--incremental`. The incremental path loads `_meta/provenance.json` (from the last build), diffs `scan.json` against the previous scan, computes the set of affected pages via `provenance.evidence ∩ changed_files`, and regenerates only those. SHA256 comparison before write ensures byte-identical content doesn't bump `last_refreshed`. If the blueprint-level structure changed (decisions/components/pitfalls), the incremental path aborts and asks the user to re-run deep-scan. `wiki_index.py` gains a `--lint` subcommand. `/archie-scan.md` invokes both and includes the report section.

**Tech Stack:** Same as Plans 1-2 (Python 3.9+ stdlib, pytest). Uses `hashlib.sha256` (already in use) and basic JSON diffing.

**Depends on:** Plans 1 and 2 (core builder + capabilities must be live).

**Reference spec:** `docs/superpowers/specs/2026-04-17-llm-wiki-design.md` §5.2, §5.3

---

## File structure (this plan)

**New files:**
- `tests/test_wiki_incremental.py` — unit + integration for `--incremental` flow.
- `tests/test_wiki_lint.py` — unit for lint findings.
- `tests/fixtures/wiki_fixture_scan_v1.json`, `tests/fixtures/wiki_fixture_scan_v2.json` — two scan snapshots to drive a synthetic diff.

**Modified files:**
- `archie/standalone/wiki_builder.py` — add `--incremental` branch, affected-page computation, SHA256-gated writes, scoped capabilities re-run.
- `archie/standalone/wiki_index.py` — add `--lint` subcommand: orphans, broken links, stale evidence, dangling backlinks, contradictions.
- `.claude/commands/archie-scan.md` — new bash step calling `wiki_builder --incremental` + `wiki_index --lint`; wiki summary section in the scan report.
- `npm-package/assets/wiki_builder.py`, `npm-package/assets/wiki_index.py` — sync.

---

## Task 1: Scan-diff utility

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Create: `tests/test_wiki_incremental.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_wiki_incremental.py`:

```python
"""Tests for wiki_builder --incremental."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))

import wiki_builder  # noqa: E402

STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
FIXTURE_BP = Path(__file__).parent / "fixtures" / "wiki_fixture_blueprint.json"


def test_diff_scans_added_modified_deleted(tmp_path):
    old = {"files": [{"path": "a.py", "hash": "1"}, {"path": "b.py", "hash": "2"}]}
    new = {"files": [{"path": "b.py", "hash": "22"}, {"path": "c.py", "hash": "3"}]}
    diff = wiki_builder.diff_scans(old, new)
    assert sorted(diff["added"]) == ["c.py"]
    assert sorted(diff["modified"]) == ["b.py"]
    assert sorted(diff["deleted"]) == ["a.py"]


def test_diff_scans_empty_old_returns_all_added():
    old = {"files": []}
    new = {"files": [{"path": "a.py", "hash": "1"}, {"path": "b.py", "hash": "2"}]}
    diff = wiki_builder.diff_scans(old, new)
    assert sorted(diff["added"]) == ["a.py", "b.py"]
    assert diff["modified"] == []
    assert diff["deleted"] == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_wiki_incremental.py -v -k diff_scans`
Expected: FAIL — `diff_scans` missing.

- [ ] **Step 3: Implement `diff_scans`**

Append to `archie/standalone/wiki_builder.py`:

```python
def diff_scans(old_scan: dict, new_scan: dict) -> dict[str, list[str]]:
    """Return {added, modified, deleted} lists of file paths based on hashes.

    Both scans are expected to have a top-level `files` key that is a list of
    {path, hash} dicts. Missing or empty inputs are treated as zero files.
    """
    def _hashes(scan: dict) -> dict[str, str]:
        return {f["path"]: f.get("hash", "") for f in scan.get("files", []) or []}

    old = _hashes(old_scan)
    new = _hashes(new_scan)
    added = sorted(set(new) - set(old))
    deleted = sorted(set(old) - set(new))
    modified = sorted(p for p in set(new) & set(old) if new[p] != old[p])
    return {"added": added, "modified": modified, "deleted": deleted}
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_wiki_incremental.py -v -k diff_scans`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/wiki_builder.py tests/test_wiki_incremental.py
git commit -m "feat(wiki): add diff_scans for incremental update"
```

---

## Task 2: Affected-page resolution via provenance

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_incremental.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_wiki_incremental.py`:

```python
import fnmatch


def test_affected_pages_matches_globs():
    provenance = {
        "capabilities/auth-flow.md": {
            "sha256": "x", "source": "wiki_builder",
            "evidence": ["features/auth/**"],
        },
        "capabilities/payment.md": {
            "sha256": "y", "source": "wiki_builder",
            "evidence": ["features/payment/**"],
        },
        "index.md": {"sha256": "z", "source": "wiki_builder"},  # no evidence field
    }
    changed = ["features/auth/AuthService.ts", "README.md"]
    affected = wiki_builder.affected_pages(provenance, changed)
    assert sorted(affected) == ["capabilities/auth-flow.md"]


def test_affected_pages_handles_no_evidence_gracefully():
    provenance = {"index.md": {"sha256": "z", "source": "wiki_builder"}}
    affected = wiki_builder.affected_pages(provenance, ["anything.py"])
    assert affected == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_wiki_incremental.py -v -k affected`
Expected: FAIL — `affected_pages` missing.

- [ ] **Step 3: Implement `affected_pages`**

Append to `archie/standalone/wiki_builder.py`:

```python
import fnmatch


def affected_pages(provenance: dict, changed_files: list[str]) -> list[str]:
    """Return wiki-root-relative page paths whose evidence globs match any
    changed file. Pages without an `evidence` field are never considered
    affected (their regeneration must be triggered by a blueprint-structure change).
    """
    affected = []
    for page, prov in provenance.items():
        evidence = prov.get("evidence") or []
        if not evidence:
            continue
        for glob in evidence:
            if any(fnmatch.fnmatch(f, glob) for f in changed_files):
                affected.append(page)
                break
    return sorted(affected)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_wiki_incremental.py -v -k affected`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/wiki_builder.py tests/test_wiki_incremental.py
git commit -m "feat(wiki): resolve affected pages via provenance evidence globs"
```

---

## Task 3: SHA256-gated write

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_incremental.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_wiki_incremental.py`:

```python
import hashlib


def test_write_if_changed_skips_identical_content(tmp_path):
    page = tmp_path / "page.md"
    page.write_text("same content\n")
    original_mtime = page.stat().st_mtime_ns
    changed = wiki_builder.write_if_changed(page, "same content\n")
    assert changed is False
    # File not rewritten; mtime unchanged.
    assert page.stat().st_mtime_ns == original_mtime


def test_write_if_changed_writes_new_content(tmp_path):
    page = tmp_path / "page.md"
    page.write_text("old\n")
    changed = wiki_builder.write_if_changed(page, "new\n")
    assert changed is True
    assert page.read_text() == "new\n"


def test_write_if_changed_creates_parent_dir(tmp_path):
    page = tmp_path / "sub" / "dir" / "page.md"
    changed = wiki_builder.write_if_changed(page, "hello\n")
    assert changed is True
    assert page.read_text() == "hello\n"
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_wiki_incremental.py -v -k write_if_changed`
Expected: FAIL.

- [ ] **Step 3: Implement `write_if_changed`**

Append to `archie/standalone/wiki_builder.py`:

```python
def write_if_changed(path: Path, content: str) -> bool:
    """Write content to path only if the file content differs. Returns True when
    the file was written. Creates parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_bytes()
        if hashlib.sha256(existing).hexdigest() == hashlib.sha256(content.encode("utf-8")).hexdigest():
            return False
    path.write_text(content, encoding="utf-8")
    return True
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_wiki_incremental.py -v -k write_if_changed`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/wiki_builder.py tests/test_wiki_incremental.py
git commit -m "feat(wiki): add SHA256-gated write_if_changed"
```

---

## Task 4: `--incremental` CLI mode

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_incremental.py`

- [ ] **Step 1: Write the failing integration test**

Append to `tests/test_wiki_incremental.py`:

```python
def _setup_project_with_previous_wiki(tmp_path):
    """Build a wiki once (simulating a prior deep-scan), then prepare an
    incremental scenario where one evidence file has changed."""
    archie = tmp_path / ".archie"
    archie.mkdir()
    shutil.copy(FIXTURE_BP, archie / "blueprint.json")
    # First: build full wiki.
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(tmp_path)],
        check=True, capture_output=True,
    )
    # Write a previous scan snapshot showing the evidence files that existed.
    old_scan = {
        "files": [
            {"path": "features/auth/AuthController.ts", "hash": "h1"},
            {"path": "features/auth/AuthService.ts", "hash": "h2"},
            {"path": "routes/api/auth.py", "hash": "h3"},
        ]
    }
    (archie / "scan.json").write_text(json.dumps(old_scan))
    return tmp_path


def test_incremental_rewrites_only_affected_pages(tmp_path):
    project = _setup_project_with_previous_wiki(tmp_path)
    wiki = project / ".archie" / "wiki"
    # Capture current file mtimes.
    before = {p: p.stat().st_mtime_ns for p in wiki.rglob("*.md")}

    # Simulate: one evidence file for "User Authentication" has changed.
    new_scan = {
        "files": [
            {"path": "features/auth/AuthController.ts", "hash": "h1-modified"},
            {"path": "features/auth/AuthService.ts", "hash": "h2"},
            {"path": "routes/api/auth.py", "hash": "h3"},
        ]
    }
    prev_scan = json.loads((project / ".archie" / "scan.json").read_text())
    (project / ".archie" / "scan.json").write_text(json.dumps(new_scan))

    # Run incremental.
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project),
         "--incremental", "--previous-scan", json.dumps(prev_scan)],
        check=True, capture_output=True,
    )

    after = {p: p.stat().st_mtime_ns for p in wiki.rglob("*.md")}
    # Capability page MAY have been rewritten (evidence matched). Other pages
    # must NOT have changed on disk.
    unchanged_pages = [
        wiki / "components" / "user-repository.md",
        wiki / "decisions" / "postgresql-as-primary-store.md",
        wiki / "patterns" / "repository.md",
    ]
    for p in unchanged_pages:
        assert after[p] == before[p], f"{p} should not have been rewritten"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_wiki_incremental.py -v -k incremental`
Expected: FAIL — no `--incremental` flag support.

- [ ] **Step 3: Extend the CLI**

Edit `archie/standalone/wiki_builder.py`. Refactor `main` to accept `--incremental` and `--previous-scan` (a JSON string, or a path to a JSON file):

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archie LLM Wiki builder.")
    parser.add_argument("project_root", help="Path to project with .archie/blueprint.json")
    parser.add_argument("--incremental", action="store_true",
                        help="Only refresh pages whose evidence files changed.")
    parser.add_argument("--previous-scan", default=None,
                        help="Path to or inline JSON of the previous scan snapshot.")
    args = parser.parse_args(argv)
    if not _wiki_enabled():
        print("Wiki generation disabled (ARCHIE_WIKI_ENABLED=false). Skipped.")
        return 0
    project = Path(args.project_root)
    if args.incremental:
        prev = _load_previous_scan(args.previous_scan, project)
        build_wiki_incremental(project, prev)
    else:
        build_wiki(project)
    print(f"Wiki built at {project}/.archie/wiki/")
    return 0


def _load_previous_scan(raw: str | None, project: Path) -> dict:
    if not raw:
        return {"files": []}
    p = Path(raw)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"files": []}


def build_wiki_incremental(project_root: Path, previous_scan: dict) -> None:
    """Refresh only pages whose evidence files changed. Aborts (raising
    RuntimeError) if the blueprint structure indicates a need for full rebuild."""
    wiki_root = project_root / ".archie" / "wiki"
    prov_path = wiki_root / "_meta" / "provenance.json"
    if not prov_path.exists():
        # No prior wiki: fall back to full build.
        build_wiki(project_root)
        return
    provenance = json.loads(prov_path.read_text(encoding="utf-8"))
    new_scan_path = project_root / ".archie" / "scan.json"
    new_scan = json.loads(new_scan_path.read_text(encoding="utf-8")) if new_scan_path.exists() else {"files": []}
    diff = diff_scans(previous_scan, new_scan)
    changed_files = diff["added"] + diff["modified"] + diff["deleted"]
    if not changed_files:
        print("Wiki incremental: no changed files, nothing to do.")
        return

    # Blueprint structure changes require a full rebuild.
    blueprint = json.loads((project_root / ".archie" / "blueprint.json").read_text())
    if _blueprint_structure_changed(provenance, blueprint):
        raise RuntimeError(
            "Blueprint structure changed (decisions/components/pitfalls). "
            "Run /archie-deep-scan instead of /archie-scan."
        )

    affected = affected_pages(provenance, changed_files)
    if not affected:
        print("Wiki incremental: no affected pages.")
        return

    slug_map = _build_slug_map(blueprint)
    rewritten: list[str] = []
    for page_rel in affected:
        # Only capability pages are regenerated by scan. All other pages depend
        # on blueprint structure and are handled by full rebuild.
        if not page_rel.startswith("capabilities/"):
            continue
        slug = Path(page_rel).stem
        cap = _find_capability_by_slug(blueprint, slug, slug_map["capabilities"])
        if not cap:
            continue
        content = render_capability(cap, slug, slug_map)
        page_abs = wiki_root / page_rel
        if write_if_changed(page_abs, content):
            rewritten.append(page_rel)

    # Rebuild backlinks + "Referenced by" + provenance on any rewrite.
    if rewritten:
        import wiki_index
        from datetime import date
        backlinks = wiki_index.build_backlinks(wiki_root)
        wiki_index.write_backlinks(wiki_root, backlinks)
        wiki_index.inject_referenced_by(wiki_root, backlinks)
        wiki_index.write_provenance(wiki_root, last_refreshed=date.today().isoformat())
    print(f"Wiki incremental: {len(rewritten)} pages rewritten.")


def _blueprint_structure_changed(provenance: dict, blueprint: dict) -> bool:
    """Return True if the set of decisions/components/pitfalls/patterns in the
    blueprint does not match the set of pages recorded in provenance."""
    def _pages(prefix: str) -> set[str]:
        return {p for p in provenance if p.startswith(prefix)}

    expected_decisions = {slugify(d.get("title", "")) for d in blueprint.get("decisions", {}).get("key_decisions", []) or []}
    expected_components = {slugify(c.get("name", "")) for c in blueprint.get("components", []) or []}
    expected_patterns = {slugify(p.get("name", "")) for p in blueprint.get("communication", {}).get("patterns", []) or []}
    expected_pitfalls = {slugify(p.get("area", "")) for p in blueprint.get("pitfalls", []) or []}

    def _slugs(prefix: str) -> set[str]:
        return {Path(p).stem for p in _pages(prefix)}

    return (
        expected_decisions != _slugs("decisions/")
        or expected_components != _slugs("components/")
        or expected_patterns != _slugs("patterns/")
        or expected_pitfalls != _slugs("pitfalls/")
    )


def _find_capability_by_slug(blueprint: dict, slug: str, slug_map: dict[str, str]) -> dict | None:
    for cap in blueprint.get("capabilities", []) or []:
        if slug_map.get(cap.get("name")) == slug:
            return cap
    return None
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_wiki_incremental.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/wiki_builder.py tests/test_wiki_incremental.py
git commit -m "feat(wiki): add --incremental mode with SHA256 gating"
```

---

## Task 5: Scoped capabilities re-run (agent call from `/archie-scan`)

**Files:**
- Modify: `.claude/commands/archie-scan.md`

- [ ] **Step 1: Add a conditional capabilities-agent step**

In `.claude/commands/archie-scan.md`, after the scanner/diff phase and before the wiki-builder invocation, add a conditional block:

```markdown
### Wiki: conditional capabilities refresh

If any changed file matches evidence globs of existing capability pages
(computed by reading `.archie/wiki/_meta/provenance.json` and intersecting
with the scan diff), dispatch the Capabilities agent in **scope-restricted**
mode — pass only the affected directories as input. Save to
`/tmp/archie_agent_capabilities_scoped.json`.

Scope restriction instructions to the agent:

> Only reconsider capabilities that live under these directories: <list>.
> Do not introduce new capabilities from outside this scope.
> Return an empty array if nothing has changed materially.

Merge the scoped output into `blueprint.capabilities[]` in place: match by
`name`, replace existing entries, leave others untouched.

If no evidence file changed (affected set is empty), SKIP this step.
```

- [ ] **Step 2: Add the `wiki_builder --incremental` invocation**

Immediately after the capabilities-refresh step, add:

```bash
python3 .archie/wiki_builder.py "$PWD" --incremental \
  --previous-scan "$PRIOR_SCAN_JSON_PATH"
```

Where `$PRIOR_SCAN_JSON_PATH` is the path the scan command already uses for the previous scan snapshot (consult the existing scan command for the exact variable name).

- [ ] **Step 3: Manual smoke**

On a fixture project with an existing wiki:

1. Modify one file under a capability's evidence glob.
2. Run `/archie-scan`.
3. Confirm: only the capability page's mtime changed; the scan report includes a "Wiki updates: <N> pages" line.

- [ ] **Step 4: Commit**

```bash
git add .claude/commands/archie-scan.md
git commit -m "feat(wiki): wire scoped capabilities refresh + incremental build into /archie-scan"
```

---

## Task 6: Lint — orphans and broken links

**Files:**
- Modify: `archie/standalone/wiki_index.py`
- Create: `tests/test_wiki_lint.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_wiki_lint.py`:

```python
"""Tests for wiki_index lint."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))

import wiki_index  # noqa: E402


def _make_wiki(tmp_path: Path, files: dict[str, str]) -> Path:
    wiki = tmp_path / "wiki"
    for rel, content in files.items():
        path = wiki / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    (wiki / "_meta").mkdir(exist_ok=True)
    return wiki


def test_lint_orphan_page(tmp_path):
    wiki = _make_wiki(tmp_path, {
        "index.md": "# I\n[A](./components/a.md)\n",
        "components/a.md": "# A\n",
        "components/orphan.md": "# Orphan\n",
    })
    findings = wiki_index.lint(wiki)
    kinds = {f["kind"] for f in findings}
    assert "orphan" in kinds
    orphans = [f for f in findings if f["kind"] == "orphan"]
    assert any(f["page"] == "components/orphan.md" for f in orphans)
    # index.md itself is exempt from orphan detection.
    assert not any(f["page"] == "index.md" for f in orphans)


def test_lint_broken_link(tmp_path):
    wiki = _make_wiki(tmp_path, {
        "index.md": "# I\n[Missing](./components/missing.md)\n",
    })
    findings = wiki_index.lint(wiki)
    broken = [f for f in findings if f["kind"] == "broken_link"]
    assert any(f["target"].endswith("components/missing.md") for f in broken)
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_wiki_lint.py -v`
Expected: FAIL — `lint` missing.

- [ ] **Step 3: Implement orphans + broken links**

Append to `archie/standalone/wiki_index.py`:

```python
def lint(wiki_root: Path) -> list[dict]:
    """Return a list of finding dicts. Each finding: {kind, page, ...detail}.

    Kinds (Task 6): orphan, broken_link.
    Kinds added in Task 7: stale_evidence, dangling_backlink, contradiction.
    """
    findings: list[dict] = []
    backlinks = build_backlinks(wiki_root)

    # Orphans: pages with no inbound links (except index.md).
    for page in sorted(wiki_root.rglob("*.md")):
        rel = page.relative_to(wiki_root).as_posix()
        if rel == "index.md" or rel.startswith("_meta/"):
            continue
        if not backlinks.get(rel):
            findings.append({"kind": "orphan", "page": rel})

    # Broken links: every relative .md reference must resolve to an existing file.
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

    return findings
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_wiki_lint.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/wiki_index.py tests/test_wiki_lint.py
git commit -m "feat(wiki): lint orphans and broken links"
```

---

## Task 7: Lint — stale evidence, dangling backlinks, contradictions

**Files:**
- Modify: `archie/standalone/wiki_index.py`
- Modify: `tests/test_wiki_lint.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_wiki_lint.py`:

```python
def test_lint_stale_evidence(tmp_path):
    wiki = _make_wiki(tmp_path, {
        "index.md": "# I\n[A](./capabilities/a.md)\n",
        "capabilities/a.md": "# A\n",
    })
    # Provenance claims A's evidence is a glob that will match no files.
    prov = {
        "capabilities/a.md": {
            "sha256": "x", "source": "wiki_builder",
            "evidence": ["features/nonexistent/**"],
        }
    }
    (wiki / "_meta" / "provenance.json").write_text(json.dumps(prov))
    # Point fs_root at a project that has no `features/nonexistent/` directory.
    findings = wiki_index.lint(wiki, fs_root=tmp_path)
    assert any(f["kind"] == "stale_evidence" and f["page"] == "capabilities/a.md" for f in findings)


def test_lint_dangling_backlink(tmp_path):
    wiki = _make_wiki(tmp_path, {
        "index.md": "# I\n",
        "components/a.md": "# A\n",
    })
    backlinks = {
        "components/a.md": [
            {"path": "capabilities/gone.md", "title": "Gone", "type": "capability"}
        ]
    }
    (wiki / "_meta" / "backlinks.json").write_text(json.dumps(backlinks))
    findings = wiki_index.lint(wiki, fs_root=tmp_path)
    assert any(f["kind"] == "dangling_backlink" and f["page"] == "components/a.md" for f in findings)
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_wiki_lint.py -v -k "stale or dangling"`
Expected: FAIL.

- [ ] **Step 3: Extend `lint`**

Replace the `lint` function in `archie/standalone/wiki_index.py` with:

```python
def lint(wiki_root: Path, fs_root: Path | None = None) -> list[dict]:
    """Lint the wiki. fs_root is the project root used to validate evidence
    globs; defaults to wiki_root.parent.parent (i.e. the consumer project)."""
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
                # Walk fs_root and test against glob.
                for candidate in fs_root.rglob("*"):
                    rel_candidate = candidate.relative_to(fs_root).as_posix()
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
    # this pitfall. Detect by walking pitfall pages and re-extracting their
    # stems_from target (via the resolved link).
    for page in sorted((wiki_root / "pitfalls").glob("*.md")) if (wiki_root / "pitfalls").exists() else []:
        text = page.read_text(encoding="utf-8")
        # Look for a "**Stems from:** [X](../decisions/slug.md)" pattern.
        for match in re.finditer(
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
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_wiki_lint.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/wiki_index.py tests/test_wiki_lint.py
git commit -m "feat(wiki): lint stale evidence, dangling backlinks, contradictions"
```

---

## Task 8: Lint CLI + JSON output

**Files:**
- Modify: `archie/standalone/wiki_index.py`
- Modify: `tests/test_wiki_lint.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_wiki_lint.py`:

```python
import subprocess

STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"


def test_lint_cli_emits_json(tmp_path):
    wiki = _make_wiki(tmp_path, {
        "index.md": "# I\n[Missing](./components/missing.md)\n",
    })
    result = subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_index.py"), "--lint",
         "--wiki", str(wiki), "--json"],
        capture_output=True, text=True, check=True,
    )
    findings = json.loads(result.stdout)
    assert any(f["kind"] == "broken_link" for f in findings)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_wiki_lint.py -v -k cli`
Expected: FAIL — no CLI.

- [ ] **Step 3: Add CLI to `wiki_index.py`**

Append at the bottom of `archie/standalone/wiki_index.py`:

```python
def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Archie LLM Wiki index + lint.")
    parser.add_argument("--wiki", required=True, help="Path to .archie/wiki/")
    parser.add_argument("--fs-root", default=None, help="Project root (for evidence glob checks)")
    parser.add_argument("--lint", action="store_true", help="Run lint and print findings")
    parser.add_argument("--json", action="store_true", help="Emit findings as JSON (requires --lint)")
    args = parser.parse_args(argv)

    wiki_root = Path(args.wiki)
    fs_root = Path(args.fs_root) if args.fs_root else None

    if args.lint:
        findings = lint(wiki_root, fs_root=fs_root)
        if args.json:
            print(json.dumps(findings, indent=2, sort_keys=True))
        else:
            for f in findings:
                print(f"[{f['kind']}] {f.get('page', '')} {f.get('target', '') or f.get('message', '')}")
        return 0

    # Default: rebuild backlinks + inject + provenance.
    from datetime import date
    backlinks = build_backlinks(wiki_root)
    write_backlinks(wiki_root, backlinks)
    inject_referenced_by(wiki_root, backlinks)
    write_provenance(wiki_root, last_refreshed=date.today().isoformat())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_wiki_lint.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/wiki_index.py tests/test_wiki_lint.py
git commit -m "feat(wiki): add wiki_index CLI with --lint JSON output"
```

---

## Task 9: Wire lint into `/archie-scan` report

**Files:**
- Modify: `.claude/commands/archie-scan.md`

- [ ] **Step 1: Add a lint step**

After the wiki incremental step (Task 5), add:

```bash
WIKI_LINT=$(python3 .archie/wiki_index.py --wiki "$PWD/.archie/wiki" --fs-root "$PWD" --lint --json)
echo "$WIKI_LINT" > /tmp/archie_wiki_lint.json
```

- [ ] **Step 2: Instruct the scan LLM to include lint findings in the report**

In the scan-report section of `archie-scan.md`, add:

```markdown
### Wiki health

Read `/tmp/archie_wiki_lint.json`. For each finding, include it under "Wiki lint
findings" in the scan report with the following format:

- **[kind]** page — detail

Categorize by kind (orphan, broken_link, stale_evidence, dangling_backlink,
contradiction). If the list is empty, write: "Wiki lint: clean."
```

- [ ] **Step 3: Commit**

```bash
git add .claude/commands/archie-scan.md
git commit -m "feat(wiki): surface wiki lint findings in scan report"
```

---

## Task 10: NPM sync + end-to-end verification

- [ ] **Step 1: Sync**

```bash
cp archie/standalone/wiki_builder.py npm-package/assets/wiki_builder.py
cp archie/standalone/wiki_index.py npm-package/assets/wiki_index.py
python3 scripts/verify_sync.py
```

Expected: exit 0.

- [ ] **Step 2: Full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all green.

- [ ] **Step 3: Manual end-to-end**

On a fixture project:

1. Run `/archie-deep-scan` (from Plans 1+2 output this populates `.archie/wiki/`).
2. Modify one evidence file for a capability.
3. Run `/archie-scan`.
4. Confirm: only that capability page's mtime changed; scan_report has "Wiki updates: 1 page" and "Wiki lint: clean."
5. Break the wiki (e.g. rename a component file referenced by evidence globs). Re-run `/archie-scan`. Confirm lint surfaces `stale_evidence`.

- [ ] **Step 4: Commit NPM sync**

```bash
git add npm-package/
git commit -m "chore(wiki): sync incremental + lint to npm-package assets"
```

---

## Self-review checklist

- [ ] Spec §5.2 (incremental pipeline steps 1-4) implemented in `build_wiki_incremental`.
- [ ] Spec §5.3 (five lint kinds) all implemented and tested.
- [ ] `--incremental` aborts cleanly when blueprint structure changed (tested via `_blueprint_structure_changed`).
- [ ] SHA256 gating means unchanged content does not bump `last_refreshed` (tested).
- [ ] `/archie-scan` command file has the two new bash steps and the report section.
- [ ] NPM sync passes.
- [ ] No placeholders or "TBD".

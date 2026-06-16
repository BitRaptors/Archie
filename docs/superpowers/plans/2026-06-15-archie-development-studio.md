# Archie Development Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a development-studio workflow to Archie — issue tracking + an autonomous dev loop — set up by `/archie-start-development-studio` and integrated with Archie's blueprint/rules/hooks.

**Architecture:** Hybrid. Deterministic mechanics (scaffold, ID allocation, status moves, INDEX generation, AGENTS.md patch) live in a zero-dependency `archie/standalone/studio.py`. The reasoning layer (plan/implement/verify/review/loop) lives in prompt markdown the agent reads. Three thin command files route to the prompts.

**Tech Stack:** Python 3.9+ stdlib only (matching existing standalone scripts), pytest, markdown prompt/command files, npm asset sync.

---

## File Structure

- Create: `archie/standalone/studio.py` — the deterministic engine (all subcommands + helpers)
- Create: `tests/test_studio.py` — pytest suite, imports `from archie.standalone import studio`
- Create: `.claude/commands/archie-start-development-studio.md` — router to setup prompt
- Create: `.claude/commands/archie-issue.md` — router to issue prompt
- Create: `.claude/commands/archie-work.md` — router to work-loop prompt
- Create: `.archie/prompts/skill_archie_studio_setup.md` — setup command body
- Create: `.archie/prompts/skill_archie_studio_issue.md` — new-issue body
- Create: `.archie/prompts/skill_archie_studio_work.md` — autonomous loop body
- Modify (sync copies): `npm-package/assets/studio.py`, `npm-package/assets/archie-*.md`, prompt copies, and `npm-package/archie.mjs` installer references
- Reference: `scripts/verify_sync.py` (run, do not edit)

All ticket data and `WORKFLOW.md` are generated into the **target** project's `.archie/issues/` at runtime by `studio.py init` — they are NOT committed to the Archie repo. The `WORKFLOW.md` body text is embedded as a string constant in `studio.py`.

---

## Task 1: Module scaffold + status constants + frontmatter parser

**Files:**
- Create: `archie/standalone/studio.py`
- Test: `tests/test_studio.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the development studio engine (archie/standalone/studio.py)."""
from __future__ import annotations

from pathlib import Path

from archie.standalone import studio


def test_parse_frontmatter_scalars_and_inline_list():
    text = (
        "---\n"
        "id: ISS-007\n"
        "title: Add upload resize\n"
        "status: planned\n"
        "labels: [backend, infra]\n"
        "type: feature\n"
        "---\n"
        "## Context\nbody here\n"
    )
    fm = studio.parse_frontmatter(text)
    assert fm["id"] == "ISS-007"
    assert fm["title"] == "Add upload resize"
    assert fm["status"] == "planned"
    assert fm["labels"] == ["backend", "infra"]
    assert fm["type"] == "feature"


def test_parse_frontmatter_returns_none_when_absent():
    assert studio.parse_frontmatter("no frontmatter here\n") is None


def test_statuses_constant():
    assert studio.STATUSES == [
        "planned",
        "in-progress",
        "in-review",
        "done",
        "blocked",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_studio.py -v`
Expected: FAIL with `ModuleNotFoundError` / `AttributeError: module 'studio' has no attribute 'parse_frontmatter'`

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
"""Archie development studio — deterministic issue-tracking engine.

Subcommands (Python never runs git — it only writes files):
  python3 studio.py init  /path/to/repo
  python3 studio.py new   /path/to/repo --title "..." --type feature --label backend
  python3 studio.py move  /path/to/repo ISS-NNN <status>
  python3 studio.py index /path/to/repo
  python3 studio.py next  /path/to/repo

Scaffolds and maintains `.archie/issues/` in the target project. The INDEX.md
tables are always DERIVED from ticket frontmatter — never hand-edited.

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import sys
from pathlib import Path

STATUSES = ["planned", "in-progress", "in-review", "done", "blocked"]


def parse_frontmatter(text: str) -> dict | None:
    """Parse a minimal YAML frontmatter block (--- ... ---) at the top of text.

    Supports scalars (`key: value`) and inline lists (`key: [a, b]`). Returns
    None if no frontmatter block is present. Robust to a leading BOM/whitespace.
    """
    s = text.lstrip("﻿")
    if not s.startswith("---"):
        return None
    lines = s.splitlines()
    # first line is the opening ---; find the closing ---
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None
    fm: dict = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, raw = line.partition(":")
        key = key.strip()
        val = raw.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            fm[key] = [x.strip() for x in inner.split(",") if x.strip()] if inner else []
        else:
            fm[key] = val
    return fm


if __name__ == "__main__":
    print("studio.py: not yet wired", file=sys.stderr)
    sys.exit(1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_studio.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Verify `archie/standalone/__init__.py` exists** (so `from archie.standalone import studio` resolves)

Run: `ls archie/standalone/__init__.py && ls archie/__init__.py`
Expected: both paths print. If missing, create empty `archie/standalone/__init__.py`.

- [ ] **Step 6: Commit**

```bash
git add archie/standalone/studio.py tests/test_studio.py
git commit -m "feat(studio): frontmatter parser + status constants"
```

---

## Task 2: Ticket discovery + ID allocation

**Files:**
- Modify: `archie/standalone/studio.py`
- Test: `tests/test_studio.py`

- [ ] **Step 1: Write the failing test**

```python
def _write_ticket(issues: Path, status: str, tid: str, **extra):
    folder = issues / status
    folder.mkdir(parents=True, exist_ok=True)
    fm_extra = "".join(f"{k}: {v}\n" for k, v in extra.items())
    (folder / f"{tid}-slug.md").write_text(
        f"---\nid: {tid}\ntitle: t\nstatus: {status}\n{fm_extra}---\n## Context\n"
    )


def test_iter_tickets_collects_across_status_folders(tmp_path: Path):
    issues = tmp_path / ".archie" / "issues"
    _write_ticket(issues, "planned", "ISS-001")
    _write_ticket(issues, "done", "ISS-002")
    tickets = studio.iter_tickets(issues)
    ids = sorted(t["id"] for t in tickets)
    assert ids == ["ISS-001", "ISS-002"]


def test_iter_tickets_skips_corrupt_file(tmp_path: Path, capsys):
    issues = tmp_path / ".archie" / "issues"
    (issues / "planned").mkdir(parents=True)
    (issues / "planned" / "ISS-001-ok.md").write_text(
        "---\nid: ISS-001\nstatus: planned\n---\n"
    )
    (issues / "planned" / "garbage.md").write_text("no frontmatter\n")
    tickets = studio.iter_tickets(issues)
    assert [t["id"] for t in tickets] == ["ISS-001"]
    assert "skip" in capsys.readouterr().err.lower()


def test_next_id_finds_max_across_folders(tmp_path: Path):
    issues = tmp_path / ".archie" / "issues"
    _write_ticket(issues, "planned", "ISS-003")
    _write_ticket(issues, "done", "ISS-011")
    _write_ticket(issues, "in-progress", "ISS-007")
    assert studio.next_id(studio.iter_tickets(issues), "ISS") == "ISS-012"


def test_next_id_first_when_empty():
    assert studio.next_id([], "ISS") == "ISS-001"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_studio.py -k "iter_tickets or next_id" -v`
Expected: FAIL with `AttributeError: module ... has no attribute 'iter_tickets'`

- [ ] **Step 3: Write minimal implementation** (add to `studio.py`, above the `__main__` block)

```python
import re


def issues_dir(root: Path) -> Path:
    return root / ".archie" / "issues"


def iter_tickets(issues: Path) -> list[dict]:
    """Parse every ticket .md across status folders. Skip corrupt files (warn)."""
    tickets: list[dict] = []
    if not issues.exists():
        return tickets
    for status in STATUSES:
        folder = issues / status
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.md")):
            try:
                fm = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                fm = None
            if not fm or "id" not in fm:
                print(f"studio: skip unparseable ticket {path}", file=sys.stderr)
                continue
            fm["_path"] = path
            fm["_folder_status"] = status
            tickets.append(fm)
    return tickets


def next_id(tickets: list[dict], prefix: str) -> str:
    """Return the next zero-padded id (e.g. ISS-012) given existing tickets."""
    pat = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    nums = [int(m.group(1)) for t in tickets if (m := pat.match(str(t.get("id", ""))))]
    return f"{prefix}-{(max(nums) + 1) if nums else 1:03d}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_studio.py -k "iter_tickets or next_id" -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/studio.py tests/test_studio.py
git commit -m "feat(studio): ticket discovery + id allocation"
```

---

## Task 3: INDEX.md generation (derived)

**Files:**
- Modify: `archie/standalone/studio.py`
- Test: `tests/test_studio.py`

- [ ] **Step 1: Write the failing test**

```python
def test_render_index_contains_next_ids_and_tables(tmp_path: Path):
    issues = tmp_path / ".archie" / "issues"
    _write_ticket(issues, "planned", "ISS-001", type="feature", labels="[backend]")
    _write_ticket(issues, "in-progress", "ISS-002", type="bugfix", labels="[frontend]")
    _write_ticket(issues, "done", "ISS-003", type="chore", labels="[infra]")
    tickets = studio.iter_tickets(issues)
    out = studio.render_index(tickets)
    assert "Next issue: ISS-004" in out
    assert "Next epic: EPIC-001" in out
    assert "ISS-001" in out and "ISS-002" in out  # active table
    assert "ISS-003" in out  # done table
    assert "## Active" in out and "## Done" in out


def test_render_index_lists_blocked_separately(tmp_path: Path):
    issues = tmp_path / ".archie" / "issues"
    _write_ticket(issues, "blocked", "ISS-005")
    out = studio.render_index(studio.iter_tickets(issues))
    assert "## Blocked" in out
    assert "ISS-005" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_studio.py -k render_index -v`
Expected: FAIL with `AttributeError: ... 'render_index'`

- [ ] **Step 3: Write minimal implementation** (add to `studio.py`)

```python
def _row(t: dict, cols: list[str]) -> str:
    def cell(key: str) -> str:
        v = t.get(key, "")
        if isinstance(v, list):
            v = ", ".join(v)
        return str(v).replace("|", "\\|") or "—"
    return "| " + " | ".join(cell(c) for c in cols) + " |"


def render_index(tickets: list[dict]) -> str:
    by = {s: [t for t in tickets if t.get("status") == s] for s in STATUSES}
    next_iss = next_id(tickets, "ISS")
    next_epic = next_id(tickets, "EPIC")  # epics live in epics/, counted separately in Task later; ISS list won't match EPIC pattern
    lines: list[str] = []
    lines.append("# Issue Index")
    lines.append("")
    lines.append("> Generated by `studio.py index` — do not edit by hand.")
    lines.append("")
    lines.append(f"- Next issue: {next_iss}")
    lines.append(f"- Next epic: {next_epic}")
    lines.append("")
    lines.append("## Blocked")
    if by["blocked"]:
        lines.append("| ID | Title | Branch |")
        lines.append("| --- | --- | --- |")
        for t in by["blocked"]:
            lines.append(_row(t, ["id", "title", "branch"]))
    else:
        lines.append("None.")
    lines.append("")
    lines.append("## Active")
    active = by["in-progress"] + by["in-review"] + by["planned"]
    lines.append("| ID | Title | Status | Type | Labels | Branch |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for t in active:
        lines.append(_row(t, ["id", "title", "status", "type", "labels", "branch"]))
    if not active:
        lines.append("| — | none | — | — | — | — |")
    lines.append("")
    lines.append("## Done")
    lines.append("| ID | Title | Type | Labels |")
    lines.append("| --- | --- | --- | --- |")
    for t in by["done"][-20:]:
        lines.append(_row(t, ["id", "title", "type", "labels"]))
    if not by["done"]:
        lines.append("| — | none | — | — |")
    lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_studio.py -k render_index -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/studio.py tests/test_studio.py
git commit -m "feat(studio): derived INDEX.md generation"
```

---

## Task 4: `init` scaffold (folders + template + WORKFLOW.md + INDEX)

**Files:**
- Modify: `archie/standalone/studio.py`
- Test: `tests/test_studio.py`

- [ ] **Step 1: Write the failing test**

```python
def test_cmd_init_creates_structure(tmp_path: Path):
    studio.cmd_init(tmp_path)
    issues = tmp_path / ".archie" / "issues"
    for sub in studio.STATUSES + ["epics", "evidence"]:
        assert (issues / sub).is_dir(), f"missing {sub}"
    assert (issues / "_TEMPLATE.md").exists()
    assert (issues / "WORKFLOW.md").exists()
    assert (issues / "INDEX.md").exists()
    assert "ISS-NNN" in (issues / "_TEMPLATE.md").read_text()
    assert "Required Workflow" in (issues / "WORKFLOW.md").read_text()


def test_cmd_init_idempotent_keeps_tickets(tmp_path: Path):
    studio.cmd_init(tmp_path)
    issues = tmp_path / ".archie" / "issues"
    (issues / "planned" / "ISS-001-x.md").write_text(
        "---\nid: ISS-001\ntitle: keep\nstatus: planned\n---\n"
    )
    studio.cmd_init(tmp_path)  # re-run
    assert (issues / "planned" / "ISS-001-x.md").exists(), "init destroyed a ticket"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_studio.py -k cmd_init -v`
Expected: FAIL with `AttributeError: ... 'cmd_init'`

- [ ] **Step 3: Write minimal implementation** (add to `studio.py`)

```python
TEMPLATE = """---
id: ISS-NNN
title: Short imperative title
status: planned
labels: []
branch: feature/ISS-NNN-slug
assignee: csaba
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: feature
epic:
---

## Context
Why this work is needed.

## Plan
- [ ] Step one (verifiable)

## Implementation Notes

## Iteration Log
- iter 01 (YYYY-MM-DD HH:MM): what / result / next

## Last Test Run
```
command:
result:
summary:
ran:
```

## Evidence

## Blocker

## Review Notes

## Testing
"""

WORKFLOW_DOC = """# Development Studio Workflow

This project uses Archie's development studio. All issue tracking lives under
`.archie/issues/`. The INDEX.md is generated — never hand-edit it.

## Required Workflow

When asked for any code change, follow these steps in order. Do not skip steps.

1. **Discovery** — read `.archie/issues/INDEX.md`. If a ticket is `blocked`, surface
   it and stop. Check `in-progress/` for overlapping work. Confirm work type
   (feature/bugfix/refactor/chore).
2. **Ticket creation (on `main`)** — `python3 .archie/studio.py new . --title "..."
   --type <type> --label <label>`. Fill Context. Commit `docs(issues): add ISS-NNN
   <title>` and push.
3. **Branch & Plan** — branch `<type>/ISS-NNN-<slug>`. Read `.archie/blueprint.json`
   for the relevant decisions, domain_invariants, pitfalls, components. Write the Plan
   as a checkbox list, annotating which rule/invariant each step preserves.
   `python3 .archie/studio.py move . ISS-NNN in-progress`. Commit `docs(issues): plan
   ISS-NNN`. **Wait for approval.**
4. **Implementation (autonomous loop)** — implement step by step. Archie's
   `pre-validate.sh` hook enforces `rules.json` on every edit; on a block, fix using
   the rule's WHY + EXAMPLE. After each checkbox: append Iteration Log, update Last
   Test Run, mark `[x]`, commit `feat(ISS-NNN): <step>`. Capture evidence into
   `evidence/ISS-NNN/`.
5. **Review** — separate review agent on the diff; findings → Review Notes;
   `move . ISS-NNN in-review`.
6. **Verify** — every acceptance criterion one by one; test touched domain invariants
   concretely. Optionally run `validate.py` + `drift.py`.
7. **Close out** — `move . ISS-NNN done`, write the PR description, commit
   `docs(issues): close ISS-NNN`, open the PR.

## Autonomous Execution

Once a plan is approved, run the loop without pausing between
implement/test/fix/review until ready to close. Stop and ask only when: the plan needs
a material change; a destructive/hard-to-reverse action is required; or after 2
consecutive failed fix attempts on the same root cause → set `status: blocked`, write
the Blocker section, and stop.

## Ralph Loop Entry

When invoked without a specific task: read INDEX.md; if anything is `blocked`, stop and
surface it; else continue the topmost `in-progress` ticket from its first unchecked
`[ ]`; else promote the topmost `planned` ticket; else report idle. Every ticket is
self-contained — never rely on conversation memory.

## Hard Rules

- Never start coding without a ticket. Never skip reading INDEX.md first.
- One ticket = one branch = one logical change.
- Always update the index via `studio.py move` / `studio.py index` — never hand-edit it.
- Commit after every checked Plan step.
- If `.archie/blueprint.json` is missing, run `/archie-deep-scan` first — the loop
  works without it but with no architectural enforcement or guidance.
"""


def write_index(root: Path) -> None:
    issues = issues_dir(root)
    (issues / "INDEX.md").write_text(render_index(iter_tickets(issues)), encoding="utf-8")


def cmd_init(root: Path) -> None:
    issues = issues_dir(root)
    for sub in STATUSES + ["epics", "evidence"]:
        (issues / sub).mkdir(parents=True, exist_ok=True)
    tmpl = issues / "_TEMPLATE.md"
    if not tmpl.exists():
        tmpl.write_text(TEMPLATE, encoding="utf-8")
    (issues / "WORKFLOW.md").write_text(WORKFLOW_DOC, encoding="utf-8")
    write_index(root)
    print(f"studio: initialized {issues}", file=sys.stderr)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_studio.py -k cmd_init -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/studio.py tests/test_studio.py
git commit -m "feat(studio): init scaffold with template + workflow doc"
```

---

## Task 5: AGENTS.md pointer patch (idempotent)

**Files:**
- Modify: `archie/standalone/studio.py` (call `patch_agents_md` from `cmd_init`)
- Test: `tests/test_studio.py`

- [ ] **Step 1: Write the failing test**

```python
def test_patch_agents_md_creates_when_absent(tmp_path: Path):
    studio.patch_agents_md(tmp_path)
    content = (tmp_path / "AGENTS.md").read_text()
    assert "ARCHIE:STUDIO:START" in content
    assert ".archie/issues/WORKFLOW.md" in content


def test_patch_agents_md_appends_to_existing(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("# Existing\nkeep me\n")
    studio.patch_agents_md(tmp_path)
    content = (tmp_path / "AGENTS.md").read_text()
    assert "keep me" in content
    assert "ARCHIE:STUDIO:START" in content


def test_patch_agents_md_idempotent_replaces_block(tmp_path: Path):
    studio.patch_agents_md(tmp_path)
    studio.patch_agents_md(tmp_path)  # twice
    content = (tmp_path / "AGENTS.md").read_text()
    assert content.count("ARCHIE:STUDIO:START") == 1, "block was duplicated"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_studio.py -k patch_agents -v`
Expected: FAIL with `AttributeError: ... 'patch_agents_md'`

- [ ] **Step 3: Write minimal implementation** (add to `studio.py`, and call it from `cmd_init`)

```python
STUDIO_START = "<!-- ARCHIE:STUDIO:START -->"
STUDIO_END = "<!-- ARCHIE:STUDIO:END -->"
STUDIO_BLOCK = f"""{STUDIO_START}
## Development Studio
This project uses Archie's development studio for issue tracking and the agentic
development loop. **Before any code change, read `.archie/issues/WORKFLOW.md`** — it
defines the required workflow, ticket lifecycle, and autonomous execution rules.
{STUDIO_END}"""


def patch_agents_md(root: Path) -> None:
    path = root / "AGENTS.md"
    if not path.exists():
        path.write_text(STUDIO_BLOCK + "\n", encoding="utf-8")
        return
    content = path.read_text(encoding="utf-8")
    if STUDIO_START in content and STUDIO_END in content:
        pre = content.split(STUDIO_START)[0]
        post = content.split(STUDIO_END, 1)[1]
        content = pre + STUDIO_BLOCK + post
    else:
        sep = "" if content.endswith("\n") else "\n"
        content = content + sep + "\n" + STUDIO_BLOCK + "\n"
    path.write_text(content, encoding="utf-8")
```

Then add to the end of `cmd_init`:

```python
    patch_agents_md(root)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_studio.py -k "patch_agents or cmd_init" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/studio.py tests/test_studio.py
git commit -m "feat(studio): idempotent AGENTS.md pointer patch"
```

---

## Task 6: `new` subcommand

**Files:**
- Modify: `archie/standalone/studio.py`
- Test: `tests/test_studio.py`

- [ ] **Step 1: Write the failing test**

```python
def test_cmd_new_creates_ticket_and_refreshes_index(tmp_path: Path):
    studio.cmd_init(tmp_path)
    tid = studio.cmd_new(tmp_path, title="Add upload resize", type_="feature",
                         labels=["backend"], today="2026-06-15")
    assert tid == "ISS-001"
    issues = tmp_path / ".archie" / "issues"
    files = list((issues / "planned").glob("ISS-001-*.md"))
    assert len(files) == 1
    body = files[0].read_text()
    assert "id: ISS-001" in body
    assert "title: Add upload resize" in body
    assert "labels: [backend]" in body
    assert "ISS-001" in (issues / "INDEX.md").read_text()


def test_cmd_new_increments_id(tmp_path: Path):
    studio.cmd_init(tmp_path)
    studio.cmd_new(tmp_path, title="one", type_="feature", labels=[], today="2026-06-15")
    second = studio.cmd_new(tmp_path, title="two", type_="bugfix", labels=[], today="2026-06-15")
    assert second == "ISS-002"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_studio.py -k cmd_new -v`
Expected: FAIL with `AttributeError: ... 'cmd_new'`

- [ ] **Step 3: Write minimal implementation** (add to `studio.py`)

```python
def _slugify(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return "-".join(s.split("-")[:6]) or "ticket"


def cmd_new(root: Path, *, title: str, type_: str, labels: list[str], today: str) -> str:
    issues = issues_dir(root)
    if not issues.exists():
        cmd_init(root)
    tid = next_id(iter_tickets(issues), "ISS")
    slug = _slugify(title)
    labels_yaml = "[" + ", ".join(labels) + "]"
    body = (
        f"---\n"
        f"id: {tid}\n"
        f"title: {title}\n"
        f"status: planned\n"
        f"labels: {labels_yaml}\n"
        f"branch: {type_}/{tid}-{slug}\n"
        f"assignee: csaba\n"
        f"created: {today}\n"
        f"updated: {today}\n"
        f"type: {type_}\n"
        f"epic:\n"
        f"---\n\n"
        f"## Context\n\n## Plan\n- [ ] \n\n## Implementation Notes\n\n"
        f"## Iteration Log\n\n## Last Test Run\n\n## Evidence\n\n"
        f"## Blocker\n\n## Review Notes\n\n## Testing\n"
    )
    (issues / "planned" / f"{tid}-{slug}.md").write_text(body, encoding="utf-8")
    write_index(root)
    print(f"studio: created {tid}", file=sys.stderr)
    return tid
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_studio.py -k cmd_new -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/studio.py tests/test_studio.py
git commit -m "feat(studio): new-ticket subcommand"
```

---

## Task 7: `move` subcommand

**Files:**
- Modify: `archie/standalone/studio.py`
- Test: `tests/test_studio.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest


def test_cmd_move_relocates_and_refreshes_index(tmp_path: Path):
    studio.cmd_init(tmp_path)
    tid = studio.cmd_new(tmp_path, title="one", type_="feature", labels=[], today="2026-06-15")
    studio.cmd_move(tmp_path, tid, "in-progress")
    issues = tmp_path / ".archie" / "issues"
    assert not list((issues / "planned").glob(f"{tid}-*.md"))
    moved = list((issues / "in-progress").glob(f"{tid}-*.md"))
    assert len(moved) == 1
    assert "status: in-progress" in moved[0].read_text()


def test_cmd_move_rejects_unknown_status(tmp_path: Path):
    studio.cmd_init(tmp_path)
    tid = studio.cmd_new(tmp_path, title="one", type_="feature", labels=[], today="2026-06-15")
    with pytest.raises(SystemExit):
        studio.cmd_move(tmp_path, tid, "frozen")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_studio.py -k cmd_move -v`
Expected: FAIL with `AttributeError: ... 'cmd_move'`

- [ ] **Step 3: Write minimal implementation** (add to `studio.py`)

```python
def _find_ticket_path(issues: Path, tid: str) -> Path | None:
    for t in iter_tickets(issues):
        if t.get("id") == tid:
            return t["_path"]
    return None


def cmd_move(root: Path, tid: str, status: str) -> None:
    if status not in STATUSES:
        print(f"studio: unknown status '{status}' (allowed: {', '.join(STATUSES)})",
              file=sys.stderr)
        sys.exit(2)
    issues = issues_dir(root)
    src = _find_ticket_path(issues, tid)
    if src is None:
        print(f"studio: ticket {tid} not found", file=sys.stderr)
        sys.exit(2)
    text = src.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^status:.*$", f"status: {status}", text, count=1)
    dest = issues / status / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    if dest != src:
        src.unlink()
    write_index(root)
    print(f"studio: moved {tid} -> {status}", file=sys.stderr)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_studio.py -k cmd_move -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/studio.py tests/test_studio.py
git commit -m "feat(studio): move subcommand with status validation"
```

---

## Task 8: `next` subcommand (Ralph priority)

**Files:**
- Modify: `archie/standalone/studio.py`
- Test: `tests/test_studio.py`

- [ ] **Step 1: Write the failing test**

```python
def test_cmd_next_surfaces_blocked(tmp_path: Path, capsys):
    studio.cmd_init(tmp_path)
    tid = studio.cmd_new(tmp_path, title="b", type_="feature", labels=[], today="2026-06-15")
    studio.cmd_move(tmp_path, tid, "blocked")
    result = studio.cmd_next(tmp_path)
    assert result["action"] == "blocked"
    assert result["id"] == tid


def test_cmd_next_prefers_in_progress(tmp_path: Path):
    studio.cmd_init(tmp_path)
    a = studio.cmd_new(tmp_path, title="a", type_="feature", labels=[], today="2026-06-15")
    studio.cmd_new(tmp_path, title="b", type_="feature", labels=[], today="2026-06-15")
    studio.cmd_move(tmp_path, a, "in-progress")
    result = studio.cmd_next(tmp_path)
    assert result["action"] == "continue"
    assert result["id"] == a


def test_cmd_next_promotes_planned(tmp_path: Path):
    studio.cmd_init(tmp_path)
    a = studio.cmd_new(tmp_path, title="a", type_="feature", labels=[], today="2026-06-15")
    result = studio.cmd_next(tmp_path)
    assert result["action"] == "promote"
    assert result["id"] == a


def test_cmd_next_idle_when_empty(tmp_path: Path):
    studio.cmd_init(tmp_path)
    result = studio.cmd_next(tmp_path)
    assert result["action"] == "idle"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_studio.py -k cmd_next -v`
Expected: FAIL with `AttributeError: ... 'cmd_next'`

- [ ] **Step 3: Write minimal implementation** (add to `studio.py`)

```python
import json


def cmd_next(root: Path) -> dict:
    """Return the next action per Ralph priority. Prints JSON to stdout."""
    tickets = iter_tickets(issues_dir(root))
    by = {s: [t for t in tickets if t.get("status") == s] for s in STATUSES}

    def pick(lst):
        return sorted(lst, key=lambda t: str(t.get("id")))[0]

    if by["blocked"]:
        t = pick(by["blocked"])
        result = {"action": "blocked", "id": t["id"], "title": t.get("title")}
    elif by["in-progress"]:
        t = pick(by["in-progress"])
        result = {"action": "continue", "id": t["id"], "title": t.get("title"),
                  "path": str(t["_path"])}
    elif by["planned"]:
        t = pick(by["planned"])
        result = {"action": "promote", "id": t["id"], "title": t.get("title"),
                  "path": str(t["_path"])}
    else:
        result = {"action": "idle"}
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_studio.py -k cmd_next -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/studio.py tests/test_studio.py
git commit -m "feat(studio): next subcommand with Ralph priority"
```

---

## Task 9: CLI entry point wiring

**Files:**
- Modify: `archie/standalone/studio.py` (replace the `__main__` stub)
- Test: `tests/test_studio.py`

- [ ] **Step 1: Write the failing test** (subprocess-level smoke test of the CLI)

```python
import subprocess
import sys as _sys


def test_cli_init_then_new_then_index(tmp_path: Path):
    script = Path("archie/standalone/studio.py").resolve()
    subprocess.run([_sys.executable, str(script), "init", str(tmp_path)], check=True)
    subprocess.run(
        [_sys.executable, str(script), "new", str(tmp_path),
         "--title", "CLI ticket", "--type", "feature", "--label", "backend"],
        check=True,
    )
    out = subprocess.run(
        [_sys.executable, str(script), "next", str(tmp_path)],
        check=True, capture_output=True, text=True,
    ).stdout
    assert '"action": "promote"' in out
    assert "ISS-001" in out


def test_cli_usage_on_no_args():
    script = Path("archie/standalone/studio.py").resolve()
    r = subprocess.run([_sys.executable, str(script)], capture_output=True, text=True)
    assert r.returncode != 0
    assert "Usage" in r.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_studio.py -k cli -v`
Expected: FAIL (current stub prints "not yet wired", `next`/`--title` unsupported)

- [ ] **Step 3: Write minimal implementation** (replace the `if __name__ == "__main__":` block)

```python
def _flag(argv: list[str], name: str, default=None):
    for i, a in enumerate(argv):
        if a == name and i + 1 < len(argv):
            return argv[i + 1]
    return default


def _flags_all(argv: list[str], name: str) -> list[str]:
    out = []
    for i, a in enumerate(argv):
        if a == name and i + 1 < len(argv):
            out.append(argv[i + 1])
    return out


def _today() -> str:
    from datetime import date
    return date.today().isoformat()


def _usage() -> None:
    print(
        "Usage:\n"
        "  studio.py init  <repo>\n"
        "  studio.py new   <repo> --title \"...\" --type <type> [--label L ...]\n"
        "  studio.py move  <repo> ISS-NNN <status>\n"
        "  studio.py index <repo>\n"
        "  studio.py next  <repo>",
        file=sys.stderr,
    )


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        _usage()
        return 1
    sub = argv[0]
    root = Path(argv[1]).resolve()
    rest = argv[2:]
    if sub == "init":
        cmd_init(root)
    elif sub == "new":
        title = _flag(rest, "--title")
        if not title:
            print("studio: --title required", file=sys.stderr)
            return 2
        cmd_new(root, title=title, type_=_flag(rest, "--type", "feature"),
                labels=_flags_all(rest, "--label"), today=_today())
    elif sub == "move":
        if len(rest) < 2:
            print("studio: move needs ISS-NNN <status>", file=sys.stderr)
            return 2
        cmd_move(root, rest[0], rest[1])
    elif sub == "index":
        write_index(root)
    elif sub == "next":
        cmd_next(root)
    else:
        _usage()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_studio.py -v`
Expected: PASS (whole suite green)

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/studio.py tests/test_studio.py
git commit -m "feat(studio): CLI entry point dispatch"
```

---

## Task 10: Prompt files (setup, issue, work)

**Files:**
- Create: `.archie/prompts/skill_archie_studio_setup.md`
- Create: `.archie/prompts/skill_archie_studio_issue.md`
- Create: `.archie/prompts/skill_archie_studio_work.md`

> No automated test — these are agent instructions. Verified by review + a manual dry run in Task 13.

- [ ] **Step 1: Write `skill_archie_studio_setup.md`**

```markdown
# Archie Development Studio — Setup

Set up the development studio in this project.

1. Run: `python3 .archie/studio.py init .`
   This scaffolds `.archie/issues/` (status folders, `_TEMPLATE.md`, `WORKFLOW.md`,
   `INDEX.md`) and inserts a pointer block into `AGENTS.md`.
2. Confirm `.archie/issues/WORKFLOW.md` exists and read it — it is the source of truth
   for the workflow.
3. If `.archie/blueprint.json` is missing, tell the user the loop will run without
   architectural enforcement/guidance and recommend running `/archie-deep-scan` first.
4. Report what was created and point the user at `/archie-issue` (create a ticket) and
   `/archie-work` (run the loop).

Do not commit automatically — let the user review, then commit
`docs(studio): initialize development studio`.
```

- [ ] **Step 2: Write `skill_archie_studio_issue.md`**

```markdown
# Archie Development Studio — New Issue

Create a new ticket.

1. Ask the user (or infer from their request): title, type
   (feature/bugfix/refactor/chore), labels.
2. Run: `python3 .archie/studio.py new . --title "<title>" --type <type>
   --label <label>` (repeat `--label` per label).
3. Open the created ticket file under `.archie/issues/planned/` and fill in the
   `## Context` section. Leave `## Plan` empty (it is filled during `/archie-work`).
4. Commit `docs(issues): add <ISS-NNN> <title>` and push so the ticket is visible.
5. Tell the user the ticket id and that `/archie-work` will pick it up.
```

- [ ] **Step 3: Write `skill_archie_studio_work.md`**

```markdown
# Archie Development Studio — Work Loop

Run the development loop. Read `.archie/issues/WORKFLOW.md` first — it is authoritative.

1. Run `python3 .archie/studio.py next .` to pick the ticket.
   - `blocked` → surface it to the user and STOP.
   - `continue` → resume the in-progress ticket from its first unchecked `[ ]`.
   - `promote` → start the planned ticket (branch + plan).
   - `idle` → report nothing to do.
2. **Scope & Plan**: read the ticket AND `.archie/blueprint.json` (relevant decisions,
   domain_invariants, pitfalls, components for the touched folders). Create branch
   `<type>/ISS-NNN-<slug>`, run `python3 .archie/studio.py move . ISS-NNN in-progress`,
   write the Plan as a checkbox list annotating which rule/invariant each step
   preserves. **Wait for user approval of the plan.**
3. **Autonomous after approval**: implement step by step. Archie's `pre-validate.sh`
   hook enforces `rules.json` on each edit — on a block, fix using the rule's WHY +
   EXAMPLE. After each checkbox: append Iteration Log, update Last Test Run, mark
   `[x]`, commit `feat(ISS-NNN): <step>`. Capture evidence into `evidence/ISS-NNN/`.
4. **Review**: separate review agent on the diff → Review Notes; `move . ISS-NNN
   in-review`.
5. **Verify**: each acceptance criterion one by one; test touched domain invariants
   concretely; optionally run `validate.py` and `drift.py`.
6. **Close out**: `move . ISS-NNN done`, write the PR description, commit
   `docs(issues): close ISS-NNN`, open the PR.

Stop and ask only for: material plan changes, destructive actions, or 2 consecutive
failed fixes on the same root cause (then set `status: blocked`, write Blocker, stop).
```

- [ ] **Step 4: Commit**

```bash
git add .archie/prompts/skill_archie_studio_setup.md .archie/prompts/skill_archie_studio_issue.md .archie/prompts/skill_archie_studio_work.md
git commit -m "feat(studio): prompt bodies for setup/issue/work"
```

---

## Task 11: Command files (routers)

**Files:**
- Create: `.claude/commands/archie-start-development-studio.md`
- Create: `.claude/commands/archie-issue.md`
- Create: `.claude/commands/archie-work.md`

- [ ] **Step 1: Write `archie-start-development-studio.md`**

```markdown
---
description: Set up Archie's development studio (issue tracking + agentic dev loop) in this project.
---

Read `.archie/prompts/skill_archie_studio_setup.md` in full and execute the instructions as written.
```

- [ ] **Step 2: Write `archie-issue.md`**

```markdown
---
description: Create a new development-studio ticket under .archie/issues/.
---

Read `.archie/prompts/skill_archie_studio_issue.md` in full and execute the instructions as written.
```

- [ ] **Step 3: Write `archie-work.md`**

```markdown
---
description: Run the Archie development loop on the next ticket (Ralph priority).
---

Read `.archie/prompts/skill_archie_studio_work.md` in full and execute the instructions as written.
```

- [ ] **Step 4: Commit**

```bash
git add .claude/commands/archie-start-development-studio.md .claude/commands/archie-issue.md .claude/commands/archie-work.md
git commit -m "feat(studio): command routers for studio/issue/work"
```

---

## Task 12: NPM sync (assets + installer references)

**Files:**
- Create (copies): `npm-package/assets/studio.py`, `npm-package/assets/archie-start-development-studio.md`, `npm-package/assets/archie-issue.md`, `npm-package/assets/archie-work.md`, and the three prompt copies
- Modify: `npm-package/archie.mjs` (register the new script, commands, and prompts so the installer copies them)

- [ ] **Step 1: Inspect how `archie.mjs` lists assets**

Run: `grep -n "intent_layer\|archie-intent-layer\|skill_archie" npm-package/archie.mjs | head -40`
Expected: shows the arrays/lists where script files, command files, and prompt files are enumerated. Mirror those patterns for the new files.

- [ ] **Step 2: Copy assets to `npm-package/assets/`**

```bash
cp archie/standalone/studio.py npm-package/assets/studio.py
cp .claude/commands/archie-start-development-studio.md npm-package/assets/archie-start-development-studio.md
cp .claude/commands/archie-issue.md npm-package/assets/archie-issue.md
cp .claude/commands/archie-work.md npm-package/assets/archie-work.md
cp .archie/prompts/skill_archie_studio_setup.md npm-package/assets/skill_archie_studio_setup.md
cp .archie/prompts/skill_archie_studio_issue.md npm-package/assets/skill_archie_studio_issue.md
cp .archie/prompts/skill_archie_studio_work.md npm-package/assets/skill_archie_studio_work.md
```

(Match the actual asset naming/paths discovered in Step 1 — adjust destinations if prompts/commands live in subfolders under `assets/`.)

- [ ] **Step 3: Register the new files in `archie.mjs`**

Add `studio.py` to the scripts list, the three `archie-*.md` to the commands list, and the three `skill_archie_studio_*.md` to the prompts list — following the exact pattern from Step 1. Show the edited arrays before saving.

- [ ] **Step 4: Run the sync checker**

Run: `python3 scripts/verify_sync.py`
Expected: PASS — no missing copies, no orphan assets, no dead installer references. Fix any reported discrepancy.

- [ ] **Step 5: Commit**

```bash
git add npm-package/
git commit -m "chore(studio): sync studio assets + installer references"
```

---

## Task 13: Full verification + manual dry run

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: all green (existing tests unaffected, studio suite passing).

- [ ] **Step 2: Manual dry run in a throwaway dir**

```bash
TMP=$(mktemp -d)
python3 archie/standalone/studio.py init "$TMP"
python3 archie/standalone/studio.py new "$TMP" --title "Demo ticket" --type feature --label backend
python3 archie/standalone/studio.py move "$TMP" ISS-001 in-progress
python3 archie/standalone/studio.py next "$TMP"
cat "$TMP/.archie/issues/INDEX.md"
cat "$TMP/AGENTS.md"
```
Expected: ISS-001 created, moved to in-progress, `next` reports `"action": "continue"`,
INDEX.md shows it in the Active table, AGENTS.md has exactly one studio pointer block.

- [ ] **Step 3: Re-run `init` to confirm idempotency**

```bash
python3 archie/standalone/studio.py init "$TMP"
grep -c "ARCHIE:STUDIO:START" "$TMP/AGENTS.md"   # expect 1
ls "$TMP/.archie/issues/in-progress/"             # ISS-001 still present
rm -rf "$TMP"
```
Expected: count is 1, ISS-001 still present.

- [ ] **Step 4: Final sync check**

Run: `python3 scripts/verify_sync.py`
Expected: PASS.

- [ ] **Step 5: Commit (if any fixups were needed)**

```bash
git add -A
git commit -m "test(studio): verification pass" || echo "nothing to commit"
```

---

## Self-Review Notes

- **Spec coverage:** init/new/move/index/next (Tasks 4,6,7,9,8) ✓; INDEX derived (Task 3) ✓; AGENTS.md lean pointer + WORKFLOW.md (Tasks 5,4) ✓; loop prompt with blueprint/hook integration (Task 10) ✓; command family (Task 11) ✓; ID allocation across folders (Task 2) ✓; edge cases — corrupt skip (Task 2), unknown status reject (Task 7), idempotent init (Tasks 4,5), blocked surface (Task 8), no-blueprint warning (Task 10 prompt) ✓; tests (every code task) ✓; sync (Task 12) ✓.
- **Deferred from spec (acceptable):** EPIC-NNN allocation and the `epics/` table are scaffolded (folder created, next-epic counter present) but epic *management* commands are out of MVP scope — tickets reference epics via frontmatter only. `validate.py`/`drift.py`/`arch_review.py` integration is invoked from the loop prompt, not new code.
- **Type consistency:** `cmd_new(title, type_, labels, today)`, `cmd_move(root, tid, status)`, `cmd_next(root)->dict{action,id,...}`, `iter_tickets`, `next_id(tickets, prefix)`, `render_index(tickets)`, `write_index`, `issues_dir` — names consistent across all tasks and tests.
- **Note for implementer:** `render_index` uses `next_id(tickets, "EPIC")` which returns `EPIC-001` when no epics exist (no ISS ticket matches the EPIC pattern) — this is intended.
```


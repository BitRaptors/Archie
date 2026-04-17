# LLM Wiki — Plan 1: Core Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate `.archie/wiki/**` from `blueprint.json` at the end of `/archie-deep-scan`, covering Decisions, Components, Patterns, Pitfalls, and an index. No capabilities yet (Plan 2), no incremental updates (Plan 3), no viewer UI (Plan 4). Ship a usable wiki generator behind the `ARCHIE_WIKI_ENABLED` feature flag.

**Architecture:** Two-pass pipeline. Pass 1: `wiki_builder.py` reads `blueprint.json`, emits one markdown file per entity under `.archie/wiki/{decisions,components,patterns,pitfalls}/<slug>.md` plus `index.md`. Pass 2: `wiki_index.py` parses the emitted pages, builds `_meta/backlinks.json` and `_meta/provenance.json`, then re-opens each page and appends a `## Referenced by` section driven by the backlinks. Zero-dep Python stdlib only. Follows Archie's `_common.py` + `sys.path.insert` convention so modules run both as `archie/standalone/*.py` in the dev repo and as `.archie/*.py` copied into consumer projects.

**Tech Stack:** Python 3.9+ stdlib, pytest, Archie's existing `_common.py`, renderer.py, `.claude/commands/archie-deep-scan.md`, `npm-package/assets/` sync, `scripts/verify_sync.py`.

**Reference spec:** `docs/superpowers/specs/2026-04-17-llm-wiki-design.md`

---

## File structure (this plan)

**New files:**
- `archie/standalone/wiki_builder.py` — blueprint → markdown pages
- `archie/standalone/wiki_index.py` — backlinks + provenance, "Referenced by" injection
- `tests/test_wiki_builder.py` — unit tests for page rendering
- `tests/test_wiki_index.py` — unit tests for backlinks + provenance
- `tests/fixtures/wiki_fixture_blueprint.json` — minimal cross-linked blueprint
- `tests/test_wiki_integration.py` — end-to-end: fixture blueprint → full wiki dir
- `npm-package/assets/wiki_builder.py` — sync copy
- `npm-package/assets/wiki_index.py` — sync copy

**Modified files:**
- `archie/standalone/renderer.py` — inject CLAUDE.md pointer + AGENTS.md usage section (flag-gated)
- `.claude/commands/archie-deep-scan.md` — new bash step after Intent Layer
- `npm-package/archie.mjs` — if it auto-discovers from assets/ nothing to do; otherwise register new scripts
- `scripts/verify_sync.py` — inspect only; may not need edits if it auto-lists

**Out of scope (Plans 2-4):**
- Capabilities agent, `capabilities/*.md` page type
- Incremental scan (`wiki_builder --incremental`), SHA256 diff
- Lint (orphans, broken links, stale evidence, contradictions)
- Viewer `/wiki/*` route, `--with-wiki-ui` flag

---

## Task 1: Test fixture blueprint

**Files:**
- Create: `tests/fixtures/wiki_fixture_blueprint.json`

- [ ] **Step 1: Write the fixture**

Create `tests/fixtures/wiki_fixture_blueprint.json`:

```json
{
  "meta": {
    "project_name": "TestProject",
    "version": "0.1.0"
  },
  "decisions": {
    "architectural_style": {
      "chosen": "Layered MVC with repository pattern",
      "rationale": "Separation of concerns"
    },
    "key_decisions": [
      {
        "title": "PostgreSQL as primary store",
        "chosen": "PostgreSQL 15",
        "rationale": "ACID guarantees for user data",
        "forced_by": "Compliance requirements for financial data",
        "enables": "Point-in-time recovery, logical replication",
        "alternatives_rejected": ["MongoDB (no ACID)", "SQLite (no concurrent writers)"]
      },
      {
        "title": "JWT over sessions",
        "chosen": "Stateless JWT",
        "rationale": "Horizontal scalability",
        "forced_by": "Multi-region deployment target",
        "enables": "Edge authentication",
        "alternatives_rejected": ["Redis-backed sessions"]
      }
    ],
    "trade_offs": [
      {
        "accepted_cost": "Token revocation is harder with stateless JWT",
        "gained_benefit": "Stateless services scale horizontally"
      }
    ],
    "out_of_scope": ["OAuth social login"]
  },
  "components": [
    {
      "name": "UserService",
      "purpose": "User authentication and lifecycle management",
      "depends_on": ["UserRepository"],
      "exposes_to": ["AuthController"]
    },
    {
      "name": "UserRepository",
      "purpose": "User data access layer",
      "depends_on": [],
      "exposes_to": ["UserService"]
    },
    {
      "name": "AuthController",
      "purpose": "HTTP auth endpoints",
      "depends_on": ["UserService"],
      "exposes_to": []
    }
  ],
  "communication": {
    "patterns": [
      {
        "name": "Repository",
        "when_to_use": "When abstracting a data source behind a contract",
        "when_not_to_use": "For trivial single-table CRUD without future flexibility needs"
      }
    ]
  },
  "pitfalls": [
    {
      "area": "Password storage",
      "description": "Storing plain-text passwords in UserRepository",
      "stems_from": "PostgreSQL as primary store",
      "recommendation": "Hash with bcrypt before persisting"
    }
  ],
  "implementation_guidelines": [],
  "development_rules": []
}
```

- [ ] **Step 2: Commit**

```bash
git add tests/fixtures/wiki_fixture_blueprint.json
git commit -m "test(wiki): add fixture blueprint for wiki builder tests"
```

---

## Task 2: Slug utility + skeleton module

**Files:**
- Create: `archie/standalone/wiki_builder.py`
- Create: `tests/test_wiki_builder.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_wiki_builder.py`:

```python
"""Tests for wiki_builder.py — deterministic blueprint → markdown generator."""

import sys
from pathlib import Path

# Make archie/standalone importable — mirrors how consumer projects use .archie/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))

import wiki_builder  # noqa: E402


def test_slugify_basic():
    assert wiki_builder.slugify("User Service") == "user-service"
    assert wiki_builder.slugify("PostgreSQL as primary store") == "postgresql-as-primary-store"
    assert wiki_builder.slugify("JWT over sessions") == "jwt-over-sessions"


def test_slugify_collision_suffix():
    seen: set[str] = set()
    a = wiki_builder.slugify_unique("User", seen)
    b = wiki_builder.slugify_unique("User", seen)
    c = wiki_builder.slugify_unique("User", seen)
    assert a == "user"
    assert b == "user-2"
    assert c == "user-3"


def test_slugify_strips_non_alnum():
    assert wiki_builder.slugify("Auth/Flow: v2!") == "auth-flow-v2"
    assert wiki_builder.slugify("   spaced   out   ") == "spaced-out"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_wiki_builder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'wiki_builder'`

- [ ] **Step 3: Create the skeleton module**

Create `archie/standalone/wiki_builder.py`:

```python
"""Archie standalone wiki builder — generates .archie/wiki/** from blueprint.

Zero dependencies beyond Python 3.9+ stdlib. Designed to run both as
archie/standalone/wiki_builder.py in the dev repo and as .archie/wiki_builder.py
copied into consumer projects.

Pipeline:
  Pass 1: blueprint.json -> page markdown under .archie/wiki/{type}/<slug>.md + index.md
  Pass 2: wiki_index.py walks the pages, builds _meta/backlinks.json and
          _meta/provenance.json, then appends "## Referenced by" to each page.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Lowercase, alphanumerics-and-hyphens only, no leading/trailing hyphens."""
    slug = _SLUG_RE.sub("-", name.lower()).strip("-")
    return slug or "untitled"


def slugify_unique(name: str, seen: set[str]) -> str:
    """Return a slug that is not in `seen`. Adds numeric suffix on collision.

    Mutates `seen` by adding the returned slug. Call with a shared set per page
    type so collisions are namespaced (components are independent from pitfalls).
    """
    base = slugify(name)
    candidate = base
    n = 2
    while candidate in seen:
        candidate = f"{base}-{n}"
        n += 1
    seen.add(candidate)
    return candidate
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_wiki_builder.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/wiki_builder.py tests/test_wiki_builder.py
git commit -m "feat(wiki): add slugify utilities in wiki_builder"
```

---

## Task 3: Render decision page

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_builder.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_wiki_builder.py`:

```python
def test_render_decision_page_basic():
    decision = {
        "title": "PostgreSQL as primary store",
        "chosen": "PostgreSQL 15",
        "rationale": "ACID guarantees for user data",
        "forced_by": "Compliance requirements",
        "enables": "Point-in-time recovery",
        "alternatives_rejected": ["MongoDB (no ACID)"],
    }
    md = wiki_builder.render_decision(decision, slug="postgresql-as-primary-store")
    assert md.startswith("---\n")
    assert "type: decision" in md
    assert "slug: postgresql-as-primary-store" in md
    assert "# PostgreSQL as primary store" in md
    assert "**Chosen:** PostgreSQL 15" in md
    assert "Compliance requirements" in md
    assert "MongoDB (no ACID)" in md


def test_render_decision_page_missing_optional_fields():
    decision = {
        "title": "Minimal decision",
        "chosen": "Option A",
    }
    md = wiki_builder.render_decision(decision, slug="minimal-decision")
    # Missing fields render as "N/A" or are omitted, but rendering must not crash
    assert "# Minimal decision" in md
    assert "**Chosen:** Option A" in md
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_wiki_builder.py -v -k decision`
Expected: FAIL with `AttributeError: module 'wiki_builder' has no attribute 'render_decision'`.

- [ ] **Step 3: Implement `render_decision`**

Append to `archie/standalone/wiki_builder.py`:

```python
def _frontmatter(**kv: str) -> str:
    """Render a YAML frontmatter block. Values must be strings (we do not escape)."""
    lines = ["---"]
    for key, value in kv.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _section(heading: str, body: str) -> str:
    """Render a section if body is non-empty, else empty string."""
    body = body.strip()
    if not body:
        return ""
    return f"\n## {heading}\n\n{body}\n"


def _list_lines(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items if item)


def render_decision(decision: dict, slug: str) -> str:
    """Render a single decision as markdown with frontmatter.

    Expects a decision dict from blueprint.decisions.key_decisions[]. Missing
    optional fields are rendered as "_(not specified)_" or the section is omitted.
    """
    title = decision.get("title", "Untitled decision")
    chosen = decision.get("chosen", "_(not specified)_")
    rationale = decision.get("rationale", "").strip()
    forced_by = decision.get("forced_by", "").strip()
    enables = decision.get("enables", "").strip()
    alternatives = decision.get("alternatives_rejected", []) or []

    parts = [
        _frontmatter(type="decision", slug=slug, provenance="EXTRACTED"),
        f"\n# {title}\n",
        f"\n**Chosen:** {chosen}\n",
    ]
    if rationale:
        parts.append(f"\n**Rationale:** {rationale}\n")
    parts.append(_section("Forced by", forced_by))
    parts.append(_section("Enables", enables))
    if alternatives:
        parts.append(_section("Alternatives rejected", _list_lines(alternatives)))
    # Referenced-by is appended by wiki_index.py in Pass 2.
    return "".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_wiki_builder.py -v -k decision`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/wiki_builder.py tests/test_wiki_builder.py
git commit -m "feat(wiki): render decision pages with frontmatter"
```

---

## Task 4: Render component page with resolvable links

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_builder.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_wiki_builder.py`:

```python
def test_render_component_page_links_depends_on():
    component = {
        "name": "UserService",
        "purpose": "User auth and lifecycle",
        "depends_on": ["UserRepository"],
        "exposes_to": ["AuthController"],
    }
    component_slugs = {"UserService": "user-service", "UserRepository": "user-repository", "AuthController": "auth-controller"}
    md = wiki_builder.render_component(component, slug="user-service", component_slugs=component_slugs)
    assert "# UserService" in md
    assert "[UserRepository](../components/user-repository.md)" in md
    assert "[AuthController](../components/auth-controller.md)" in md
    assert "User auth and lifecycle" in md


def test_render_component_page_handles_unknown_reference():
    component = {
        "name": "OrphanService",
        "purpose": "Depends on something not in the blueprint",
        "depends_on": ["ExternalThing"],
    }
    component_slugs = {"OrphanService": "orphan-service"}
    md = wiki_builder.render_component(component, slug="orphan-service", component_slugs=component_slugs)
    # Unknown references render as plain text, not broken links
    assert "ExternalThing" in md
    assert "[ExternalThing]" not in md
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_wiki_builder.py -v -k component`
Expected: FAIL — `render_component` does not exist.

- [ ] **Step 3: Implement `render_component`**

Append to `archie/standalone/wiki_builder.py`:

```python
def _link_or_text(name: str, slugs: dict[str, str], dir_name: str) -> str:
    """Return '[Name](../dir/slug.md)' if name is known, else 'Name' plain."""
    slug = slugs.get(name)
    if slug:
        return f"[{name}](../{dir_name}/{slug}.md)"
    return name


def render_component(component: dict, slug: str, component_slugs: dict[str, str]) -> str:
    name = component.get("name", "Untitled component")
    purpose = component.get("purpose", "").strip()
    depends_on = component.get("depends_on", []) or []
    exposes_to = component.get("exposes_to", []) or []

    dep_links = [_link_or_text(n, component_slugs, "components") for n in depends_on]
    exp_links = [_link_or_text(n, component_slugs, "components") for n in exposes_to]

    parts = [
        _frontmatter(type="component", slug=slug, provenance="EXTRACTED"),
        f"\n# {name}\n",
    ]
    if purpose:
        parts.append(f"\n**Purpose:** {purpose}\n")
    if dep_links:
        parts.append(_section("Depends on", _list_lines(dep_links)))
    if exp_links:
        parts.append(_section("Exposes to", _list_lines(exp_links)))
    return "".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_wiki_builder.py -v -k component`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/wiki_builder.py tests/test_wiki_builder.py
git commit -m "feat(wiki): render component pages with resolvable depends_on links"
```

---

## Task 5: Render pattern and pitfall pages

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_builder.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_wiki_builder.py`:

```python
def test_render_pattern_page():
    pattern = {
        "name": "Repository",
        "when_to_use": "When abstracting data access",
        "when_not_to_use": "For trivial CRUD",
    }
    md = wiki_builder.render_pattern(pattern, slug="repository")
    assert "# Repository" in md
    assert "type: pattern" in md
    assert "When abstracting data access" in md
    assert "For trivial CRUD" in md


def test_render_pitfall_page_with_stems_from_link():
    pitfall = {
        "area": "Password storage",
        "description": "Plain text passwords",
        "stems_from": "PostgreSQL as primary store",
        "recommendation": "Hash with bcrypt",
    }
    decision_slugs = {"PostgreSQL as primary store": "postgresql-as-primary-store"}
    md = wiki_builder.render_pitfall(
        pitfall, slug="password-storage", decision_slugs=decision_slugs
    )
    assert "# Password storage" in md
    assert "Plain text passwords" in md
    assert "[PostgreSQL as primary store](../decisions/postgresql-as-primary-store.md)" in md
    assert "Hash with bcrypt" in md


def test_render_pitfall_page_with_unknown_stems_from():
    pitfall = {"area": "Foo", "description": "Bar", "stems_from": "UnknownDecision", "recommendation": "Fix"}
    md = wiki_builder.render_pitfall(pitfall, slug="foo", decision_slugs={})
    # Unknown stems_from still renders the prose
    assert "UnknownDecision" in md
    assert "[UnknownDecision]" not in md
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_wiki_builder.py -v -k "pattern or pitfall"`
Expected: FAIL — `render_pattern` and `render_pitfall` missing.

- [ ] **Step 3: Implement both renderers**

Append to `archie/standalone/wiki_builder.py`:

```python
def render_pattern(pattern: dict, slug: str) -> str:
    name = pattern.get("name", "Untitled pattern")
    when_to_use = pattern.get("when_to_use", "").strip()
    when_not = pattern.get("when_not_to_use", "").strip()

    parts = [
        _frontmatter(type="pattern", slug=slug, provenance="EXTRACTED"),
        f"\n# {name}\n",
    ]
    parts.append(_section("When to use", when_to_use))
    parts.append(_section("When NOT to use", when_not))
    return "".join(parts)


def render_pitfall(pitfall: dict, slug: str, decision_slugs: dict[str, str]) -> str:
    area = pitfall.get("area", "Untitled pitfall")
    description = pitfall.get("description", "").strip()
    stems_from = pitfall.get("stems_from", "").strip()
    recommendation = pitfall.get("recommendation", "").strip()

    parts = [
        _frontmatter(type="pitfall", slug=slug, provenance="EXTRACTED"),
        f"\n# {area}\n",
    ]
    if description:
        parts.append(f"\n**Description:** {description}\n")
    if stems_from:
        linked = _link_or_text(stems_from, decision_slugs, "decisions")
        parts.append(f"\n**Stems from:** {linked}\n")
    if recommendation:
        parts.append(f"\n**Recommendation:** {recommendation}\n")
    return "".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_wiki_builder.py -v`
Expected: all decision/component/pattern/pitfall tests pass.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/wiki_builder.py tests/test_wiki_builder.py
git commit -m "feat(wiki): render pattern and pitfall pages"
```

---

## Task 6: Render index.md

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_builder.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_wiki_builder.py`:

```python
import json


def test_render_index():
    fixture = Path(__file__).parent / "fixtures" / "wiki_fixture_blueprint.json"
    blueprint = json.loads(fixture.read_text())
    slug_map = {
        "decisions": {
            "PostgreSQL as primary store": "postgresql-as-primary-store",
            "JWT over sessions": "jwt-over-sessions",
        },
        "components": {
            "UserService": "user-service",
            "UserRepository": "user-repository",
            "AuthController": "auth-controller",
        },
        "patterns": {"Repository": "repository"},
        "pitfalls": {"Password storage": "password-storage"},
    }
    md = wiki_builder.render_index(blueprint, slug_map)
    assert "# TestProject Wiki" in md
    assert "## Browse by type" in md
    assert "Decisions (2)" in md
    assert "Components (3)" in md
    assert "Patterns (1)" in md
    assert "Pitfalls (1)" in md
    # At least one link into a sub-page
    assert "[PostgreSQL as primary store](./decisions/postgresql-as-primary-store.md)" in md
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_wiki_builder.py::test_render_index -v`
Expected: FAIL — `render_index` missing.

- [ ] **Step 3: Implement `render_index`**

Append to `archie/standalone/wiki_builder.py`:

```python
def render_index(blueprint: dict, slug_map: dict[str, dict[str, str]]) -> str:
    project_name = blueprint.get("meta", {}).get("project_name", "Project")
    decisions = slug_map.get("decisions", {})
    components = slug_map.get("components", {})
    patterns = slug_map.get("patterns", {})
    pitfalls = slug_map.get("pitfalls", {})

    def _list(name_to_slug: dict[str, str], subdir: str) -> str:
        return "\n".join(
            f"- [{name}](./{subdir}/{slug}.md)" for name, slug in sorted(name_to_slug.items())
        )

    parts = [f"# {project_name} Wiki\n"]
    parts.append(
        "\n> Generated by Archie. Start here before implementing anything — follow\n"
        "> links to understand decisions, components, and pitfalls that affect your work.\n"
    )
    parts.append(
        "\n## Browse by type\n\n"
        f"- **Decisions ({len(decisions)})** — why the architecture is the way it is\n"
        f"- **Components ({len(components)})** — the parts of the system and how they connect\n"
        f"- **Patterns ({len(patterns)})** — reusable design choices\n"
        f"- **Pitfalls ({len(pitfalls)})** — known traps and how to avoid them\n"
    )
    if decisions:
        parts.append("\n## Decisions\n\n" + _list(decisions, "decisions") + "\n")
    if components:
        parts.append("\n## Components\n\n" + _list(components, "components") + "\n")
    if patterns:
        parts.append("\n## Patterns\n\n" + _list(patterns, "patterns") + "\n")
    if pitfalls:
        parts.append("\n## Pitfalls\n\n" + _list(pitfalls, "pitfalls") + "\n")
    return "".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_wiki_builder.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/wiki_builder.py tests/test_wiki_builder.py
git commit -m "feat(wiki): render index.md with per-type page listings"
```

---

## Task 7: wiki_builder CLI — orchestrate Pass 1

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Create: `tests/test_wiki_integration.py`

- [ ] **Step 1: Write the failing integration test**

Create `tests/test_wiki_integration.py`:

```python
"""End-to-end tests for the wiki build pipeline."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
FIXTURE = Path(__file__).parent / "fixtures" / "wiki_fixture_blueprint.json"


def _setup_project(tmp_path: Path) -> Path:
    """Create a temp project with .archie/blueprint.json from the fixture."""
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    shutil.copy(FIXTURE, archie_dir / "blueprint.json")
    return tmp_path


def test_wiki_builder_cli_produces_expected_pages(tmp_path):
    project = _setup_project(tmp_path)
    result = subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr

    wiki = project / ".archie" / "wiki"
    assert (wiki / "index.md").exists()
    assert (wiki / "decisions" / "postgresql-as-primary-store.md").exists()
    assert (wiki / "decisions" / "jwt-over-sessions.md").exists()
    assert (wiki / "components" / "user-service.md").exists()
    assert (wiki / "components" / "user-repository.md").exists()
    assert (wiki / "components" / "auth-controller.md").exists()
    assert (wiki / "patterns" / "repository.md").exists()
    assert (wiki / "pitfalls" / "password-storage.md").exists()


def test_wiki_builder_forward_links_resolve(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    wiki = project / ".archie" / "wiki"
    us = (wiki / "components" / "user-service.md").read_text()
    assert "[UserRepository](../components/user-repository.md)" in us
    pitfall = (wiki / "pitfalls" / "password-storage.md").read_text()
    assert "[PostgreSQL as primary store](../decisions/postgresql-as-primary-store.md)" in pitfall
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_wiki_integration.py -v`
Expected: FAIL — no CLI entry yet.

- [ ] **Step 3: Implement the CLI orchestrator**

Append to `archie/standalone/wiki_builder.py`:

```python
import json
import argparse


def _build_slug_map(blueprint: dict) -> dict[str, dict[str, str]]:
    """Return {type: {name: slug}} where each type has its own slug namespace."""
    decisions = blueprint.get("decisions", {}).get("key_decisions", []) or []
    components = blueprint.get("components", []) or []
    patterns = blueprint.get("communication", {}).get("patterns", []) or []
    pitfalls = blueprint.get("pitfalls", []) or []

    def _map(items: list[dict], key: str) -> dict[str, str]:
        seen: set[str] = set()
        out: dict[str, str] = {}
        for item in items:
            name = item.get(key)
            if not name:
                continue
            out[name] = slugify_unique(name, seen)
        return out

    return {
        "decisions": _map(decisions, "title"),
        "components": _map(components, "name"),
        "patterns": _map(patterns, "name"),
        "pitfalls": _map(pitfalls, "area"),
    }


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_wiki(project_root: Path) -> None:
    """Pass 1: read blueprint.json, emit all pages + index.md under .archie/wiki/."""
    blueprint_path = project_root / ".archie" / "blueprint.json"
    if not blueprint_path.exists():
        raise FileNotFoundError(f"blueprint.json not found at {blueprint_path}")
    blueprint = json.loads(blueprint_path.read_text(encoding="utf-8"))

    wiki_root = project_root / ".archie" / "wiki"
    # Full rebuild — Plan 1 has no incremental update.
    if wiki_root.exists():
        import shutil as _sh
        _sh.rmtree(wiki_root)
    wiki_root.mkdir(parents=True)

    slug_map = _build_slug_map(blueprint)

    for decision in blueprint.get("decisions", {}).get("key_decisions", []) or []:
        slug = slug_map["decisions"].get(decision.get("title"))
        if not slug:
            continue
        _write(wiki_root / "decisions" / f"{slug}.md", render_decision(decision, slug))

    for component in blueprint.get("components", []) or []:
        slug = slug_map["components"].get(component.get("name"))
        if not slug:
            continue
        _write(
            wiki_root / "components" / f"{slug}.md",
            render_component(component, slug, slug_map["components"]),
        )

    for pattern in blueprint.get("communication", {}).get("patterns", []) or []:
        slug = slug_map["patterns"].get(pattern.get("name"))
        if not slug:
            continue
        _write(wiki_root / "patterns" / f"{slug}.md", render_pattern(pattern, slug))

    for pitfall in blueprint.get("pitfalls", []) or []:
        slug = slug_map["pitfalls"].get(pitfall.get("area"))
        if not slug:
            continue
        _write(
            wiki_root / "pitfalls" / f"{slug}.md",
            render_pitfall(pitfall, slug, slug_map["decisions"]),
        )

    _write(wiki_root / "index.md", render_index(blueprint, slug_map))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archie LLM Wiki builder (Pass 1).")
    parser.add_argument("project_root", help="Path to project with .archie/blueprint.json")
    args = parser.parse_args(argv)
    build_wiki(Path(args.project_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_wiki_integration.py -v`
Expected: both integration tests pass. Also re-run unit tests: `python -m pytest tests/test_wiki_builder.py -v` — all green.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/wiki_builder.py tests/test_wiki_integration.py
git commit -m "feat(wiki): add wiki_builder CLI orchestrating Pass 1"
```

---

## Task 8: wiki_index.py — backlinks extraction

**Files:**
- Create: `archie/standalone/wiki_index.py`
- Create: `tests/test_wiki_index.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_wiki_index.py`:

```python
"""Tests for wiki_index.py — backlinks and provenance."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))

import wiki_index  # noqa: E402


def test_extract_links_from_page(tmp_path):
    page = tmp_path / "a.md"
    page.write_text(
        "# Title\n"
        "See [B](../components/b.md) and [C](../decisions/c.md).\n"
        "Also [broken]() and [external](https://example.com).\n"
    )
    links = wiki_index.extract_links(page)
    # Only relative links with .md targets are collected. External and empty ignored.
    assert sorted(links) == [("../components/b.md", "B"), ("../decisions/c.md", "C")]


def test_build_backlinks(tmp_path):
    wiki = tmp_path / "wiki"
    (wiki / "components").mkdir(parents=True)
    (wiki / "decisions").mkdir(parents=True)
    (wiki / "components" / "a.md").write_text("# A\n[B](../components/b.md)\n")
    (wiki / "components" / "b.md").write_text("# B\n")
    (wiki / "decisions" / "d.md").write_text("# D\n[A](../components/a.md)\n")

    backlinks = wiki_index.build_backlinks(wiki)
    # B is referenced by A
    assert backlinks["components/b.md"] == [
        {"path": "components/a.md", "title": "A", "type": "component"}
    ]
    # A is referenced by D
    assert backlinks["components/a.md"] == [
        {"path": "decisions/d.md", "title": "D", "type": "decision"}
    ]
    # D has no inbound links
    assert "decisions/d.md" not in backlinks or backlinks["decisions/d.md"] == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_wiki_index.py -v`
Expected: FAIL — `wiki_index` missing.

- [ ] **Step 3: Create `wiki_index.py` with link extraction and backlink build**

Create `archie/standalone/wiki_index.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_wiki_index.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/wiki_index.py tests/test_wiki_index.py
git commit -m "feat(wiki): add wiki_index with link extraction and backlink build"
```

---

## Task 9: Inject "Referenced by" section + provenance

**Files:**
- Modify: `archie/standalone/wiki_index.py`
- Modify: `tests/test_wiki_index.py`
- Modify: `archie/standalone/wiki_builder.py` (call Pass 2 from CLI)
- Modify: `tests/test_wiki_integration.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_wiki_index.py`:

```python
def test_inject_referenced_by(tmp_path):
    wiki = tmp_path / "wiki"
    (wiki / "components").mkdir(parents=True)
    page = wiki / "components" / "b.md"
    page.write_text("# B\n\nSome content.\n")
    backlinks = {
        "components/b.md": [
            {"path": "components/a.md", "title": "A", "type": "component"},
            {"path": "decisions/d.md", "title": "D", "type": "decision"},
        ]
    }
    wiki_index.inject_referenced_by(wiki, backlinks)
    content = page.read_text()
    assert "## Referenced by" in content
    assert "[A](../components/a.md) (component)" in content
    assert "[D](../decisions/d.md) (decision)" in content


def test_inject_referenced_by_idempotent(tmp_path):
    wiki = tmp_path / "wiki"
    (wiki / "components").mkdir(parents=True)
    page = wiki / "components" / "b.md"
    page.write_text("# B\n")
    backlinks = {"components/b.md": [{"path": "components/a.md", "title": "A", "type": "component"}]}
    wiki_index.inject_referenced_by(wiki, backlinks)
    first = page.read_text()
    # Running again with the same backlinks must produce the identical file.
    wiki_index.inject_referenced_by(wiki, backlinks)
    assert page.read_text() == first


def test_write_provenance(tmp_path):
    wiki = tmp_path / "wiki"
    (wiki / "components").mkdir(parents=True)
    (wiki / "components" / "a.md").write_text("# A\n")
    wiki_index.write_provenance(wiki, last_refreshed="2026-04-17")
    prov = json.loads((wiki / "_meta" / "provenance.json").read_text())
    assert "components/a.md" in prov
    assert "sha256" in prov["components/a.md"]
    assert prov["components/a.md"]["last_refreshed"] == "2026-04-17"
    assert prov["components/a.md"]["source"] == "wiki_builder"
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_wiki_index.py -v -k "referenced_by or provenance"`
Expected: FAIL on all three.

- [ ] **Step 3: Implement injection + provenance**

Append to `archie/standalone/wiki_index.py`:

```python
_REFERENCED_BY_MARKER = "<!-- archie:referenced-by -->"


def _relative_link(src_page: str, target_path: str) -> str:
    """Produce '../decisions/x.md' from two wiki-root-relative posix paths."""
    src = Path(src_page).parent
    target = Path(target_path)
    # Compute path from src to target using Path walk.
    parts_src = src.parts
    parts_tgt = target.parts
    i = 0
    while i < len(parts_src) and i < len(parts_tgt) and parts_src[i] == parts_tgt[i]:
        i += 1
    up = [".."] * (len(parts_src) - i)
    down = list(parts_tgt[i:])
    if not up and not down:
        return target.name
    return "/".join(up + down) if up else "/".join(down)


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
```

- [ ] **Step 4: Wire Pass 2 into the CLI**

Edit `archie/standalone/wiki_builder.py`. Replace the bottom of the file (the `build_wiki` function's final return and `main`) so `build_wiki` also runs Pass 2.

Old:
```python
    _write(wiki_root / "index.md", render_index(blueprint, slug_map))
```

New (insert after the existing line):
```python
    _write(wiki_root / "index.md", render_index(blueprint, slug_map))

    # Pass 2: backlinks + referenced-by + provenance.
    import wiki_index
    from datetime import date
    backlinks = wiki_index.build_backlinks(wiki_root)
    wiki_index.write_backlinks(wiki_root, backlinks)
    wiki_index.inject_referenced_by(wiki_root, backlinks)
    wiki_index.write_provenance(wiki_root, last_refreshed=date.today().isoformat())
```

Append to `tests/test_wiki_integration.py`:

```python
def test_wiki_builder_emits_backlinks_and_provenance(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    wiki = project / ".archie" / "wiki"
    backlinks = json.loads((wiki / "_meta" / "backlinks.json").read_text())
    # UserRepository is referenced by UserService (depends_on).
    assert any(
        ref["path"] == "components/user-service.md"
        for ref in backlinks.get("components/user-repository.md", [])
    )
    # Referenced by is appended to user-repository.
    ur = (wiki / "components" / "user-repository.md").read_text()
    assert "## Referenced by" in ur
    assert "[UserService](../components/user-service.md)" in ur
    # Provenance has SHA256 for all pages.
    prov = json.loads((wiki / "_meta" / "provenance.json").read_text())
    assert "index.md" in prov
    assert len(prov["index.md"]["sha256"]) == 64


def test_wiki_builder_is_idempotent(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    first = (project / ".archie" / "wiki" / "components" / "user-repository.md").read_text()
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    second = (project / ".archie" / "wiki" / "components" / "user-repository.md").read_text()
    assert first == second
```

- [ ] **Step 5: Run all tests**

Run: `python -m pytest tests/test_wiki_builder.py tests/test_wiki_index.py tests/test_wiki_integration.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add archie/standalone/wiki_builder.py archie/standalone/wiki_index.py tests/test_wiki_index.py tests/test_wiki_integration.py
git commit -m "feat(wiki): inject Referenced by, write backlinks.json + provenance.json"
```

---

## Task 10: Feature flag + renderer patches

**Files:**
- Modify: `archie/standalone/renderer.py`
- Create: `tests/test_renderer_wiki_patch.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_renderer_wiki_patch.py`:

```python
"""Tests for the CLAUDE.md and AGENTS.md wiki patches in renderer.py."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))

import renderer  # noqa: E402


def test_wiki_flag_default_on(monkeypatch):
    monkeypatch.delenv("ARCHIE_WIKI_ENABLED", raising=False)
    assert renderer.wiki_enabled() is True


def test_wiki_flag_off_when_env_false(monkeypatch):
    monkeypatch.setenv("ARCHIE_WIKI_ENABLED", "false")
    assert renderer.wiki_enabled() is False


def test_wiki_flag_off_when_env_zero(monkeypatch):
    monkeypatch.setenv("ARCHIE_WIKI_ENABLED", "0")
    assert renderer.wiki_enabled() is False


def test_claude_md_pointer_when_flag_on():
    patch = renderer.claude_md_wiki_pointer()
    assert "Before you implement anything" in patch
    assert ".archie/wiki/index.md" in patch


def test_agents_md_usage_section():
    section = renderer.agents_md_wiki_section()
    assert "Using the Archie Wiki" in section
    assert ".archie/wiki/" in section
    assert "Referenced by" in section  # mentions the backlinks mechanism
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_renderer_wiki_patch.py -v`
Expected: FAIL — new helpers missing.

- [ ] **Step 3: Implement the helpers + inject into the existing generators**

Read the current shape of `renderer.py` first so you insert the helpers in a consistent place:

```bash
python -m pytest --collect-only -q tests/test_renderer_wiki_patch.py  # sanity
```

In `archie/standalone/renderer.py`, near the top imports add:

```python
import os
```

Then add these helpers somewhere near the existing `generate_claude_md` / `generate_agents_md` (the explore showed them at lines 486 and 662 — put the helpers just above `generate_claude_md`):

```python
# --- LLM Wiki integration (Plan 1) ---

def wiki_enabled() -> bool:
    """Return False only when ARCHIE_WIKI_ENABLED is explicitly 'false' or '0'."""
    raw = os.environ.get("ARCHIE_WIKI_ENABLED", "true").strip().lower()
    return raw not in {"false", "0", "no", "off"}


def claude_md_wiki_pointer() -> str:
    return (
        "\n## Before you implement anything\n\n"
        "Open `.archie/wiki/index.md` and scan the browse-by-type lists. "
        "If your task matches an existing capability or component, open that page "
        "and follow its links to decisions and pitfalls before coding. "
        "Extending beats reimplementing.\n"
    )


def agents_md_wiki_section() -> str:
    return (
        "\n## Using the Archie Wiki\n\n"
        "The wiki at `.archie/wiki/` is the linked, browsable view of this app's\n"
        "architecture. Every page ends with a `## Referenced by` section showing\n"
        "what points to it.\n\n"
        "Before any implementation task:\n\n"
        "1. Read `.archie/wiki/index.md` — does an existing capability or component match?\n"
        "   - YES -> open that page. Its **Components**, **Decisions**, and **Pitfalls**\n"
        "     sections tell you what to reuse and what to avoid.\n"
        "   - NO  -> the work is genuinely new. Continue.\n\n"
        "2. If your change touches an existing component, open\n"
        "   `.archie/wiki/components/<name>.md` and read its **Referenced by** section —\n"
        "   every page listed there depends on this component. Breaking changes ripple.\n\n"
        "3. If you introduce a new capability, name it and list the evidence files in\n"
        "   your PR description. The next `/archie-scan` will pick it up.\n"
    )
```

Now append the patches to the existing generators. Find the `return "\n".join(lines)` (or equivalent) at the end of `generate_claude_md(bp)` and `generate_agents_md(bp)`.

For `generate_claude_md(bp)`, right before returning, add:

```python
    if wiki_enabled():
        lines.append(claude_md_wiki_pointer())
```

For `generate_agents_md(bp)`, right before returning, add:

```python
    if wiki_enabled():
        lines.append(agents_md_wiki_section())
```

(If the function builds a string via `"".join(parts)` rather than `lines.append`, adapt accordingly — append the patch string to the appropriate container and keep the existing joining logic.)

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_renderer_wiki_patch.py -v`
Expected: 5 passed.

Also re-run the existing renderer tests (if any) to confirm no regression:
Run: `python -m pytest tests/ -v -k renderer`
Expected: no failures.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/renderer.py tests/test_renderer_wiki_patch.py
git commit -m "feat(wiki): add ARCHIE_WIKI_ENABLED flag and renderer patches"
```

---

## Task 11: Gate wiki_builder on feature flag

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_integration.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_wiki_integration.py`:

```python
import os


def test_wiki_builder_skips_when_flag_off(tmp_path, monkeypatch):
    project = _setup_project(tmp_path)
    env = os.environ.copy()
    env["ARCHIE_WIKI_ENABLED"] = "false"
    result = subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        capture_output=True, text=True, check=False, env=env,
    )
    assert result.returncode == 0
    # Nothing should be written under .archie/wiki/
    assert not (project / ".archie" / "wiki").exists()
    assert "skipped" in result.stdout.lower() or "disabled" in result.stdout.lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_wiki_integration.py::test_wiki_builder_skips_when_flag_off -v`
Expected: FAIL.

- [ ] **Step 3: Gate the CLI**

Edit `archie/standalone/wiki_builder.py`. Replace the `main` function with:

```python
def _wiki_enabled() -> bool:
    raw = os.environ.get("ARCHIE_WIKI_ENABLED", "true").strip().lower()
    return raw not in {"false", "0", "no", "off"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archie LLM Wiki builder (Pass 1 + Pass 2).")
    parser.add_argument("project_root", help="Path to project with .archie/blueprint.json")
    args = parser.parse_args(argv)
    if not _wiki_enabled():
        print("Wiki generation disabled (ARCHIE_WIKI_ENABLED=false). Skipped.")
        return 0
    build_wiki(Path(args.project_root))
    print(f"Wiki built at {args.project_root}/.archie/wiki/")
    return 0
```

At the top of the file, add:

```python
import os
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_wiki_integration.py -v`
Expected: all pass (including the new skip test).

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/wiki_builder.py tests/test_wiki_integration.py
git commit -m "feat(wiki): gate wiki_builder on ARCHIE_WIKI_ENABLED flag"
```

---

## Task 12: Wire into `/archie-deep-scan`

**Files:**
- Modify: `.claude/commands/archie-deep-scan.md`

- [ ] **Step 1: Read the current structure**

Run: `python -c "print(open('.claude/commands/archie-deep-scan.md').read())" | head -200`

Locate the Intent Layer phase (currently the last substantive step before the scan report — search for "Intent Layer" or "intent_layer.py merge"). The wiki build belongs **after** Intent Layer (because per-folder CLAUDE.md-s are ready) and **before** the final scan report so the report can summarize wiki state.

- [ ] **Step 2: Insert the new step**

After the Intent Layer phase and before the final report phase, insert a new step (use the same phase-numbering convention already used in the file — if the last step is "Phase 4: Intent Layer" make this "Phase 4.5: Build wiki" or increment subsequent numbers). Example block to insert:

```markdown
### Phase 4.5: Build the LLM Wiki

Generate the browsable, linked wiki under `.archie/wiki/` from the finalized blueprint.

```bash
python3 .archie/wiki_builder.py "$PWD"
```

Expected output: `Wiki built at <project>/.archie/wiki/` or `Wiki generation disabled (ARCHIE_WIKI_ENABLED=false). Skipped.` Either is acceptable — do not fail the scan on wiki errors, but do surface any non-zero exit code in the scan report.

Check that these exist (report any that are missing in the scan report):

- `.archie/wiki/index.md`
- `.archie/wiki/_meta/backlinks.json`
- `.archie/wiki/_meta/provenance.json`
```

- [ ] **Step 3: Add a Wiki summary line to the scan report section**

Find the final "Phase N: Scan report" section. Add this bullet to the report template:

```markdown
- **Wiki:** `<N_pages> pages across <N_types> types` — see `.archie/wiki/index.md`. Provenance: `.archie/wiki/_meta/provenance.json`.
```

(If the command instructs the LLM to generate a structured report, add the Wiki line to the instruction set so it appears in the final markdown report.)

- [ ] **Step 4: Manually dry-run the deep-scan flow**

On this repo (or on a fixture project with an existing `.archie/blueprint.json`):

```bash
python3 archie/standalone/wiki_builder.py .
ls -la .archie/wiki/
cat .archie/wiki/index.md | head -40
```

Expected: the wiki directory is populated; `index.md` contains the browse-by-type lists.

- [ ] **Step 5: Commit**

```bash
git add .claude/commands/archie-deep-scan.md
git commit -m "feat(wiki): integrate wiki build into /archie-deep-scan"
```

---

## Task 13: NPM asset sync

**Files:**
- Create: `npm-package/assets/wiki_builder.py` (copy of canonical)
- Create: `npm-package/assets/wiki_index.py` (copy of canonical)
- Potentially modify: `npm-package/archie.mjs`
- Run: `scripts/verify_sync.py`

- [ ] **Step 1: Copy canonical files into npm-package assets**

```bash
cp archie/standalone/wiki_builder.py npm-package/assets/wiki_builder.py
cp archie/standalone/wiki_index.py npm-package/assets/wiki_index.py
```

- [ ] **Step 2: Inspect `npm-package/archie.mjs` to see whether new scripts need registration**

```bash
grep -n "standalone\|assets/.*\.py\|scripts" npm-package/archie.mjs | head -40
```

If the installer auto-copies every `.py` under `npm-package/assets/` to the target project's `.archie/`, nothing to do. If it has an explicit whitelist, add `wiki_builder.py` and `wiki_index.py` to it.

- [ ] **Step 3: Run the sync verifier**

```bash
python3 scripts/verify_sync.py
```

Expected: exit 0, no mismatches.

If the verifier complains, re-read its output and fix the delta (usually: missing entry in `archie.mjs` script list or a stale copy).

- [ ] **Step 4: Commit**

```bash
git add npm-package/
git commit -m "chore(wiki): sync wiki_builder + wiki_index to npm-package assets"
```

---

## Task 14: End-to-end verification on this repo

**Files:** none (verification step)

- [ ] **Step 1: Run the full wiki pipeline against the Archie repo's own blueprint**

```bash
# Only if .archie/blueprint.json exists on this repo. If not, skip this task
# and verify manually on a fixture consumer project.
python3 archie/standalone/wiki_builder.py .
```

Expected: `.archie/wiki/` populated; exit 0.

- [ ] **Step 2: Inspect output**

```bash
find .archie/wiki -name "*.md" | head -20
cat .archie/wiki/index.md | head -40
cat .archie/wiki/_meta/backlinks.json | head -20 | python3 -m json.tool
```

Manually verify:

1. Each `.md` page starts with frontmatter (`---\ntype: ...\nslug: ...`).
2. `## Referenced by` appears on pages that have inbound links (at least the depends_on / exposes_to / stems_from connections).
3. `backlinks.json` is valid JSON and symmetric with the inline backlinks.
4. `provenance.json` has a SHA256 per page.
5. Clicking a link in `index.md` (or opening the referenced file) resolves to an existing page.

- [ ] **Step 3: Run the full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all new tests pass, no regressions in existing tests.

- [ ] **Step 4: Add `.archie/wiki/` to the top-level `.gitignore` if it is not there yet**

```bash
grep -q "^\.archie/wiki/" .gitignore || echo ".archie/wiki/" >> .gitignore
```

(The Archie repo itself does not check in its own `.archie/` state; generated wiki content follows the same rule.)

- [ ] **Step 5: Commit any .gitignore change**

```bash
git add .gitignore 2>/dev/null
git diff --cached --quiet || git commit -m "chore(wiki): ignore generated .archie/wiki/"
```

(If there is nothing to commit, the second command is a no-op.)

---

## Self-review checklist (run after completing all tasks)

- [ ] Every spec section under "Plan 1 scope" has a corresponding task.
- [ ] No task contains "TODO", "implement later", or "similar to Task N".
- [ ] Method names are consistent across tasks (`render_decision`, `render_component`, `render_pattern`, `render_pitfall`, `render_index`, `build_wiki`, `extract_links`, `build_backlinks`, `inject_referenced_by`, `write_provenance`, `write_backlinks`, `wiki_enabled`, `claude_md_wiki_pointer`, `agents_md_wiki_section`).
- [ ] All tests pass: `python -m pytest tests/ -v`.
- [ ] `python3 scripts/verify_sync.py` exits 0.
- [ ] Manual smoke test on a fixture project or this repo confirms `.archie/wiki/index.md` is usable and links resolve.

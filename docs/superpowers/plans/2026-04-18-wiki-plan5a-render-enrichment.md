# LLM Wiki — Plan 5a: Render-Layer Enrichment

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand wiki_builder.py to render every agent-critical blueprint section that's currently ignored. Raise wiki coverage from ~25% to ~75-80% of the blueprint. Zero new AI calls, zero new Wave 1 agents — pure render-layer work.

**Architecture:** 8 new page types + 2 existing page type enrichments + index overhaul. `wiki_builder.py` grows with new `render_*` functions and new loops inside `build_wiki()`. `wiki_index.py` untouched — its backlinks and lint walk the whole `.archie/wiki/` tree, so new pages integrate automatically.

**Tech Stack:** Python 3.9+ stdlib, pytest. No new runtime dependencies.

**Depends on:** Plans 1-4 (already merged state of `feat/llm-wiki-design`).

**Reference spec:** `docs/superpowers/specs/2026-04-17-llm-wiki-design.md` (will be extended with new page type definitions as part of Task 14).

---

## File structure (this plan)

**New files:** none — all new pages are generated output, not source modules.

**Modified files:**
- `archie/standalone/wiki_builder.py` — ~8 new `render_*` functions + refactor of `render_component`, `render_pitfall`, `render_index`; `_build_slug_map` extension; `build_wiki` new loops
- `tests/fixtures/wiki_fixture_blueprint.json` — add `implementation_guidelines`, `architecture_rules`, `development_rules`, `technology`, `quick_reference`, `frontend`, `architecture_diagram` sections + enrich existing `components[*]` with `responsibility`/`location`/`key_interfaces`/`key_files` + enrich existing `pitfalls[*]` with `applies_to` + enrich existing `decisions.trade_offs`/`out_of_scope` + add `meta.executive_summary`/`architecture_style`/`platforms`
- `tests/test_wiki_builder.py` — ~15 new unit tests
- `tests/test_wiki_integration.py` — ~3 new e2e tests covering the new page types
- `npm-package/assets/wiki_builder.py` — sync
- `docs/superpowers/specs/2026-04-17-llm-wiki-design.md` — spec extension note (new page types documented)

---

## Task 1: Extend test fixture with all missing blueprint sections

**Goal:** The fixture must carry one meaningful example of every blueprint section the upcoming renders will consume. Downstream tests rely on this.

**Files:**
- Modify: `tests/fixtures/wiki_fixture_blueprint.json`

**Add to fixture:**

- `meta.executive_summary`: ~200-word summary sentence explaining the system
- `meta.architecture_style`: 50-word architectural description
- `meta.platforms`: `["mobile-ios"]` (array)
- `decisions.trade_offs`: 2 entries with `accepted_cost`/`gained_benefit`
- `decisions.out_of_scope`: 2 string entries
- `decisions.architectural_style`: one object with `chosen`/`rationale`
- `components[0]` (UserService) — add: `responsibility` (50 words), `location` (`"features/user/UserService.ts"`), `key_interfaces` (2-3 methods each with `name`/`signature`/`description`), `key_files` (2 entries each with `file`/`description`), `platform` (`"ios"` or `"universal"`)
- `components[1..2]` — same pattern but simpler
- `pitfalls[0]` — add `applies_to`: `["features/auth/UserRepository.ts", "features/auth/PasswordHelper.ts"]`
- `pitfalls[1..2]` — same pattern
- `architecture_rules`:
  ```json
  {
    "file_placement_rules": [
      {"pattern": "ViewControllers", "location": "Sources/Controllers/", "rationale": "..."},
      {"pattern": "Services", "location": "Sources/Services/", "rationale": "..."}
    ],
    "naming_conventions": [
      {"applies_to": "ViewController classes", "convention": "*ViewController.swift suffix", "example": "MapViewController.swift"}
    ]
  }
  ```
- `development_rules`: 3 entries, mix of with/without `category` field, each with `rule` + optional `rationale` + optional `applies_to`
- `implementation_guidelines`: 2 entries with `category`/`name`/`pattern_description`/`libraries`/`key_files`/`usage_example`/`tips`
- `technology`: `{stack: [{category, name, version, purpose}, ...], run_commands: {dev, test, build}, project_structure: "..."}`
- `communication.integrations`: 2 entries with `service`/`purpose`/`integration_point`
- `communication.pattern_selection_guide`: 2 entries with `scenario`/`recommended_pattern`
- `quick_reference`:
  ```json
  {
    "pattern_selection": [{"scenario": "...", "pattern": "..."}],
    "error_mapping": [{"error": "...", "status_code": 403, "solution": "..."}]
  }
  ```
- `frontend`: `{framework: "React", state_management: "Zustand", routing: "Next.js App Router", styling: "Tailwind", conventions: "..."}`
- `architecture_diagram`: a mermaid string, e.g. `"graph TD\n  A[UserService] --> B[UserRepository]"`

Keep the fixture a single valid JSON file. Commit: `test(wiki): extend fixture with blueprint sections for Plan 5a`.

**Steps:**
- [ ] **Step 1:** Add all missing sections to the fixture
- [ ] **Step 2:** Validate JSON: `python3 -c "import json; json.load(open('tests/fixtures/wiki_fixture_blueprint.json'))"`
- [ ] **Step 3:** Run existing wiki tests — they should all still pass (existing renderers ignore new fields)
- [ ] **Step 4:** Commit

---

## Task 2: `render_guideline` + guidelines/*.md loop

**Goal:** New page type for `implementation_guidelines[]`. One page per entry, hyperlinked to referenced component `key_files` when possible.

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_builder.py`

**New function:** `render_guideline(guideline: dict, slug: str, component_slugs: dict) -> str`

**Expected page structure:**
```markdown
---
type: guideline
slug: how-to-fetch-firebase-data
category: Data
provenance: EXTRACTED
---

# How to fetch Firebase data

**Category:** Data

## Pattern

<pattern_description prose>

## Libraries

- RxSwift 6.x
- FirebaseDatabase

## Key files

- `Sources/Services/PlacesService.swift`
- `Sources/Extensions/Firebase+Rx.swift`

## Usage example

```swift
<usage_example fenced code>
```

## Tips

- <tip 1>
- <tip 2>
```

**Steps:**
- [ ] **Step 1:** Write 2 unit tests — one full-path guideline (all fields), one minimal (name + pattern_description only)
- [ ] **Step 2:** Verify FAIL
- [ ] **Step 3:** Implement `render_guideline`. Reuse `_frontmatter`, `_as_text`, `_as_list`, `_section`, `_list_lines`. Add slug namespace to `_build_slug_map`. Add iteration block to `build_wiki` after capabilities.
- [ ] **Step 4:** Verify PASS
- [ ] **Step 5:** Commit: `feat(wiki): render guidelines from implementation_guidelines`

---

## Task 3: `render_architecture_rules` + rules/architecture.md single page

**Goal:** One page merging `architecture_rules.file_placement_rules` + `naming_conventions`.

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_builder.py`

**New function:** `render_architecture_rules(blueprint: dict) -> str` (returns a complete markdown doc)

**Page structure:**
```markdown
---
type: rules-page
slug: rules-architecture
---

# Architecture rules

## File placement

| Pattern | Location | Rationale |
|---|---|---|
| ViewControllers | `Sources/Controllers/` | ... |
| Services | `Sources/Services/` | ... |

## Naming conventions

| Applies to | Convention | Example |
|---|---|---|
| ViewController classes | `*ViewController.swift` suffix | `MapViewController.swift` |
```

Emit only if at least one of the two sub-sections has entries. Emit to `wiki_root / "rules" / "architecture.md"`.

**Steps:**
- [ ] **Step 1:** Write unit test — fixture has both rules, assert both tables appear
- [ ] **Step 2:** Write unit test — only file_placement_rules present, only that table
- [ ] **Step 3:** Verify FAIL
- [ ] **Step 4:** Implement. Gate in `build_wiki`: only write if the page is non-empty.
- [ ] **Step 5:** Verify PASS
- [ ] **Step 6:** Commit: `feat(wiki): render architecture_rules as rules/architecture.md`

---

## Task 4: `render_development_rules` + rules/development.md single page

**Goal:** `development_rules[]` categorized page.

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_builder.py`

**New function:** `render_development_rules(blueprint: dict) -> str`

**Page structure:**
```markdown
---
type: rules-page
slug: rules-development
---

# Development rules

## <category name> (3 rules)

- **<rule text>**
  <rationale if present>
  _Applies to:_ `features/auth/**`, `Sources/Services/*.swift`

## Uncategorized rules (N rules)

- ...
```

Group by `rule.category` if present; else fall through to "Uncategorized rules".

**Steps:**
- [ ] **Step 1:** Write unit tests (3): categorized mix, all-uncategorized, empty list (no page emitted)
- [ ] **Step 2:** Verify FAIL
- [ ] **Step 3:** Implement. Emit to `rules/development.md` only if non-empty.
- [ ] **Step 4:** Verify PASS
- [ ] **Step 5:** Commit: `feat(wiki): render development_rules as rules/development.md`

---

## Task 5: `render_technology` + technology.md

**Goal:** One page combining `technology.stack` + `communication.integrations` + `technology.run_commands`.

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_builder.py`

**Page structure:**
```markdown
---
type: technology
slug: technology
---

# Technology

## Stack

| Category | Name | Version | Purpose |
|---|---|---|---|
| Language | Swift | 5.0 | Primary language |
| Framework | RxSwift | 6.x | Reactive programming |

## External integrations

- **Firebase Realtime Database** — sole backend; real-time sync for restaurant data
  _Integration point:_ `Sources/Services/PlacesService.swift`
- **Mapbox** — map rendering
  _Integration point:_ `Sources/MapViewController.swift`

## Run commands

```bash
# dev
<command>

# test
<command>

# build
<command>
```
```

**Steps:**
- [ ] **Step 1:** 2 unit tests — all three sections present, only stack present
- [ ] **Step 2:** Verify FAIL
- [ ] **Step 3:** Implement
- [ ] **Step 4:** Verify PASS
- [ ] **Step 5:** Commit: `feat(wiki): render technology stack + integrations + commands`

---

## Task 6: `render_quick_reference` + quick-reference.md

**Goal:** `quick_reference.pattern_selection` + `error_mapping` + `communication.pattern_selection_guide` in one page.

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_builder.py`

**Page structure:**
```markdown
---
type: quick-reference
slug: quick-reference
---

# Quick reference

## Which pattern should I use?

| Scenario | Recommended pattern |
|---|---|
| "Fetch Firebase data" | RxSwift Observable |
| "View-triggered event" | PublishSubject + Notification |

## Pattern decision tree

- **"Fetch Firebase data"** → use RxSwift Observable. _Why:_ entire codebase uses this pattern.
- ...

## Error handling

| Error | Status code | Solution |
|---|---|---|
| Firebase permission denied | 403 | Check Firebase Rules; re-auth user |
```

**Steps:**
- [ ] **Step 1:** 2 unit tests
- [ ] **Step 2:** Verify FAIL
- [ ] **Step 3:** Implement
- [ ] **Step 4:** Verify PASS
- [ ] **Step 5:** Commit: `feat(wiki): render quick-reference page`

---

## Task 7: `render_frontend` + frontend.md

**Goal:** `blueprint.frontend` as a single page. Skip if blueprint has no frontend section (iOS projects typically do not).

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_builder.py`

**Page structure:**
```markdown
---
type: frontend
slug: frontend
---

# Frontend

**Framework:** Next.js 14 App Router
**State management:** Zustand
**Routing:** App Router (file-based)
**Styling:** Tailwind CSS
**Data fetching:** React Query
**Rendering strategy:** Mixed SSR + CSR

## Conventions

<conventions prose>
```

Emit only if `blueprint.frontend` has at least one meaningful field populated.

**Steps:**
- [ ] **Step 1:** 2 unit tests — fixture has frontend, fixture without frontend
- [ ] **Step 2:** Verify FAIL
- [ ] **Step 3:** Implement with gating
- [ ] **Step 4:** Verify PASS
- [ ] **Step 5:** Commit: `feat(wiki): render frontend configuration page`

---

## Task 8: `render_architecture` + architecture.md (Mermaid)

**Goal:** Dedicated page for `architecture_diagram` with embedded Mermaid, prefaced by executive_summary excerpt.

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_builder.py`

**Page structure:**
```markdown
---
type: architecture
slug: architecture
---

# Architecture

<executive_summary first paragraph>

## System diagram

```mermaid
<architecture_diagram content>
```
```

**Steps:**
- [ ] **Step 1:** Unit test — fixture with diagram + summary, assert mermaid fenced block present
- [ ] **Step 2:** Verify FAIL
- [ ] **Step 3:** Implement with gating (skip if both fields empty)
- [ ] **Step 4:** Verify PASS
- [ ] **Step 5:** Commit: `feat(wiki): render architecture diagram page`

---

## Task 9: Enrich `render_component`

**Goal:** Add Responsibility, Location, Public interface, Key files, Platform sections.

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_builder.py`

**Updated page:**
```markdown
---
type: component
slug: user-service
provenance: EXTRACTED
---

# UserService

**Platform:** ios
**Location:** `Sources/Services/UserService.swift`

**Purpose:** <purpose one-liner, unchanged>

## Responsibility

<responsibility 50-200 word block>

## Depends on
- [UserRepository](../components/user-repository.md)

## Exposes to
- [AuthController](../components/auth-controller.md)

## Public interface

- **`login(email:password:)`** — `Observable<AuthResult>`
  Authenticates and returns an auth token observable.
- **`logout()`** — `Completable`
  Clears session and signals downstream.

## Key files

- `Sources/Services/UserService.swift` — main implementation
- `Sources/Services/UserService+Anonymous.swift` — anonymous auth path
```

Preserve backward compatibility: missing fields render as omitted sections. Platform only renders if non-empty.

**Steps:**
- [ ] **Step 1:** 3 unit tests — full enrichment, sparse (only purpose+depends_on), platform variants
- [ ] **Step 2:** Verify FAIL (new assertions)
- [ ] **Step 3:** Refactor `render_component`. Add `_render_key_interfaces()` helper.
- [ ] **Step 4:** Verify PASS (old tests still pass with unchanged fixture behavior)
- [ ] **Step 5:** Commit: `feat(wiki): enrich component pages with responsibility + interface + files`

---

## Task 10: Enrich `render_pitfall` with applies_to

**Goal:** Add file-path list from `pitfalls[*].applies_to`.

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_builder.py`

**New section in pitfall pages:**
```markdown
## Applies to

```
features/auth/UserRepository.ts
features/auth/PasswordHelper.ts
```
```

Render as a fenced code block (so grep can find paths). Skip if empty.

**Steps:**
- [ ] **Step 1:** Unit test — pitfall with applies_to, assert fenced file paths
- [ ] **Step 2:** Verify FAIL
- [ ] **Step 3:** Modify `render_pitfall`
- [ ] **Step 4:** Verify PASS
- [ ] **Step 5:** Commit: `feat(wiki): add Applies to file list on pitfall pages`

---

## Task 11: `render_decisions_index` + decisions/index.md

**Goal:** An overview page for decisions collecting `architectural_style`, `trade_offs`, `out_of_scope`.

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_builder.py`

**Page structure:**
```markdown
---
type: decisions-index
slug: decisions-index
---

# Architectural decisions

## Architectural style

**Chosen:** <architectural_style.chosen>

**Rationale:** <architectural_style.rationale>

## Trade-offs accepted

| Accepted cost | Gained benefit |
|---|---|
| ... | ... |

## Explicitly out of scope

- ...

## All decisions

- [Decision A](./postgresql-as-primary-store.md)
- [Decision B](./jwt-over-sessions.md)
```

Emit to `wiki_root / "decisions" / "index.md"` (alongside individual decision pages).

**Steps:**
- [ ] **Step 1:** Unit test — fixture with all three fields, assert sections
- [ ] **Step 2:** Verify FAIL
- [ ] **Step 3:** Implement. Be careful not to conflict with the top-level `index.md` — this is a sub-index.
- [ ] **Step 4:** Verify PASS (also verify the top-level index.md still works)
- [ ] **Step 5:** Commit: `feat(wiki): add decisions/index.md overview`

---

## Task 12: Index overhaul — System overview section

**Goal:** Top-level `index.md` gets a "System overview" section at the top with `meta.executive_summary` + `meta.architecture_style` + `meta.platforms`. Existing "Before you implement anything" and "Browse by type" sections stay below.

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_builder.py`

**Updated index layout:**
```markdown
# <project_name> Wiki

## System overview

**Platforms:** mobile-ios

<meta.executive_summary full text>

### Architecture style

<meta.architecture_style full text>

## Before you implement anything
<unchanged capabilities list>

## Browse by type

- **Capabilities (N)** — ...
- **Decisions (N)** — ...
- **Components (N)** — ...
- **Patterns (N)** — ...
- **Pitfalls (N)** — ...
- **Guidelines (N)** — implementation recipes
- **Rules (2 pages)** — architecture + development rules
- **Quick reference** — pattern selection + error handling
- **Technology** — stack + integrations
- **Frontend** (if applicable)
- **Architecture** — diagram + overview

## Capabilities
<unchanged>
## Decisions
- [Decisions overview](./decisions/index.md)
<existing list>
## Guidelines
- [How to fetch Firebase data](./guidelines/how-to-fetch-firebase-data.md)
...
```

**Steps:**
- [ ] **Step 1:** Refactor `render_index` — build the new layout. The existing sub-listings keep their structure.
- [ ] **Step 2:** Update existing `test_render_index` + `test_render_index_promotes_capabilities_at_top` — they assert on existing structure; ensure they still pass with the new additions (the new "System overview" section appears BEFORE existing sections).
- [ ] **Step 3:** Add 1 new test asserting "System overview" appears at top with executive_summary present.
- [ ] **Step 4:** Verify all tests pass
- [ ] **Step 5:** Commit: `feat(wiki): overhaul index.md with system overview at top`

---

## Task 13: End-to-end integration test + manual smoke

**Goal:** A single integration test that runs `wiki_builder.py` against the enriched fixture and asserts ALL new pages + sections exist.

**Files:**
- Modify: `tests/test_wiki_integration.py`

**Test structure:**
```python
def test_wiki_builder_renders_all_plan5a_page_types(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(...)
    wiki = project / ".archie" / "wiki"

    # New page types
    assert (wiki / "guidelines" / ...).exists()  # at least one
    assert (wiki / "rules" / "architecture.md").exists()
    assert (wiki / "rules" / "development.md").exists()
    assert (wiki / "technology.md").exists()
    assert (wiki / "quick-reference.md").exists()
    assert (wiki / "frontend.md").exists()
    assert (wiki / "architecture.md").exists()
    assert (wiki / "decisions" / "index.md").exists()

    # Enriched existing pages
    us = (wiki / "components" / "user-service.md").read_text()
    assert "## Responsibility" in us
    assert "## Public interface" in us
    assert "## Key files" in us

    # Index overhaul
    idx = (wiki / "index.md").read_text()
    assert "## System overview" in idx
    assert "## Browse by type" in idx
    before_sys = idx.index("## System overview")
    before_browse = idx.index("## Browse by type")
    assert before_sys < before_browse
```

**Steps:**
- [ ] **Step 1:** Write the test
- [ ] **Step 2:** Run full suite — everything green
- [ ] **Step 3:** Commit: `test(wiki): e2e coverage for Plan 5a page types`

---

## Task 14: NPM sync + spec update + Gasztroterkepek smoke

**Files:**
- Modify: `npm-package/assets/wiki_builder.py` (copy)
- Modify: `docs/superpowers/specs/2026-04-17-llm-wiki-design.md` — add Plan 5a page-type summaries under Section 4
- Verification: run on `/Users/csacsi/DEV/Gasztroterkepek.iOS`

**Steps:**
- [ ] **Step 1:** `cp archie/standalone/wiki_builder.py npm-package/assets/wiki_builder.py`
- [ ] **Step 2:** `python3 scripts/verify_sync.py` — SYNC CHECK PASSED
- [ ] **Step 3:** Append to `docs/superpowers/specs/2026-04-17-llm-wiki-design.md` a new "Section 4.7: Plan 5a page types" block briefly describing each new page type
- [ ] **Step 4:** `cp archie/standalone/wiki_builder.py /Users/csacsi/DEV/Gasztroterkepek.iOS/.archie/wiki_builder.py && python3 /Users/csacsi/DEV/Gasztroterkepek.iOS/.archie/wiki_builder.py /Users/csacsi/DEV/Gasztroterkepek.iOS`
- [ ] **Step 5:** Manually inspect — `find /Users/csacsi/DEV/Gasztroterkepek.iOS/.archie/wiki -name "*.md" | sort` should show all new page types (guidelines/*, rules/{architecture,development}.md, technology.md, quick-reference.md, architecture.md, decisions/index.md, frontend.md if blueprint has it). Enriched component pages should have "Public interface" section when `key_interfaces` is populated.
- [ ] **Step 6:** Commit: `chore(wiki): sync Plan 5a render-enrichment + spec update`

---

## Self-review checklist

- [ ] All existing Plan 1-4 tests still pass (77 wiki tests + 3 merge_capabilities + 5 viewer + renderer + others).
- [ ] New tests added at unit level (per-page type) and e2e level (full fixture → wiki).
- [ ] No new external dependency (`requirements.txt` unchanged).
- [ ] `wiki_index.py` — zero modifications (backlinks + lint walk the new pages automatically).
- [ ] `wiki_builder.py` remains importable without wiki_index (the two render paths stay separable).
- [ ] `verify_sync.py` passes.
- [ ] Gasztroterkepek smoke shows the enriched wiki — especially `rules/architecture.md` (file placement!) and at least one `guidelines/*.md` recipe.
- [ ] `docs/superpowers/specs/2026-04-17-llm-wiki-design.md` has a Section 4.7 documenting the new page types.

## Known follow-ups (out of scope for Plan 5a)

- Data models are still missing — handled in Plan 5b.1 (needs new Wave 1 agent).
- Utility/helper catalog is still missing — handled in Plan 5b.2 (needs scanner extension).
- Cross-type linking between the new page types (e.g., guideline → related components) is minimal; can be enriched later once we see real-world need.

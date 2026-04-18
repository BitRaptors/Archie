# LLM Wiki — Plan 5b.1: Data Models

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add data models (entities / structs / types representing domain objects) as a first-class concept in the blueprint and wiki. The user explicitly flagged this gap: without seeing the data structure, agents have to grep the source to understand what a `Place` is, which risks reimplementation and inconsistency.

**Architecture:** New Wave 1 "data_models agent" extracts domain entities from source code. Output merges into `blueprint.data_models[]`. `wiki_builder.py` gains `render_data_model` + a new `data-models/*.md` page type. Component pages gain a "Data models" section listing the entities they touch. Index gains a "Data models" browse entry.

**Tech Stack:** Python 3.9+ stdlib, pytest, Claude Sonnet (Wave 1). No new runtime dependencies.

**Depends on:** Plan 5a merged (render-layer stable with enriched component pages).

**Reference spec:** To be updated in Task 10 — spec gets a new Section 4.8 documenting data models.

---

## File structure (this plan)

**Modified files:**
- `.claude/commands/archie-deep-scan.md` — new Wave 1 "Data models agent" block (mirrors the Capabilities agent) + Step 4 merge invocation extension + cleanup step
- `archie/standalone/merge.py` — new `merge_data_models()` function + CLI arg handling
- `archie/standalone/wiki_builder.py` — new `render_data_model`, `_build_slug_map` extension, `build_wiki` new loop, component page enrichment (Data models section), index bump
- `tests/fixtures/wiki_fixture_blueprint.json` — add `data_models[]`
- `tests/test_wiki_builder.py` — new render tests
- `tests/test_wiki_integration.py` — e2e coverage
- `tests/test_merge_data_models.py` — NEW file
- `npm-package/assets/wiki_builder.py`, `merge.py`, `archie-deep-scan.md` — sync
- `docs/superpowers/specs/2026-04-17-llm-wiki-design.md` — Section 4.8

---

## Blueprint schema extension

Add to blueprint top level:

```json
{
  "data_models": [
    {
      "name": "Place",
      "purpose": "Restaurant/POI with location and metadata",
      "fields": [
        {"name": "id", "type": "String", "nullable": false},
        {"name": "coordinate", "type": "CLLocationCoordinate2D", "nullable": false},
        {"name": "name", "type": "String", "nullable": false},
        {"name": "categories", "type": "[PlaceCategory]", "nullable": false},
        {"name": "openingHours", "type": "OpeningHours?", "nullable": true}
      ],
      "location": "Gasztroterkep/Sources/Models/Place.swift",
      "used_by_components": ["PlacesService", "MapViewController", "PlaceDetailsVC"],
      "evidence": ["Sources/Models/Place.swift"],
      "provenance": "INFERRED"
    }
  ]
}
```

`used_by_components` values must match exact `components[*].name` strings. Synthesis validates this and drops unknown refs.

---

## Task 1: Extend test fixture with data_models

**Files:** `tests/fixtures/wiki_fixture_blueprint.json`

Add a `data_models[]` array at the top level with 2 entries:
- `User`: id, email, createdAt, passwordHash — used by UserService + UserRepository
- `Session`: id, userId, token, expiresAt — used by UserService + AuthController

- [ ] **Step 1:** Add `data_models[]` block with 2 entries
- [ ] **Step 2:** Validate JSON
- [ ] **Step 3:** Run existing tests — should pass (nothing reads data_models yet)
- [ ] **Step 4:** Commit: `test(wiki): add data_models fixture`

---

## Task 2: `render_data_model` function

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_builder.py`

**Expected page structure:**
```markdown
---
type: data-model
slug: user
provenance: INFERRED
evidence:
  - features/auth/User.ts
---

# User

> **Source:** Wave 1 data_models agent · **Evidence:** 1 file
> **Provenance:** INFERRED

**Purpose:** Represents a registered user account.

**Location:** `features/auth/User.ts`

## Fields

| Name | Type | Nullable |
|---|---|---|
| `id` | `string` | no |
| `email` | `string` | no |
| `createdAt` | `Date` | no |
| `passwordHash` | `string` | no |

## Used by

- [UserService](../components/user-service.md)
- [UserRepository](../components/user-repository.md)
```

**Function signature:**
```python
def render_data_model(
    model: dict,
    slug: str,
    component_slugs: dict[str, str],
) -> str:
```

Required fields: `name`. Missing fields degrade gracefully (no Fields table if empty, no Used by section if empty).

**Steps:**
- [ ] **Step 1:** Write 3 unit tests — full entity, minimal (name only), with unknown used_by_components (render as plain text)
- [ ] **Step 2:** Verify FAIL
- [ ] **Step 3:** Implement. Reuse `_frontmatter`, `_as_text`, `_as_list`, `_link_or_text`, `_list_lines`. Fields table built via string join. Handle `nullable` field as "yes"/"no" string.
- [ ] **Step 4:** Verify PASS
- [ ] **Step 5:** Commit: `feat(wiki): add render_data_model with fields table`

---

## Task 3: Wire data models into build_wiki + slug_map

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_integration.py`

**Changes:**
1. `_build_slug_map` gets a new `data_models` namespace keyed by model name.
2. `build_wiki` new loop after capabilities:
   ```python
   for model in _as_list(blueprint.get("data_models")):
       slug = slug_map["data_models"].get(model.get("name"))
       if not slug:
           continue
       _write(
           wiki_root / "data-models" / f"{slug}.md",
           render_data_model(model, slug, slug_map["components"]),
       )
   ```
3. `_collect_evidence_map` extension: include data model evidence globs in provenance.

**Integration test:**
```python
def test_wiki_builder_emits_data_model_pages(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(...)
    wiki = project / ".archie" / "wiki"
    assert (wiki / "data-models" / "user.md").exists()
    assert (wiki / "data-models" / "session.md").exists()
    user = (wiki / "data-models" / "user.md").read_text()
    assert "# User" in user
    assert "| `email` | `string` | no |" in user
    assert "[UserService](../components/user-service.md)" in user
```

- [ ] **Step 1:** Write integration test
- [ ] **Step 2:** Verify FAIL
- [ ] **Step 3:** Implement build_wiki extension + slug_map + _collect_evidence_map changes
- [ ] **Step 4:** Verify PASS
- [ ] **Step 5:** Commit: `feat(wiki): emit data-models/*.md pages from build_wiki`

---

## Task 4: Component page "Data models" backlink section

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_integration.py`

Component pages get a new section listing the data models they use (reverse lookup from `data_models[*].used_by_components`).

**Expected addition to component pages:**
```markdown
## Data models

- [User](../data-models/user.md)
- [Session](../data-models/session.md)
```

Approach: compute a reverse map inside `build_wiki` (or a helper), pass it to `render_component`. Alternative cleaner approach: let the existing "Referenced by" auto-backlinks handle this — data-model pages link to components, so component pages automatically get the reverse link. **If this already works via backlinks.json**, skip adding a dedicated "Data models" section and rely on "Referenced by" — but that's mixed with capability backlinks. Better to have a dedicated section for clarity.

**Steps:**
- [ ] **Step 1:** Integration test asserting component page has "Data models" section with correct entries
- [ ] **Step 2:** Verify FAIL
- [ ] **Step 3:** Compute reverse map; pass to render_component; emit the section when non-empty
- [ ] **Step 4:** Verify PASS
- [ ] **Step 5:** Commit: `feat(wiki): add Data models section on component pages`

---

## Task 5: Index overhaul — Data models browse entry

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_builder.py`

`render_index` gets:
- New count in "Browse by type": `**Data models (N)** — entities moving through the system`
- New dedicated `## Data models` section listing entries (same format as existing lists)

**Steps:**
- [ ] **Step 1:** Unit test for render_index with data_models in slug_map
- [ ] **Step 2:** Verify FAIL (or amend prior tests if existing ones fail due to new count)
- [ ] **Step 3:** Extend render_index
- [ ] **Step 4:** Verify PASS (all index tests)
- [ ] **Step 5:** Commit: `feat(wiki): add Data models to index.md browse list`

---

## Task 6: Wave 1 data_models agent prompt

**Files:**
- Modify: `.claude/commands/archie-deep-scan.md`

Add a new agent block alongside the existing Wave 1 agents (structure/patterns/technology/ui_layer/capabilities). Pattern mirrors Capabilities agent:

**Agent header:** `### Data models agent`
**Model:** sonnet
**Output:** `/tmp/archie_agent_data_models.json`

**Trigger:** Skip if file-tree shows no "model-like" directory (`Models/`, `models/`, `entities/`, `domain/`, `types/`). Write `[]` when skipped.

**Prompt body (truncated — full text goes in the command file):**
> Identify primary data models — structs/classes/interfaces/types representing domain entities. Exclude test fixtures, DTO wrappers, internal state. For each entity: name, purpose (1 sentence), fields array with `name`/`type`/`nullable`, file location, which components USE this model.
>
> Cross-reference: use exact `components[*].name` from the blueprint for `used_by_components`.
>
> Evidence threshold: at least 2 component users OR exposed via public API.
>
> Return ONLY a JSON array.

Add `/tmp/archie_agent_data_models.json` to Step 4's merge invocation argv list and to the cleanup `rm -f` line.

**Steps:**
- [ ] **Step 1:** Read archie-deep-scan.md, locate Wave 1 block, identify exact insertion point
- [ ] **Step 2:** Insert the new Data models agent block (copy Capabilities format)
- [ ] **Step 3:** Extend merge invocation + cleanup
- [ ] **Step 4:** Commit: `feat(wiki): add Wave 1 Data models agent prompt`

---

## Task 7: `merge_data_models` in merge.py

**Files:**
- Modify: `archie/standalone/merge.py`
- Create: `tests/test_merge_data_models.py`

**Function:**
```python
def merge_data_models(blueprint: dict, data_models_input: list) -> tuple[int, int]:
    """Validate and append data_model entries. Returns (accepted, dropped_refs)."""
```

Logic mirrors `merge_capabilities`:
- Validate `used_by_components` refs against `blueprint.components[*].name` (also handle the dict-wrapper case via `_extract_components` equivalent — import or duplicate that helper)
- Drop unknown refs individually (not whole entries)
- Drop entries without a `name`
- Append validated entries to `blueprint["data_models"]` (create if missing)
- Print summary: `Data models: N accepted, M dropped due to unknown refs`

**Wire into argv parsing:** positional name-detection ("data_models" in filename → route to `merge_data_models`, mirror the capabilities pattern).

**Test file — `tests/test_merge_data_models.py`:**
```python
def test_merge_data_models_validates_refs():
    blueprint = {
        "components": [{"name": "UserService"}, {"name": "UserRepository"}],
    }
    input_models = [
        {
            "name": "User",
            "fields": [{"name": "id", "type": "string"}],
            "used_by_components": ["UserService", "UnknownService"],
        }
    ]
    accepted, dropped = merge.merge_data_models(blueprint, input_models)
    assert accepted == 1
    assert dropped == 1  # UnknownService dropped
    assert blueprint["data_models"][0]["used_by_components"] == ["UserService"]


def test_merge_data_models_handles_empty():
    blueprint = {"components": []}
    accepted, dropped = merge.merge_data_models(blueprint, [])
    assert accepted == 0
    assert dropped == 0


def test_merge_data_models_creates_key_if_missing():
    blueprint = {"components": [{"name": "X"}]}
    merge.merge_data_models(blueprint, [{"name": "Thing", "used_by_components": ["X"]}])
    assert blueprint["data_models"][0]["name"] == "Thing"
```

**Steps:**
- [ ] **Step 1:** Create test file with 3 tests
- [ ] **Step 2:** Verify FAIL
- [ ] **Step 3:** Implement `merge_data_models` + argv routing
- [ ] **Step 4:** Verify PASS (all merge tests)
- [ ] **Step 5:** Commit: `feat(wiki): synthesize data_models into blueprint.data_models[]`

---

## Task 8: E2E integration test

**Files:**
- Modify: `tests/test_wiki_integration.py`

Single end-to-end test that:
1. Loads fixture with `data_models[]`
2. Runs `wiki_builder.py`
3. Asserts: `data-models/*.md` pages exist, component pages have "Data models" section, index has "Data models (N)" count.

Use the existing fixture (with data_models added in Task 1).

- [ ] **Step 1:** Write the test
- [ ] **Step 2:** Run full suite — green
- [ ] **Step 3:** Commit: `test(wiki): e2e coverage for data models`

---

## Task 9: NPM sync + spec update

**Files:**
- Modify: `npm-package/assets/wiki_builder.py`, `merge.py`, `archie-deep-scan.md`
- Modify: `docs/superpowers/specs/2026-04-17-llm-wiki-design.md` — Section 4.8 "Data model page"

**Steps:**
- [ ] **Step 1:** Copy canonical to assets
- [ ] **Step 2:** `python3 scripts/verify_sync.py`
- [ ] **Step 3:** Add Section 4.8 to the spec
- [ ] **Step 4:** Commit: `chore(wiki): sync data models + spec Section 4.8`

---

## Task 10: Fresh deep-scan on a real project

**Verification only — no code changes.**

On a Claude Code session opened at `/Users/csacsi/DEV/Gasztroterkepek.iOS`:

1. Run `/archie-deep-scan` (expect ~15-20 min).
2. After completion, inspect `.archie/blueprint.json` — `data_models[]` should have 3-8 entries (Place, Article, User, possibly more).
3. Inspect `.archie/wiki/data-models/` — should see markdown pages.
4. Open component pages for PlacesService, ArticlesService — each should have a "Data models" section.
5. Open `.archie/wiki/index.md` — "Data models (N)" appears in Browse by type; dedicated `## Data models` section listed.

- [ ] **Step 1:** Run fresh deep-scan
- [ ] **Step 2:** Inspect blueprint and wiki
- [ ] **Step 3:** Manual validation: agent-probe ("What fields does Place have?", "Which components use User?") — the wiki should answer both.
- [ ] **Step 4:** No commit — verification only.

---

## Self-review checklist

- [ ] All Plan 5a tests still pass.
- [ ] New merge tests + render tests + integration test all green.
- [ ] `verify_sync.py` passes with 5 commands, 19 scripts (+ sync diffs for merge.py, wiki_builder.py, archie-deep-scan.md).
- [ ] Fresh deep-scan on Gasztroterkepek produces non-empty data_models.
- [ ] Spec Section 4.8 documents the page format.

## Known follow-ups

- **Plan 5b.2 (utility catalog)** is separate and can proceed independently.
- **Data model field-type normalization:** field types are language-specific strings. Could be worth normalizing (e.g., map `String?` / `Optional<String>` / `str | None` → a canonical `string?` form). Out of scope for 5b.1 — consider in a later iteration if the mixed types become confusing.
- **Relationships between data models:** if `User` has a `Session?` field, the Session page currently doesn't auto-backlink from the User page. Could be inferred by parsing field types for known model names. Follow-up.

# LLM Wiki — Plan 5c: Polish bundle (page-type backlinks + data-model relations + field-type normalization)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement task-by-task.

**Goal:** Three small follow-up improvements bundled into one plan since they share testing infrastructure and all touch the data-models / wiki rendering surface.

- **F1 — Page-type backlinks:** `wiki_index._page_type_from_dir` currently returns `unknown` for the new `data-models/` and `utilities.md` page types, so backlinks render as `[Foo](...) (unknown)`. Recognize them.
- **F2 — Data-model relations:** When a data-model field's `type` references another known data-model name (e.g. `User.session: Session?`), the Session page should auto-link back. Render a `## Related models` section on each data-model page listing entities it references via field types.
- **F3 — Field-type normalization:** Mixed language conventions (`String?`, `Optional<String>`, `str | None`, `Optional[str]`, etc.) make the Fields table noisy. Add a `_normalize_field_type` helper that produces a canonical form (lowercase, `?` suffix for optionals) and render both: `string? (Optional<String>)` — canonical first, raw in parens.

**Tech Stack:** Python 3.9+ stdlib, pytest. Zero new runtime dependencies.

**Depends on:** Plan 5b.1 merged (data-models live).

**Reference spec:** Spec gets Section 4.13 in F4.

---

## File structure

**Modified files:**
- `archie/standalone/wiki_index.py` — extend `_page_type_from_dir`
- `archie/standalone/wiki_builder.py` — `_normalize_field_type`, `_extract_data_model_refs`, `render_data_model` extension, `build_wiki` wiring
- `tests/test_wiki_index.py` — backlink type tests
- `tests/test_wiki_builder.py` — render_data_model + normalization tests
- `tests/test_wiki_integration.py` — e2e for Related models + normalized types
- `tests/fixtures/wiki_fixture_blueprint.json` — extend Session.fields with a `User?` reference (or User.fields with `Session?`) so the e2e can exercise the relation
- `npm-package/assets/wiki_index.py`, `wiki_builder.py` — sync
- `docs/superpowers/specs/2026-04-17-llm-wiki-design.md` — Section 4.13

---

## Task 1: F1 — wiki_index page-type recognition

**Files:**
- Modify: `archie/standalone/wiki_index.py`
- Modify: `tests/test_wiki_index.py`

### Required change

`_page_type_from_dir` (around line 28). Extend the mapping:

```python
mapping = {
    "components": "component",
    "decisions": "decision",
    "patterns": "pattern",
    "pitfalls": "pitfall",
    "capabilities": "capability",
    "data-models": "data-model",
    "guidelines": "guideline",
    "rules": "rule",
}
```

For root-level single-file pages, special-case before falling through to the dir-based lookup. The function currently only inspects `path_parts[0]`; root files have `path_parts == ('utilities.md',)`. Add:

```python
single_file_types = {
    "utilities.md": "utility-catalog",
    "technology.md": "technology",
    "quick-reference.md": "quick-reference",
    "frontend.md": "frontend",
    "architecture.md": "architecture",
    "index.md": "index",
}
if len(path_parts) == 1 and path_parts[0] in single_file_types:
    return single_file_types[path_parts[0]]
```

### Tests

Add to `tests/test_wiki_index.py`:

```python
def test_page_type_from_dir_recognizes_data_models():
    from wiki_index import _page_type_from_dir
    assert _page_type_from_dir(("data-models", "user.md")) == "data-model"


def test_page_type_from_dir_recognizes_utilities_root_file():
    from wiki_index import _page_type_from_dir
    assert _page_type_from_dir(("utilities.md",)) == "utility-catalog"


def test_page_type_from_dir_recognizes_other_root_files():
    from wiki_index import _page_type_from_dir
    assert _page_type_from_dir(("technology.md",)) == "technology"
    assert _page_type_from_dir(("frontend.md",)) == "frontend"
```

### Steps (TDD)

- [ ] **Step 1:** Add the 3 unit tests
- [ ] **Step 2:** Verify FAIL
- [ ] **Step 3:** Implement the mapping extension
- [ ] **Step 4:** Verify PASS, full suite green
- [ ] **Step 5:** Commit `fix(wiki): recognize data-model + root-page types in backlinks`

---

## Task 2: F3 — Field-type normalization

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_builder.py`

(F3 done before F2 because F2 doesn't depend on it but F2's relation parser also benefits from normalized type strings — so F3 lands first as a building block.)

### Helper `_normalize_field_type(raw)`

Place near `render_data_model`. Behavior:

| Input | Output (canonical) |
|---|---|
| `String` | `string` |
| `String?` | `string?` |
| `Optional<String>` | `string?` |
| `Optional[str]` | `string?` |
| `str \| None` | `string?` |
| `[PlaceCategory]` | `[PlaceCategory]` (preserve unknown wrappers verbatim, lowercase the inner if it's a primitive) |
| `Date` | `Date` (custom types stay as-is, just stripped) |
| `CLLocationCoordinate2D` | `CLLocationCoordinate2D` |
| `null` / empty | `""` |

Algorithm (kept simple):
1. Strip whitespace.
2. Detect optional: matches `^Optional<(.+)>$`, `^Optional\[(.+)\]$`, `(.+)\s*\|\s*None$`, or `(.+)\?$`. Unwrap to inner type and remember the optional flag.
3. Lowercase known primitives (`String`/`Str` → `string`, `Int`/`Integer` → `int`, `Bool`/`Boolean` → `bool`, `Float`/`Double` → `float`, `Date` stays as `Date` because it's a stdlib type but not a primitive — keep capitalization).
4. Re-add `?` if optional.

### Render change in `render_data_model`

In the Fields table, render the canonical form, with the original in parens **only if it differs**:

```python
canonical = _normalize_field_type(raw_type)
display = canonical if canonical == raw_type else f"{canonical} ({raw_type})"
```

If canonical is empty, fall back to raw.

### Tests

```python
def test_normalize_field_type_canonical_forms():
    from wiki_builder import _normalize_field_type
    assert _normalize_field_type("String") == "string"
    assert _normalize_field_type("String?") == "string?"
    assert _normalize_field_type("Optional<String>") == "string?"
    assert _normalize_field_type("Optional[str]") == "string?"
    assert _normalize_field_type("str | None") == "string?"
    assert _normalize_field_type("Int") == "int"
    assert _normalize_field_type("CLLocationCoordinate2D") == "CLLocationCoordinate2D"
    assert _normalize_field_type("[PlaceCategory]") == "[PlaceCategory]"
    assert _normalize_field_type("") == ""
    assert _normalize_field_type(None) == ""


def test_render_data_model_shows_normalized_and_raw_types():
    model = {
        "name": "Place",
        "fields": [
            {"name": "id", "type": "String", "nullable": False},
            {"name": "name", "type": "String?", "nullable": True},
            {"name": "openingHours", "type": "Optional<OpeningHours>", "nullable": True},
        ],
    }
    md = wiki_builder.render_data_model(model, "place", {})
    # Plain string normalizes to lowercase — show only canonical
    assert "| `id` | `string` |" in md
    # String? differs from string? → show both
    assert "| `name` | `string? (String?)` |" in md
    # Optional<X> wrapped → show canonical + raw
    assert "openingHours" in md
    assert "(Optional<OpeningHours>)" in md
```

### Steps (TDD)

- [ ] **Step 1:** Add the 2 unit tests
- [ ] **Step 2:** Verify FAIL
- [ ] **Step 3:** Implement `_normalize_field_type` + wire into `render_data_model`
- [ ] **Step 4:** Existing `test_render_data_model_full_entity` may break (the fixture used `string` already, so probably stable — but verify and amend if needed)
- [ ] **Step 5:** Verify PASS
- [ ] **Step 6:** Commit `feat(wiki): normalize data-model field types with raw fallback`

---

## Task 3: F2 — Data-model relations

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/fixtures/wiki_fixture_blueprint.json`
- Modify: `tests/test_wiki_builder.py`
- Modify: `tests/test_wiki_integration.py`

### Helper `_extract_data_model_refs(model, known_model_names)`

Returns a list of `(referenced_model_name, raw_field_name)` tuples for any field whose `type` mentions a known data-model name.

Detection: for each field's raw type string, find any token matching a name in `known_model_names`. Use a word-boundary regex to avoid partial matches: `\b(Name1|Name2|...)\b`. This means `[User]`, `User?`, `Optional<User>`, and `User | None` all match. A field can reference multiple models (e.g. `Either<User, Session>`); list each.

Edge cases:
- A model never references itself even if its name appears in its own field types (defensive — unlikely in practice).
- Sort the output by `(referenced_name, field_name)` for deterministic rendering.
- Deduplicate: if `User` appears in two field types of the same model, list it once.

### Render change in `render_data_model`

After the existing `## Used by` section, add:

```markdown

## Related models

- [Session](./session.md) — via `session` field
- [Place](./place.md) — via `homeLocation`, `workLocation` fields
```

When a model is referenced via multiple fields, list the field names comma-separated. Section omitted entirely if no relations found. Position: between `## Fields` and `## Used by`.

Wait — re-read: "Position: between `## Fields` and `## Used by`" yes that's the natural reading order. Confirm in implementation.

### Wiring in `build_wiki`

`render_data_model` needs the set of known model names. Pass `slug_map["data_models"]` as a new optional parameter `model_slugs`:

```python
def render_data_model(
    model: dict,
    slug: str,
    component_slugs: dict[str, str],
    model_slugs: dict[str, str] | None = None,
) -> str:
```

Inside, compute `known = set((model_slugs or {}).keys()) - {model.get("name")}` and pass to `_extract_data_model_refs`. Use `model_slugs` (name → slug map) to render the relative links in the Related models section: `[Name](./{slug}.md)` (sibling files in `data-models/`).

### Fixture extension

Edit `tests/fixtures/wiki_fixture_blueprint.json`. Add a `session` field to `User` referencing `Session`:

```json
{"name": "session", "type": "Session?", "nullable": true}
```

This means the Session page should backlink-count User (already covered by `## Used by` from `used_by_components` — different mechanism). The new Related models section on the User page should list Session.

Also add a back-direction: Session's `userId` is a string — that's not a data-model reference. To exercise multi-direction, also add a field to `Session` referencing `User`:

```json
{"name": "user", "type": "Optional<User>", "nullable": true}
```

So User → Session (via `session`) and Session → User (via `user`). Both pages get Related models sections.

### Tests

Unit test (in tests/test_wiki_builder.py):

```python
def test_render_data_model_emits_related_models_section():
    model = {
        "name": "User",
        "fields": [
            {"name": "id", "type": "string"},
            {"name": "session", "type": "Session?", "nullable": True},
            {"name": "homeLocation", "type": "Place?", "nullable": True},
            {"name": "workLocation", "type": "Optional<Place>", "nullable": True},
        ],
    }
    model_slugs = {"User": "user", "Session": "session", "Place": "place"}
    md = wiki_builder.render_data_model(model, "user", {}, model_slugs=model_slugs)
    assert "## Related models" in md
    # Each link points at sibling data-model file
    assert "[Session](./session.md) — via `session` field" in md
    # Multiple-field references combined
    assert "[Place](./place.md) — via `homeLocation`, `workLocation` fields" in md


def test_render_data_model_omits_related_when_no_known_refs():
    model = {
        "name": "Lonely",
        "fields": [{"name": "id", "type": "string"}],
    }
    md = wiki_builder.render_data_model(model, "lonely", {}, model_slugs={"Lonely": "lonely"})
    assert "## Related models" not in md


def test_render_data_model_does_not_self_reference():
    model = {
        "name": "Recursive",
        "fields": [{"name": "parent", "type": "Recursive?", "nullable": True}],
    }
    md = wiki_builder.render_data_model(model, "recursive", {}, model_slugs={"Recursive": "recursive"})
    assert "## Related models" not in md
```

Integration test (in tests/test_wiki_integration.py):

```python
def test_data_model_pages_show_related_models_from_field_types(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(["python3", str(WIKI_BUILDER), str(project)], check=True, capture_output=True)
    user_md = (project / ".archie" / "wiki" / "data-models" / "user.md").read_text()
    session_md = (project / ".archie" / "wiki" / "data-models" / "session.md").read_text()
    assert "## Related models" in user_md
    assert "[Session](./session.md)" in user_md
    assert "## Related models" in session_md
    assert "[User](./user.md)" in session_md
```

### Steps (TDD)

- [ ] **Step 1:** Extend the fixture (add User.session and Session.user fields)
- [ ] **Step 2:** Run existing tests; if any break due to fixture change, amend (the data_models e2e tests may now see one more field per model — only assertions on specific `email` row should still pass)
- [ ] **Step 3:** Add the 3 unit tests + 1 integration test
- [ ] **Step 4:** Verify FAIL
- [ ] **Step 5:** Implement `_extract_data_model_refs` + render extension + `build_wiki` plumbing
- [ ] **Step 6:** Verify PASS
- [ ] **Step 7:** Commit `feat(wiki): auto-link related data models via field types`

---

## Task 4: NPM sync + spec Section 4.13

**Files:**
- Modify: `npm-package/assets/wiki_index.py`, `wiki_builder.py`
- Modify: `docs/superpowers/specs/2026-04-17-llm-wiki-design.md`

### Spec section 4.13

Insert after `### 4.12 Utilities catalog (Plan 5b.2)`, before `## 5. Generation pipeline`:

```markdown
### 4.13 Wiki polish bundle (Plan 5c)

Three small refinements to the data-model and backlink rendering:

- **Page-type backlinks** — `wiki_index._page_type_from_dir` now recognizes `data-models/` (singular: `data-model`) and the root-level single-page outputs (`utilities.md`, `technology.md`, `quick-reference.md`, `frontend.md`, `architecture.md`, `index.md`) so the auto-injected `## Referenced by` section displays a meaningful page-type label instead of `(unknown)`.
- **Data-model relations** — `render_data_model` gains a `## Related models` section listing entities referenced via field types. Detection is regex-based against the set of known data-model names; multi-field references are coalesced into a single line per related model. Self-references are excluded. Section sits between `## Fields` and `## Used by`.
- **Field-type normalization** — `_normalize_field_type` maps language-specific optional notations (`String?`, `Optional<String>`, `Optional[str]`, `str | None`) to a canonical lowercase + `?` form. Primitive type names (`String`/`Int`/`Bool`) are lowercased; custom and acronym types are preserved verbatim. The Fields table renders `canonical (raw)` when the two differ — agents see the canonical form first, with the original kept for fidelity.
```

### Steps

- [ ] **Step 1:** Copy `archie/standalone/wiki_index.py` and `wiki_builder.py` → `npm-package/assets/`
- [ ] **Step 2:** `python3 scripts/verify_sync.py` → PASSED
- [ ] **Step 3:** Add Section 4.13 to spec
- [ ] **Step 4:** Commit `chore(wiki): sync polish bundle + spec Section 4.13`

---

## Self-review checklist

- [ ] All previous tests pass.
- [ ] Backlinks now show `(data-model)`, `(utility-catalog)`, etc. instead of `(unknown)`.
- [ ] Data-model pages with field-type references to other models show `## Related models`.
- [ ] Field-type normalization renders canonical + raw in the Fields table.
- [ ] `verify_sync.py` passes.
- [ ] Spec Section 4.13 documents all three changes.

## Known follow-ups (out of scope)

- **AI-enhanced utility categorization** — when filename heuristics fail, a Haiku pass could re-categorize. Separate plan if needed.
- **Kotlin/Go/Rust utility extractors** — straightforward port of the Swift/TS/Python pattern. Separate plan when projects need them.
- **Field-type normalization for collection wrappers** — `[Place]`, `Array<Place>`, `List<Place>` could all canonicalize to `[place]`. Currently we preserve them verbatim. Tighten if real projects produce confusing outputs.

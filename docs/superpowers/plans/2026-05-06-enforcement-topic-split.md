# Enforcement Topic-Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the monolithic `.claude/rules/enforcement.md` (~70 KB on a real project) with a small `enforcement/index.md` plus per-topic files under `enforcement/by-topic/`, so an agent loads only the topic relevant to the current task.

**Architecture:** Renderer groups rules by a new `topic` field (with a prefix-based fallback for legacy rules), partitions project rules from Archie-baked platform rules (which go to a separate `universal.md`), and emits an index file with both a topic table and a path-glob lookup table. Pre-validate hook is unaffected — it still reads `.archie/rules.json` directly.

**Tech Stack:** Python 3.9+ stdlib only (`json`, `collections.defaultdict`, `re` for slugify). Tests use pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-05-06-enforcement-topic-split-design.md`

---

## File Structure

**Modified:**
- `archie/standalone/renderer.py` — replace `build_enforcement_rules_topic` with `build_enforcement_directory` + helpers; update `generate_all`; update AGENTS.md template line in `_render_main`
- `archie/standalone/finalize.py` — stamp `_archie_source` on rules during loader merge
- `archie/standalone/platform_rules.json` — add `topic` field to all 30 rules
- `.claude/commands/archie-deep-scan.md` — Step 6 prompt: instruct AI to emit `topic` on every rule
- `tests/test_renderer.py` — replace enforcement.md tests with directory-layout tests

**Mirrored to `npm-package/assets/` (per File Sync rule in CLAUDE.md):**
- `renderer.py`, `finalize.py`, `platform_rules.json`, `archie-deep-scan.md`

**Unchanged but referenced:**
- `archie/standalone/install_hooks.py` — pre-validate reads `rules.json` directly, no change
- `scripts/verify_sync.py` — runs at end to confirm canonical/asset parity
- `archie/renderer/render.py` — adapter passes through to `generate_all`, no change

---

### Task 1: Add `_topic_for_rule` helper with prefix-fallback heuristic

**Files:**
- Modify: `archie/standalone/renderer.py` (add helper near other render helpers, ~line 1217)
- Test: `tests/test_renderer.py` (append at end)

- [ ] **Step 1: Write failing tests for `_topic_for_rule`**

Append to `tests/test_renderer.py`:
```python
from archie.standalone.renderer import _topic_for_rule


def test_topic_for_rule_uses_topic_field_when_present():
    rule = {"id": "rx-001", "topic": "concurrency"}
    assert _topic_for_rule(rule) == "concurrency"


def test_topic_for_rule_slugifies_topic_field():
    rule = {"id": "x-001", "topic": "Data Access"}
    assert _topic_for_rule(rule) == "data-access"


def test_topic_for_rule_falls_back_to_known_prefix():
    # No topic field — fall back to prefix heuristic.
    assert _topic_for_rule({"id": "rx-001"}) == "concurrency"
    assert _topic_for_rule({"id": "combine-002"}) == "concurrency"
    assert _topic_for_rule({"id": "nav-001"}) == "navigation"
    assert _topic_for_rule({"id": "ui-003"}) == "ui"
    assert _topic_for_rule({"id": "swiftui-001"}) == "ui"
    assert _topic_for_rule({"id": "snapkit-001"}) == "ui"
    assert _topic_for_rule({"id": "rswift-001"}) == "ui"
    assert _topic_for_rule({"id": "firebase-002"}) == "data-access"
    assert _topic_for_rule({"id": "mapbox-001"}) == "mapping"
    assert _topic_for_rule({"id": "map-003"}) == "mapping"
    assert _topic_for_rule({"id": "layer-001"}) == "layering"
    assert _topic_for_rule({"id": "file-placement-001"}) == "layering"
    assert _topic_for_rule({"id": "svc-001"}) == "services"
    assert _topic_for_rule({"id": "sing-001"}) == "services"
    assert _topic_for_rule({"id": "model-001"}) == "layering"
    assert _topic_for_rule({"id": "dep-001"}) == "dependencies"
    assert _topic_for_rule({"id": "secret-001"}) == "security"
    assert _topic_for_rule({"id": "gdpr-001"}) == "security"
    assert _topic_for_rule({"id": "testing-001"}) == "testing"
    assert _topic_for_rule({"id": "res-001"}) == "resources"


def test_topic_for_rule_unknown_prefix_returns_misc():
    assert _topic_for_rule({"id": "totally-unknown-001"}) == "misc"


def test_topic_for_rule_no_id_returns_misc():
    assert _topic_for_rule({}) == "misc"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_renderer.py::test_topic_for_rule_uses_topic_field_when_present -v`
Expected: `ImportError` or `AttributeError: ... _topic_for_rule`.

- [ ] **Step 3: Implement `_topic_for_rule` and `_slugify_topic`**

In `archie/standalone/renderer.py`, just above `_severity_label_for_render` (around line 1207), add:
```python
import re as _re

# Prefix → topic fallback for rules without an explicit `topic` field.
# Used during the transition window for legacy rules.json files written
# before Step 6 began emitting `topic`. New rules should always carry topic.
_PREFIX_TO_TOPIC_FALLBACK = {
    "rx-": "concurrency",
    "combine-": "concurrency",
    "nav-": "navigation",
    "ui-": "ui",
    "swiftui-": "ui",
    "snapkit-": "ui",
    "rswift-": "ui",
    "firebase-": "data-access",
    "mapbox-": "mapping",
    "map-": "mapping",
    "layer-": "layering",
    "file-placement-": "layering",
    "extension-filename-": "layering",
    "arch-": "layering",
    "model-": "layering",
    "svc-": "services",
    "sing-": "services",
    "filter-": "services",
    "dep-": "dependencies",
    "build-": "dependencies",
    "secret-": "security",
    "gdpr-": "security",
    "testing-": "testing",
    "res-": "resources",
    "loc-": "resources",
    "god-controller-": "complexity",
    "erosion-": "complexity",
    "decay-": "quality",
}


def _slugify_topic(value: str) -> str:
    """Lowercase, collapse whitespace/underscores into single hyphens, strip."""
    s = value.strip().lower()
    s = _re.sub(r"[\s_]+", "-", s)
    s = _re.sub(r"[^a-z0-9-]", "", s)
    s = _re.sub(r"-+", "-", s).strip("-")
    return s or "misc"


def _topic_for_rule(rule: dict) -> str:
    """Resolve a rule's topic. Prefer explicit `topic` field, fall back to
    matching the longest known prefix in `_PREFIX_TO_TOPIC_FALLBACK`. Unknown
    rules go to `misc`."""
    explicit = rule.get("topic")
    if isinstance(explicit, str) and explicit.strip():
        return _slugify_topic(explicit)
    rid = rule.get("id") or ""
    # Match longest prefix first so `file-placement-` wins over `file-`.
    for prefix in sorted(_PREFIX_TO_TOPIC_FALLBACK, key=len, reverse=True):
        if rid.startswith(prefix):
            return _PREFIX_TO_TOPIC_FALLBACK[prefix]
    return "misc"
```

- [ ] **Step 4: Run all new tests, verify pass**

Run: `python -m pytest tests/test_renderer.py -v -k "topic_for_rule or slugify"`
Expected: 5 passes.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/renderer.py tests/test_renderer.py
git commit -m "feat(renderer): add _topic_for_rule helper with prefix-fallback heuristic"
```

---

### Task 2: Stamp `_archie_source` on rules during loader merge

**Why:** The renderer needs to distinguish project rules (from `rules.json`, go to `by-topic/`) from Archie-baked platform rules (from `platform_rules.json`, go to `universal.md`). The current loader merges them into a flat list and loses this signal. We tag each rule at load time with `_archie_source = "project"` or `"platform"`.

**Files:**
- Modify: `archie/standalone/finalize.py:154-165`
- Modify: `archie/standalone/renderer.py:1414-1425` (CLI loader)
- Test: `tests/test_renderer.py`

- [ ] **Step 1: Write failing test for `_archie_source` propagation through `generate_all`**

Append to `tests/test_renderer.py`:
```python
from archie.standalone.renderer import generate_all


def test_generate_all_partitions_rules_by_archie_source():
    """generate_all should partition rules into project (by-topic/) and
    platform (universal.md) buckets based on _archie_source."""
    bp = {"meta": {"repository": "x", "schema_version": "2.0.0"}}
    rules = [
        {
            "id": "rx-001",
            "topic": "concurrency",
            "description": "test",
            "_archie_source": "project",
        },
        {
            "id": "erosion-god-function",
            "topic": "complexity",
            "description": "test",
            "_archie_source": "platform",
        },
    ]
    files = generate_all(bp, enforcement_rules=rules)
    assert ".claude/rules/enforcement/universal.md" in files
    assert ".claude/rules/enforcement/by-topic/concurrency.md" in files
    # Project rule should NOT leak into universal.md
    assert "rx-001" not in files[".claude/rules/enforcement/universal.md"]
    # Platform rule should NOT leak into by-topic/
    assert "erosion-god-function" not in files[
        ".claude/rules/enforcement/by-topic/concurrency.md"
    ]
```

- [ ] **Step 2: Run test, verify failure**

Run: `python -m pytest tests/test_renderer.py::test_generate_all_partitions_rules_by_archie_source -v`
Expected: FAIL — keys not in files dict (the new directory layout doesn't exist yet).

- [ ] **Step 3: Update `archie/standalone/finalize.py` loader**

Find the loop at line 154-165 and replace:
```python
    enforcement_rules: list = []
    for fname in ("rules.json", "platform_rules.json"):
        path = archie_dir / fname
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        items = data if isinstance(data, list) else data.get("rules", [])
        if isinstance(items, list):
            enforcement_rules.extend(r for r in items if isinstance(r, dict))
```

with:
```python
    enforcement_rules: list = []
    for fname, src in (("rules.json", "project"), ("platform_rules.json", "platform")):
        path = archie_dir / fname
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        items = data if isinstance(data, list) else data.get("rules", [])
        if isinstance(items, list):
            for r in items:
                if isinstance(r, dict):
                    r.setdefault("_archie_source", src)
                    enforcement_rules.append(r)
```

- [ ] **Step 4: Apply identical change to `archie/standalone/renderer.py:1414-1425`**

Same replacement pattern in the CLI loader block. (`r.setdefault` so we don't clobber an existing tag — defensive against double-loading.)

- [ ] **Step 5: Skip running the test from Step 1 yet** — `generate_all` doesn't write the new directory paths. We just made the upstream loader correct. The test still fails until Task 4. Don't run it.

- [ ] **Step 6: Commit**

```bash
git add archie/standalone/finalize.py archie/standalone/renderer.py tests/test_renderer.py
git commit -m "feat(renderer): tag rules with _archie_source during loader merge"
```

---

### Task 3: Add `_render_one_universal_rule` is reused as-is — no new code yet

**Note:** `_render_one_enforcement_rule` (line ~1235) renders one rule's markdown body and is platform-agnostic. We reuse it for both `universal.md` and per-topic files. No change needed in this task — this is a marker step to confirm the design before Task 4.

- [ ] **Step 1: Verify `_render_one_enforcement_rule` accepts any rule shape**

Open `archie/standalone/renderer.py`, jump to `_render_one_enforcement_rule` (~line 1235). Read the function. Confirm it only reads `id`, `description`, `why`/`rationale`, `example`, `source`, `triggers`, `applies_to`, `check`, and `_severity_label_for_render(rule)` — none of which we are changing. The new `_archie_source` and `topic` fields are simply ignored. **No edit needed.**

- [ ] **Step 2: No commit** (this task is a verification step only).

---

### Task 4: Implement `build_enforcement_directory`

**Files:**
- Modify: `archie/standalone/renderer.py` — add new function, leave `build_enforcement_rules_topic` for now (removed in Task 6)
- Test: `tests/test_renderer.py`

- [ ] **Step 1: Write failing tests for the directory builder**

Append to `tests/test_renderer.py`:
```python
from archie.standalone.renderer import build_enforcement_directory


def _mk(id_, topic, source, **extra):
    return {"id": id_, "topic": topic, "_archie_source": source,
            "description": f"desc {id_}", **extra}


def test_build_enforcement_directory_groups_project_by_topic():
    rules = [
        _mk("rx-001", "concurrency", "project"),
        _mk("rx-002", "concurrency", "project"),
        _mk("nav-001", "navigation", "project"),
    ]
    out = build_enforcement_directory(rules)
    assert "enforcement/by-topic/concurrency.md" in out
    assert "enforcement/by-topic/navigation.md" in out
    body = out["enforcement/by-topic/concurrency.md"]
    assert "rx-001" in body and "rx-002" in body
    assert "nav-001" not in body


def test_build_enforcement_directory_routes_platform_to_universal():
    rules = [
        _mk("rx-001", "concurrency", "project"),
        _mk("erosion-god-function", "complexity", "platform"),
        _mk("decay-empty-catch", "quality", "platform"),
    ]
    out = build_enforcement_directory(rules)
    assert "enforcement/universal.md" in out
    universal = out["enforcement/universal.md"]
    assert "erosion-god-function" in universal
    assert "decay-empty-catch" in universal
    # Project rule should NOT be in universal.md
    assert "rx-001" not in universal
    # No by-topic file for platform topic.
    assert "enforcement/by-topic/complexity.md" not in out


def test_build_enforcement_directory_emits_index():
    rules = [
        _mk("rx-001", "concurrency", "project"),
        _mk("nav-001", "navigation", "project"),
        _mk("erosion-god-function", "complexity", "platform"),
    ]
    out = build_enforcement_directory(rules)
    idx = out["enforcement/index.md"]
    assert "Enforcement Rules" in idx
    # Topic table lists every project topic + universal row.
    assert "concurrency" in idx
    assert "navigation" in idx
    assert "Universal" in idx
    # Counts surface.
    assert "1" in idx  # one rule per topic in this fixture


def test_build_enforcement_directory_path_glob_inversion():
    rules = [
        _mk("rx-001", "concurrency", "project",
            triggers={"path_glob": ["Sources/Controllers/**/*.swift"]}),
        _mk("nav-001", "navigation", "project",
            triggers={"path_glob": ["Sources/Controllers/**/*.swift"]}),
        _mk("ui-001", "ui", "project",
            triggers={"path_glob": ["Sources/Views/**/*.swift"]}),
    ]
    out = build_enforcement_directory(rules)
    idx = out["enforcement/index.md"]
    # The Controllers glob should list both concurrency and navigation.
    controllers_section = idx.split("Sources/Controllers")[1].split("|")[0:6]
    joined = " ".join(controllers_section)
    assert "concurrency" in joined
    assert "navigation" in joined


def test_build_enforcement_directory_legacy_rules_use_fallback_heuristic():
    """Rules with no `topic` field still get grouped via the prefix table."""
    rules = [
        {"id": "rx-001", "description": "x", "_archie_source": "project"},
        {"id": "ui-001", "description": "x", "_archie_source": "project"},
    ]
    out = build_enforcement_directory(rules)
    assert "enforcement/by-topic/concurrency.md" in out
    assert "enforcement/by-topic/ui.md" in out


def test_build_enforcement_directory_empty_input_returns_empty_dict():
    assert build_enforcement_directory([]) == {}


def test_build_enforcement_directory_slugifies_topic_with_spaces():
    rules = [_mk("x-001", "Data Access", "project")]
    out = build_enforcement_directory(rules)
    assert "enforcement/by-topic/data-access.md" in out
```

- [ ] **Step 2: Run tests, verify failure**

Run: `python -m pytest tests/test_renderer.py -v -k "build_enforcement_directory"`
Expected: All FAIL — `build_enforcement_directory` not defined.

- [ ] **Step 3: Implement `build_enforcement_directory`**

In `archie/standalone/renderer.py`, just above `# ----- Main orchestrator -----` (~line 1335), add:
```python
def _render_topic_file(topic: str, rules: list[dict]) -> str:
    """Render a single by-topic markdown file. Rules are severity-grouped
    in the same order as universal.md."""
    by_severity: dict[str, list[dict]] = defaultdict(list)
    for r in rules:
        by_severity[_severity_label_for_render(r)].append(r)
    lines = [f"# Enforcement: {topic} ({len(rules)} rule"
             f"{'s' if len(rules) != 1 else ''})", ""]
    lines.append(
        "Topic file. Loaded on demand when an agent works on something "
        f"in the `{topic}` area. The pre-edit hook reads "
        "`.archie/rules.json` directly — this file is for browsing/context only."
    )
    lines.append("")
    for sev in _SEVERITY_RENDER_ORDER:
        bucket = by_severity.get(sev) or []
        if not bucket:
            continue
        lines.append(f"## {_SEVERITY_HEADINGS[sev]}")
        lines.append("")
        for r in bucket:
            lines.extend(_render_one_enforcement_rule(r))
    return "\n".join(lines).rstrip() + "\n"


def _render_universal_file(rules: list[dict]) -> str:
    """Render the universal.md file holding Archie-baked platform rules."""
    by_severity: dict[str, list[dict]] = defaultdict(list)
    for r in rules:
        by_severity[_severity_label_for_render(r)].append(r)
    lines = [f"# Universal Enforcement ({len(rules)} rule"
             f"{'s' if len(rules) != 1 else ''})", ""]
    lines.append(
        "Anti-patterns shipped with Archie that apply to every project "
        "regardless of stack. These come from `platform_rules.json`, not "
        "from your project's `rules.json`."
    )
    lines.append("")
    for sev in _SEVERITY_RENDER_ORDER:
        bucket = by_severity.get(sev) or []
        if not bucket:
            continue
        lines.append(f"## {_SEVERITY_HEADINGS[sev]}")
        lines.append("")
        for r in bucket:
            lines.extend(_render_one_enforcement_rule(r))
    return "\n".join(lines).rstrip() + "\n"


def _build_index_file(
    project_topics: dict[str, list[dict]],
    universal_rules: list[dict],
    all_rules: list[dict],
) -> str:
    """Build enforcement/index.md with topic table + path-glob lookup table."""
    total = sum(len(v) for v in project_topics.values()) + len(universal_rules)
    lines = ["# Enforcement Rules — Index", ""]
    lines.append(
        f"This project has {total} rule{'s' if total != 1 else ''} "
        f"across {len(project_topics)} project topic"
        f"{'s' if len(project_topics) != 1 else ''}. Load only the topic "
        "file(s) relevant to your task. Universal Archie anti-patterns "
        "live in `universal.md` and apply to every project."
    )
    lines.append("")

    # By-topic table
    lines.append("## By topic")
    lines.append("")
    lines.append("| Topic | File | Rules |")
    lines.append("|-------|------|-------|")
    for topic in sorted(project_topics):
        n = len(project_topics[topic])
        lines.append(f"| {topic} | by-topic/{topic}.md | {n} |")
    if universal_rules:
        lines.append(f"| Universal | universal.md | {len(universal_rules)} |")
    lines.append("")

    # By-path table — invert path_glob → set of topics
    glob_to_topics: dict[str, set[str]] = defaultdict(set)
    for r in all_rules:
        triggers = r.get("triggers") or {}
        if not isinstance(triggers, dict):
            continue
        globs = triggers.get("path_glob") or []
        if isinstance(globs, str):
            globs = [globs]
        topic = (
            "universal" if r.get("_archie_source") == "platform"
            else _topic_for_rule(r)
        )
        for g in globs:
            if isinstance(g, str) and g:
                glob_to_topics[g].add(topic)

    if glob_to_topics:
        lines.append("## By path")
        lines.append("")
        lines.append(
            "When editing a file matching one of these globs, load the "
            "listed topics first."
        )
        lines.append("")
        lines.append("| Path glob | Topics to load |")
        lines.append("|-----------|----------------|")
        for g in sorted(glob_to_topics):
            topics = ", ".join(sorted(glob_to_topics[g]))
            lines.append(f"| `{g}` | {topics} |")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_enforcement_directory(rules: list[dict]) -> dict[str, str]:
    """Build the enforcement/ directory file map.

    Splits rules by `_archie_source` into project (→ by-topic/) and platform
    (→ universal.md) buckets, groups project rules by topic (resolved via
    `_topic_for_rule`), and emits an index file with a topic table plus a
    path-glob-keyed lookup table.

    Returns a dict mapping relative paths (e.g. `enforcement/index.md`,
    `enforcement/by-topic/concurrency.md`, `enforcement/universal.md`) to
    file contents. Returns `{}` for an empty rule list.
    """
    valid = [r for r in rules if isinstance(r, dict) and r.get("id")]
    if not valid:
        return {}

    project_topics: dict[str, list[dict]] = defaultdict(list)
    universal_rules: list[dict] = []
    for r in valid:
        if r.get("_archie_source") == "platform":
            universal_rules.append(r)
        else:
            project_topics[_topic_for_rule(r)].append(r)

    out: dict[str, str] = {}
    for topic, bucket in project_topics.items():
        out[f"enforcement/by-topic/{topic}.md"] = _render_topic_file(topic, bucket)
    if universal_rules:
        out["enforcement/universal.md"] = _render_universal_file(universal_rules)
    out["enforcement/index.md"] = _build_index_file(project_topics, universal_rules, valid)
    return out
```

- [ ] **Step 4: Run all new tests**

Run: `python -m pytest tests/test_renderer.py -v -k "build_enforcement_directory"`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/renderer.py tests/test_renderer.py
git commit -m "feat(renderer): add build_enforcement_directory + topic/universal/index split"
```

---

### Task 5: Wire `build_enforcement_directory` into `generate_all`

**Files:**
- Modify: `archie/standalone/renderer.py:1383-1387` (the call site that emits enforcement.md)
- Modify: `archie/standalone/renderer.py` `_render_main` template — replace the `enforcement.md` link line
- Test: `tests/test_renderer.py` (the test from Task 2 will finally pass here)

- [ ] **Step 1: Replace the `enforcement.md` emit block in `generate_all`**

Find (around line 1383):
```python
    if enforcement_rules:
        body = build_enforcement_rules_topic(enforcement_rules)
        if body:
            files[".claude/rules/enforcement.md"] = body
```

Replace with:
```python
    if enforcement_rules:
        directory = build_enforcement_directory(enforcement_rules)
        for rel_path, content in directory.items():
            files[f".claude/rules/{rel_path}"] = content
```

- [ ] **Step 2: Update the AGENTS.md template — `_render_main` enforcement link**

Find this block in `_render_main` (approx line 1112-1124):
```python
        "[`.claude/rules/enforcement.md`](.claude/rules/enforcement.md) lists every rule "
        "the pre-edit hook (`PRE_VALIDATE_HOOK`) and plan/commit classifier "
        "(`align_check.py`) consult, grouped by severity. The underlying source on disk "
        "is [`.archie/rules.json`](.archie/rules.json) (project-specific) plus "
        "[`.archie/platform_rules.json`](.archie/platform_rules.json) (universal anti-"
        "patterns shipped with Archie)."
```

Replace with:
```python
        "[`.claude/rules/enforcement/index.md`](.claude/rules/enforcement/index.md) "
        "indexes every rule, grouped by topic and by path glob. Load only the topic "
        "file(s) relevant to the file you're editing — universal anti-patterns sit in "
        "`enforcement/universal.md`. The pre-edit hook (`PRE_VALIDATE_HOOK`) and "
        "plan/commit classifier (`align_check.py`) read "
        "[`.archie/rules.json`](.archie/rules.json) directly; the markdown is for "
        "agent/human browsing only."
```

- [ ] **Step 3: Update the topic-list bullet in `_render_main`**

Find the topic list around line 1083 (the tuple `("enforcement", "Every rule the pre-edit hook + plan/commit classifier consults, grouped by severity")`). The link in the bullet list still points at the old single file — find the renderer logic that emits the bullet and replace `enforcement.md` with `enforcement/index.md`.

Specifically, search for this string in the file:
```
.claude/rules/enforcement.md
```

There should be 2 remaining occurrences after Step 1 — one in the bullet emit logic, one in the description string from Step 2 we just replaced. Update the bullet emit logic so it emits `[\`enforcement/index.md\`](.claude/rules/enforcement/index.md)` instead of `[\`enforcement.md\`](.claude/rules/enforcement.md)`. Read the surrounding lines to be sure.

- [ ] **Step 4: Run the partition test from Task 2**

Run: `python -m pytest tests/test_renderer.py::test_generate_all_partitions_rules_by_archie_source -v`
Expected: PASS.

- [ ] **Step 5: Run the full renderer test suite, verify nothing else broke**

Run: `python -m pytest tests/test_renderer.py -v`
Expected: All previously passing tests still pass. (One test from the OLD `enforcement.md` shape may now fail — that's expected and we'll delete it in Task 6.)

If any test fails with a message about `.claude/rules/enforcement.md` not existing, note its name and proceed — Task 6 retires it.

- [ ] **Step 6: Commit**

```bash
git add archie/standalone/renderer.py
git commit -m "feat(renderer): emit enforcement/ directory from generate_all + AGENTS.md link"
```

---

### Task 6: Remove `build_enforcement_rules_topic` and update legacy tests

**Files:**
- Modify: `archie/standalone/renderer.py` — delete `build_enforcement_rules_topic` and its docstring (~line 1289-1332)
- Modify: `tests/test_renderer.py` — remove or replace any tests asserting on `.claude/rules/enforcement.md`

- [ ] **Step 1: Identify legacy tests**

Run: `grep -n "enforcement.md\b\|build_enforcement_rules_topic" tests/test_renderer.py`

For each match, decide:
- If the test asserts presence of `.claude/rules/enforcement.md` → delete the test (replaced by Task 4 directory tests).
- If the test calls `build_enforcement_rules_topic` directly → delete it.
- If the test just incidentally mentions the string → leave alone.

- [ ] **Step 2: Delete `build_enforcement_rules_topic` from renderer**

In `archie/standalone/renderer.py`, locate `def build_enforcement_rules_topic(rules:` (~line 1289) and delete the function and its docstring through the `return "\n".join(lines).rstrip()` at the end. Leave `_render_one_enforcement_rule`, `_severity_label_for_render`, `_SEVERITY_RENDER_ORDER`, `_SEVERITY_HEADINGS` — those are used by `_render_topic_file` / `_render_universal_file`.

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/test_renderer.py -v`
Expected: ALL tests pass. No reference to `build_enforcement_rules_topic` remains.

Run: `grep -rn "build_enforcement_rules_topic\|enforcement.md\b" archie/standalone/ tests/`
Expected: No matches. (The string `enforcement` will still appear in the new directory paths — that's fine.)

- [ ] **Step 4: Commit**

```bash
git add archie/standalone/renderer.py tests/test_renderer.py
git commit -m "refactor(renderer): remove build_enforcement_rules_topic — replaced by directory builder"
```

---

### Task 7: Tag `platform_rules.json` with `topic` field

**Files:**
- Modify: `archie/standalone/platform_rules.json` (30 rules)

**Topic mapping** (derived from existing `category` field on each rule):
- `category: "complexity"` → `topic: "complexity"` (erosion-* rules)
- `category: "quality"` / `category: "decay"` → `topic: "quality"` (decay-* rules)
- `category: "layering"` → `topic: "layering"`
- `category: "security"` → `topic: "security"`
- `category: "testing"` → `topic: "testing"`
- (anything else) → look at the rule and assign manually

- [ ] **Step 1: Read every rule in `platform_rules.json`**

Run: `python3 -c "import json; rules=json.load(open('archie/standalone/platform_rules.json')); rules=rules if isinstance(rules,list) else rules['rules']; [print(r['id'], '|', r.get('category','-'), '|', r['description'][:80]) for r in rules]"`

Print all 30 rule IDs with their existing category. Use this to decide each topic.

- [ ] **Step 2: Edit `platform_rules.json`**

For every rule object, add a `"topic": "<slug>"` field next to `"category"`. Use the mapping above. If `category` is absent or ambiguous, read the description and pick from: `complexity`, `quality`, `layering`, `security`, `testing`, `dependencies`, `concurrency`, `error-handling`.

The file may be a list at the top level OR `{"rules": [...]}` — preserve whichever shape it has.

- [ ] **Step 3: Validate JSON parses**

Run: `python3 -c "import json; json.load(open('archie/standalone/platform_rules.json'))"`
Expected: No output (silent success).

- [ ] **Step 4: Run a smoke render to confirm universal.md gets a real body**

Create a temporary test script `/tmp/smoke_render.py`:
```python
import json
from archie.standalone.renderer import build_enforcement_directory

with open("archie/standalone/platform_rules.json") as f:
    raw = json.load(f)
rules = raw if isinstance(raw, list) else raw["rules"]
for r in rules:
    r["_archie_source"] = "platform"

out = build_enforcement_directory(rules)
print("files:", list(out))
print()
print("universal.md preview:")
print(out["enforcement/universal.md"][:1500])
```

Run: `python3 /tmp/smoke_render.py`
Expected: `files: ['enforcement/universal.md', 'enforcement/index.md']` and a non-empty universal.md preview that includes the rule IDs.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/platform_rules.json
git commit -m "feat(platform-rules): add topic field to all 30 universal rules"
```

---

### Task 8: Mirror canonical files to `npm-package/assets/`

**Why:** CLAUDE.md's File Sync rule requires every change in `archie/standalone/` to be mirrored. `scripts/verify_sync.py` will fail otherwise.

**Files:**
- Copy: `archie/standalone/renderer.py` → `npm-package/assets/renderer.py`
- Copy: `archie/standalone/finalize.py` → `npm-package/assets/finalize.py`
- Copy: `archie/standalone/platform_rules.json` → `npm-package/assets/platform_rules.json`

- [ ] **Step 1: Copy the three files**

```bash
cp archie/standalone/renderer.py npm-package/assets/renderer.py
cp archie/standalone/finalize.py npm-package/assets/finalize.py
cp archie/standalone/platform_rules.json npm-package/assets/platform_rules.json
```

- [ ] **Step 2: Run the sync verifier**

```bash
python3 scripts/verify_sync.py
```
Expected: Exit 0, no diff messages. If it complains about the `.claude/commands/archie-deep-scan.md` not being mirrored, ignore that — we'll handle it in Task 9.

- [ ] **Step 3: Commit**

```bash
git add npm-package/assets/renderer.py npm-package/assets/finalize.py npm-package/assets/platform_rules.json
git commit -m "chore(npm): mirror enforcement directory split to assets"
```

---

### Task 9: Update Step 6 prompt in `archie-deep-scan.md`

**Files:**
- Modify: `.claude/commands/archie-deep-scan.md` — the Step 6 rule synthesis section
- Mirror: `npm-package/assets/archie-deep-scan.md`

- [ ] **Step 1: Locate Step 6 in the deep-scan command**

Run: `grep -n "Step 6\|## Step 6\|severity_class\|rules.json" .claude/commands/archie-deep-scan.md | head -20`

Open the file and find the section where the AI is instructed to emit a rule schema (the JSON example with `id`, `severity_class`, `description`, `why`, `example`, `triggers` fields). It is typically labelled "Step 6" or "Rule synthesis".

- [ ] **Step 2: Add the `topic` instruction**

In that section, add to the rule schema specification a `topic` field, and add an instruction paragraph just below the schema. Example wording (adapt to local style):

```markdown
Each rule MUST include a `topic` field — a short slug naming the conceptual
area the rule governs. Prefer one of these recommended cross-platform topics:

- `data-access` — fetching, persisting, caching, ORMs, network
- `concurrency` — async/reactive primitives, threads, schedulers
- `ui` — view layer, components, styling, layout
- `navigation` — routing, deep links, screen transitions
- `layering` — file placement, dependency direction, layer rules
- `services` — singletons, DI, cross-cutting service patterns
- `state-management` — global state, stores, reactive sources
- `dependencies` — package managers, build, secrets handling
- `security` — auth, secrets, GDPR/PII, crypto
- `testing` — test harness, fixtures, anti-patterns
- `resources` — assets, i18n, localized strings
- `error-handling` — error propagation, fallbacks, retries

You MAY introduce a project-specific topic when a coherent group of 3 or more
rules clearly belongs together under a name not in the list (examples:
`mapping`, `payments`, `auth`, `realtime`, `migrations`, `accessibility`).
Use a kebab-case slug.
```

Also add `"topic": "<topic-slug>"` to the example JSON rule object shown in the prompt.

- [ ] **Step 3: Mirror to npm-package/assets**

```bash
cp .claude/commands/archie-deep-scan.md npm-package/assets/archie-deep-scan.md
```

- [ ] **Step 4: Run sync verifier again**

```bash
python3 scripts/verify_sync.py
```
Expected: Exit 0.

- [ ] **Step 5: Commit**

```bash
git add .claude/commands/archie-deep-scan.md npm-package/assets/archie-deep-scan.md
git commit -m "feat(deep-scan): instruct Step 6 to emit topic field on every rule"
```

---

### Task 10: End-to-end smoke test on Gasztroterkepek.iOS

**Files:** None modified — this is a verification task using a real project's data.

- [ ] **Step 1: Render Gasztroterkepek.iOS with the new code**

```bash
cd /Users/csacsi/DEV/Gasztroterkepek.iOS
python3 /Users/csacsi/DEV/Archie/archie/standalone/renderer.py .
```

(If that command line is wrong for the renderer's CLI signature, run `python3 /Users/csacsi/DEV/Archie/archie/standalone/renderer.py --help` first and adapt.)

- [ ] **Step 2: Inspect the new directory**

```bash
ls -la .claude/rules/enforcement/ .claude/rules/enforcement/by-topic/
wc -c .claude/rules/enforcement/index.md .claude/rules/enforcement/universal.md .claude/rules/enforcement/by-topic/*.md
```

Expected:
- `index.md` exists, < 8 KB
- `universal.md` exists, contains all 30 platform rules
- Several `by-topic/*.md` files, none larger than ~15 KB
- The legacy `.claude/rules/enforcement.md` is GONE (the renderer no longer emits it)

- [ ] **Step 3: Inspect index.md visually**

```bash
glow .claude/rules/enforcement/index.md
```

Confirm: topic table lists every topic with rule counts; path-glob table maps `Sources/Controllers/**/*.swift` etc. to the right topics.

- [ ] **Step 4: Inspect AGENTS.md update**

```bash
grep -n "enforcement" AGENTS.md
```

Expected: AGENTS.md links to `enforcement/index.md`, NOT `enforcement.md`. The rest of AGENTS.md (architecture/patterns/technology/etc. links) is unchanged.

- [ ] **Step 5: Cleanup — restore Gasztroterkepek.iOS to its committed state**

```bash
cd /Users/csacsi/DEV/Gasztroterkepek.iOS
git checkout -- AGENTS.md CLAUDE.md .claude/
git clean -fd .claude/rules/enforcement/
```

(Only if Gasztroterkepek.iOS is a git repo and we don't want to commit our smoke-test outputs to it. Adapt if it isn't.)

- [ ] **Step 6: No commit** — this is a verification task. If anything failed, file the issue back to the relevant earlier task and re-run.

---

### Task 11: Final verification — clean test run + sync check

- [ ] **Step 1: Full test suite**

```bash
cd /Users/csacsi/DEV/Archie
python -m pytest tests/ -v
```
Expected: All pass.

- [ ] **Step 2: Sync verifier**

```bash
python3 scripts/verify_sync.py
```
Expected: Exit 0.

- [ ] **Step 3: Push branch**

```bash
git push
```

- [ ] **Step 4: Open PR (optional — depends on user preference)**

```bash
gh pr create --title "feat: split enforcement.md into topic-indexed directory" --body "$(cat <<'EOF'
## Summary
- Replaces monolithic `.claude/rules/enforcement.md` with `enforcement/index.md` + per-topic files under `enforcement/by-topic/` and a separate `enforcement/universal.md` for Archie-baked platform rules.
- Adds a `topic` field to the rule schema; legacy rules without `topic` use a prefix-based fallback heuristic.
- Step 6 prompt updated to instruct the AI to assign a `topic` per rule, with a recommended cross-platform vocabulary plus freedom for project-specific topics.

## Test plan
- [ ] `python -m pytest tests/ -v` passes
- [ ] `python3 scripts/verify_sync.py` passes
- [ ] Smoke-render Gasztroterkepek.iOS produces an `index.md` < 8 KB and topic files no larger than ~15 KB

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Spec coverage check (self-review)

| Spec section | Plan task |
|--------------|-----------|
| Directory layout | Tasks 4, 5 |
| `topic` field on every rule | Task 1 (helper), Task 7 (platform), Task 9 (Step 6 prompt) |
| Cross-platform topic vocabulary | Task 9 |
| `index.md` format | Task 4 (Steps 1, 3) |
| Renderer changes | Tasks 4, 5, 6 |
| Backwards compatibility (fallback heuristic) | Task 1 |
| Step 6 prompt update | Task 9 |
| `platform_rules.json` migration | Task 7 |
| `AGENTS.md` template change | Task 5 |
| Testing | Tasks 1, 2, 4, 6, 11 |
| File Sync rule | Tasks 8, 9 |
| Smoke test against real project | Task 10 |

All spec sections covered.

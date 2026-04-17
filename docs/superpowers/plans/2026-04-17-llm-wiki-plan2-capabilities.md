# LLM Wiki — Plan 2: Capabilities Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new Wave 1 agent that identifies user-facing capabilities (auth flow, payment pipeline, etc.) during `/archie-deep-scan`, merge those into `blueprint.capabilities[]`, and render `.archie/wiki/capabilities/<slug>.md` pages that link to the components, decisions, and pitfalls that realize each capability. Also promote capabilities to the top of `index.md`.

**Architecture:** The agent prompt lives inline in `.claude/commands/archie-deep-scan.md` (existing convention). It is dispatched in parallel with the other Wave 1 agents, writes its JSON output to `/tmp/archie_agent_capabilities.json`, and is merged into `blueprint.json` during the existing synthesis phase. `wiki_builder.py` gains a `render_capability` function and an iteration over `blueprint.capabilities[]`. `render_index` gets a new "Before you implement anything" section listing all capabilities.

**Tech Stack:** Same as Plan 1 (Python 3.9+ stdlib, pytest). Adds a Sonnet agent prompt in the slash command; no new Python dependencies.

**Depends on:** Plan 1 (core wiki builder must be shipped and working).

**Reference spec:** `docs/superpowers/specs/2026-04-17-llm-wiki-design.md` §4.1, §5.1

---

## File structure (this plan)

**New files:** none (the agent prompt is embedded in an existing command file).

**Modified files:**
- `archie/standalone/wiki_builder.py` — add `render_capability`, iterate capabilities in `build_wiki`, extend `render_index` with a "Capabilities" / "Before you implement anything" top section.
- `tests/test_wiki_builder.py` — unit tests for `render_capability` and capabilities-aware index.
- `tests/test_wiki_integration.py` — integration test: fixture with capabilities produces capability pages and a capabilities-leading index.
- `tests/fixtures/wiki_fixture_blueprint.json` — add a `capabilities[]` section.
- `.claude/commands/archie-deep-scan.md` — new Wave 1 agent block + synthesis merge step.
- `npm-package/assets/wiki_builder.py` — sync.

---

## Task 1: Extend test fixture with capabilities

**Files:**
- Modify: `tests/fixtures/wiki_fixture_blueprint.json`

- [ ] **Step 1: Add a `capabilities` section to the fixture**

Open `tests/fixtures/wiki_fixture_blueprint.json` and insert a top-level `capabilities` array before the closing brace (and after `pitfalls`):

```json
  "capabilities": [
    {
      "name": "User Authentication",
      "slug_hint": "user-authentication",
      "purpose": "Users sign up, log in, and receive a JWT.",
      "entry_points": [
        "POST /api/auth/login -> AuthController.login",
        "POST /api/auth/signup -> AuthController.signup",
        "screens/LoginScreen.tsx"
      ],
      "uses_components": ["UserService", "UserRepository", "AuthController"],
      "constrained_by_decisions": ["JWT over sessions"],
      "related_pitfalls": ["Password storage"],
      "key_files": ["features/auth/**", "AuthController.ts"],
      "evidence": ["features/auth/**", "routes matching /api/auth/*"],
      "provenance": "INFERRED"
    }
  ],
```

- [ ] **Step 2: Commit**

```bash
git add tests/fixtures/wiki_fixture_blueprint.json
git commit -m "test(wiki): add capabilities section to fixture blueprint"
```

---

## Task 2: `render_capability` function

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_builder.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_wiki_builder.py`:

```python
def test_render_capability_page_links_all_relations():
    capability = {
        "name": "User Authentication",
        "purpose": "Users sign up, log in, and receive a JWT.",
        "entry_points": [
            "POST /api/auth/login -> AuthController.login",
            "screens/LoginScreen.tsx",
        ],
        "uses_components": ["UserService", "AuthController"],
        "constrained_by_decisions": ["JWT over sessions"],
        "related_pitfalls": ["Password storage"],
        "key_files": ["features/auth/**"],
        "evidence": ["features/auth/**"],
        "provenance": "INFERRED",
    }
    slugs = {
        "components": {"UserService": "user-service", "AuthController": "auth-controller"},
        "decisions": {"JWT over sessions": "jwt-over-sessions"},
        "pitfalls": {"Password storage": "password-storage"},
    }
    md = wiki_builder.render_capability(capability, slug="user-authentication", slugs=slugs)
    assert "type: capability" in md
    assert "provenance: INFERRED" in md
    assert "# User Authentication" in md
    assert "POST /api/auth/login -> AuthController.login" in md
    assert "[UserService](../components/user-service.md)" in md
    assert "[AuthController](../components/auth-controller.md)" in md
    assert "[JWT over sessions](../decisions/jwt-over-sessions.md)" in md
    assert "[Password storage](../pitfalls/password-storage.md)" in md
    assert "features/auth/**" in md


def test_render_capability_tolerates_missing_fields():
    capability = {"name": "Minimal cap", "purpose": "Just a name"}
    md = wiki_builder.render_capability(
        capability, slug="minimal-cap", slugs={"components": {}, "decisions": {}, "pitfalls": {}}
    )
    assert "# Minimal cap" in md
    assert "type: capability" in md
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_wiki_builder.py -v -k capability`
Expected: FAIL — `render_capability` missing.

- [ ] **Step 3: Implement `render_capability`**

Append to `archie/standalone/wiki_builder.py`:

```python
def render_capability(capability: dict, slug: str, slugs: dict[str, dict[str, str]]) -> str:
    """Render a capability page.

    `slugs` has sub-dicts keyed by type ('components', 'decisions', 'pitfalls').
    Unknown references degrade to plain text.
    """
    name = capability.get("name", "Untitled capability")
    purpose = capability.get("purpose", "").strip()
    provenance = capability.get("provenance", "INFERRED")
    entry_points = capability.get("entry_points", []) or []
    uses = capability.get("uses_components", []) or []
    decisions = capability.get("constrained_by_decisions", []) or []
    pitfalls = capability.get("related_pitfalls", []) or []
    key_files = capability.get("key_files", []) or []
    evidence = capability.get("evidence", []) or []

    parts = [
        _frontmatter(type="capability", slug=slug, provenance=provenance),
        f"\n# {name}\n",
    ]
    if purpose:
        parts.append(f"\n**Purpose:** {purpose}\n")
    if entry_points:
        parts.append(_section("Entry points", _list_lines(entry_points)))
    if uses:
        linked = [_link_or_text(n, slugs.get("components", {}), "components") for n in uses]
        parts.append(_section("Components", _list_lines(linked)))
    if decisions:
        linked = [_link_or_text(n, slugs.get("decisions", {}), "decisions") for n in decisions]
        parts.append(_section("Decisions", _list_lines(linked)))
    if pitfalls:
        linked = [_link_or_text(n, slugs.get("pitfalls", {}), "pitfalls") for n in pitfalls]
        parts.append(_section("Pitfalls", _list_lines(linked)))
    if key_files:
        parts.append(_section("Key files", _list_lines(f"`{f}`" for f in key_files)))
    if evidence:
        parts.append(_section("Evidence", _list_lines(f"`{e}`" for e in evidence)))
    return "".join(parts)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_wiki_builder.py -v -k capability`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/wiki_builder.py tests/test_wiki_builder.py
git commit -m "feat(wiki): add render_capability with typed cross-links"
```

---

## Task 3: Iterate capabilities in `build_wiki` and `_build_slug_map`

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_integration.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_wiki_integration.py`:

```python
def test_wiki_builder_emits_capability_page(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    cap = project / ".archie" / "wiki" / "capabilities" / "user-authentication.md"
    assert cap.exists()
    text = cap.read_text()
    assert "# User Authentication" in text
    assert "[UserService](../components/user-service.md)" in text
    assert "[JWT over sessions](../decisions/jwt-over-sessions.md)" in text
    assert "[Password storage](../pitfalls/password-storage.md)" in text


def test_capability_backlinks_appear_on_components(tmp_path):
    project = _setup_project(tmp_path)
    subprocess.run(
        [sys.executable, str(STANDALONE / "wiki_builder.py"), str(project)],
        check=True, capture_output=True,
    )
    us = (project / ".archie" / "wiki" / "components" / "user-service.md").read_text()
    # UserService is used by the User Authentication capability, so its
    # "Referenced by" section must include it.
    assert "[User Authentication](../capabilities/user-authentication.md)" in us
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_wiki_integration.py -v -k capability`
Expected: FAIL — capability page not produced.

- [ ] **Step 3: Extend `_build_slug_map` and `build_wiki`**

Edit `archie/standalone/wiki_builder.py`. In `_build_slug_map`, add capabilities:

```python
def _build_slug_map(blueprint: dict) -> dict[str, dict[str, str]]:
    """Return {type: {name: slug}} where each type has its own slug namespace."""
    decisions = blueprint.get("decisions", {}).get("key_decisions", []) or []
    components = blueprint.get("components", []) or []
    patterns = blueprint.get("communication", {}).get("patterns", []) or []
    pitfalls = blueprint.get("pitfalls", []) or []
    capabilities = blueprint.get("capabilities", []) or []

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
        "capabilities": _map(capabilities, "name"),
    }
```

In `build_wiki`, after the pitfalls loop and before writing index.md, add:

```python
    for capability in blueprint.get("capabilities", []) or []:
        slug = slug_map["capabilities"].get(capability.get("name"))
        if not slug:
            continue
        _write(
            wiki_root / "capabilities" / f"{slug}.md",
            render_capability(capability, slug, slug_map),
        )
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_wiki_integration.py -v`
Expected: new capability tests pass; prior tests still pass.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/wiki_builder.py tests/test_wiki_integration.py
git commit -m "feat(wiki): emit capability pages and auto-wire backlinks"
```

---

## Task 4: Promote capabilities in `render_index`

**Files:**
- Modify: `archie/standalone/wiki_builder.py`
- Modify: `tests/test_wiki_builder.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_wiki_builder.py`:

```python
def test_render_index_promotes_capabilities_at_top():
    fixture = Path(__file__).parent / "fixtures" / "wiki_fixture_blueprint.json"
    blueprint = json.loads(fixture.read_text())
    slug_map = {
        "decisions": {"PostgreSQL as primary store": "postgresql-as-primary-store"},
        "components": {"UserService": "user-service"},
        "patterns": {"Repository": "repository"},
        "pitfalls": {"Password storage": "password-storage"},
        "capabilities": {"User Authentication": "user-authentication"},
    }
    md = wiki_builder.render_index(blueprint, slug_map)
    assert "## Before you implement anything" in md
    # The capabilities section comes before the "Browse by type" section.
    before_idx = md.index("## Before you implement anything")
    browse_idx = md.index("## Browse by type")
    assert before_idx < browse_idx
    assert "[User Authentication](./capabilities/user-authentication.md)" in md
    assert "Capabilities (1)" in md
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_wiki_builder.py -v -k "promotes_capabilities"`
Expected: FAIL — no capabilities handling in index.

- [ ] **Step 3: Extend `render_index`**

Replace the `render_index` function body in `archie/standalone/wiki_builder.py` (Task 6 version) with this capabilities-aware version:

```python
def render_index(blueprint: dict, slug_map: dict[str, dict[str, str]]) -> str:
    project_name = blueprint.get("meta", {}).get("project_name", "Project")
    decisions = slug_map.get("decisions", {})
    components = slug_map.get("components", {})
    patterns = slug_map.get("patterns", {})
    pitfalls = slug_map.get("pitfalls", {})
    capabilities = slug_map.get("capabilities", {})

    cap_entries = []
    for cap in blueprint.get("capabilities", []) or []:
        name = cap.get("name")
        slug = capabilities.get(name)
        if not slug:
            continue
        purpose = (cap.get("purpose") or "").strip().replace("\n", " ")
        cap_entries.append((name, slug, purpose))

    def _list(name_to_slug: dict[str, str], subdir: str) -> str:
        return "\n".join(
            f"- [{name}](./{subdir}/{slug}.md)" for name, slug in sorted(name_to_slug.items())
        )

    parts = [f"# {project_name} Wiki\n"]

    if cap_entries:
        parts.append(
            "\n## Before you implement anything\n\n"
            "These capabilities already exist. If your task belongs to one, open it and\n"
            "follow its links before writing any code.\n\n"
        )
        for name, slug, purpose in sorted(cap_entries):
            suffix = f" — {purpose}" if purpose else ""
            parts.append(f"- [{name}](./capabilities/{slug}.md){suffix}\n")
        parts.append("\n")
    else:
        parts.append(
            "\n> Generated by Archie. Start here before implementing anything — follow\n"
            "> links to understand decisions, components, and pitfalls that affect your work.\n"
        )

    parts.append(
        "\n## Browse by type\n\n"
        f"- **Capabilities ({len(capabilities)})** — user-facing features\n"
        f"- **Decisions ({len(decisions)})** — why the architecture is the way it is\n"
        f"- **Components ({len(components)})** — system parts and how they connect\n"
        f"- **Patterns ({len(patterns)})** — reusable design choices\n"
        f"- **Pitfalls ({len(pitfalls)})** — known traps and how to avoid them\n"
    )
    if capabilities:
        parts.append("\n## Capabilities\n\n" + _list(capabilities, "capabilities") + "\n")
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

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_wiki_builder.py tests/test_wiki_integration.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/wiki_builder.py tests/test_wiki_builder.py
git commit -m "feat(wiki): promote capabilities to index.md top section"
```

---

## Task 5: Capabilities agent prompt in `/archie-deep-scan`

**Files:**
- Modify: `.claude/commands/archie-deep-scan.md`

- [ ] **Step 1: Locate the Wave 1 / Phase 3 agent block**

Read the current command file:

```bash
grep -n "agent\|Agent\|Phase 3\|parallel" .claude/commands/archie-deep-scan.md | head -30
```

Identify where the existing Wave 1 agents are dispatched (Agent A/B/C or structure/patterns/technology — whichever convention the current file uses).

- [ ] **Step 2: Add a new agent block for capabilities**

Insert a new agent block following the existing Wave 1 pattern. The agent uses `sonnet`, runs in parallel with the others, writes to `/tmp/archie_agent_capabilities.json`. Template:

```markdown
### Wave 1 — Agent D (Capabilities)

**Purpose:** Identify user-facing capabilities (auth flow, payment pipeline, etc.) by reading file-tree + symbol evidence. Output a JSON list that Wave 2 synthesis merges into `blueprint.capabilities[]`.

**Trigger condition:** Skip this agent when `scan.json` contains fewer than 5 files under plausible feature directories (`features/`, `routes/`, `controllers/`, `pages/`, `app/`). In that case write `[]` to `/tmp/archie_agent_capabilities.json` and continue.

**Input:**
- `.archie/scan.json` (file tree, symbols, frameworks)
- `.archie/blueprint.json` (if present — for existing component/decision/pitfall slugs; on first run this will not exist)

**Prompt:**

```
You are the Capabilities agent for Archie. Identify the user-facing capabilities of this codebase — concrete features a user or external system exercises (e.g. "User Authentication", "Payment Checkout", "Admin Dashboard"). Do NOT list architectural concepts; those go elsewhere.

For each capability, return:
- name (title case, concrete noun phrase)
- purpose (one sentence, <140 chars)
- entry_points (routes, CLI commands, UI screens, event handlers — concrete paths + handler names)
- uses_components (exact component names from the existing blueprint, if provided)
- constrained_by_decisions (exact decision titles from the existing blueprint, if provided)
- related_pitfalls (exact pitfall areas, if any apply)
- key_files (glob patterns or concrete file paths — at least 1, max 5)
- evidence (globs or one-line justifications — what evidence supports that this capability exists)
- provenance (always "INFERRED")

Evidence threshold: a capability must have at least 3 concrete files backing it, or a route / controller / explicit entry point. Do not invent capabilities from directory names alone.

If `blueprint.json` is provided, use its `components[]`, `decisions.key_decisions[]`, and `pitfalls[]` names verbatim. Do not introduce new component/decision/pitfall names from this agent — synthesis owns the cross-link wiring.

Return ONLY a JSON array, no prose:
[
  {
    "name": "User Authentication",
    "purpose": "Users sign up, log in, and receive a JWT.",
    "entry_points": ["POST /api/auth/login -> AuthController.login", "screens/LoginScreen.tsx"],
    "uses_components": ["UserService", "AuthController"],
    "constrained_by_decisions": ["JWT over sessions"],
    "related_pitfalls": [],
    "key_files": ["features/auth/**"],
    "evidence": ["features/auth/**", "routes matching /api/auth/*"],
    "provenance": "INFERRED"
  }
]

If the project is too small or there is insufficient evidence, return `[]`.
```

**Output:** `/tmp/archie_agent_capabilities.json`

**Dispatch (as a bash block within the command):**

```bash
# Read the prompt from above and dispatch as a Sonnet subagent, capturing
# the JSON response to /tmp/archie_agent_capabilities.json. The existing
# dispatch pattern for other Wave 1 agents is the template — mirror it.
```
```

(Adapt the exact "Dispatch" wording to match the mechanical pattern already present in the file for agents A/B/C.)

- [ ] **Step 3: Commit (prompt only — synthesis wire-up is next task)**

```bash
git add .claude/commands/archie-deep-scan.md
git commit -m "feat(wiki): add Wave 1 Capabilities agent prompt"
```

---

## Task 6: Synthesize capabilities into `blueprint.capabilities[]`

**Files:**
- Modify: `.claude/commands/archie-deep-scan.md`

- [ ] **Step 1: Locate the synthesis phase**

```bash
grep -n "finalize\|synthesi\|normalize\|merge" .claude/commands/archie-deep-scan.md | head -20
```

Find the phase that reads the temp JSON files from Wave 1 and writes the consolidated `.archie/blueprint.json`. (In the current file this is driven by `finalize.py --normalize-only` or equivalent — the exact invocation is already in place for the other agents.)

- [ ] **Step 2: Add capabilities to the synthesis input list**

Add `/tmp/archie_agent_capabilities.json` to the set of files the synthesis step reads. Extend the prompt (or the bash block that invokes synthesis) so the output blueprint includes a top-level `capabilities[]` array with entries of the shape the wiki_builder expects.

Append these instructions where the synthesis merging is described:

```markdown
**Capabilities merge:**

Read `/tmp/archie_agent_capabilities.json` (a JSON array — may be empty or missing). For each entry:

1. Validate that every string in `uses_components` matches an existing `components[].name`. Drop unknown refs (log at end of synthesis).
2. Validate that every string in `constrained_by_decisions` matches an existing `decisions.key_decisions[].title`. Drop unknown.
3. Validate that every string in `related_pitfalls` matches an existing `pitfalls[].area`. Drop unknown.
4. Append the validated entry to `blueprint.capabilities[]` (create if missing).

Produce a brief validation summary in the scan report: `Capabilities: <N> accepted, <M> dropped due to unknown refs`.
```

- [ ] **Step 3: Manual smoke test**

Run a dry deep-scan on this repo (or a small fixture project). After deep-scan, inspect the blueprint:

```bash
python3 -c "import json; bp=json.load(open('.archie/blueprint.json')); print(json.dumps(bp.get('capabilities', []), indent=2))"
```

Expected: an array of capability objects with validated cross-references. On a very small repo, an empty array `[]` is acceptable (agent returns nothing rather than fabricate).

- [ ] **Step 4: Commit**

```bash
git add .claude/commands/archie-deep-scan.md
git commit -m "feat(wiki): synthesize capabilities into blueprint.capabilities[]"
```

---

## Task 7: NPM sync

**Files:**
- Modify: `npm-package/assets/wiki_builder.py`

- [ ] **Step 1: Copy updated standalone**

```bash
cp archie/standalone/wiki_builder.py npm-package/assets/wiki_builder.py
python3 scripts/verify_sync.py
```

Expected: exit 0.

- [ ] **Step 2: Commit**

```bash
git add npm-package/assets/wiki_builder.py
git commit -m "chore(wiki): sync capabilities support to npm-package assets"
```

---

## Task 8: End-to-end verification

- [ ] **Step 1: Run the full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 2: Manual deep-scan smoke on a project with feature directories**

On a fixture project that has a `features/` or `routes/` structure, run `/archie-deep-scan`. Inspect:

- `.archie/blueprint.json` — `capabilities[]` has non-empty entries.
- `.archie/wiki/capabilities/*.md` — one page per capability; components/decisions/pitfalls are clickable links.
- `.archie/wiki/index.md` — "Before you implement anything" section lists each capability with its purpose.
- Open a component page that is used by a capability — confirm its "Referenced by" section includes the capability.

- [ ] **Step 3: Done — no commit**

This task is verification only.

---

## Self-review checklist

- [ ] Spec §4.1 (capability page schema) matches `render_capability` output.
- [ ] Spec §5.1 (capabilities agent as new Wave 1 agent) matches command-file changes.
- [ ] No placeholder steps or "TBD".
- [ ] Method names consistent with Plan 1 (`render_capability`, `_build_slug_map`, `build_wiki`, `render_index`).
- [ ] Capabilities degrade gracefully: unknown refs drop at synthesis, empty array renders no capability section (reuses the plain index from Plan 1).
- [ ] `scripts/verify_sync.py` passes.
- [ ] Full test suite green.

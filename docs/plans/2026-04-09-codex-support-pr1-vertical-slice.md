# Codex CLI Support — PR 1 (Vertical Slice) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship the smallest possible end-to-end Codex experience: `npx @bitraptors/archie /path --target=codex` installs a Codex Skill that runs `$archie-scan`, which produces `AGENTS.md` and rule files. No deep-scan, no parallel subagents, no hooks, no per-folder context.

**Architecture:** Four boxes — Codex connector (`SKILL.md`), shared logic (existing `.archie/*.py` + new `.archie/prompts/scan_analyzer.md`), platform-specific instructions (live in connectors), dual-target installer (`archie.mjs --target=auto|claude|codex|both`). The Python analysis layer is target-agnostic except for the renderer's `--target` flag, which controls whether `CLAUDE.md` is written. Shared sub-agent prompts live in `archie/prompts/`, are synced to `npm-package/assets/prompts/`, and land in `.archie/prompts/` in user projects. Both connectors read prompts via their host CLI's native file-read mechanism.

**Tech Stack:** Python 3.9+ (analysis + tests via pytest), Node 18+ (installer is plain ESM, no test framework — use pytest subprocess), bash for git hooks. No new runtime dependencies. No new dev dependencies.

**Branch:** `feature/codex_support` (already created, design doc already committed at `f25312b`).

**Out of scope for this PR (covered by later PRs):**
- Deep-scan workflow + Wave 1 / Wave 2 fan-out → PR 2
- Codex agent TOMLs (`spawn_agent`) and `features.multi_agent` enablement → PR 2
- Hook enforcement (`.codex/hooks.json`, Stop hook, pre-commit) → PR 3
- Per-folder `AGENTS.md` via `intent_layer.py` → PR 4
- README / CHANGELOG / version bump → PR 5

---

## Task ordering rationale

Tasks are ordered from inside out:
1. **Renderer first** (Tasks 1-2): purely Python, well-tested, foundational. Adds `--target` flag without touching anything else.
2. **Shared prompts** (Tasks 3-4): create the `archie/prompts/` directory + sync to assets.
3. **Verify sync extensions** (Tasks 5-6): extend the existing static check before any consumer relies on it.
4. **Codex connector** (Task 7): write the SKILL.md that uses the prompt.
5. **Installer dual-target** (Tasks 8-11): the most complex change, but safe because everything below it is tested first.
6. **End-to-end smoke test** (Task 12): pytest subprocess against the installer.
7. **Manual verification + PR prep** (Task 13): final sanity check, push, draft PR.

Run the full test suite (`python -m pytest tests/ -v`) and `python3 scripts/verify_sync.py` after every task. Don't move on if either is red.

---

## Task 1: Add `target` parameter to `generate_all()` in standalone renderer

**Files:**
- Modify: `archie/standalone/renderer.py:912-913` (the `generate_all` function that returns the output dict)
- Modify: `tests/test_renderer.py` (add new test)

**Context:** Today `generate_all(bp)` returns a dict like `{"CLAUDE.md": "...", "AGENTS.md": "...", ".claude/rules/architecture.md": "..."}`. We want a new `target` parameter that controls whether `CLAUDE.md` and `AGENTS.md` are included. `target="claude"` (default) preserves today's behavior — both files. `target="codex"` excludes `CLAUDE.md`. `target="both"` is identical to `claude`.

### Step 1: Write the failing test

Add to `tests/test_renderer.py`:

```python
def test_render_outputs_codex_target_omits_claude_md(tmp_path: Path) -> None:
    """render_outputs with target='codex' should NOT write CLAUDE.md."""
    render_outputs(MINIMAL_BLUEPRINT, tmp_path, target="codex")
    claude_md = tmp_path / "CLAUDE.md"
    agents_md = tmp_path / "AGENTS.md"
    assert not claude_md.exists(), "CLAUDE.md should not be created with target=codex"
    assert agents_md.exists(), "AGENTS.md should still be created with target=codex"


def test_render_outputs_claude_target_writes_both(tmp_path: Path) -> None:
    """render_outputs with target='claude' (default) should write both CLAUDE.md and AGENTS.md."""
    render_outputs(MINIMAL_BLUEPRINT, tmp_path)  # default target
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / "AGENTS.md").exists()


def test_render_outputs_both_target_writes_both(tmp_path: Path) -> None:
    """render_outputs with target='both' should write both files."""
    render_outputs(MINIMAL_BLUEPRINT, tmp_path, target="both")
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / "AGENTS.md").exists()
```

### Step 2: Run tests to verify they fail

```bash
python -m pytest tests/test_renderer.py::test_render_outputs_codex_target_omits_claude_md -v
```
Expected: FAIL with `TypeError: render_outputs() got an unexpected keyword argument 'target'` or similar.

### Step 3: Implement in `archie/standalone/renderer.py`

Find the `generate_all` function (around line 910). Modify its signature and the dict construction:

```python
def generate_all(blueprint_dict: dict, target: str = "claude") -> dict[str, str]:
    """Generate all output files from a blueprint dict.

    Args:
        blueprint_dict: The parsed blueprint.
        target: 'claude' (default), 'codex', or 'both'.
                'claude' and 'both' write CLAUDE.md + AGENTS.md.
                'codex' writes only AGENTS.md.

    Returns:
        Dict of {relative_path: content} for all output files.
    """
    bp = blueprint_dict
    files: dict[str, str] = {}

    # Root context files — controlled by target
    if target in ("claude", "both"):
        files["CLAUDE.md"] = generate_claude_md(bp)
    files["AGENTS.md"] = generate_agents_md(bp)

    # Rule files — unchanged for now
    files.update(generate_rule_files(bp))  # or whatever the existing call is

    return files
```

**Verify the existing structure:** before editing, run `grep -n 'def generate_all' archie/standalone/renderer.py` and read 30 lines around it. The existing function may have additional logic — preserve it. The only change is conditional on `CLAUDE.md` and adding the `target` parameter.

Then modify `archie/renderer/render.py` to pass `target` through:

```python
def render_outputs(
    blueprint_dict: dict,
    project_root: Path,
    target: str = "claude",
) -> dict[str, str]:
    """Render all output files from a blueprint dict.

    Returns a dict of {relative_path: content} for all generated files.
    Also writes them to disk under project_root.
    """
    from archie.standalone.renderer import generate_all
    from archie.renderer.intent_layer import generate_folder_context

    files: dict[str, str] = generate_all(blueprint_dict, target=target)

    # Per-folder CLAUDE.md files (intent layer) — unchanged for PR 1, target switching is PR 4
    scan_path = project_root / ".archie" / "scan.json"
    if scan_path.exists():
        folder_files = generate_folder_context(blueprint_dict, scan_path)
        files.update(folder_files)

    # Write all files to disk
    for rel_path, content in files.items():
        full_path = project_root / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)

    return files
```

### Step 4: Run tests to verify they pass

```bash
python -m pytest tests/test_renderer.py -v
```
Expected: All renderer tests PASS, including the three new ones.

Also run the full suite to catch regressions:
```bash
python -m pytest tests/ -v
```
Expected: All previously-passing tests still pass.

### Step 5: Commit

```bash
git add archie/standalone/renderer.py archie/renderer/render.py tests/test_renderer.py
git commit -m "feat(renderer): add --target flag controlling CLAUDE.md output

target=claude (default) and target=both write both CLAUDE.md and AGENTS.md.
target=codex writes only AGENTS.md, leaving Codex projects without an
unused CLAUDE.md file."
```

---

## Task 2: Add `--target` CLI flag to standalone renderer's `main()`

**Files:**
- Modify: `archie/standalone/renderer.py:927` (the `main()` function)
- Modify: `tests/test_renderer.py` (add subprocess test for CLI)

**Context:** The standalone renderer has its own `main()` invoked by `python3 .archie/renderer.py /path/to/project`. Connectors (the SKILL.md) call this CLI directly via Bash. We need `--target=codex` to work as a CLI flag.

### Step 1: Write the failing test

Add to `tests/test_renderer.py`:

```python
import subprocess
import sys


def test_renderer_cli_accepts_target_codex(tmp_path: Path) -> None:
    """Standalone renderer CLI should accept --target=codex and write only AGENTS.md."""
    # Set up a minimal blueprint in the tmp project
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    blueprint_path = archie_dir / "blueprint.json"
    import json
    blueprint_path.write_text(json.dumps(MINIMAL_BLUEPRINT))

    repo_root = Path(__file__).resolve().parent.parent
    renderer = repo_root / "archie" / "standalone" / "renderer.py"

    result = subprocess.run(
        [sys.executable, str(renderer), str(tmp_path), "--target=codex"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"renderer failed: {result.stderr}"
    assert not (tmp_path / "CLAUDE.md").exists(), "CLAUDE.md should not exist for codex target"
    assert (tmp_path / "AGENTS.md").exists(), "AGENTS.md should exist for codex target"
```

### Step 2: Run the test to verify it fails

```bash
python -m pytest tests/test_renderer.py::test_renderer_cli_accepts_target_codex -v
```
Expected: FAIL — either CLAUDE.md exists (today's behavior) or the script errors on the unknown flag.

### Step 3: Implement the flag in `archie/standalone/renderer.py:main()`

Replace the existing `main()` (around line 927). Use stdlib `argparse` to keep it dependency-free:

```python
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Render Archie blueprint to context files.")
    parser.add_argument("project_root", help="Path to the project root")
    parser.add_argument(
        "--target",
        choices=["claude", "codex", "both"],
        default="claude",
        help="Which target's context files to render (default: claude)",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    blueprint_path = project_root / ".archie" / "blueprint.json"
    if not blueprint_path.exists():
        print(f"ERROR: blueprint not found at {blueprint_path}", file=sys.stderr)
        sys.exit(1)

    import json
    blueprint = json.loads(blueprint_path.read_text())

    files = generate_all(blueprint, target=args.target)
    for rel_path, content in files.items():
        full_path = project_root / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        print(f"  ✓ {rel_path}")
```

**Verify:** read the existing `main()` first to confirm the current logic (it might already use sys.argv directly — just replace it with argparse).

### Step 4: Run tests to verify they pass

```bash
python -m pytest tests/test_renderer.py -v
python -m pytest tests/ -v
```
Expected: All pass.

### Step 5: Commit

```bash
git add archie/standalone/renderer.py tests/test_renderer.py
git commit -m "feat(renderer): expose --target flag on standalone renderer CLI

Allows connectors to invoke 'python3 .archie/renderer.py PROJECT --target=codex'
to render only AGENTS.md (skipping CLAUDE.md). Backward compatible: omitting
the flag preserves today's behavior."
```

---

## Task 3: Create `archie/prompts/` directory + `scan_analyzer.md`

**Files:**
- Create: `archie/prompts/scan_analyzer.md`
- Create: `archie/prompts/.gitkeep` (only if directory would otherwise be empty after this task — it won't be, skip)

**Context:** This is the canonical home for shared sub-agent prompts. PR 1 needs only the scan analyzer prompt. The content should match what today's `/archie-scan` command tells the analysis agent to do — distilled from `.claude/commands/archie-scan.md`.

### Step 1: Read the existing scan command to source the prompt

```bash
cat /Users/hamutarto/DEV/BitRaptors/Archie/.claude/commands/archie-scan.md | head -120
```

Look for the section that describes what the scan analysis agent is supposed to do (the system prompt for the Sonnet subagent it spawns). Extract that into a self-contained instruction.

### Step 2: Create `archie/prompts/scan_analyzer.md`

```markdown
# Scan Analyzer

You are the Archie scan analysis agent. Your job is to read the deterministic
scanner output and produce an architecture health report.

## Inputs

You will be given access to the following files in `.archie/`:
- `scan.json` — file tree, framework detection, basic metrics from scanner.py
- `blueprint.json` (if it exists) — prior architecture baseline from a previous deep-scan
- `dependency_graph.json` (if it exists) — import/dependency edges

## Your task

Analyze the codebase like a senior architect doing a focused health check:

1. **Dependency violations** — find modules that import across architectural
   boundaries they shouldn't (e.g., domain importing infrastructure).
2. **Pattern drift** — identify places where new code diverges from the
   established patterns in the existing blueprint.
3. **Complexity hotspots** — call out files or modules with disproportionate
   complexity (high fan-in/fan-out, deep nesting, large file size).
4. **Proposed rules** — suggest 0-5 enforceable rules that would prevent
   the violations you found. Each rule must specify:
   - `check_type`: one of `forbidden_import`, `required_pattern`,
     `forbidden_content`, `architectural_constraint`, `file_naming`
   - `pattern`: the regex or path glob the check applies to
   - `rationale`: one sentence explaining why this matters

## Output format

Write your analysis to stdout as a JSON object with these top-level keys:

```json
{
  "summary": "1-2 sentence overall health assessment",
  "violations": [
    {"file": "path/to/file.py", "issue": "description", "severity": "high|medium|low"}
  ],
  "drift": [
    {"area": "name", "expected": "...", "actual": "...", "impact": "..."}
  ],
  "hotspots": [
    {"file": "path/to/file.py", "metric": "complexity|size|fan_in|fan_out", "value": 42}
  ],
  "proposed_rules": [
    {
      "check_type": "forbidden_import",
      "pattern": "from infrastructure.*",
      "applies_to": "domain/**/*.py",
      "rationale": "Domain layer must not depend on infrastructure."
    }
  ]
}
```

Be specific. Cite exact file paths and line numbers when you can.
Prefer fewer high-quality findings over many shallow ones.
```

This is starter content — the implementing engineer should review and tighten it against the existing scan command's prompt before committing. The exact wording is less important than that it exists in `archie/prompts/` and is self-contained.

### Step 3: Commit

```bash
git add archie/prompts/scan_analyzer.md
git commit -m "feat(prompts): add shared scan_analyzer prompt

First entry in the new archie/prompts/ directory. Both Claude and Codex
connectors will read this file at runtime to get the scan analysis
instructions. PR 1 only — Wave 1/Wave 2 prompts come in PR 2."
```

Note: no test for this task. The file is data; its correctness is verified end-to-end by Task 12's smoke test and Task 13's manual verification.

---

## Task 4: Sync `archie/prompts/` → `npm-package/assets/prompts/`

**Files:**
- Create: `npm-package/assets/prompts/scan_analyzer.md` (verbatim copy of `archie/prompts/scan_analyzer.md`)

**Context:** Archie's existing pattern (per `CLAUDE.md`'s "File Sync" section) is canonical-in-`archie/standalone/`, copy-in-`npm-package/assets/`, verified by `scripts/verify_sync.py`. Prompts follow the same pattern but in a `prompts/` subdirectory so they don't mix with `.py` scripts.

### Step 1: Copy the file

```bash
mkdir -p /Users/hamutarto/DEV/BitRaptors/Archie/npm-package/assets/prompts
cp /Users/hamutarto/DEV/BitRaptors/Archie/archie/prompts/scan_analyzer.md \
   /Users/hamutarto/DEV/BitRaptors/Archie/npm-package/assets/prompts/scan_analyzer.md
```

### Step 2: Verify it matches

```bash
diff archie/prompts/scan_analyzer.md npm-package/assets/prompts/scan_analyzer.md
```
Expected: no output (files identical).

### Step 3: Commit

```bash
git add npm-package/assets/prompts/scan_analyzer.md
git commit -m "feat(npm): vendor scan_analyzer prompt under npm-package/assets/prompts/

Mirrors the canonical archie/prompts/scan_analyzer.md. The next task
extends verify_sync.py to enforce this stays in lockstep."
```

---

## Task 5: Extend `verify_sync.py` to check prompt sync

**Files:**
- Modify: `scripts/verify_sync.py` (add prompts check)

**Context:** Today `verify_sync.py` checks that `archie/standalone/*.py` matches `npm-package/assets/*.py` and that file contents are identical. We need the same check for `archie/prompts/*.md` ↔ `npm-package/assets/prompts/*.md`.

### Step 1: Write the failing test

Create `tests/test_verify_sync.py` (new file):

```python
"""Tests for scripts/verify_sync.py — sync check between canonical and vendored assets."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
VERIFY_SYNC = REPO_ROOT / "scripts" / "verify_sync.py"


def test_verify_sync_passes_on_clean_repo() -> None:
    """verify_sync.py should exit 0 when canonical and assets match."""
    result = subprocess.run(
        [sys.executable, str(VERIFY_SYNC)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"verify_sync failed unexpectedly:\n{result.stdout}\n{result.stderr}"


def test_verify_sync_detects_missing_prompt_asset(tmp_path: Path, monkeypatch) -> None:
    """If a file exists in archie/prompts/ but not in npm-package/assets/prompts/, verify_sync must fail."""
    # Make a copy of the repo into tmp_path so we can corrupt it
    shutil.copytree(REPO_ROOT, tmp_path / "repo", ignore=shutil.ignore_patterns("__pycache__", ".git", "node_modules"))
    repo_copy = tmp_path / "repo"

    # Delete the prompt's asset copy
    (repo_copy / "npm-package" / "assets" / "prompts" / "scan_analyzer.md").unlink()

    result = subprocess.run(
        [sys.executable, str(repo_copy / "scripts" / "verify_sync.py")],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, "verify_sync should fail when a prompt asset is missing"
    assert "scan_analyzer.md" in result.stdout, f"Error message should mention the missing prompt: {result.stdout}"


def test_verify_sync_detects_prompt_content_drift(tmp_path: Path) -> None:
    """If archie/prompts/X.md and assets/prompts/X.md differ in content, verify_sync must fail."""
    shutil.copytree(REPO_ROOT, tmp_path / "repo", ignore=shutil.ignore_patterns("__pycache__", ".git", "node_modules"))
    repo_copy = tmp_path / "repo"

    # Corrupt the asset copy
    asset = repo_copy / "npm-package" / "assets" / "prompts" / "scan_analyzer.md"
    asset.write_text(asset.read_text() + "\nDRIFT")

    result = subprocess.run(
        [sys.executable, str(repo_copy / "scripts" / "verify_sync.py")],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "OUT OF SYNC" in result.stdout or "scan_analyzer" in result.stdout
```

### Step 2: Run tests to verify they fail

```bash
python -m pytest tests/test_verify_sync.py -v
```
Expected: `test_verify_sync_passes_on_clean_repo` may pass (repo IS clean), but the other two FAIL because verify_sync.py doesn't check prompts yet.

### Step 3: Implement the prompt sync check in `scripts/verify_sync.py`

Add new constants near the top:

```python
PROMPTS = ROOT / "archie" / "prompts"
ASSETS_PROMPTS = ROOT / "npm-package" / "assets" / "prompts"
```

Inside `main()`, after the existing data file check section (around line 70), add:

```python
    # 3c. Check: prompts
    if PROMPTS.exists():
        canonical_prompts = {f.name for f in PROMPTS.glob("*.md")}
        asset_prompts = {f.name for f in ASSETS_PROMPTS.glob("*.md")} if ASSETS_PROMPTS.exists() else set()

        for name in sorted(canonical_prompts - asset_prompts):
            errors.append(f"MISSING ASSET: archie/prompts/{name} has no copy in npm-package/assets/prompts/")
        for name in sorted(asset_prompts - canonical_prompts):
            errors.append(f"ORPHAN ASSET: npm-package/assets/prompts/{name} has no canonical in archie/prompts/")
        for name in sorted(canonical_prompts & asset_prompts):
            if (PROMPTS / name).read_text() != (ASSETS_PROMPTS / name).read_text():
                errors.append(f"OUT OF SYNC: prompts/{name} differs between archie/prompts/ and npm-package/assets/prompts/")
```

### Step 4: Run tests to verify they pass

```bash
python -m pytest tests/test_verify_sync.py -v
python3 scripts/verify_sync.py  # should still pass on the real repo
```
Expected: All pass.

### Step 5: Commit

```bash
git add scripts/verify_sync.py tests/test_verify_sync.py
git commit -m "feat(verify_sync): check archie/prompts/ ↔ npm-package/assets/prompts/

Catches missing copies, orphan asset files, and content drift between
the canonical prompts directory and its vendored npm copy. Mirrors the
existing pattern for standalone Python scripts."
```

---

## Task 6: Extend `verify_sync.py` to verify prompt references resolve

**Files:**
- Modify: `scripts/verify_sync.py`
- Modify: `tests/test_verify_sync.py`

**Context:** The Codex SKILL.md (created in Task 7) will reference prompt files like `.archie/prompts/scan_analyzer.md`. If someone renames or deletes a prompt without updating the SKILL.md, the connector silently breaks at runtime. The static check catches this.

### Step 1: Write the failing test

Add to `tests/test_verify_sync.py`:

```python
def test_verify_sync_detects_unresolved_prompt_reference(tmp_path: Path) -> None:
    """If a connector references a prompt file that doesn't exist, verify_sync must fail."""
    shutil.copytree(REPO_ROOT, tmp_path / "repo", ignore=shutil.ignore_patterns("__pycache__", ".git", "node_modules"))
    repo_copy = tmp_path / "repo"

    # Inject a bad reference into the SKILL.md
    skill_md = repo_copy / "npm-package" / "assets" / "codex" / "skills" / "archie-scan" / "SKILL.md"
    if skill_md.exists():
        skill_md.write_text(skill_md.read_text() + "\nReference: .archie/prompts/nonexistent.md\n")
    else:
        # SKILL.md will be created in Task 7. For now, simulate by writing a fake one.
        skill_md.parent.mkdir(parents=True, exist_ok=True)
        skill_md.write_text("---\nname: archie-scan\n---\nReference: .archie/prompts/nonexistent.md\n")
        # Also mirror to canonical so the existing sync check doesn't fail first
        (repo_copy / "archie" / "prompts" / "nonexistent.md").unlink(missing_ok=True)

    result = subprocess.run(
        [sys.executable, str(repo_copy / "scripts" / "verify_sync.py")],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "nonexistent.md" in result.stdout, f"Should report unresolved reference: {result.stdout}"
```

### Step 2: Run the test to verify it fails

```bash
python -m pytest tests/test_verify_sync.py::test_verify_sync_detects_unresolved_prompt_reference -v
```
Expected: FAIL — the unresolved reference check doesn't exist yet.

### Step 3: Implement the reference check in `scripts/verify_sync.py`

Add new constant near the top:

```python
CODEX_SKILLS_DIR = ROOT / "npm-package" / "assets" / "codex" / "skills"
```

Add a new check section in `main()` after the prompts check:

```python
    # 3d. Check: every .archie/prompts/<file> reference in connector files resolves
    canonical_prompts = {f.name for f in PROMPTS.glob("*.md")} if PROMPTS.exists() else set()

    if CODEX_SKILLS_DIR.exists():
        prompt_ref_pattern = re.compile(r"\.archie/prompts/([a-zA-Z0-9_\-]+\.md)")
        for skill_md in CODEX_SKILLS_DIR.rglob("SKILL.md"):
            referenced = set(prompt_ref_pattern.findall(skill_md.read_text()))
            for prompt_name in sorted(referenced - canonical_prompts):
                rel = skill_md.relative_to(ROOT)
                errors.append(f"UNRESOLVED REFERENCE: {rel} references .archie/prompts/{prompt_name} which does not exist")
```

### Step 4: Run tests to verify they pass

```bash
python -m pytest tests/test_verify_sync.py -v
python3 scripts/verify_sync.py
```
Expected: All pass on the real repo. The new test passes against the corrupted copy.

### Step 5: Commit

```bash
git add scripts/verify_sync.py tests/test_verify_sync.py
git commit -m "feat(verify_sync): verify connector references to .archie/prompts/ resolve

Scans every Codex SKILL.md for .archie/prompts/<file>.md references and
fails if any referenced prompt doesn't exist in archie/prompts/. Catches
typos and renames before they reach users."
```

---

## Task 7: Author the Codex SKILL.md for `archie-scan`

**Files:**
- Create: `npm-package/assets/codex/skills/archie-scan/SKILL.md`

**Context:** This is the Codex connector. Hand-written, ~30-50 lines, references the shared prompt from Task 3. Codex Skills use frontmatter (`name`, `description`) and a markdown body. The body should be self-contained instructions that Codex's main agent can follow in one turn — no `spawn_agent` (that's PR 2), no fan-out.

### Step 1: Write the failing test

Add to `tests/test_verify_sync.py`:

```python
def test_codex_scan_skill_exists_and_resolves() -> None:
    """The Codex archie-scan SKILL.md must exist and reference only valid prompts."""
    skill = REPO_ROOT / "npm-package" / "assets" / "codex" / "skills" / "archie-scan" / "SKILL.md"
    assert skill.exists(), f"Missing Codex skill: {skill}"

    content = skill.read_text()
    assert content.startswith("---"), "SKILL.md must have YAML frontmatter"
    assert "name: archie-scan" in content
    assert "description:" in content
    assert ".archie/prompts/scan_analyzer.md" in content, "SKILL.md must reference the scan analyzer prompt"
```

### Step 2: Run the test to verify it fails

```bash
python -m pytest tests/test_verify_sync.py::test_codex_scan_skill_exists_and_resolves -v
```
Expected: FAIL — file does not exist.

### Step 3: Create `npm-package/assets/codex/skills/archie-scan/SKILL.md`

```bash
mkdir -p npm-package/assets/codex/skills/archie-scan
```

Then create the file with this content:

````markdown
---
name: archie-scan
description: Architecture health check for the current project. Runs the Archie scanner, analyzes the codebase against the existing blueprint, and produces AGENTS.md plus rule files. ~1-3 minutes.
---

# archie-scan

Run an architecture health check on the current project. This is the fast,
incremental scan — for the comprehensive baseline, use `archie-deep-scan` instead.

## Steps

1. **Run the deterministic scanner.** This populates `.archie/scan.json` with the
   file tree, framework detection, and basic metrics. No AI involved.

   ```bash
   python3 .archie/scanner.py "$PWD"
   ```

   If the command fails or `.archie/scanner.py` doesn't exist, stop and tell the
   user to run `npx @bitraptors/archie .` first.

2. **Read the scan analyzer prompt and follow it.** Your full instructions for the
   analysis step live in a shared prompt file:

   ```bash
   cat .archie/prompts/scan_analyzer.md
   ```

   Read that file in full, then perform the analysis it describes. Your inputs are:
   - `.archie/scan.json` (always exists after step 1)
   - `.archie/blueprint.json` (only if a prior deep-scan has run)
   - `.archie/dependency_graph.json` (only if scanner produced one)

   Produce the JSON output described in the prompt and save it to
   `.archie/scan_analysis.json`.

3. **Render the context files.** This converts the analysis into AGENTS.md and
   rule files using the deterministic renderer.

   ```bash
   python3 .archie/renderer.py "$PWD" --target=codex
   ```

   The `--target=codex` flag ensures only `AGENTS.md` is written (not `CLAUDE.md`).

4. **Run the validator** to cross-check the output against the actual codebase
   and surface any rule violations.

   ```bash
   python3 .archie/validate.py all "$PWD"
   ```

5. **Summarize for the user.** In your final message, report:
   - Top 3 health findings from the analysis
   - Any new rules proposed (and where they came from)
   - Whether `AGENTS.md` was updated and what changed
   - Any validation errors that need attention

## Notes

- This skill does not spawn parallel sub-agents. The analysis runs in your single
  turn. For projects > 50k LOC, this is fine; for very large monorepos, consider
  `archie-deep-scan` which uses parallel Wave 1 / Wave 2 analysis.
- All Archie analysis scripts under `.archie/` are pure Python with no external
  dependencies beyond Python 3.9+.
- The prompt at `.archie/prompts/scan_analyzer.md` is shared with the Claude Code
  version of this command — both targets get the same analysis instructions.
````

### Step 4: Run tests to verify they pass

```bash
python -m pytest tests/test_verify_sync.py -v
python3 scripts/verify_sync.py
```
Expected: All pass.

### Step 5: Commit

```bash
git add npm-package/assets/codex/skills/archie-scan/SKILL.md
git commit -m "feat(codex): add archie-scan SKILL.md connector

Codex connector for the scan command. Reads the shared prompt from
.archie/prompts/scan_analyzer.md, performs analysis in a single turn
(no spawn_agent — that comes in PR 2), then renders AGENTS.md via
the deterministic renderer with --target=codex."
```

---

## Task 8: Add `--target` flag parsing to `archie.mjs`

**Files:**
- Modify: `npm-package/bin/archie.mjs`

**Context:** Today `archie.mjs` reads only `process.argv[2]` as the project root and unconditionally installs Claude assets. We need to parse `--target=auto|claude|codex|both`, default to `auto`. This task adds parsing only — install behavior stays Claude-only until Tasks 9-11.

### Step 1: Write the failing test

Create `tests/test_install.py` (new file):

```python
"""Smoke tests for npm-package/bin/archie.mjs (the dual-target installer)."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHIE_MJS = REPO_ROOT / "npm-package" / "bin" / "archie.mjs"


def _has_node() -> bool:
    return shutil.which("node") is not None


pytestmark = pytest.mark.skipif(not _has_node(), reason="node not available")


def _run_installer(project_root: Path, target: str | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    args = ["node", str(ARCHIE_MJS), str(project_root)]
    if target is not None:
        args.append(f"--target={target}")
    return subprocess.run(args, capture_output=True, text=True, env=env or os.environ.copy())


def test_installer_accepts_target_flag(tmp_path: Path) -> None:
    """archie.mjs --target=claude must run without error."""
    result = _run_installer(tmp_path, target="claude")
    assert result.returncode == 0, f"installer failed: {result.stderr}"


def test_installer_rejects_unknown_target(tmp_path: Path) -> None:
    """archie.mjs --target=blah must fail with a clear error."""
    result = _run_installer(tmp_path, target="blah")
    assert result.returncode != 0
    assert "target" in (result.stderr + result.stdout).lower()
```

### Step 2: Run the tests to verify they fail

```bash
python -m pytest tests/test_install.py -v
```
Expected: `test_installer_accepts_target_flag` likely passes (ignored unknown args), `test_installer_rejects_unknown_target` FAILS (no validation).

### Step 3: Implement the flag parsing

In `npm-package/bin/archie.mjs`, replace the line:

```js
const projectRoot = resolve(process.argv[2] || ".");
```

with:

```js
// Parse CLI args: archie.mjs <project_root> [--target=auto|claude|codex|both]
function parseArgs(argv) {
  const positional = [];
  let target = "auto";
  for (const arg of argv.slice(2)) {
    if (arg.startsWith("--target=")) {
      target = arg.slice("--target=".length);
    } else if (arg === "--target") {
      console.error("ERROR: --target requires a value, e.g. --target=codex");
      process.exit(2);
    } else if (arg.startsWith("--")) {
      console.error(`ERROR: unknown flag ${arg}`);
      process.exit(2);
    } else {
      positional.push(arg);
    }
  }
  const validTargets = new Set(["auto", "claude", "codex", "both"]);
  if (!validTargets.has(target)) {
    console.error(`ERROR: invalid --target=${target}. Must be one of: auto, claude, codex, both.`);
    process.exit(2);
  }
  return { projectRoot: resolve(positional[0] || "."), target };
}

const { projectRoot, target } = parseArgs(process.argv);
```

### Step 4: Run tests to verify they pass

```bash
python -m pytest tests/test_install.py -v
```
Expected: Both tests pass.

### Step 5: Commit

```bash
git add npm-package/bin/archie.mjs tests/test_install.py
git commit -m "feat(installer): parse --target flag, validate values

Adds --target=auto|claude|codex|both flag parsing to archie.mjs. Default
is 'auto'. Invalid values exit with code 2 and a clear error message.
This task only adds parsing; install behavior is still Claude-only and
will be split per-target in the next tasks."
```

---

## Task 9: Add auto-detect logic for `--target=auto`

**Files:**
- Modify: `npm-package/bin/archie.mjs`
- Modify: `tests/test_install.py`

**Context:** When `--target=auto` (the default), the installer should detect which CLIs the user has installed by checking for `~/.codex/` and `~/.claude/`. If both exist → install both. If only one exists → install that one. If neither exists → fall back to `claude` (today's behavior) and print a warning.

### Step 1: Write the failing test

Add to `tests/test_install.py`:

```python
def _fake_home(tmp_path: Path, *, has_claude: bool, has_codex: bool) -> dict:
    """Return an env dict with HOME pointing at a fake home with optional .claude / .codex dirs."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    if has_claude:
        (fake_home / ".claude").mkdir()
    if has_codex:
        (fake_home / ".codex").mkdir()
    env = os.environ.copy()
    env["HOME"] = str(fake_home)
    return env


def test_installer_auto_detects_codex_only(tmp_path: Path) -> None:
    """With only ~/.codex, --target=auto should resolve to codex."""
    project = tmp_path / "project"
    project.mkdir()
    env = _fake_home(tmp_path, has_claude=False, has_codex=True)
    result = _run_installer(project, target="auto", env=env)
    assert result.returncode == 0, f"installer failed: {result.stderr}"
    assert "codex" in (result.stdout + result.stderr).lower()


def test_installer_auto_detects_claude_only(tmp_path: Path) -> None:
    """With only ~/.claude, --target=auto should resolve to claude."""
    project = tmp_path / "project"
    project.mkdir()
    env = _fake_home(tmp_path, has_claude=True, has_codex=False)
    result = _run_installer(project, target="auto", env=env)
    assert result.returncode == 0
    # Existing Claude assets should land
    assert (project / ".claude" / "commands" / "archie-scan.md").exists()


def test_installer_auto_detects_both(tmp_path: Path) -> None:
    """With both ~/.claude and ~/.codex, --target=auto should install both."""
    project = tmp_path / "project"
    project.mkdir()
    env = _fake_home(tmp_path, has_claude=True, has_codex=True)
    result = _run_installer(project, target="auto", env=env)
    assert result.returncode == 0
```

### Step 2: Run tests to verify they fail

```bash
python -m pytest tests/test_install.py -v
```
Expected: New tests fail because auto-detect resolution isn't implemented.

### Step 3: Implement auto-detect resolution

Add a `resolveTarget` function in `archie.mjs`, just below `parseArgs`:

```js
function resolveTarget(target) {
  if (target !== "auto") return target;
  const home = process.env.HOME || process.env.USERPROFILE || "";
  const hasClaude = home && existsSync(join(home, ".claude"));
  const hasCodex = home && existsSync(join(home, ".codex"));
  if (hasClaude && hasCodex) return "both";
  if (hasCodex) return "codex";
  if (hasClaude) return "claude";
  console.log(`  ${DIM}⚠ no Claude or Codex CLI detected; defaulting to --target=claude${RESET}`);
  return "claude";
}

const resolvedTarget = resolveTarget(target);
```

Then add a status line near the start of installation output:

```js
console.log(`  ${DIM}target: ${resolvedTarget}${RESET}`);
```

### Step 4: Run tests to verify they pass

```bash
python -m pytest tests/test_install.py -v
```
Expected: All pass.

### Step 5: Commit

```bash
git add npm-package/bin/archie.mjs tests/test_install.py
git commit -m "feat(installer): auto-detect target from ~/.claude and ~/.codex presence

--target=auto (the default) inspects \$HOME for .claude and .codex
directories. Both → 'both'. Only one → that one. Neither → fall back
to 'claude' with a warning, preserving today's default behavior for
users with no detection-friendly CLI install."
```

---

## Task 10: Refactor `archie.mjs` install logic into per-target functions

**Files:**
- Modify: `npm-package/bin/archie.mjs`

**Context:** Today `archie.mjs` runs install steps inline in module top-level. We need to factor them into named functions: `installSharedAssets(projectRoot)` for the target-agnostic `.archie/*.py` + `.archie/prompts/*.md` copies, and `installClaude(projectRoot)` for the existing Claude-specific work. This makes Task 11's `installCodex(projectRoot)` a clean addition. **No behavior change** in this task — it's a pure refactor verified by the existing tests.

### Step 1: Confirm current tests still pass before refactor

```bash
python -m pytest tests/test_install.py -v
```
Expected: All pass (this is your safety net).

### Step 2: Refactor — extract `installSharedAssets`

Extract this block (currently lines ~91-110 of archie.mjs):

```js
function installSharedAssets(projectRoot) {
  const archieDir = join(projectRoot, ".archie");
  mkdirSync(archieDir, { recursive: true });

  // Copy standalone Python scripts (target-agnostic)
  const SCRIPTS = ["_common.py", "scanner.py", "refresh.py", "intent_layer.py", "renderer.py", "install_hooks.py", "merge.py", "finalize.py", "validate.py", "viewer.py", "drift.py", "extract_output.py", "arch_review.py", "measure_health.py", "check_rules.py", "detect_cycles.py"];
  for (const script of SCRIPTS) {
    const src = join(ASSETS, script);
    const dest = join(archieDir, script);
    if (existsSync(src)) {
      writeFileSync(dest, readFileSync(src, "utf8"));
      chmodSync(dest, 0o755);
      console.log(`  ${GREEN}✓${RESET} .archie/${script}`);
    }
  }

  // Copy data files
  for (const dataFile of ["platform_rules.json"]) {
    const src = join(ASSETS, dataFile);
    const dest = join(archieDir, dataFile);
    if (existsSync(src)) {
      writeFileSync(dest, readFileSync(src, "utf8"));
      console.log(`  ${GREEN}✓${RESET} .archie/${dataFile}`);
    }
  }

  // Copy shared sub-agent prompts (target-agnostic)
  const promptsDir = join(archieDir, "prompts");
  mkdirSync(promptsDir, { recursive: true });
  const PROMPTS_ASSETS = join(ASSETS, "prompts");
  if (existsSync(PROMPTS_ASSETS)) {
    for (const f of readdirSync(PROMPTS_ASSETS)) {
      if (f.endsWith(".md")) {
        const src = join(PROMPTS_ASSETS, f);
        const dest = join(promptsDir, f);
        writeFileSync(dest, readFileSync(src, "utf8"));
        console.log(`  ${GREEN}✓${RESET} .archie/prompts/${f}`);
      }
    }
  }
}
```

### Step 3: Refactor — extract `installClaude`

```js
function installClaude(projectRoot) {
  const claudeCommands = join(projectRoot, ".claude", "commands");
  mkdirSync(claudeCommands, { recursive: true });

  // Clean previous Claude assets (existing logic from lines 32-79)
  // ... keep the existing cleanup block, just wrap it in this function

  for (const cmd of ["archie-scan.md", "archie-deep-scan.md", "archie-viewer.md"]) {
    const src = join(ASSETS, cmd);
    const dest = join(claudeCommands, cmd);
    if (existsSync(src)) {
      writeFileSync(dest, readFileSync(src, "utf8"));
      console.log(`  ${GREEN}✓${RESET} .claude/commands/${cmd}`);
    }
  }
}
```

Then in the module's main flow, call:

```js
installSharedAssets(projectRoot);
if (resolvedTarget === "claude" || resolvedTarget === "both") {
  installClaude(projectRoot);
}
// installCodex is added in Task 11
```

The Python hooks installation (currently lines 112-129) stays where it is for now — it will be moved into a target-aware branch in PR 3.

### Step 4: Run tests to verify nothing broke

```bash
python -m pytest tests/test_install.py -v
python3 scripts/verify_sync.py
```
Expected: All pass. The refactor is invisible to users.

### Step 5: Commit

```bash
git add npm-package/bin/archie.mjs
git commit -m "refactor(installer): extract installSharedAssets and installClaude

Pure refactor — same behavior, cleaner structure. Sets up the next
task to add installCodex without growing the module's top-level
imperative blob. Also adds the .archie/prompts/ copy step that ships
shared sub-agent prompts to user projects regardless of target."
```

---

## Task 11: Add `installCodex(projectRoot)` for SKILL.md

**Files:**
- Modify: `npm-package/bin/archie.mjs`
- Modify: `tests/test_install.py`

**Context:** This is the actual Codex install. Copies the SKILL.md from `npm-package/assets/codex/skills/archie-scan/SKILL.md` to `.agents/skills/archie-scan/SKILL.md` in the user's project.

### Step 1: Write the failing test

Add to `tests/test_install.py`:

```python
def test_installer_codex_target_writes_skill_md(tmp_path: Path) -> None:
    """--target=codex must write the archie-scan SKILL.md to .agents/skills/archie-scan/."""
    project = tmp_path / "project"
    project.mkdir()
    result = _run_installer(project, target="codex")
    assert result.returncode == 0, f"installer failed: {result.stderr}"

    skill = project / ".agents" / "skills" / "archie-scan" / "SKILL.md"
    assert skill.exists(), f"missing: {skill}"
    content = skill.read_text()
    assert "name: archie-scan" in content
    assert ".archie/prompts/scan_analyzer.md" in content


def test_installer_codex_target_writes_shared_prompts(tmp_path: Path) -> None:
    """--target=codex must also write .archie/prompts/scan_analyzer.md."""
    project = tmp_path / "project"
    project.mkdir()
    _run_installer(project, target="codex")
    prompt = project / ".archie" / "prompts" / "scan_analyzer.md"
    assert prompt.exists(), f"missing: {prompt}"


def test_installer_codex_target_skips_claude_assets(tmp_path: Path) -> None:
    """--target=codex must NOT install Claude command files."""
    project = tmp_path / "project"
    project.mkdir()
    _run_installer(project, target="codex")
    claude_cmd = project / ".claude" / "commands" / "archie-scan.md"
    assert not claude_cmd.exists(), "Claude command should not be installed for --target=codex"


def test_installer_both_target_installs_both(tmp_path: Path) -> None:
    """--target=both must install both Claude and Codex assets."""
    project = tmp_path / "project"
    project.mkdir()
    _run_installer(project, target="both")
    assert (project / ".claude" / "commands" / "archie-scan.md").exists()
    assert (project / ".agents" / "skills" / "archie-scan" / "SKILL.md").exists()
```

### Step 2: Run tests to verify they fail

```bash
python -m pytest tests/test_install.py -v
```
Expected: Codex tests fail — no `installCodex` function yet.

### Step 3: Implement `installCodex`

Add to `archie.mjs`:

```js
function installCodex(projectRoot) {
  const codexSkillsDir = join(projectRoot, ".agents", "skills");
  mkdirSync(codexSkillsDir, { recursive: true });

  const CODEX_SKILLS_SRC = join(ASSETS, "codex", "skills");
  if (!existsSync(CODEX_SKILLS_SRC)) {
    console.log(`  ${DIM}⚠ no codex skills found in package assets${RESET}`);
    return;
  }

  for (const skillName of readdirSync(CODEX_SKILLS_SRC)) {
    const srcDir = join(CODEX_SKILLS_SRC, skillName);
    const srcSkill = join(srcDir, "SKILL.md");
    if (!existsSync(srcSkill)) continue;

    const destDir = join(codexSkillsDir, skillName);
    mkdirSync(destDir, { recursive: true });
    const destSkill = join(destDir, "SKILL.md");
    writeFileSync(destSkill, readFileSync(srcSkill, "utf8"));
    console.log(`  ${GREEN}✓${RESET} .agents/skills/${skillName}/SKILL.md`);
  }
}
```

Then update the main flow:

```js
installSharedAssets(projectRoot);
if (resolvedTarget === "claude" || resolvedTarget === "both") {
  installClaude(projectRoot);
}
if (resolvedTarget === "codex" || resolvedTarget === "both") {
  installCodex(projectRoot);
}
```

Update the "Next steps" output at the bottom of the file to reflect the resolved target:

```js
console.log(`  Next steps:`);
if (resolvedTarget === "codex" || resolvedTarget === "both") {
  console.log(`  • Open this project in ${BOLD}Codex CLI${RESET}`);
  console.log(`  • Run ${BOLD}\$archie-scan${RESET} for an architecture health check`);
}
if (resolvedTarget === "claude" || resolvedTarget === "both") {
  console.log(`  • Open this project in ${BOLD}Claude Code${RESET}`);
  console.log(`  • Run ${BOLD}/archie-scan${RESET} for an architecture health check`);
}
```

### Step 4: Run tests to verify they pass

```bash
python -m pytest tests/test_install.py -v
python -m pytest tests/ -v   # full suite
python3 scripts/verify_sync.py
```
Expected: All pass.

### Step 5: Commit

```bash
git add npm-package/bin/archie.mjs tests/test_install.py
git commit -m "feat(installer): add installCodex() for .agents/skills/

--target=codex now installs the archie-scan SKILL.md to
.agents/skills/archie-scan/SKILL.md alongside the shared .archie/
scripts and prompts. --target=both installs both surfaces. The
'Next steps' output adapts to whichever target(s) were installed."
```

---

## Task 12: End-to-end smoke test against a real fixture project

**Files:**
- (no new files — manual verification + a final pytest run)

**Context:** Tasks 1-11 each tested a slice. This task verifies the whole pipeline by running the installer against a real-looking project, then visually inspecting what was installed. This is the gate before pushing the branch.

### Step 1: Create a fixture project

```bash
mkdir -p /tmp/archie_pr1_test/src
cd /tmp/archie_pr1_test
git init -q
echo "print('hello')" > src/app.py
echo "# Test fixture" > README.md
git add . && git commit -q -m "fixture"
```

### Step 2: Run the installer with `--target=codex`

```bash
cd /Users/hamutarto/DEV/BitRaptors/Archie
node npm-package/bin/archie.mjs /tmp/archie_pr1_test --target=codex
```

Expected output:
- Lines like `✓ .archie/scanner.py`, `✓ .archie/prompts/scan_analyzer.md`, `✓ .agents/skills/archie-scan/SKILL.md`
- A "Next steps" message mentioning Codex CLI and `$archie-scan`

### Step 3: Verify the installed files

```bash
ls -la /tmp/archie_pr1_test/.archie/
ls -la /tmp/archie_pr1_test/.archie/prompts/
ls -la /tmp/archie_pr1_test/.agents/skills/archie-scan/
test ! -f /tmp/archie_pr1_test/.claude/commands/archie-scan.md && echo "OK: no Claude assets"
cat /tmp/archie_pr1_test/.agents/skills/archie-scan/SKILL.md | head -20
```

Expected: `.archie/` contains all Python scripts + `prompts/scan_analyzer.md`. `.agents/skills/archie-scan/SKILL.md` exists. No `.claude/commands/archie-scan.md`.

### Step 4: Repeat for `--target=both` and `--target=claude`

```bash
rm -rf /tmp/archie_pr1_test/.archie /tmp/archie_pr1_test/.agents /tmp/archie_pr1_test/.claude
node npm-package/bin/archie.mjs /tmp/archie_pr1_test --target=both
ls -la /tmp/archie_pr1_test/.claude/commands/ /tmp/archie_pr1_test/.agents/skills/

rm -rf /tmp/archie_pr1_test/.archie /tmp/archie_pr1_test/.agents /tmp/archie_pr1_test/.claude
node npm-package/bin/archie.mjs /tmp/archie_pr1_test --target=claude
ls -la /tmp/archie_pr1_test/.claude/commands/
test ! -d /tmp/archie_pr1_test/.agents && echo "OK: no Codex assets"
```

Expected: each target installs only what it should.

### Step 5: Run the full test suite + sync check one final time

```bash
cd /Users/hamutarto/DEV/BitRaptors/Archie
python -m pytest tests/ -v
python3 scripts/verify_sync.py
```
Expected: green across the board.

### Step 6: Commit (if anything changed)

If you discovered any issues during smoke testing, fix them and commit:

```bash
git add -p   # review carefully — only stage related changes
git commit -m "fix(installer): <specific fix from smoke test>"
```

If everything was clean, no commit needed for this task.

---

## Task 13: Push branch and prepare draft PR (do NOT merge)

**Files:**
- (none — git operations only)

**Context:** Per `feedback_feature_branches.md`, this PR targets `feature/codex_support`, NOT main. PR 5 (later) is the integration to main. Per `feedback_feature_branches.md` and Gabor's explicit instruction, PR 5 will be **prepared but never auto-merged** — Gabor clicks the merge button himself.

For PR 1 specifically: this PR's base is `feature/codex_support` itself (since PR 1 lands on the feature branch directly). On a brand-new feature branch with only PR 1's commits, you can either:
- (a) push the feature branch and create a draft PR with `main` as the base, marked clearly as "PR 1 of 5 — do not merge yet, see design doc", OR
- (b) just push the branch and skip creating a PR until the integration is ready in PR 5

Option (a) is better for visibility and CI feedback. **Use option (a) but mark the PR as draft so it cannot be accidentally merged.**

### Step 1: Final pre-push checks

```bash
cd /Users/hamutarto/DEV/BitRaptors/Archie
git status                           # should be clean
python -m pytest tests/ -v          # all green
python3 scripts/verify_sync.py      # passes
git log --oneline main..HEAD         # review the commit train
```

Expected: ~10-12 commits, working tree clean, all checks green.

### Step 2: Push the branch

```bash
git push -u origin feature/codex_support
```

### Step 3: Create the draft PR

```bash
gh pr create --draft --title "PR 1/5: Codex CLI support — vertical slice (scan only)" --body "$(cat <<'EOF'
## Summary
First of 5 PRs implementing Codex CLI support in Archie. This PR ships the vertical slice — `npx @bitraptors/archie /path --target=codex` installs a Codex Skill that runs `\$archie-scan` end-to-end.

**See the design doc** at \`docs/plans/2026-04-09-codex-cli-support-design.md\` and the implementation plan at \`docs/plans/2026-04-09-codex-support-pr1-vertical-slice.md\` for context.

**This PR is intentionally limited:**
- Scan only — no deep-scan, no Wave 1/Wave 2 fan-out
- No \`spawn_agent\`, no agent TOMLs, no \`features.multi_agent\` flag
- No hook enforcement
- No per-folder \`AGENTS.md\`

These ship in PRs 2-4 against this same \`feature/codex_support\` branch. PR 5 is the final integration to main.

## What's in this PR
- \`archie/standalone/renderer.py\`: new \`--target\` flag controls whether \`CLAUDE.md\` is written
- \`archie/prompts/scan_analyzer.md\`: shared sub-agent prompt (one source of truth)
- \`npm-package/assets/prompts/scan_analyzer.md\`: vendored copy
- \`npm-package/assets/codex/skills/archie-scan/SKILL.md\`: Codex connector
- \`npm-package/bin/archie.mjs\`: \`--target=auto|claude|codex|both\` flag with auto-detect
- \`scripts/verify_sync.py\`: extended to verify prompt sync + connector reference resolution
- \`tests/test_renderer.py\`, \`tests/test_install.py\`, \`tests/test_verify_sync.py\`: new test coverage

## Test plan
- [x] \`python -m pytest tests/ -v\` passes
- [x] \`python3 scripts/verify_sync.py\` passes
- [x] Manual smoke: \`node npm-package/bin/archie.mjs /tmp/fixture --target=codex\` lands the right files
- [x] Manual smoke: \`--target=claude\` preserves today's behavior
- [x] Manual smoke: \`--target=both\` installs both surfaces
- [ ] **DO NOT MERGE** — this is part of a 5-PR train. Wait for PR 5 (integration to main) which Gabor will merge himself.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

The `--draft` flag plus the bold "DO NOT MERGE" disclaimer in the body makes the intent unmistakable.

### Step 4: Print the PR URL for the user

`gh pr create` returns the URL. Capture it and print to the user with a clear note:

> **PR 1 created as draft.** URL: <url>. This is intentionally not mergeable — it's part of a 5-PR train on `feature/codex_support`. Wait for PR 5 before clicking merge. Per instruction, the integration PR (PR 5) is prepared but never auto-merged — you click merge yourself.

### Step 5: No commit

Git operations only. Nothing to commit.

---

## Done criteria for PR 1

When all of the following are true, PR 1 is complete:

- [ ] All 13 tasks committed on `feature/codex_support`
- [ ] `python -m pytest tests/ -v` passes
- [ ] `python3 scripts/verify_sync.py` passes
- [ ] Manual smoke test against a fresh fixture project succeeds for `--target=codex`, `--target=claude`, and `--target=both`
- [ ] `--target=auto` correctly resolves based on detected `~/.codex` and `~/.claude` directories
- [ ] Existing Claude users see ZERO behavior change when running `npx @bitraptors/archie .` (no flag)
- [ ] Branch pushed to origin
- [ ] Draft PR created with "DO NOT MERGE" disclaimer
- [ ] No new runtime dependencies, no new dev dependencies

## What this PR explicitly does NOT do

These belong to later PRs and must not be added here even if tempting:

- Deep-scan workflow → PR 2
- Wave 1 / Wave 2 sub-agent prompts (`wave1_*.md`, `wave2_reasoning.md`) → PR 2
- Codex agent TOMLs (`spawn_agent` parallelism) → PR 2
- `.codex/config.toml` editing or feature flag enablement → PR 2
- Codex hooks (`.codex/hooks.json`, Stop hook, pre-commit) → PR 3
- Per-folder `AGENTS.md` from `intent_layer.py` → PR 4
- README updates documenting Codex support → PR 5
- CHANGELOG entry, version bump → PR 5

If any of these become necessary mid-PR-1, stop and add a deferred-decision note to the design doc instead of expanding scope.

---

## References

- Design doc: `docs/plans/2026-04-09-codex-cli-support-design.md`
- Existing sync pattern: `scripts/verify_sync.py` (extend, don't replace)
- File sync rules: `CLAUDE.md` § "File Sync"
- Memory: `feedback_simplicity_first.md` (default to smallest viable design)
- Memory: `feedback_feature_branches.md` (multi-PR initiatives use feature branches; never auto-merge to main)
- Memory: `feedback_iterative_over_batch.md` (no batch one-shot scans)

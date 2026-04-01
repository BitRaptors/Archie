# Incremental Deep Scan — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `--incremental` mode to `/archie-deep-scan` — only process changed files and affected folders. Default behavior (full baseline) remains unchanged. Incremental auto-falls back to full when changes are too large.

**Architecture:** Change detection via git diff against last deep scan commit SHA (stored in `.archie/last_deep_scan.json`). Threshold logic decides single-agent vs multi-agent. Intent layer gets `--only-folders` to scope re-enrichment. merge.py and finalize.py get `--patch` modes. The deep-scan slash command orchestrates it all.

**Tech Stack:** Python 3.9+ stdlib, git CLI

---

### Task 1: Change detection — `last_deep_scan.json` tracking

**Files:**
- Modify: `archie/standalone/intent_layer.py` (add to `cmd_deep_scan_state`)
- Modify: `.claude/commands/archie-deep-scan.md` (write marker after Step 9)

**Step 1: Add `save-baseline` subcommand to intent_layer.py**

Find the `cmd_deep_scan_state` function in `archie/standalone/intent_layer.py`. Add a new action `save-baseline` that writes `.archie/last_deep_scan.json`:

```python
elif action == "save-baseline":
    import subprocess
    try:
        sha = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
    except Exception:
        sha = ""
    from datetime import datetime, timezone
    marker = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "commit_sha": sha,
        "mode": step if isinstance(step, str) else "full",
    }
    (root / ".archie" / "last_deep_scan.json").write_text(
        json.dumps(marker, indent=2), encoding="utf-8"
    )
    print(f"Baseline saved: {sha[:8]}", file=sys.stderr)
```

The `step` parameter here is overloaded to pass the mode string ("full" or "incremental").

**Step 2: Add `detect-changes` subcommand**

Add another action that reads `last_deep_scan.json` and returns changed files:

```python
elif action == "detect-changes":
    import subprocess
    marker_path = root / ".archie" / "last_deep_scan.json"
    if not marker_path.exists():
        # No previous scan — everything is new
        print(json.dumps({"mode": "full", "reason": "no previous deep scan"}))
        return
    marker = json.loads(marker_path.read_text())
    sha = marker.get("commit_sha", "")
    if not sha:
        print(json.dumps({"mode": "full", "reason": "no commit SHA in marker"}))
        return
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", sha + "..HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        changed = [f for f in result.stdout.strip().split("\n") if f]
    except Exception:
        print(json.dumps({"mode": "full", "reason": "git diff failed"}))
        return
    # Count total files from scan.json
    scan = _load_json(root / ".archie" / "scan.json")
    total = len(scan.get("file_tree", []))
    ratio = len(changed) / max(total, 1)
    threshold_count = 30
    threshold_ratio = 0.20
    if len(changed) > threshold_count or ratio > threshold_ratio:
        mode = "full"
        reason = f"{len(changed)} files changed ({ratio:.0%}), exceeds threshold"
    else:
        mode = "incremental"
        reason = f"{len(changed)} files changed ({ratio:.0%})"
    # Identify affected folders
    affected_folders = set()
    for f in changed:
        parts = Path(f).parts
        for i in range(1, len(parts)):
            affected_folders.add(str(Path(*parts[:i])))
    print(json.dumps({
        "mode": mode,
        "reason": reason,
        "changed_files": changed,
        "changed_count": len(changed),
        "total_files": total,
        "ratio": round(ratio, 4),
        "affected_folders": sorted(affected_folders),
    }))
```

**Step 3: Wire up the CLI dispatcher**

In the CLI dispatcher at the bottom of intent_layer.py, add the new actions to the `deep-scan-state` subcmd handler. The `save-baseline` action takes a mode string instead of step number. The `detect-changes` action takes no extra args.

**Step 4: Test manually**

```bash
# On a repo with an existing deep scan:
python3 archie/standalone/intent_layer.py deep-scan-state /path/to/repo save-baseline full
cat /path/to/repo/.archie/last_deep_scan.json

# Make a change, then:
python3 archie/standalone/intent_layer.py deep-scan-state /path/to/repo detect-changes
```

**Step 5: Commit**

```bash
git add archie/standalone/intent_layer.py
git commit -m "feat: change detection for incremental deep scan — detect-changes + save-baseline"
```

---

### Task 2: Intent layer `--only-folders` support

**Files:**
- Modify: `archie/standalone/intent_layer.py` (`cmd_prepare`, `cmd_next_ready`)

**Step 1: Add `--only-folders` to `cmd_prepare`**

The current `cmd_prepare` builds a DAG of ALL folders. Add an optional parameter `only_folders: list[str] | None = None`. When set:
- Still build the full DAG (needed for parent chain)
- But mark only the specified folders + their parent chain as "dirty"
- `cmd_next_ready` should only return folders that are in the dirty set

Modify `cmd_prepare` signature:

```python
def cmd_prepare(root: Path, only_folders: list[str] | None = None):
```

After building the full DAG and writing `enrich_batches.json`, if `only_folders` is set:
- Compute the dirty set: `only_folders` + all ancestors of each folder up to root
- Write `"dirty_folders"` key into `enrich_batches.json`

```python
if only_folders:
    dirty = set()
    for f in only_folders:
        dirty.add(f)
        parts = Path(f).parts
        for i in range(1, len(parts)):
            ancestor = str(Path(*parts[:i]))
            if ancestor in folders_info:
                dirty.add(ancestor)
    plan["dirty_folders"] = sorted(dirty)
    print(f"Incremental: {len(dirty)} dirty folders (of {len(qualifying)} total)", file=sys.stderr)
```

**Step 2: Filter `cmd_next_ready` by dirty set**

In `cmd_next_ready`, after computing the `ready` list, filter by dirty folders if the key exists:

```python
dirty = set(plan.get("dirty_folders", []))
if dirty:
    ready = [f for f in ready if f in dirty]
```

**Step 3: Wire CLI — add `--only-folders` flag to `prepare` subcommand**

In the CLI dispatcher, parse `--only-folders folder1,folder2,...` and pass to `cmd_prepare`.

**Step 4: Test**

```bash
# Full prepare (all 107 folders):
python3 .archie/intent_layer.py prepare /path/to/repo

# Incremental (only 5 folders + parents):
python3 .archie/intent_layer.py prepare /path/to/repo --only-folders app/src/main/java/com/bitraptors/babyweather/page_dashboard/fragment,app/src/main/java/com/bitraptors/babyweather/common/domain

# Check that next-ready only returns dirty folders:
python3 .archie/intent_layer.py next-ready /path/to/repo
```

**Step 5: Commit**

```bash
git add archie/standalone/intent_layer.py
git commit -m "feat: intent layer --only-folders for incremental enrichment"
```

---

### Task 3: merge.py `--patch` mode

**Files:**
- Modify: `archie/standalone/merge.py`

**Step 1: Add `--patch` flag handling**

Current merge.py takes: `merge.py /path/to/repo output1.json [output2.json ...]` and writes a fresh `blueprint_raw.json`.

Add `--patch` mode: `merge.py /path/to/repo --patch incremental.json`

When `--patch` is set:
1. Read existing `blueprint_raw.json`
2. Read incremental findings JSON
3. Deep-merge incremental into existing (using existing `deep_merge` function)
4. Write updated `blueprint_raw.json`

In the `main()` function:

```python
if len(sys.argv) >= 4 and sys.argv[2] == "--patch":
    patch_file = sys.argv[3]
    root = Path(sys.argv[1]).resolve()
    bp_raw = root / ".archie" / "blueprint_raw.json"
    if not bp_raw.exists():
        print("Error: no existing blueprint_raw.json to patch", file=sys.stderr)
        sys.exit(1)
    existing = json.loads(bp_raw.read_text())
    patch_text = Path(patch_file).read_text()
    patch_data = extract_json_from_text(patch_text)
    if not patch_data:
        print("Error: could not extract JSON from patch file", file=sys.stderr)
        sys.exit(1)
    merged = deep_merge(existing, patch_data)
    # Deduplicate components by name
    comps = merged.get("components", {})
    if isinstance(comps, dict) and "components" in comps:
        seen = {}
        deduped = []
        for c in comps["components"]:
            name = c.get("name", "")
            if name in seen:
                # Update existing with new data
                seen[name].update(c)
            else:
                seen[name] = c
                deduped.append(c)
        comps["components"] = deduped
    bp_raw.write_text(json.dumps(merged, indent=2, ensure_ascii=False))
    comp_count = len(merged.get("components", {}).get("components", []))
    print(f"  Patched blueprint_raw.json ({comp_count} components)", file=sys.stderr)
    sys.exit(0)
```

**Step 2: Test**

```bash
# Create a small incremental JSON:
echo '{"components": {"components": [{"name": "NewFeature", "location": "app/new/", "responsibility": "test"}]}}' > /tmp/test_patch.json

# Patch existing blueprint:
python3 .archie/merge.py /path/to/repo --patch /tmp/test_patch.json

# Verify the new component was added:
python3 -c "import json; bp=json.load(open('/path/to/repo/.archie/blueprint_raw.json')); print([c['name'] for c in bp.get('components',{}).get('components',[])])"
```

**Step 3: Commit**

```bash
git add archie/standalone/merge.py
git commit -m "feat: merge.py --patch mode for incremental blueprint updates"
```

---

### Task 4: finalize.py `--patch` mode

**Files:**
- Modify: `archie/standalone/finalize.py`

**Step 1: Add `--patch` flag handling**

Current finalize.py takes: `finalize.py /path/to/repo [agent_x_output.json]` and runs the full pipeline (merge Agent X → normalize → render → hooks → validate).

Add `--patch` mode: `finalize.py /path/to/repo --patch incremental_reasoning.json`

When `--patch`:
1. Read existing `blueprint.json`
2. Read incremental reasoning output
3. Extract JSON from the reasoning output
4. Deep-merge into existing blueprint (update decisions, trade-offs, pitfalls — only sections present in the patch)
5. Re-run renderer (to regenerate CLAUDE.md, AGENTS.md, rule files from updated blueprint)
6. Re-run validator
7. Skip hooks installation (already installed)

In the `finalize` function, add a `patch_mode` parameter:

```python
def finalize(root: Path, agent_x_file: str | None = None, patch_mode: bool = False):
    if patch_mode and agent_x_file:
        # Read existing blueprint
        bp_path = archie_dir / "blueprint.json"
        if not bp_path.exists():
            print("Error: no existing blueprint.json to patch", file=sys.stderr)
            sys.exit(1)
        bp = json.loads(bp_path.read_text())
        # Read and merge patch
        merge_mod = _import_sibling("merge")
        patch_text = Path(agent_x_file).read_text()
        patch_data = merge_mod.extract_json_from_text(patch_text)
        if patch_data:
            bp = merge_mod.deep_merge(bp, patch_data)
            bp_path.write_text(json.dumps(bp, indent=2, ensure_ascii=False))
            print(f"  Patched blueprint.json", file=sys.stderr)
        # Still render and validate from updated blueprint
        # (falls through to existing render/validate logic)
```

Wire in CLI: check for `--patch` in sys.argv.

**Step 2: Test**

```bash
# Patch with incremental reasoning:
python3 .archie/finalize.py /path/to/repo --patch /tmp/incremental_reasoning.json

# Verify blueprint updated and CLAUDE.md regenerated:
head -20 /path/to/repo/CLAUDE.md
```

**Step 3: Commit**

```bash
git add archie/standalone/finalize.py
git commit -m "feat: finalize.py --patch mode for incremental reasoning merge"
```

---

### Task 5: Update deep-scan command — incremental orchestration

**Files:**
- Modify: `.claude/commands/archie-deep-scan.md`

**Step 1: Add `--incremental` flag to the preamble**

After the existing flag parsing (`--from N`, `--continue`), add `--incremental` handling:

```markdown
**If `--incremental` is present:**
1. Check if `.archie/blueprint.json` exists. If not: print "No existing blueprint — running full baseline instead." Set SCAN_MODE = "full".
2. If blueprint exists, detect changes:
\`\`\`bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" detect-changes
\`\`\`
3. Read the JSON output. If `mode` is "full" (threshold exceeded): print "Too many changes (N files, X%) — running full baseline." Set SCAN_MODE = "full".
4. If `mode` is "incremental":
   - Set SCAN_MODE = "incremental"
   - Save the `changed_files` list and `affected_folders` list
   - Print: "Incremental deep scan: N files changed since last baseline. Analyzing changes only."
5. Set START_STEP = 1

**If no flags (default — full baseline, unchanged behavior):**
1. Set SCAN_MODE = "full", START_STEP = 1
2. Initialize fresh state (same as today)
```

**Step 2: Modify Step 3 (Wave 1) for incremental mode**

Add conditional logic:

```markdown
**If SCAN_MODE = "incremental":**

Spawn a single **Sonnet subagent** with:
- The changed file list (from detect-changes output)
- The existing `.archie/blueprint_raw.json`
- Skeletons for changed files only (filter from .archie/skeletons.json)

Agent prompt:
> You have the existing architectural blueprint and a list of files that changed since the last analysis. Read the changed files and their skeletons. Report what changed architecturally:
> - New or modified components (name, location, responsibility, depends_on)
> - Changed communication patterns
> - New technology/dependencies
> - Modified file placement patterns
>
> Return the same JSON structure as the full analysis but ONLY for sections affected by the changes. Unchanged sections should be omitted (they'll be preserved from the existing blueprint).

Save output to `/tmp/archie_incremental_$PROJECT_NAME.json`.

**If SCAN_MODE = "full":**
Same as today — 3 agents (or 4 with UI Layer).
```

**Step 3: Modify Step 4 (Merge) for incremental mode**

```markdown
**If SCAN_MODE = "incremental":**
\`\`\`bash
python3 .archie/merge.py "$PROJECT_ROOT" --patch /tmp/archie_incremental_$PROJECT_NAME.json
\`\`\`

**If SCAN_MODE = "full":**
Same as today.
```

**Step 4: Modify Step 5 (Wave 2 Reasoning) for incremental mode**

```markdown
**If SCAN_MODE = "incremental":**

Spawn **Opus subagent** with:
- Existing `.archie/blueprint.json` (full current architecture)
- The incremental diff (what changed from Step 4)
- Changed file contents

Agent prompt:
> The architecture was previously analyzed (blueprint attached). These files changed and the structural analysis was updated. Review the changes and update ONLY the affected sections:
> - If changes affect a key decision, update it
> - If changes introduce a new trade-off or invalidate an existing one, update trade_offs
> - If changes trigger or resolve a pitfall, update pitfalls
> - Add/update the decision_chain only for affected branches
> Return ONLY the sections that need updating. Unchanged sections will be preserved.

Save and finalize:
\`\`\`bash
python3 .archie/finalize.py "$PROJECT_ROOT" --patch /tmp/archie_sub_x_$PROJECT_NAME.json
\`\`\`

**If SCAN_MODE = "full":**
Same as today.
```

**Step 5: Modify Step 6 (Rules) for incremental mode**

```markdown
**If SCAN_MODE = "incremental":**

Agent prompt addition:
> These are the existing rules. Only propose rules for patterns discovered in the changed files. Do not regenerate existing rules. If a change invalidates an existing rule, flag it for removal.

**If SCAN_MODE = "full":**
Same as today.
```

**Step 6: Modify Step 7 (Intent Layer) for incremental mode**

```markdown
**If SCAN_MODE = "incremental":**

Use the `affected_folders` list from change detection. Pass to prepare:
\`\`\`bash
python3 .archie/intent_layer.py prepare "$PROJECT_ROOT" --only-folders FOLDER1,FOLDER2,...
\`\`\`
This marks only affected folders + their parent chain as dirty. All subsequent `next-ready` calls only return dirty folders.

**If SCAN_MODE = "full":**
Same as today (prepare without --only-folders).
```

**Step 7: Add baseline marker save at end of Step 9**

After the existing Step 9 completion:
```markdown
Save baseline marker for future incremental runs:
\`\`\`bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" save-baseline SCAN_MODE
\`\`\`
(Replace SCAN_MODE with "full" or "incremental")
```

**Step 8: Test the full incremental flow**

Run on BabyWeather.Android (which already has a deep scan):
1. Make a small change to one file
2. Run `/archie-deep-scan` (should detect incremental mode)
3. Verify it only processes affected folders
4. Run `/archie-deep-scan --full` (should do full baseline)
5. Verify all artifacts are regenerated

**Step 9: Commit**

```bash
git add .claude/commands/archie-deep-scan.md
git commit -m "feat: incremental deep scan — default when blueprint exists, --full for baseline"
```

---

### Task 6: Sync and deploy

**Files:**
- Copy: all modified scripts to `npm-package/assets/`
- Copy: all modified commands to `npm-package/assets/`
- Copy: to BabyWeather.Android `.archie/` and `.claude/commands/`

**Step 1: Sync**

```bash
cp archie/standalone/intent_layer.py npm-package/assets/intent_layer.py
cp archie/standalone/merge.py npm-package/assets/merge.py
cp archie/standalone/finalize.py npm-package/assets/finalize.py
cp .claude/commands/archie-deep-scan.md npm-package/assets/archie-deep-scan.md
python3 scripts/verify_sync.py
```

**Step 2: Update BabyWeather.Android**

```bash
BW="/Users/hamutarto/DEV/BitRaptors/BabyWeather.Android"
cp archie/standalone/intent_layer.py "$BW/.archie/intent_layer.py"
cp archie/standalone/merge.py "$BW/.archie/merge.py"
cp archie/standalone/finalize.py "$BW/.archie/finalize.py"
cp .claude/commands/archie-deep-scan.md "$BW/.claude/commands/archie-deep-scan.md"
```

**Step 3: Create baseline marker for BabyWeather (so incremental works)**

```bash
python3 "$BW/.archie/intent_layer.py" deep-scan-state "$BW" save-baseline full
```

**Step 4: Test end-to-end**

In BabyWeather.Android:
- Run `/archie-deep-scan` — should detect "0 files changed" and skip most work
- Make a small edit, run `/archie-deep-scan` — should run incrementally
- Run `/archie-deep-scan --full` — should do full baseline

**Step 5: Commit**

```bash
git add archie/standalone/intent_layer.py archie/standalone/merge.py archie/standalone/finalize.py .claude/commands/archie-deep-scan.md npm-package/assets/
git commit -m "feat: incremental deep scan — complete pipeline with sync"
```

---

## Accuracy Safeguards

The incremental approach must maintain accuracy. These guards prevent drift:

1. **Threshold fallback** — if >30 files or >20% changed, auto-switch to full mode. Large changes need full re-analysis.

2. **Parent chain always updated** — when a leaf folder changes, every ancestor re-enriches using the updated child summary. No stale parent descriptions.

3. **Blueprint merge preserves all existing data** — `--patch` adds/updates but never deletes. Only a `--full` run can remove stale components.

4. **Periodic full baseline recommended** — the scan command should recommend `--full` every N incremental runs or after M weeks. Add this to the scan's re-baseline check in section 2f.

5. **Stale component detection** — if a file is deleted, detect-changes sees it in the git diff. The incremental agent should flag components whose location no longer exists.

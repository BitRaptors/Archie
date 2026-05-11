# Archie Deep Scan Modularization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `.claude/commands/archie-deep-scan.md` from a 1906-line monolith into a slim router + per-step files under `archie-deep-scan/{steps,fragments,templates}/`, mirroring the tree into `npm-package/assets/` and collapsing the duplicated Phase 0 into a reference to the existing `_shared/scope_resolution.md`.

**Architecture:** Pure file movement — no behavioral change. The router stays at the same path so `/archie-deep-scan` UX is unchanged. Each step file is self-contained; the router contains only activation + a routing table that tells the AI which file to Read before starting each step. Cross-cutting concerns (telemetry, resume contract, scope resolution) live as fragments loaded once at activation.

**Tech Stack:** Markdown only. Two Python/JS edits (verify_sync.py + archie.mjs) to teach the install tooling about the new tree shape.

**Spec:** `docs/superpowers/specs/2026-05-11-archie-deep-scan-modular-design.md`

---

## File structure (target end-state)

**New canonical files:**
```
.claude/commands/archie-deep-scan.md                        ← slim router (~150 lines)
.claude/commands/archie-deep-scan/
  steps/
    step-1-scanner.md
    step-2-read-scan.md
    step-3-wave1/
      orchestration.md
      structure-agent.md
      patterns-agent.md
      technology-agent.md
      ui-layer-agent.md
      grounding-rules.md
    step-4-merge.md
    step-5-wave2-reasoning.md
    step-6-rule-synthesis.md
    step-7-intent-layer.md
    step-8-cleanup.md
    step-9-drift.md
    step-10-telemetry.md
  fragments/
    telemetry-conventions.md
    compact-resume-contract.md
    resume-prelude.md
  templates/
    scan-report.md
```

Mirrored at `npm-package/assets/` with identical tree, plus a new mirror of the existing `.claude/commands/_shared/scope_resolution.md` at `npm-package/assets/_shared/scope_resolution.md` (this file is currently NOT in the npm asset bundle — see Task 2).

**Modified files:**
- `scripts/verify_sync.py` — recursive walk for new subtree + `_shared/` (Task 1)
- `npm-package/bin/archie.mjs` — recursive copy + `_shared/` + gitignore block (Task 2)
- `.claude/commands/archie-deep-scan.md` — shrunk to ~150-line router (Task 14)

---

## Conventions

**Each extraction task follows the same pattern:**

1. Read the exact line range from `.claude/commands/archie-deep-scan.md`.
2. Create the new canonical file with that content (verbatim — do not edit prose).
3. Replace the original lines in the router with a 2-line breadcrumb comment that points at the new file. (The router's "real" reorganization comes in Task 14; intermediate state just leaves a stub.)
4. Copy the new file to `npm-package/assets/` at the mirrored path.
5. Run `python3 scripts/verify_sync.py` → expect PASS.
6. Run a sanity check: `diff <(awk '/^## Step N:/,/^## Step .+:/' archie-deep-scan-before.md) <new-file>` to confirm the content moved cleanly. (Use the snapshot from Task 0 as `archie-deep-scan-before.md`.)
7. Commit with the per-task message.

**Intermediate router state during Tasks 3-13:** the router shrinks gradually. Each extraction replaces its inline content with a one-line marker like:
```
<!-- archie:extracted -> archie-deep-scan/steps/step-N-<name>.md -->
```
These markers get cleaned up and replaced with the proper routing table in Task 14.

**Why this intermediate shape:** during the migration, the router file still works as a slash command — anyone who runs `/archie-deep-scan` between Task 5 and Task 14 will see "this content lives in `archie-deep-scan/steps/step-5...md`" instead of the actual content. The AI can Read the referenced file. This isn't pretty but it keeps every commit functional rather than risking a 12-step "everything is broken" window.

---

### Task 0: Snapshot the current file for reference

**Files:** none modified.

**Why:** Several later tasks need to confirm that extracted content matches the original byte-for-byte. We snapshot before any edits and stash it outside the repo.

- [ ] **Step 1: Snapshot the current canonical file**

```bash
cp .claude/commands/archie-deep-scan.md /tmp/archie-deep-scan-before.md
wc -l /tmp/archie-deep-scan-before.md
```
Expected: `1906 /tmp/archie-deep-scan-before.md`.

- [ ] **Step 2: Snapshot the npm-package mirror too (for safety)**

```bash
cp npm-package/assets/archie-deep-scan.md /tmp/archie-deep-scan-asset-before.md
diff /tmp/archie-deep-scan-before.md /tmp/archie-deep-scan-asset-before.md
```
Expected: no output (files identical — verify_sync invariant).

- [ ] **Step 3: No commit** (snapshot files live in /tmp).

---

### Task 1: Extend `verify_sync.py` to walk the new subtree

**Files:**
- Modify: `scripts/verify_sync.py`

**Why:** The current verifier matches flat `archie-*.md` only (line 54-55). Once we start adding files under `.claude/commands/archie-deep-scan/`, it won't see them and will silently miss drift. We update it BEFORE any extraction so subsequent tasks can rely on `verify_sync.py` as the gate.

The new logic walks:
- `.claude/commands/archie-*.md` (top-level commands — unchanged behavior)
- `.claude/commands/archie-deep-scan/**/*.md` (the new subtree)
- `.claude/commands/_shared/*.md` (the shared fragments — currently not mirrored at all; this task makes the verifier require the mirror to exist)

And matches them against the same relative paths under `npm-package/assets/`.

- [ ] **Step 1: Read current `verify_sync.py`** to confirm line numbers haven't drifted

```bash
sed -n '50,80p' scripts/verify_sync.py
```
Expected: `command_mds = {f.name for f in COMMANDS.glob("archie-*.md")}` at ~line 55.

- [ ] **Step 2: Replace the flat-glob discovery + check block (lines ~54-76)**

Find this block:
```python
    asset_mds = {f.name for f in ASSETS.glob("archie-*.md")}
    command_mds = {f.name for f in COMMANDS.glob("archie-*.md")}
```

Replace with:
```python
    # Command markdown files — both top-level (archie-*.md) and the recursive
    # subtree under archie-deep-scan/ (introduced by the modularization
    # refactor). Plus _shared/ which holds cross-command fragments.
    def _collect_command_mds(base: Path) -> set[str]:
        out: set[str] = set()
        for p in base.glob("archie-*.md"):
            if p.is_file():
                out.add(p.name)
        for sub in ("archie-deep-scan", "_shared"):
            sub_dir = base / sub
            if sub_dir.is_dir():
                for p in sub_dir.rglob("*.md"):
                    out.add(str(p.relative_to(base)))
        return out

    asset_mds = _collect_command_mds(ASSETS)
    command_mds = _collect_command_mds(COMMANDS)
```

Then find the existence-check block:
```python
    # 4. Check: every command .md should have an asset copy
    for name in sorted(command_mds - asset_mds):
        errors.append(f"MISSING ASSET: .claude/commands/{name} has no copy in npm-package/assets/")
    for name in sorted(asset_mds - command_mds):
        errors.append(f"ORPHAN ASSET: npm-package/assets/{name} has no canonical in .claude/commands/")
```
(No edit needed — the strings `name` will now be relative paths like `archie-deep-scan/steps/step-1-scanner.md`, which renders cleanly in the error message.)

And the content-equality block at the bottom:
```python
    for name in sorted(command_mds & asset_mds):
        canonical = (COMMANDS / name).read_text()
        asset = (ASSETS / name).read_text()
        if canonical != asset:
            errors.append(f"OUT OF SYNC: {name} differs between .claude/commands/ and npm-package/assets/")
```
(No edit needed — `Path / str` correctly handles `Path / "archie-deep-scan/steps/step-1-scanner.md"`.)

- [ ] **Step 3: Run the verifier — expect drift**

```bash
python3 scripts/verify_sync.py
```
Expected: `SYNC CHECK FAILED` reporting `MISSING ASSET: .claude/commands/_shared/scope_resolution.md has no copy in npm-package/assets/`. This is the existing drift the verifier now sees. Task 2 fixes it.

- [ ] **Step 4: Mirror `_shared/scope_resolution.md` to assets to satisfy the new check**

```bash
mkdir -p npm-package/assets/_shared
cp .claude/commands/_shared/scope_resolution.md npm-package/assets/_shared/scope_resolution.md
python3 scripts/verify_sync.py
```
Expected: `SYNC CHECK PASSED`.

- [ ] **Step 5: Commit**

```bash
git add scripts/verify_sync.py npm-package/assets/_shared/scope_resolution.md
git commit -m "$(cat <<'EOF'
chore(sync): teach verify_sync to walk archie-deep-scan/ + _shared/ subtrees

Adds recursive discovery for .claude/commands/archie-deep-scan/**/*.md
and .claude/commands/_shared/*.md so subsequent extraction commits can
rely on verify_sync as the drift gate. Also mirrors the existing
_shared/scope_resolution.md into npm-package/assets/_shared/ to fix
the drift this newly enables the verifier to see.

EOF
)"
```

---

### Task 2: Update `archie.mjs` installer for the new tree

**Files:**
- Modify: `npm-package/bin/archie.mjs`

**Why:** When a user runs `npx @bitraptors/archie /path/to/project`, the installer copies asset files into the project. Today it iterates a hardcoded array of single filenames (line ~98) and writes them flat. After our refactor the deep-scan command depends on a subtree of files plus `_shared/scope_resolution.md` — without an installer update, npm-installed users get a broken `/archie-deep-scan` once the router stops being self-contained (Task 14).

The installer's cleanup block (line ~63) also needs to know about the subtree so re-installs don't leave stale files behind.

- [ ] **Step 1: Read the current installer command-copy block (lines ~98-106)**

```bash
sed -n '95,115p' npm-package/bin/archie.mjs
```

- [ ] **Step 2: Add a recursive copy helper near the top of the file**

Find the imports block (top of file). After the existing `import { ... } from "node:fs"` line, add `readdirSync` and `statSync` to the imports if not already present. Then add this helper function near the other top-level helpers (above the `for (const cmd of ...)` block, around line 95):

```javascript
function copyDirRecursive(srcDir, destDir) {
  if (!existsSync(srcDir)) return [];
  mkdirSync(destDir, { recursive: true });
  const copied = [];
  for (const entry of readdirSync(srcDir, { withFileTypes: true })) {
    const srcPath = join(srcDir, entry.name);
    const destPath = join(destDir, entry.name);
    if (entry.isDirectory()) {
      copied.push(...copyDirRecursive(srcPath, destPath));
    } else if (entry.isFile()) {
      writeFileSync(destPath, readFileSync(srcPath, "utf8"));
      copied.push(destPath);
    }
  }
  return copied;
}
```

- [ ] **Step 3: After the existing command-copy `for` loop (line ~106), append recursive copies**

Find:
```javascript
for (const cmd of ["archie-scan.md", "archie-deep-scan.md", "archie-viewer.md", "archie-share.md", "archie-intent-layer.md"]) {
  const src = join(ASSETS, cmd);
  const dest = join(claudeCommands, cmd);
  if (existsSync(src)) {
    writeFileSync(dest, readFileSync(src, "utf8"));
    console.log(`  ${GREEN}✓${RESET} ${commandsDirRel}/${cmd}`);
  }
}
```

Immediately after that closing `}`, add:

```javascript
// Copy the archie-deep-scan/ subtree (steps, fragments, templates) introduced
// by the modular refactor. The subtree is required for /archie-deep-scan to
// work — the router file references files inside this subtree.
const deepScanSubtree = copyDirRecursive(
  join(ASSETS, "archie-deep-scan"),
  join(claudeCommands, "archie-deep-scan")
);
for (const p of deepScanSubtree) {
  const rel = p.substring(claudeCommands.length + 1);
  console.log(`  ${GREEN}✓${RESET} ${commandsDirRel}/${rel}`);
}

// Copy shared fragments referenced by multiple commands (e.g.
// _shared/scope_resolution.md used by archie-deep-scan's Phase 0).
const sharedSubtree = copyDirRecursive(
  join(ASSETS, "_shared"),
  join(claudeCommands, "_shared")
);
for (const p of sharedSubtree) {
  const rel = p.substring(claudeCommands.length + 1);
  console.log(`  ${GREEN}✓${RESET} ${commandsDirRel}/${rel}`);
}
```

- [ ] **Step 4: Update the cleanup block to remove the subtree on re-install**

Find the cleanup block (line ~60-68):
```javascript
// Remove all archie-*.md commands from .claude/commands/
if (existsSync(claudeCommands)) {
  for (const f of readdirSync(claudeCommands)) {
    if (f.startsWith("archie-") && f.endsWith(".md")) {
      try { unlinkSync(join(claudeCommands, f)); cleanedCount++; } catch {}
    }
  }
}
```

Replace with:
```javascript
// Remove all archie-*.md commands from .claude/commands/ and the
// archie-deep-scan/ subtree introduced by the modular refactor.
if (existsSync(claudeCommands)) {
  for (const f of readdirSync(claudeCommands)) {
    if (f.startsWith("archie-") && f.endsWith(".md")) {
      try { unlinkSync(join(claudeCommands, f)); cleanedCount++; } catch {}
    }
  }
  const deepScanDir = join(claudeCommands, "archie-deep-scan");
  if (existsSync(deepScanDir)) {
    try { rmSync(deepScanDir, { recursive: true, force: true }); cleanedCount++; } catch {}
  }
  // Do NOT delete _shared/ wholesale — other tools may live alongside.
  // Only remove the scope_resolution.md file we installed.
  const sharedFile = join(claudeCommands, "_shared", "scope_resolution.md");
  if (existsSync(sharedFile)) {
    try { unlinkSync(sharedFile); cleanedCount++; } catch {}
  }
}
```

Make sure `rmSync` is imported at the top from `"node:fs"`.

- [ ] **Step 5: Update the gitignore block (around line 148)**

Find:
```javascript
const archieGitignoreBlock = `\n# Archie (installed tooling — outputs are NOT ignored)\n.archie/*.py\n.archie/__pycache__/\n.archie/platform_rules.json\n.claude/commands/archie-*.md\n.claude/hooks/\n.claude/settings.local.json\n`;
```

Replace with:
```javascript
const archieGitignoreBlock = `\n# Archie (installed tooling — outputs are NOT ignored)\n.archie/*.py\n.archie/__pycache__/\n.archie/platform_rules.json\n.claude/commands/archie-*.md\n.claude/commands/archie-deep-scan/\n.claude/commands/_shared/scope_resolution.md\n.claude/hooks/\n.claude/settings.local.json\n`;
```

- [ ] **Step 6: Smoke-test the installer locally**

```bash
mkdir -p /tmp/archie-installer-test
cd /tmp/archie-installer-test
node /Users/csacsi/DEV/Archie/npm-package/bin/archie.mjs .
ls -R .claude/commands/
ls -R .archie/ | head -20
```

Expected: a `.claude/commands/archie-deep-scan/` directory and a `.claude/commands/_shared/scope_resolution.md` file exist (currently empty subtree apart from `_shared/scope_resolution.md` — the deep-scan subtree fills up in later tasks; the installer should still create the dir gracefully even when it's empty).

Cleanup: `rm -rf /tmp/archie-installer-test` and `cd /Users/csacsi/DEV/Archie`.

- [ ] **Step 7: Run verify_sync — still expect pass**

```bash
python3 scripts/verify_sync.py
```
Expected: `SYNC CHECK PASSED`.

- [ ] **Step 8: Commit**

```bash
git add npm-package/bin/archie.mjs
git commit -m "$(cat <<'EOF'
chore(installer): recursive copy for archie-deep-scan/ subtree + _shared/

Adds copyDirRecursive helper and uses it to mirror the new modularized
deep-scan tree plus _shared/scope_resolution.md into installed projects.
Cleanup logic and the gitignore block updated to match.

EOF
)"
```

---

### Task 3: Verify `_shared/scope_resolution.md` is identical to inline Phase 0

**Files:** none modified.

**Why:** The spec says we can collapse the duplicated Phase 0 to a reference to the existing shared file. That only works if the shared file is content-identical (or a strict superset of) the inline Phase 0. We check before relying on this assumption.

- [ ] **Step 1: Extract lines 119-255 of the router (the inline Phase 0)**

```bash
sed -n '119,255p' /tmp/archie-deep-scan-before.md > /tmp/phase-0-inline.md
wc -l /tmp/phase-0-inline.md
```
Expected: 137 lines.

- [ ] **Step 2: Read the shared file**

```bash
wc -l .claude/commands/_shared/scope_resolution.md
```
Note the line count.

- [ ] **Step 3: Diff the two**

```bash
diff /tmp/phase-0-inline.md .claude/commands/_shared/scope_resolution.md > /tmp/phase-0-diff.txt
wc -l /tmp/phase-0-diff.txt
cat /tmp/phase-0-diff.txt
```

Three outcomes:

- **A) No diff (file is identical):** safe to reference the shared file as-is.
- **B) Diff is whitespace / heading / wrapping noise only:** still safe — log the differences for the commit message and proceed.
- **C) Diff includes substantive content changes:** the inline version drifted from the shared one. Pause and report findings to the user: "Phase 0 has drifted from `_shared/scope_resolution.md` in the following ways: [list]. Should I (i) update the shared file to match the inline one, (ii) keep the shared one and accept the inline differences are lost, or (iii) keep Phase 0 inline and skip the dedup?"

- [ ] **Step 4: If A or B — no action needed beyond noting the diff. If C — escalate to user before continuing.**

- [ ] **Step 5: No commit** (verification only).

---

### Task 4: Extract three fragments + scan-report template

**Files:**
- Create: `.claude/commands/archie-deep-scan/fragments/telemetry-conventions.md`
- Create: `.claude/commands/archie-deep-scan/fragments/compact-resume-contract.md`
- Create: `.claude/commands/archie-deep-scan/fragments/resume-prelude.md`
- Create: `.claude/commands/archie-deep-scan/templates/scan-report.md`
- Mirror all 4 to `npm-package/assets/archie-deep-scan/{fragments,templates}/...`
- Modify: `.claude/commands/archie-deep-scan.md` — replace 4 inline blocks with stubs

**Why this is the first extraction:** fragments and templates have the lowest semantic coupling. Each is a self-contained block. If the pattern works here, it works for steps too.

**Source line ranges** (per the snapshot taken in Task 0, with the section headers grep verified at the start of Task 0):

| Source lines | Heading | Target file |
|---|---|---|
| 256-261 | `## Telemetry conventions` | fragments/telemetry-conventions.md |
| 262-273 | `## Compact-and-resume contract` | fragments/compact-resume-contract.md |
| 274-343 | `## Resume Prelude (runs whenever RESUME_ACTION=resume)` | fragments/resume-prelude.md |
| 1814-1884 | `# Archie Scan Report` markdown template (Step 9, inside the prose) | templates/scan-report.md |

The first three are clean section breaks. The 4th (scan-report.md) is a block embedded INSIDE Step 9's body — extract the markdown template block that starts with `# Archie Scan Report` and ends just before the next `## Step` boundary or before Step 9's `## Step 10` neighbor.

- [ ] **Step 1: Create the four target directories**

```bash
mkdir -p .claude/commands/archie-deep-scan/fragments
mkdir -p .claude/commands/archie-deep-scan/templates
mkdir -p npm-package/assets/archie-deep-scan/fragments
mkdir -p npm-package/assets/archie-deep-scan/templates
```

- [ ] **Step 2: Extract `telemetry-conventions.md` (lines 256-261)**

Read the exact lines:
```bash
sed -n '256,261p' /tmp/archie-deep-scan-before.md
```

Create `.claude/commands/archie-deep-scan/fragments/telemetry-conventions.md` with those lines verbatim — including the `## Telemetry conventions` heading. (We keep the heading so the file is intelligible as a standalone.)

Then mirror:
```bash
cp .claude/commands/archie-deep-scan/fragments/telemetry-conventions.md \
   npm-package/assets/archie-deep-scan/fragments/telemetry-conventions.md
```

- [ ] **Step 3: Extract `compact-resume-contract.md` (lines 262-273)**

Same pattern. Read lines, write to file, mirror.

- [ ] **Step 4: Extract `resume-prelude.md` (lines 274-343)**

Same pattern. The fenced bash blocks inside this section MUST be preserved verbatim including indentation, because the AI executes them as shell commands.

- [ ] **Step 5: Extract `scan-report.md` (lines 1814-1884)**

Read the lines first to confirm boundaries:
```bash
sed -n '1810,1890p' /tmp/archie-deep-scan-before.md
```

Find the precise boundaries of the markdown template block (look for the `# Archie Scan Report` header at the start and the line BEFORE the next `## Step` or end of template block). Extract those lines into `templates/scan-report.md`. Do NOT include the surrounding prose that says "use this template" — that prose stays in Step 9.

- [ ] **Step 6: Replace the four extracted blocks in the router with breadcrumb stubs**

For each extracted range, delete those lines from `.claude/commands/archie-deep-scan.md` and insert a single-line breadcrumb at the deletion point:

```
<!-- archie:extracted -> archie-deep-scan/fragments/telemetry-conventions.md -->
```

(And the equivalent for the other three files. The router's structure is preserved — just the body of each section is now a one-liner.)

- [ ] **Step 7: Mirror the modified router**

```bash
cp .claude/commands/archie-deep-scan.md npm-package/assets/archie-deep-scan.md
```

- [ ] **Step 8: Run verify_sync.py — expect PASS**

```bash
python3 scripts/verify_sync.py
```

- [ ] **Step 9: Confirm content preservation**

```bash
# Build a "what the router USED TO contain at lines 256-273" extract and
# compare against the concatenation of the 2 new fragment files.
cat /tmp/archie-deep-scan-before.md | sed -n '256,273p' > /tmp/expected-256-273.txt
cat .claude/commands/archie-deep-scan/fragments/telemetry-conventions.md \
    .claude/commands/archie-deep-scan/fragments/compact-resume-contract.md \
    > /tmp/actual-256-273.txt
diff /tmp/expected-256-273.txt /tmp/actual-256-273.txt
```
Expected: empty diff (the two fragments concatenated equal the original 18-line block).

- [ ] **Step 10: Commit**

```bash
git add .claude/commands/archie-deep-scan.md \
        .claude/commands/archie-deep-scan/fragments/ \
        .claude/commands/archie-deep-scan/templates/ \
        npm-package/assets/archie-deep-scan.md \
        npm-package/assets/archie-deep-scan/
git commit -m "refactor(deep-scan): extract telemetry, resume, scan-report fragments"
```

---

### Task 5: Extract simple Steps 1, 2, 4

**Files:**
- Create: `.claude/commands/archie-deep-scan/steps/step-1-scanner.md`
- Create: `.claude/commands/archie-deep-scan/steps/step-2-read-scan.md`
- Create: `.claude/commands/archie-deep-scan/steps/step-4-merge.md`
- Mirror each to `npm-package/assets/archie-deep-scan/steps/`
- Modify: router — replace 3 inline blocks with breadcrumbs

**Source line ranges:**

| Source lines | Heading | Target file |
|---|---|---|
| 344-362 | `## Step 1: Run the scanner` | steps/step-1-scanner.md |
| 363-382 | `## Step 2: Read scan results` | steps/step-2-read-scan.md |
| 926-987 | `## Step 4: Save Wave 1 output and merge` | steps/step-4-merge.md |

**Note:** these line numbers refer to the ORIGINAL `/tmp/archie-deep-scan-before.md`. After Task 4 removed earlier sections, the live router's line numbers have shifted — always extract from the snapshot, not from the live file.

- [ ] **Step 1: Create the steps directories**

```bash
mkdir -p .claude/commands/archie-deep-scan/steps
mkdir -p npm-package/assets/archie-deep-scan/steps
```

- [ ] **Step 2: Extract `step-1-scanner.md`**

```bash
sed -n '344,362p' /tmp/archie-deep-scan-before.md > /tmp/step-1.md
```

Review `/tmp/step-1.md` for sanity (heading present, no leaking content from neighbors). Then create `.claude/commands/archie-deep-scan/steps/step-1-scanner.md` with those contents.

- [ ] **Step 3: Extract `step-2-read-scan.md`** (lines 363-382)

Same pattern.

- [ ] **Step 4: Extract `step-4-merge.md`** (lines 926-987)

Same pattern. Step 4 is longer (62 lines) but still self-contained.

- [ ] **Step 5: Replace each section in the live router with a breadcrumb**

For each extracted range, find the corresponding section in the live `.claude/commands/archie-deep-scan.md` (search for the `## Step N:` heading — line numbers have shifted, but heading text is stable), delete the section body, and insert:

```
<!-- archie:extracted -> archie-deep-scan/steps/step-N-<name>.md -->
```

Keep the `## Step N:` heading in the router for now (Task 14 cleans it). The body underneath becomes the one-line breadcrumb.

- [ ] **Step 6: Mirror everything**

```bash
cp .claude/commands/archie-deep-scan.md npm-package/assets/archie-deep-scan.md
cp .claude/commands/archie-deep-scan/steps/step-1-scanner.md npm-package/assets/archie-deep-scan/steps/
cp .claude/commands/archie-deep-scan/steps/step-2-read-scan.md npm-package/assets/archie-deep-scan/steps/
cp .claude/commands/archie-deep-scan/steps/step-4-merge.md npm-package/assets/archie-deep-scan/steps/
```

- [ ] **Step 7: Run verify_sync — expect PASS**

```bash
python3 scripts/verify_sync.py
```

- [ ] **Step 8: Commit**

```bash
git add .claude/commands/archie-deep-scan.md \
        .claude/commands/archie-deep-scan/steps/ \
        npm-package/assets/archie-deep-scan.md \
        npm-package/assets/archie-deep-scan/steps/
git commit -m "refactor(deep-scan): extract Steps 1, 2, 4 into steps/"
```

---

### Task 6: Extract Steps 7, 8, 10

**Files:**
- Create: `.claude/commands/archie-deep-scan/steps/step-7-intent-layer.md`
- Create: `.claude/commands/archie-deep-scan/steps/step-8-cleanup.md`
- Create: `.claude/commands/archie-deep-scan/steps/step-10-telemetry.md`
- Mirror each + modified router

**Source line ranges:**

| Source lines | Heading | Target file |
|---|---|---|
| 1539-1613 | `## Step 7: Intent Layer — per-folder CLAUDE.md` | steps/step-7-intent-layer.md |
| 1614-1631 | `## Step 8: Clean up` | steps/step-8-cleanup.md |
| 1885-1906 | `## Step 10: Write telemetry` | steps/step-10-telemetry.md |

- [ ] **Step 1: Extract each section** using `sed -n` from `/tmp/archie-deep-scan-before.md`, write to the target file, mirror to assets.

- [ ] **Step 2: Replace each router section with the breadcrumb stub.**

- [ ] **Step 3: Mirror router + 3 new files to assets.**

- [ ] **Step 4: `python3 scripts/verify_sync.py` — expect PASS.**

- [ ] **Step 5: Commit**

```bash
git add .claude/commands/archie-deep-scan.md \
        .claude/commands/archie-deep-scan/steps/step-7-intent-layer.md \
        .claude/commands/archie-deep-scan/steps/step-8-cleanup.md \
        .claude/commands/archie-deep-scan/steps/step-10-telemetry.md \
        npm-package/assets/archie-deep-scan.md \
        npm-package/assets/archie-deep-scan/steps/step-7-intent-layer.md \
        npm-package/assets/archie-deep-scan/steps/step-8-cleanup.md \
        npm-package/assets/archie-deep-scan/steps/step-10-telemetry.md
git commit -m "refactor(deep-scan): extract Steps 7, 8, 10 into steps/"
```

---

### Task 7: Extract Step 9 (drift detection)

**Files:**
- Create: `.claude/commands/archie-deep-scan/steps/step-9-drift.md`
- Mirror to assets + modified router

**Source line range:** 1632-1813 (`## Step 9: Drift Detection & Architectural Assessment`).

**Special handling:** the Scan Report template (lines 1814-1884) was already extracted in Task 4 into `templates/scan-report.md`. Step 9's prose at lines ~1800-1814 likely says something like "use the template below" — that prose needs to be rewritten to say "Read `archie-deep-scan/templates/scan-report.md` and use it as the template for the report you write to `.archie/scan_report.md`."

- [ ] **Step 1: Extract lines 1632-1813 verbatim** to `.claude/commands/archie-deep-scan/steps/step-9-drift.md`.

- [ ] **Step 2: Find the prose that introduces the template** (typically the last 5-10 lines of Step 9's body). Rewrite it to reference the extracted template:

Find a sentence like "Write to `.archie/scan_report.md` using this template:" followed by the template block (which is no longer in this file). Replace with:

```markdown
Write to `.archie/scan_report.md` using the template at
`archie-deep-scan/templates/scan-report.md` — Read that file first if you
haven't already, then substitute the project-specific values in place of
the placeholder text.
```

- [ ] **Step 3: Replace the Step 9 body in the router with a breadcrumb.**

- [ ] **Step 4: Mirror router + new file to assets.**

- [ ] **Step 5: `python3 scripts/verify_sync.py` — expect PASS.**

- [ ] **Step 6: Commit**

```bash
git add .claude/commands/archie-deep-scan.md \
        .claude/commands/archie-deep-scan/steps/step-9-drift.md \
        npm-package/assets/archie-deep-scan.md \
        npm-package/assets/archie-deep-scan/steps/step-9-drift.md
git commit -m "refactor(deep-scan): extract Step 9 (drift detection) + template reference"
```

---

### Task 8: Extract Step 5 (Wave 2 reasoning)

**Files:**
- Create: `.claude/commands/archie-deep-scan/steps/step-5-wave2-reasoning.md`
- Mirror to assets + modified router

**Source line range:** 988-1285 (`## Step 5: Wave 2 — Reasoning agent`). This is the second-largest chunk (297 lines) and contains a single massive sub-agent prompt for the Opus reasoning pass.

- [ ] **Step 1: Extract lines 988-1285 verbatim** to `.claude/commands/archie-deep-scan/steps/step-5-wave2-reasoning.md`.

- [ ] **Step 2: Sanity-check** the extracted file is exactly 298 lines (988→1285 inclusive):
```bash
wc -l .claude/commands/archie-deep-scan/steps/step-5-wave2-reasoning.md
```

- [ ] **Step 3: Replace Step 5 body in router with breadcrumb.**

- [ ] **Step 4: Mirror + verify_sync — expect PASS.**

- [ ] **Step 5: Commit**

```bash
git add .claude/commands/archie-deep-scan.md \
        .claude/commands/archie-deep-scan/steps/step-5-wave2-reasoning.md \
        npm-package/assets/archie-deep-scan.md \
        npm-package/assets/archie-deep-scan/steps/step-5-wave2-reasoning.md
git commit -m "refactor(deep-scan): extract Step 5 (Wave 2 reasoning prompt)"
```

---

### Task 9: Extract Step 6 (Rule synthesis)

**Files:**
- Create: `.claude/commands/archie-deep-scan/steps/step-6-rule-synthesis.md`
- Mirror to assets + modified router

**Source line range:** 1286-1538 (`## Step 6: AI Rule Synthesis`). 252 lines. Contains the rule synthesis prompt, the rule schema, and the 4 worked examples updated in the earlier enforcement-topic-split PR.

- [ ] **Step 1: Extract lines 1286-1538 verbatim** to `.claude/commands/archie-deep-scan/steps/step-6-rule-synthesis.md`.

- [ ] **Step 2: Sanity-check** the extracted file is exactly 253 lines.

- [ ] **Step 3: Replace Step 6 body in router with breadcrumb.**

- [ ] **Step 4: Mirror + verify_sync — expect PASS.**

- [ ] **Step 5: Commit**

```bash
git add .claude/commands/archie-deep-scan.md \
        .claude/commands/archie-deep-scan/steps/step-6-rule-synthesis.md \
        npm-package/assets/archie-deep-scan.md \
        npm-package/assets/archie-deep-scan/steps/step-6-rule-synthesis.md
git commit -m "refactor(deep-scan): extract Step 6 (rule synthesis prompt)"
```

---

### Task 10: Extract Step 3 (Wave 1 orchestration + 4 sub-agent prompts + grounding rules)

**Files:**
- Create: `.claude/commands/archie-deep-scan/steps/step-3-wave1/orchestration.md`
- Create: `.claude/commands/archie-deep-scan/steps/step-3-wave1/structure-agent.md`
- Create: `.claude/commands/archie-deep-scan/steps/step-3-wave1/patterns-agent.md`
- Create: `.claude/commands/archie-deep-scan/steps/step-3-wave1/technology-agent.md`
- Create: `.claude/commands/archie-deep-scan/steps/step-3-wave1/ui-layer-agent.md`
- Create: `.claude/commands/archie-deep-scan/steps/step-3-wave1/grounding-rules.md`
- Mirror all to assets + modified router

**Source line range:** 383-925 (`## Step 3: Spawn analytical agents`). 542 lines. This is the most complex extraction because the section internally splits into:

- **Orchestration prelude** (~lines 383-424) — telemetry mark, incremental/full branching, scan mode dispatch logic, the "Bulk content — off-limits" rule.
- **Structure agent** (~lines 425-XXX) — full prompt body for the Structure sub-agent.
- **Patterns agent** — full prompt body.
- **Technology agent** — full prompt body.
- **UI Layer agent** — full prompt body.
- **GROUNDING RULES appendix** (typically at the END of the section, around lines 900-925) — shared rules that ALL 4 agents must follow.

The exact boundaries depend on the file's internal headings. The plan task BEGINS with a discovery step to find them.

- [ ] **Step 1: Map the internal headings of Step 3**

```bash
sed -n '383,925p' /tmp/archie-deep-scan-before.md | grep -n "^###\|^GROUNDING\|^## " | head -20
```

This prints every `###` sub-heading inside Step 3. Note the line numbers (relative to the start of Step 3 at line 383). Use these to determine the exact ranges for each of the 6 target files.

Expected sub-headings (roughly):
- `### Structure agent`
- `### Patterns agent`
- `### Technology agent`
- `### UI Layer agent` (only if frontend-relevant)
- A `### GROUNDING RULES` block at the end (could be `**GROUNDING RULES:**` instead — check both)

- [ ] **Step 2: Create the sub-directory**

```bash
mkdir -p .claude/commands/archie-deep-scan/steps/step-3-wave1
mkdir -p npm-package/assets/archie-deep-scan/steps/step-3-wave1
```

- [ ] **Step 3: Extract `grounding-rules.md` first** (it's referenced by all 4 agents)

Locate the grounding rules block (typically near the end of Step 3, ~lines 900-925). Extract those exact lines into `grounding-rules.md`. Add a short header at the top:

```markdown
# Wave 1 Grounding Rules

Shared rules that ALL four Wave 1 sub-agents must follow. The Step 3
orchestrator appends this file's body to every sub-agent prompt before
dispatching.
```

Followed verbatim by the extracted grounding-rules content.

- [ ] **Step 4: Extract each of the 4 sub-agent prompts**

For each sub-agent (Structure, Patterns, Technology, UI Layer):
- Locate the line range using the heading map from Step 1.
- The prompt body starts AFTER the `### <Name> agent` heading and ends BEFORE the next `### ` heading (or before the grounding rules block, whichever comes first).
- Write the prompt body verbatim into `<name>-agent.md`. Add a short header at the top:

```markdown
# <Name> Sub-Agent Prompt

Body for the Wave 1 <Name> sub-agent. Step 3's orchestrator passes the
contents of this file (with `grounding-rules.md` appended) as the `prompt`
argument to its Agent tool call.

---
```

Followed by the verbatim prompt content (without the `### <Name> agent`
heading itself — that's now in the file's title).

- [ ] **Step 5: Extract orchestration prelude**

The orchestration prelude is the content between `## Step 3: Spawn analytical agents` and the first `### Structure agent` (or whatever the first sub-agent is). It contains the telemetry mark, the incremental-vs-full branch, the scan-mode dispatch instructions, and the "Bulk content — off-limits" inheritance rule.

Extract that range into `orchestration.md`. Add a header:

```markdown
# Step 3: Wave 1 Orchestration

Telemetry mark, mode branching (incremental vs. full), and dispatch logic
for the four parallel Wave 1 sub-agents. After running this file, the AI
reads the 4 sub-agent prompt files plus `grounding-rules.md`, composes
them, and dispatches via the Agent tool.

---
```

Followed by the verbatim orchestration content.

- [ ] **Step 6: Rewrite the dispatch section of `orchestration.md` to reference the sub-files**

The orchestration's "spawn 3-4 Sonnet subagents in parallel" instruction in the original file flows directly into the inline sub-agent prompts. After extraction, that instruction must explicitly point at the files:

Find the line that reads (approximately):
```
Spawn 3–4 Sonnet subagents in parallel (Agent tool, `model: "sonnet"`), each focused on a different analytical concern.
```

Append immediately after it (or restructure the surrounding paragraph):
```markdown
**Dispatching the sub-agents:**

For each sub-agent below, Read the corresponding prompt file, then ALSO Read
`grounding-rules.md`, and pass the concatenated text (agent body + a blank
line + grounding rules) as the `prompt` parameter of the Agent tool call.

| Sub-agent | Prompt file | Spawn when |
|---|---|---|
| Structure | `archie-deep-scan/steps/step-3-wave1/structure-agent.md` | Always |
| Patterns | `archie-deep-scan/steps/step-3-wave1/patterns-agent.md` | Always |
| Technology | `archie-deep-scan/steps/step-3-wave1/technology-agent.md` | Always |
| UI Layer | `archie-deep-scan/steps/step-3-wave1/ui-layer-agent.md` | Only when `frontend_ratio >= 0.20` |

All four use `model: "sonnet"`. Dispatch in a single message so they run in parallel.
```

The rest of the orchestration prelude (telemetry, incremental branch, bulk content rule) stays as-is.

- [ ] **Step 7: Confirm no agent-prompt content is left behind in the router**

```bash
sed -n '/## Step 3:/,/## Step 4:/p' .claude/commands/archie-deep-scan.md | wc -l
```
Expected: around 5 lines (just the heading, the breadcrumb, blank lines, and the Step 4 heading). If significantly more, some agent content is still inline — recheck.

- [ ] **Step 8: Replace the Step 3 body in the router with a breadcrumb pointing at orchestration.md**

```
## Step 3: Spawn analytical agents
<!-- archie:extracted -> archie-deep-scan/steps/step-3-wave1/orchestration.md -->
```

- [ ] **Step 9: Mirror everything**

```bash
cp .claude/commands/archie-deep-scan.md npm-package/assets/archie-deep-scan.md
cp -R .claude/commands/archie-deep-scan/steps/step-3-wave1/ \
      npm-package/assets/archie-deep-scan/steps/step-3-wave1/
```

- [ ] **Step 10: `python3 scripts/verify_sync.py` — expect PASS.**

- [ ] **Step 11: Confirm content preservation**

The 6 new files concatenated (in order: orchestration, structure, patterns, technology, ui-layer, grounding-rules) should contain — modulo the file-header preambles we added — the same content as the original lines 383-925. Run an approximate check:

```bash
wc -l .claude/commands/archie-deep-scan/steps/step-3-wave1/*.md
# Total should be ~542 + small overhead from the 6 file headers (~30 lines)
```

- [ ] **Step 12: Commit**

```bash
git add .claude/commands/archie-deep-scan.md \
        .claude/commands/archie-deep-scan/steps/step-3-wave1/ \
        npm-package/assets/archie-deep-scan.md \
        npm-package/assets/archie-deep-scan/steps/step-3-wave1/
git commit -m "$(cat <<'EOF'
refactor(deep-scan): split Step 3 into orchestration + 4 sub-agents + grounding

Step 3's 542 lines now live in archie-deep-scan/steps/step-3-wave1/ —
orchestration.md handles dispatch, each Sonnet sub-agent's prompt body
lives in its own file, and grounding-rules.md is referenced by all four.

EOF
)"
```

---

### Task 11: Collapse the router — delete inline Phase 0, add the routing table

**Files:**
- Modify: `.claude/commands/archie-deep-scan.md` (final shape)
- Mirror to: `npm-package/assets/archie-deep-scan.md`

**Why this is last:** by now every step body has been extracted and replaced with a breadcrumb. The router file currently looks like a skeleton — section headings with `<!-- archie:extracted -> ... -->` comments underneath. Task 11 rewrites the router into its final clean shape.

The final shape:
1. Title + 1-paragraph description.
2. Args block (verbatim from the snapshot, currently around lines 13-21).
3. Preamble determining starting step (currently lines 22-118 — keep this; it's the boot logic that runs every time).
4. Activation sequence (Read fragments + _shared/scope_resolution.md).
5. Routing table (10 rows, one per step).
6. Loading discipline statement.

Inline Phase 0 (lines 119-255 of the original) is DELETED — its content lives in `_shared/scope_resolution.md` already (confirmed in Task 3).

- [ ] **Step 1: Read the current state of the router** to see all the breadcrumbs and headings

```bash
wc -l .claude/commands/archie-deep-scan.md
grep -n "^## \|archie:extracted" .claude/commands/archie-deep-scan.md
```

Note which sections still have inline content (should be none) and which have just heading + breadcrumb (most of them).

- [ ] **Step 2: Write the new router from scratch**

Open `.claude/commands/archie-deep-scan.md` and replace its entire content with:

```markdown
# Archie Deep Scan — Comprehensive Architecture Baseline

Generate a complete architectural baseline for the current project:
blueprint, rules, per-folder CLAUDE.md files, scan report, drift assessment.
A full deep scan takes 15–20 minutes; run it once when onboarding Archie to
a new codebase, then use `/archie-scan` for fast incremental health checks.

This command is a **router** — each step lives in its own file under
`archie-deep-scan/`. Before starting any step, Read the file listed in the
routing table below. Loading step files lazily (only when you reach each
step) keeps the conversation context lean.

## Args

[VERBATIM from /tmp/archie-deep-scan-before.md lines 13-21 — copy the
existing Args block.]

## Preamble: Determine starting step

[VERBATIM from /tmp/archie-deep-scan-before.md lines 22-118 — copy the
existing preamble. This sets START_STEP, RESUME_ACTION, SCAN_MODE etc.]

## Activation

Before running any step, Read these files in this order:

1. `archie-deep-scan/fragments/telemetry-conventions.md`
2. `archie-deep-scan/fragments/compact-resume-contract.md`
3. If `RESUME_ACTION=resume`: `archie-deep-scan/fragments/resume-prelude.md`
4. `_shared/scope_resolution.md` (this is the Phase 0 — scope resolution
   that every Archie command shares)

After reading those, `PROJECT_ROOT`, `PROJECT_NAME`, `SCOPE`,
`MONOREPO_TYPE`, `SCAN_MODE`, `START_STEP`, and the telemetry helpers
are all in place. Each step file assumes they exist.

## Step-by-step routing

Before starting any Step N, Read the file listed in the "Load this file"
column. The router does not contain step content — each step is a
self-contained file. If `START_STEP > N` (the Preamble decided to skip
some steps), do not Read or run those steps.

| Step | What it does | Load this file before starting |
|---|---|---|
| 1 | Run the scanner | `archie-deep-scan/steps/step-1-scanner.md` |
| 2 | Read scan results | `archie-deep-scan/steps/step-2-read-scan.md` |
| 3 | Wave 1 parallel agents | `archie-deep-scan/steps/step-3-wave1/orchestration.md` |
| 4 | Save & merge Wave 1 | `archie-deep-scan/steps/step-4-merge.md` |
| 5 | Wave 2 reasoning | `archie-deep-scan/steps/step-5-wave2-reasoning.md` |
| 6 | Rule synthesis | `archie-deep-scan/steps/step-6-rule-synthesis.md` |
| 7 | Intent Layer | `archie-deep-scan/steps/step-7-intent-layer.md` |
| 8 | Cleanup | `archie-deep-scan/steps/step-8-cleanup.md` |
| 9 | Drift detection | `archie-deep-scan/steps/step-9-drift.md` |
| 10 | Final telemetry | `archie-deep-scan/steps/step-10-telemetry.md` |

Step 3's orchestration file in turn references four sub-agent prompt files
plus a shared grounding-rules file — read those as the orchestration
instructs.
```

Use the snapshot at `/tmp/archie-deep-scan-before.md` to copy the Args block (lines 13-21) and the Preamble (lines 22-118) verbatim into the new router. Don't rewrite them — they're the boot logic and need to behave identically.

- [ ] **Step 3: Sanity-check the new router**

```bash
wc -l .claude/commands/archie-deep-scan.md
grep -n "^## " .claude/commands/archie-deep-scan.md
```

Expected: roughly 150-180 lines (Args + Preamble ~100 lines + new content ~50-80 lines). Headings: Args, Preamble, Activation, Step-by-step routing — no `## Step N` headings (the routing table replaces them), no `## Phase 0` (replaced by Activation).

- [ ] **Step 4: Confirm no orphan breadcrumbs remain**

```bash
grep -c "archie:extracted" .claude/commands/archie-deep-scan.md
```
Expected: 0.

- [ ] **Step 5: Mirror to assets**

```bash
cp .claude/commands/archie-deep-scan.md npm-package/assets/archie-deep-scan.md
```

- [ ] **Step 6: `python3 scripts/verify_sync.py` — expect PASS.**

- [ ] **Step 7: Run the full test suite to confirm no Python regression**

```bash
python -m pytest tests/ -v 2>&1 | tail -10
```
Expected: all pass (none of these tests should care about the markdown refactor).

- [ ] **Step 8: Commit**

```bash
git add .claude/commands/archie-deep-scan.md npm-package/assets/archie-deep-scan.md
git commit -m "$(cat <<'EOF'
refactor(deep-scan): collapse router — drop inline Phase 0, add routing table

Router now ~150 lines: title, args, preamble (boot logic), activation
(load fragments + _shared/scope_resolution.md), and a step-by-step
routing table. Inline Phase 0 is gone — the canonical version at
.claude/commands/_shared/scope_resolution.md handles it via the
Activation block.

EOF
)"
```

---

### Task 12: Smoke test against Gasztroterkepek.iOS

**Files:** none modified — verification only.

**Why:** the spec requires that `/archie-deep-scan` produces identical output before and after the refactor. We test that by running the command twice (before-state from the snapshot, after-state from the current branch) against the same project and diffing.

Because this is a 15-20 minute AI run, it's done manually by the user — but the plan documents the exact procedure so the user/subagent can execute it.

- [ ] **Step 1: Verify the current branch is the refactor branch**

```bash
git branch --show-current
```
Expected: `refactor/archie-deep-scan-modular`.

- [ ] **Step 2: Pick a test project**

Recommended: `/Users/csacsi/DEV/Gasztroterkepek.iOS` — known-good, used as the reference project in the earlier enforcement-topic-split smoke test.

- [ ] **Step 3: Snapshot the project's CURRENT `.archie/` and `.claude/rules/` state**

```bash
cd /Users/csacsi/DEV/Gasztroterkepek.iOS
mkdir -p /tmp/archie-before
cp -R .archie/ /tmp/archie-before/.archie
cp -R .claude/rules/ /tmp/archie-before/rules
cp AGENTS.md /tmp/archie-before/AGENTS.md
cp CLAUDE.md /tmp/archie-before/CLAUDE.md
cd /Users/csacsi/DEV/Archie
```

- [ ] **Step 4: Tell the user to run `/archie-deep-scan` in Gasztroterkepek.iOS**

Print this exact instruction:

> Open a new Claude Code session in `/Users/csacsi/DEV/Gasztroterkepek.iOS`
> and run `/archie-deep-scan`. Let it complete fully (~15-20 minutes).
> When it's done, come back here and say "done".

This task BLOCKS until the user confirms. (For an autonomous subagent: report this as `NEEDS_CONTEXT` and wait for the controller to prompt the user.)

- [ ] **Step 5: After user confirms — snapshot AFTER state and diff**

```bash
cd /Users/csacsi/DEV/Gasztroterkepek.iOS
mkdir -p /tmp/archie-after
cp -R .archie/ /tmp/archie-after/.archie
cp -R .claude/rules/ /tmp/archie-after/rules
cp AGENTS.md /tmp/archie-after/AGENTS.md
cp CLAUDE.md /tmp/archie-after/CLAUDE.md

diff -r /tmp/archie-before /tmp/archie-after > /tmp/archie-diff.txt
wc -l /tmp/archie-diff.txt
head -50 /tmp/archie-diff.txt
```

Expected output structure:
- `.archie/blueprint.json` may have a different `meta.generated_at` timestamp — that's expected.
- `.archie/scan.json` may have a different `meta.scanned_at` timestamp — that's expected.
- `.archie/health.json`, `.archie/drift_*.json` will reflect a new run — accept.
- Per-folder `CLAUDE.md` files may have a regenerated timestamp comment at the top — accept.
- `AGENTS.md` may have a regenerated `archie:generated` block timestamp — accept.

**Unacceptable differences:**
- Structural changes in `blueprint.json` (e.g. missing fields, different keys)
- Different rule IDs or rule count in `rules.json`
- Missing or different files in `.claude/rules/enforcement/`
- Different content in per-folder CLAUDE.md beyond the timestamp comment

If unacceptable differences appear, the refactor changed behavior — investigate which step file's content diverged from the original and fix.

- [ ] **Step 6: If the diff is acceptable (only timestamps differ), report PASS. If not, report FAIL with the specific differences and pause for user/controller intervention.**

- [ ] **Step 7: No commit** (verification only).

---

### Task 13: Final verification + push + open PR

- [ ] **Step 1: Run the full test suite one more time**

```bash
cd /Users/csacsi/DEV/Archie
python -m pytest tests/ -v 2>&1 | tail -10
```
Expected: all pass.

- [ ] **Step 2: Run verify_sync**

```bash
python3 scripts/verify_sync.py
```
Expected: `SYNC CHECK PASSED`.

- [ ] **Step 3: Final scan of the new tree for sanity**

```bash
echo "--- canonical tree ---"
find .claude/commands/archie-deep-scan -type f -name "*.md" | sort
echo "--- mirror tree ---"
find npm-package/assets/archie-deep-scan -type f -name "*.md" | sort
echo "--- _shared tree (canonical) ---"
find .claude/commands/_shared -type f -name "*.md"
echo "--- _shared tree (mirror) ---"
find npm-package/assets/_shared -type f -name "*.md"
echo "--- router size ---"
wc -l .claude/commands/archie-deep-scan.md
```

Expected: both trees identical, router ~150 lines.

- [ ] **Step 4: Push the branch**

```bash
git push
```

- [ ] **Step 5: Open PR**

```bash
gh pr create --title "refactor: modularize /archie-deep-scan into router + step files" --body "$(cat <<'EOF'
## Summary

Refactors `.claude/commands/archie-deep-scan.md` from a 1906-line monolith into a slim router (~150 lines) plus per-step files under `archie-deep-scan/{steps,fragments,templates}/`. Inspired by the B-Mad skill pattern — each step is now a self-contained file the AI loads on demand instead of having all 1900 lines in context for every operation.

- Slash-command UX unchanged — `/archie-deep-scan` still works exactly as before.
- Phase 0 deduplicated — the router now references the existing `_shared/scope_resolution.md` instead of inlining its own copy.
- Step 3 (Wave 1 orchestration) split into 6 files: orchestration, 4 sub-agent prompts, shared grounding-rules.
- `npm-package/assets/` mirrors the new tree; installer (`archie.mjs`) does recursive copy.
- `verify_sync.py` extended to walk the new subtree.

## Test plan

- [x] `python -m pytest tests/ -v` — all pass (no Python changes)
- [x] `python3 scripts/verify_sync.py` — PASS
- [x] Smoke test against Gasztroterkepek.iOS — output diff is timestamp-only

## Spec & plan

- Spec: `docs/superpowers/specs/2026-05-11-archie-deep-scan-modular-design.md`
- Plan: `docs/superpowers/plans/2026-05-11-archie-deep-scan-modular.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Spec coverage check (self-review)

| Spec section | Plan task(s) |
|---|---|
| Final directory layout | Tasks 4, 5, 6, 7, 8, 9, 10 |
| Router file shape | Task 11 |
| Step 3 sub-structure | Task 10 |
| Fragments vs steps distinction | Task 4 (fragments) + various step tasks |
| Templates | Task 4 (extraction) + Task 7 (Step 9 references template) |
| Router loading semantics | Task 11 (writes the "Read this before running step N" instruction) |
| npm-package mirroring (tree shape) | Tasks 1, 2 (tooling) + every extraction task (mirror step) |
| `verify_sync.py` update | Task 1 |
| `archie.mjs` installer update | Task 2 |
| Phase 0 dedup → `_shared/scope_resolution.md` | Task 3 (drift check) + Task 11 (router collapse) |
| `_shared/scope_resolution.md` mirror to assets | Task 1 (initial mirror) |
| Smoke test against Gasztroterkepek.iOS | Task 12 |
| Final verify + PR | Task 13 |

All spec requirements covered.

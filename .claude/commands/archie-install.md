# Archie Install

Install Archie into a target project. After this, `/archie-init` will be available.

The ARGUMENTS field contains the target project path. If empty, ask the user for the target path.

## Steps

### 1. Locate the Archie source repo

Find the Archie repo by searching common locations. Try these in order:
1. Check if this command is running FROM the Archie repo (look for `archie/standalone/scanner.py` relative to the repo root)
2. Look for `~/DEV/BitRaptors/Archie/archie/standalone/scanner.py`
3. Search for any directory containing `archie/standalone/scanner.py` under `~/DEV`

Save the found path as `ARCHIE_SRC`. If not found, tell the user: "Could not find the Archie source repo. Please provide the path."

### 2. Create directories in the target project

```bash
mkdir -p <target>/.claude/commands
mkdir -p <target>/.archie
```

### 3. Copy all command files

```bash
for cmd in archie-init.md archie-intent-layer.md archie-viewer.md archie-refresh.md; do
  cp $ARCHIE_SRC/.claude/commands/$cmd <target>/.claude/commands/$cmd
done
```

### 4. Copy all standalone scripts

```bash
for script in scanner.py merge.py finalize.py renderer.py normalize.py rules.py validate.py intent_layer.py install_hooks.py viewer.py refresh.py; do
  cp $ARCHIE_SRC/archie/standalone/$script <target>/.archie/$script
done
```

### 5. Verify all scripts are present

```bash
ls <target>/.archie/*.py | wc -l
```

Should show 11 files. If not, report which are missing.

### 6. Add to .gitignore

```bash
echo ".archie/scan.json" >> <target>/.gitignore
echo ".archie/stats.jsonl" >> <target>/.gitignore
```

The blueprint.json, rules.json, CLAUDE.md, and AGENTS.md should be committed — they're useful for the whole team.

### 7. Done

Tell the user: "Archie installed. Run `/archie-init` in that project to analyze your architecture."

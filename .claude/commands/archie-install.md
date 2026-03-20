# Archie Install

Install Archie into the current project. After this, `/archie-init` will be available.

## Steps

### 1. Create the commands directory

```bash
mkdir -p .claude/commands
```

### 2. Download the archie-init command

```bash
curl -fsSL https://raw.githubusercontent.com/BitRaptors/Archie/main/.claude/commands/archie-init.md -o .claude/commands/archie-init.md
```

### 3. Download the standalone scanner

```bash
mkdir -p .archie
curl -fsSL https://raw.githubusercontent.com/BitRaptors/Archie/main/archie/standalone/scanner.py -o .archie/scanner.py
```

### 4. Verify

Tell the user: "Archie installed. Run `/archie-init` to analyze your architecture."

### 5. Optional: Add to .gitignore

```bash
echo ".archie/scan.json" >> .gitignore
echo ".archie/stats.jsonl" >> .gitignore
```

The blueprint.json, rules.json, CLAUDE.md, and AGENTS.md should be committed — they're useful for the whole team.

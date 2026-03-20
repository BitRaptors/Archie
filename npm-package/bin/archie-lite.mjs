#!/usr/bin/env node

import { mkdirSync, writeFileSync, readFileSync, existsSync, chmodSync } from "fs";
import { join, resolve } from "path";
import { fileURLToPath } from "url";
import { dirname } from "path";
import { execSync } from "child_process";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const ASSETS = join(__dirname, "..", "assets");

const CYAN = "\x1b[36m";
const GREEN = "\x1b[32m";
const DIM = "\x1b[2m";
const RESET = "\x1b[0m";
const BOLD = "\x1b[1m";

const projectRoot = resolve(process.argv[2] || ".");

console.log("");
console.log(`${BOLD}${CYAN}  Archie${RESET} — architecture enforcement for AI coding agents`);
console.log("");

// 1. Create directories
const claudeCommands = join(projectRoot, ".claude", "commands");
const archieDir = join(projectRoot, ".archie");
mkdirSync(claudeCommands, { recursive: true });
mkdirSync(archieDir, { recursive: true });

// 2. Copy Claude Code commands
for (const cmd of ["archie-init.md", "archie-refresh.md"]) {
  const src = join(ASSETS, cmd);
  const dest = join(claudeCommands, cmd);
  if (existsSync(src)) {
    writeFileSync(dest, readFileSync(src, "utf8"));
    console.log(`  ${GREEN}✓${RESET} .claude/commands/${cmd}`);
  }
}

// 3. Copy standalone Python scripts
for (const script of ["scanner.py", "refresh.py", "intent_layer.py", "renderer.py", "rules.py", "install_hooks.py", "merge.py"]) {
  const src = join(ASSETS, script);
  const dest = join(archieDir, script);
  if (existsSync(src)) {
    writeFileSync(dest, readFileSync(src, "utf8"));
    chmodSync(dest, 0o755);
    console.log(`  ${GREEN}✓${RESET} .archie/${script}`);
  }
}

// 4. Update .gitignore
const gitignorePath = join(projectRoot, ".gitignore");
try {
  let content = existsSync(gitignorePath) ? readFileSync(gitignorePath, "utf8") : "";
  let added = false;
  for (const entry of [".archie/scan.json", ".archie/stats.jsonl"]) {
    if (!content.includes(entry)) {
      content += `\n${entry}`;
      added = true;
    }
  }
  if (added) {
    writeFileSync(gitignorePath, content.trimEnd() + "\n");
    console.log(`  ${GREEN}✓${RESET} .gitignore updated`);
  }
} catch { /* not critical */ }

// 5. Check Python availability
let hasPython = false;
try {
  execSync("python3 --version", { stdio: "ignore" });
  hasPython = true;
} catch { /* noop */ }

// Done
console.log("");
console.log(`${BOLD}  Installed!${RESET}`);
console.log("");
console.log(`  Next steps:`);
console.log(`  1. Open this project in ${BOLD}Claude Code${RESET}`);
console.log(`  2. Run ${BOLD}/archie-init${RESET} to analyze your architecture`);
console.log(`  3. After code changes, run ${BOLD}/archie-refresh${RESET} to update`);
console.log("");

if (!hasPython) {
  console.log(`  ⚠ python3 not found — the scanner needs Python 3.11+`);
  console.log("");
}

console.log(`  ${DIM}What gets generated:${RESET}`);
console.log(`  ${DIM}  CLAUDE.md            — architecture context for AI agents${RESET}`);
console.log(`  ${DIM}  AGENTS.md            — multi-agent guidance${RESET}`);
console.log(`  ${DIM}  .claude/hooks/       — real-time architecture enforcement${RESET}`);
console.log(`  ${DIM}  per-folder CLAUDE.md — directory-level context${RESET}`);
console.log("");

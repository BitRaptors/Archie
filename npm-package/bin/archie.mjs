#!/usr/bin/env node

import { mkdirSync, writeFileSync, readFileSync, existsSync, chmodSync, unlinkSync } from "fs";
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
for (const cmd of ["archie-scan.md", "archie-deep-scan.md", "archie-init.md", "archie-refresh.md", "archie-viewer.md", "archie-drift.md", "archie-intent-layer.md", "archie-install.md"]) {
  const src = join(ASSETS, cmd);
  const dest = join(claudeCommands, cmd);
  if (existsSync(src)) {
    writeFileSync(dest, readFileSync(src, "utf8"));
    console.log(`  ${GREEN}✓${RESET} .claude/commands/${cmd}`);
  }
}

// 3. Copy standalone Python scripts
for (const script of ["scanner.py", "refresh.py", "intent_layer.py", "renderer.py", "install_hooks.py", "merge.py", "finalize.py", "validate.py", "viewer.py", "drift.py", "extract_output.py", "arch_review.py", "measure_health.py", "check_rules.py", "detect_cycles.py"]) {
  const src = join(ASSETS, script);
  const dest = join(archieDir, script);
  if (existsSync(src)) {
    writeFileSync(dest, readFileSync(src, "utf8"));
    chmodSync(dest, 0o755);
    console.log(`  ${GREEN}✓${RESET} .archie/${script}`);
  }
}

// 3b. Copy data files (non-script)
for (const dataFile of ["platform_rules.json"]) {
  const src = join(ASSETS, dataFile);
  const dest = join(archieDir, dataFile);
  if (existsSync(src)) {
    writeFileSync(dest, readFileSync(src, "utf8"));
    console.log(`  ${GREEN}✓${RESET} .archie/${dataFile}`);
  }
}

// 3c. Remove obsolete scripts from previous installs
for (const dead of ["enrich_test.py", "normalize.py", "rules.py", "enrich.py"]) {
  const deadPath = join(archieDir, dead);
  if (existsSync(deadPath)) {
    try { unlinkSync(deadPath); console.log(`  ${DIM}removed obsolete .archie/${dead}${RESET}`); } catch {}
  }
}

// 4. Update .gitignore
const gitignorePath = join(projectRoot, ".gitignore");
try {
  let content = existsSync(gitignorePath) ? readFileSync(gitignorePath, "utf8") : "";
  let added = false;
  for (const entry of [".archie/scan.json", ".archie/skeletons.json", ".archie/stats.jsonl", ".archie/scan_report.md", ".archie/scan_history/", ".archie/health_history.json", ".archie/ignored_rules.json", ".archie/observations.json", ".archie/drift_history/", ".archie/enrichments/", ".archie/enrich_state.json", ".archie/enrich_batches.json"]) {
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

// 5. Set up permissions so /archie-init runs without interactive prompts
const settingsPath = join(projectRoot, ".claude", "settings.local.json");
try {
  let settings = {};
  if (existsSync(settingsPath)) {
    try { settings = JSON.parse(readFileSync(settingsPath, "utf8")); } catch {}
  }
  const perms = settings.permissions || {};
  const existing = new Set(perms.allow || []);
  const archieAllow = [
    // Archie scripts
    "Bash(python3 .archie/*.py *)",
    "Bash(python3 .archie/*.py)",
    // Shell utilities Claude uses during orchestration
    "Bash(git *)",
    "Bash(test *)",
    "Bash(cp *)",
    "Bash(wc *)",
    "Bash(cat *)",
    "Bash(echo *)",
    "Bash(for *)",
    "Bash(mkdir *)",
    "Bash(rm -f /tmp/archie_*)",
    // Temp files for agent output
    "Write(//tmp/archie_*)",
    "Read(//tmp/archie_*)",
    // Reading/writing archie data & generated files
    "Read(.archie/*)",
    "Read(.archie/**)",
    "Write(.archie/*)",
    "Write(.archie/**)",
    // Subagent spawning (Wave 1, Wave 2, rules, intent layer)
    "Agent(*)",
  ];
  for (const entry of archieAllow) existing.add(entry);
  perms.allow = [...existing].sort();
  settings.permissions = perms;
  writeFileSync(settingsPath, JSON.stringify(settings, null, 2) + "\n");
  console.log(`  ${GREEN}✓${RESET} .claude/settings.local.json (permissions)`);
} catch { /* not critical */ }

// 6. Check Python availability
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
console.log(`  2. Run ${BOLD}/archie-scan${RESET} for a fast architecture health check (1-3 min)`);
console.log(`  3. Run ${BOLD}/archie-deep-scan${RESET} for a comprehensive baseline (15-20 min)`);
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

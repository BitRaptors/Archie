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
for (const cmd of ["archie-scan.md", "archie-deep-scan.md", "archie-viewer.md"]) {
  const src = join(ASSETS, cmd);
  const dest = join(claudeCommands, cmd);
  if (existsSync(src)) {
    writeFileSync(dest, readFileSync(src, "utf8"));
    console.log(`  ${GREEN}✓${RESET} .claude/commands/${cmd}`);
  }
}

// 3. Copy standalone Python scripts
for (const script of ["_common.py", "scanner.py", "refresh.py", "intent_layer.py", "renderer.py", "install_hooks.py", "merge.py", "finalize.py", "validate.py", "viewer.py", "drift.py", "extract_output.py", "arch_review.py", "measure_health.py", "check_rules.py", "detect_cycles.py"]) {
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

// 3c. Remove obsolete files from previous installs
for (const dead of ["enrich_test.py", "normalize.py", "rules.py", "enrich.py"]) {
  const deadPath = join(archieDir, dead);
  if (existsSync(deadPath)) {
    try { unlinkSync(deadPath); console.log(`  ${DIM}removed obsolete .archie/${dead}${RESET}`); } catch {}
  }
}
for (const deadCmd of ["archie-init.md", "archie-refresh.md", "archie-drift.md", "archie-intent-layer.md", "archie-install.md"]) {
  const deadPath = join(claudeCommands, deadCmd);
  if (existsSync(deadPath)) {
    try { unlinkSync(deadPath); console.log(`  ${DIM}removed obsolete .claude/commands/${deadCmd}${RESET}`); } catch {}
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

// 5. Check Python and run install_hooks.py (sets up hooks + permissions)
let hasPython = false;
try {
  execSync("python3 --version", { stdio: "ignore" });
  hasPython = true;
} catch { /* noop */ }

if (hasPython) {
  try {
    execSync(`python3 "${join(archieDir, "install_hooks.py")}" "${projectRoot}"`, { stdio: "pipe" });
    console.log(`  ${GREEN}✓${RESET} hooks + permissions installed`);
  } catch (e) {
    console.log(`  ${DIM}⚠ hook installation failed (non-critical)${RESET}`);
  }
} else {
  console.log("");
  console.log(`  ⚠ python3 not found — hooks not installed, scanner needs Python 3.9+`);
}

// Done
console.log("");
console.log(`${BOLD}  Installed!${RESET}`);
console.log("");
console.log(`  Next steps:`);
console.log(`  1. Open this project in ${BOLD}Claude Code${RESET}`);
console.log(`  2. Run ${BOLD}/archie-scan${RESET} for a fast architecture health check (1-3 min)`);
console.log(`  3. Run ${BOLD}/archie-deep-scan${RESET} for a comprehensive baseline (15-20 min)`);
console.log("");

console.log(`  ${DIM}What gets generated:${RESET}`);
console.log(`  ${DIM}  CLAUDE.md            — architecture context for AI agents${RESET}`);
console.log(`  ${DIM}  AGENTS.md            — multi-agent guidance${RESET}`);
console.log(`  ${DIM}  .claude/hooks/       — real-time architecture enforcement${RESET}`);
console.log(`  ${DIM}  per-folder CLAUDE.md — directory-level context${RESET}`);
console.log("");

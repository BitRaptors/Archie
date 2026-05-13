#!/usr/bin/env node

import { mkdirSync, writeFileSync, readFileSync, existsSync, chmodSync, unlinkSync, readdirSync, rmSync } from "fs";
import { join, resolve } from "path";
import { fileURLToPath } from "url";
import { dirname } from "path";
import { execSync, spawnSync } from "child_process";
import { createInterface } from "readline";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const ASSETS = join(__dirname, "..", "assets");

const CYAN = "\x1b[36m";
const GREEN = "\x1b[32m";
const DIM = "\x1b[2m";
const RESET = "\x1b[0m";
const BOLD = "\x1b[1m";

const MIN_NODE_MAJOR = 18;
const nodeMajor = parseInt(process.versions.node.split(".")[0], 10);
if (nodeMajor < MIN_NODE_MAJOR) {
  console.error(`Archie requires Node ${MIN_NODE_MAJOR}+. You're on ${process.versions.node}.`);
  process.exit(1);
}

function readPackageVersion() {
  try {
    const pkg = JSON.parse(readFileSync(join(__dirname, "..", "package.json"), "utf8"));
    return pkg.version || "0.0.0";
  } catch { return "0.0.0"; }
}

function streamPrefix(prefix, stream) {
  let buffer = "";
  return (chunk) => {
    buffer += chunk.toString();
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (line.length) stream.write(`${prefix} ${line}\n`);
    }
  };
}

function runWithPrefix(prefix, cmd, args, opts) {
  const result = spawnSync(cmd, args, { ...opts, stdio: "pipe", encoding: "buffer" });
  const onOut = streamPrefix(prefix, process.stdout);
  const onErr = streamPrefix(prefix, process.stderr);
  if (result.stdout) onOut(result.stdout);
  if (result.stderr) onErr(result.stderr);
  return result.status === 0;
}

function buildLocalViewer(viewerDir, packageVersion) {
  const marker = join(viewerDir, "dist", ".archie-version");
  if (existsSync(marker)) {
    const cached = readFileSync(marker, "utf8").trim();
    if (cached === packageVersion) {
      console.log(`  ${GREEN}✓${RESET} Local viewer up to date (v${packageVersion}) — skipping build`);
      return true;
    }
  }

  console.log("");
  console.log(`${BOLD}  Local viewer setup${RESET} ${DIM}(one-time, ~45s)${RESET}`);
  console.log(`  ${DIM}Installs React deps and builds the UI. Cached by version.${RESET}`);
  console.log("");

  const startedAt = Date.now();

  console.log(`  ${CYAN}→${RESET} Installing dependencies (npm ci)`);
  if (!runWithPrefix(`${DIM}[npm]${RESET}`, "npm", ["ci", "--silent"], { cwd: viewerDir })) {
    console.error("");
    console.error(`  ${BOLD}npm ci failed.${RESET} Common causes:`);
    console.error("    - No internet / corporate proxy blocking npm registry");
    console.error("    - Old node (<18). Run `node --version`.");
    console.error("    - npm misconfigured. Run `npm ping`.");
    return false;
  }

  console.log(`  ${CYAN}→${RESET} Building viewer bundle (vite build)`);
  if (!runWithPrefix(`${DIM}[vite]${RESET}`, "npm", ["run", "build", "--silent"], { cwd: viewerDir })) {
    console.error("");
    console.error(`  ${BOLD}vite build failed.${RESET} See output above.`);
    return false;
  }

  console.log(`  ${CYAN}→${RESET} Cleaning up build dependencies`);
  rmSync(join(viewerDir, "node_modules"), { recursive: true, force: true });

  console.log(`  ${CYAN}→${RESET} Writing version marker`);
  writeFileSync(marker, packageVersion);

  const elapsed = ((Date.now() - startedAt) / 1000).toFixed(0);
  console.log("");
  console.log(`  ${GREEN}✓${RESET} Local viewer built in ${elapsed}s`);
  return true;
}

const args = process.argv.slice(2);
let projectRootArg = ".";
let commandsDirArg = null;
let projectRootExplicit = false;

const USAGE = `Usage: npx @bitraptors/archie [path] [--commands-dir dir]

Installs Archie tooling into the project at <path> (default: current directory).
  path             Project directory to install into. Defaults to the cwd.
  --commands-dir   Override .claude/commands location (advanced).
  -h, --help       Show this help.`;

for (let i = 0; i < args.length; i++) {
  if (args[i] === "-h" || args[i] === "--help") {
    console.log(USAGE);
    process.exit(0);
  } else if (args[i] === "--commands-dir" && i + 1 < args.length) {
    commandsDirArg = args[i + 1];
    i++;
  } else if (args[i].startsWith("--")) {
    console.error(`Unknown flag: ${args[i]}\n\n${USAGE}`);
    process.exit(2);
  } else {
    projectRootArg = args[i];
    projectRootExplicit = true;
  }
}

const projectRoot = resolve(projectRootArg);

console.log("");
console.log(`${BOLD}${CYAN}  Archie${RESET} — architecture enforcement for AI coding agents`);
console.log("");

// 1. Create directories
const claudeCommands = commandsDirArg
  ? join(projectRoot, commandsDirArg)
  : join(projectRoot, ".claude", "commands");
const commandsDirRel = commandsDirArg || ".claude/commands";
const claudeSkills = join(projectRoot, ".claude", "skills");
const skillsDirRel = ".claude/skills";
const archieDir = join(projectRoot, ".archie");
mkdirSync(claudeCommands, { recursive: true });
mkdirSync(claudeSkills, { recursive: true });
mkdirSync(archieDir, { recursive: true });

// 1b. Clean install — remove ALL previous Archie scripts, commands, and hooks
//     before re-installing. Preserves user data files (blueprint.json, rules.json, etc.)
let cleanedCount = 0;

// Remove all .py files from .archie/ (scripts only, not data)
if (existsSync(archieDir)) {
  for (const f of readdirSync(archieDir)) {
    if (f.endsWith(".py")) {
      try { unlinkSync(join(archieDir, f)); cleanedCount++; } catch {}
    }
  }
}

// Remove all archie-*.md commands from .claude/commands/ and the
// archie-deep-scan/ subtree introduced by the modular refactor.
if (existsSync(claudeCommands)) {
  for (const f of readdirSync(claudeCommands)) {
    if (f.startsWith("archie-") && f.endsWith(".md")) {
      try { unlinkSync(join(claudeCommands, f)); cleanedCount++; } catch {}
    }
  }
  // Legacy location (≤3.2.0): substeps used to live under .claude/commands/archie-deep-scan/.
  // Remove if present so Claude Code stops listing them as slash commands.
  const legacyDeepScanDir = join(claudeCommands, "archie-deep-scan");
  if (existsSync(legacyDeepScanDir)) {
    try { rmSync(legacyDeepScanDir, { recursive: true, force: true }); cleanedCount++; } catch {}
  }
  // Do NOT delete _shared/ wholesale — other tools may live alongside.
  // Only remove the scope_resolution.md file we installed.
  const sharedFile = join(claudeCommands, "_shared", "scope_resolution.md");
  if (existsSync(sharedFile)) {
    try { unlinkSync(sharedFile); cleanedCount++; } catch {}
  }
}

// Remove the new-location skill subtree so re-installs start clean.
if (existsSync(claudeSkills)) {
  const skillDeepScanDir = join(claudeSkills, "archie-deep-scan");
  if (existsSync(skillDeepScanDir)) {
    try { rmSync(skillDeepScanDir, { recursive: true, force: true }); cleanedCount++; } catch {}
  }
}

// Remove .claude/hooks/ entirely (will be regenerated by install_hooks.py)
const hooksDir = join(projectRoot, ".claude", "hooks");
if (existsSync(hooksDir)) {
  try { rmSync(hooksDir, { recursive: true, force: true }); cleanedCount++; } catch {}
}

// Remove hooks section from settings.local.json (will be regenerated by install_hooks.py)
const settingsPath = join(projectRoot, ".claude", "settings.local.json");
if (existsSync(settingsPath)) {
  try {
    const settings = JSON.parse(readFileSync(settingsPath, "utf8"));
    if (settings.hooks) {
      delete settings.hooks;
      writeFileSync(settingsPath, JSON.stringify(settings, null, 2) + "\n");
    }
  } catch {}
}

// Remove platform_rules.json (will be re-copied)
const platformRulesPath = join(archieDir, "platform_rules.json");
if (existsSync(platformRulesPath)) {
  try { unlinkSync(platformRulesPath); cleanedCount++; } catch {}
}

if (cleanedCount > 0) {
  console.log(`  ${DIM}cleaned ${cleanedCount} previous Archie files${RESET}`);
}

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

// 2. Copy Claude Code commands
for (const cmd of ["archie-scan.md", "archie-deep-scan.md", "archie-viewer.md", "archie-share.md", "archie-intent-layer.md"]) {
  const src = join(ASSETS, cmd);
  const dest = join(claudeCommands, cmd);
  if (existsSync(src)) {
    writeFileSync(dest, readFileSync(src, "utf8"));
    console.log(`  ${GREEN}✓${RESET} ${commandsDirRel}/${cmd}`);
  }
}

// Copy the archie-deep-scan/ subtree (steps, fragments, templates) to
// .claude/skills/ instead of .claude/commands/. Claude Code lists every .md
// under .claude/commands/ recursively as a slash command — moving the
// substeps to skills/ keeps them invisible in the picker while the top-level
// /archie-deep-scan router still references them by path.
const deepScanSubtree = copyDirRecursive(
  join(ASSETS, "skills", "archie-deep-scan"),
  join(claudeSkills, "archie-deep-scan")
);
for (const p of deepScanSubtree) {
  const rel = p.substring(claudeSkills.length + 1);
  console.log(`  ${GREEN}✓${RESET} ${skillsDirRel}/${rel}`);
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

// 3. Copy standalone Python scripts
for (const script of ["_common.py", "scanner.py", "refresh.py", "intent_layer.py", "renderer.py", "install_hooks.py", "merge.py", "finalize.py", "validate.py", "viewer.py", "drift.py", "extract_output.py", "arch_review.py", "measure_health.py", "check_rules.py", "detect_cycles.py", "upload.py", "share_setup.py", "telemetry.py", "lint_gate.py", "code_shape.py", "rule_index.py", "align_check.py", "verify_findings.py", "apply_verdicts.py", "migrate_blueprint_rules.py", "config.py", "telemetry_sync.py", "update_check.py", "analytics.py"]) {
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

// 3e. Copy share/viewer/ source into target's .archie/viewer/ for install-time build.
function cpDirSync(src, dest) {
  mkdirSync(dest, { recursive: true });
  for (const entry of readdirSync(src, { withFileTypes: true })) {
    const s = join(src, entry.name);
    const d = join(dest, entry.name);
    if (entry.isDirectory()) {
      cpDirSync(s, d);
    } else {
      writeFileSync(d, readFileSync(s));
    }
  }
}

const viewerSrc = join(ASSETS, "viewer");
const viewerDest = join(archieDir, "viewer");
if (existsSync(viewerSrc)) {
  // Refresh source files but preserve dist/ (build cache, guarded by .archie-version marker).
  if (existsSync(viewerDest)) {
    for (const entry of readdirSync(viewerDest, { withFileTypes: true })) {
      if (entry.name === "dist") continue;
      rmSync(join(viewerDest, entry.name), { recursive: true, force: true });
    }
  }
  cpDirSync(viewerSrc, viewerDest);
  console.log(`  ${GREEN}✓${RESET} .archie/viewer/ (React source)`);

  const ok = buildLocalViewer(viewerDest, readPackageVersion());
  if (!ok) {
    console.error("");
    console.error("  ⚠ Local viewer build failed. /archie-viewer will not work.");
    console.error("  ⚠ Other Archie features still work. Re-run `npx @bitraptors/archie`");
    console.error("    after fixing the npm/node issue above.");
    // Don't process.exit(1) — preserve the rest of the install (scripts, hooks)
  }
}

// 3c. Copy .archieignore (only if it doesn't exist — user may have customized)
const archieignoreSrc = join(ASSETS, "archieignore.default");
const archieignoreDest = join(projectRoot, ".archieignore");
if (!existsSync(archieignoreDest) && existsSync(archieignoreSrc)) {
  writeFileSync(archieignoreDest, readFileSync(archieignoreSrc, "utf8"));
  console.log(`  ${GREEN}✓${RESET} .archieignore (default patterns)`);
}

// 3c². Copy .archiebulk (only if it doesn't exist — user may have customized).
// .archiebulk tags files as "visible but not read" (UI resources, generated
// code, migrations, lockfiles). Scanner counts them; agents never Read them.
const archiebulkSrc = join(ASSETS, "archiebulk.default");
const archiebulkDest = join(projectRoot, ".archiebulk");
if (!existsSync(archiebulkDest) && existsSync(archiebulkSrc)) {
  writeFileSync(archiebulkDest, readFileSync(archiebulkSrc, "utf8"));
  console.log(`  ${GREEN}✓${RESET} .archiebulk (default bulk-content rules)`);
}

// 3d. Add .gitignore entries for Archie scripts (idempotent)
const gitignorePath = join(projectRoot, ".gitignore");
const archieGitignoreBlock = `\n# Archie (installed tooling — outputs are NOT ignored)\n.archie/*.py\n.archie/__pycache__/\n.archie/platform_rules.json\n.claude/commands/archie-*.md\n.claude/skills/archie-deep-scan/\n.claude/commands/_shared/scope_resolution.md\n.claude/hooks/\n.claude/settings.local.json\n`;

let gitignoreContent = "";
if (existsSync(gitignorePath)) {
  gitignoreContent = readFileSync(gitignorePath, "utf8");
}

if (gitignoreContent.includes("# Archie")) {
  // Replace existing Archie block (upgrade path)
  gitignoreContent = gitignoreContent.replace(/\n?# Archie[^\n]*\n(?:[^\n#]*\n)*/m, archieGitignoreBlock);
  writeFileSync(gitignorePath, gitignoreContent);
  console.log(`  ${GREEN}✓${RESET} .gitignore updated (Archie section refreshed)`);
} else {
  writeFileSync(gitignorePath, gitignoreContent + archieGitignoreBlock);
  console.log(`  ${GREEN}✓${RESET} .gitignore updated (Archie tooling ignored)`);
}

// 4. Check Python and run install_hooks.py (sets up hooks + permissions)
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

// 5. First-run telemetry consent (machine-level, asked once across all installs).
//    Skipped when stdin isn't a TTY (CI, pipes) — defaults to "off" until the
//    user opts in interactively or via `python3 .archie/config.py set telemetry`.
async function maybePromptTelemetry() {
  if (!hasPython) return;
  const configScript = join(archieDir, "config.py");
  if (!existsSync(configScript)) return;

  const check = spawnSync("python3", [configScript, "should-prompt"], { stdio: "ignore" });
  if (check.status !== 0) return; // already prompted (or error → skip silently)

  if (!process.stdin.isTTY || !process.stdout.isTTY) {
    // Non-interactive: leave telemetry off but mark prompted=false so an
    // interactive re-install (or `archie config set telemetry ...`) still asks.
    return;
  }

  console.log("");
  console.log(`${BOLD}  Help Archie improve${RESET} ${DIM}(anonymous, opt-in)${RESET}`);
  console.log(`  ${DIM}We'd like to collect: command name, Archie version, OS/arch,${RESET}`);
  console.log(`  ${DIM}step durations, outcome, detected stack (e.g. kotlin/gradle/android).${RESET}`);
  console.log(`  ${DIM}Never: source code, file paths, repo names, blueprint contents.${RESET}`);
  console.log(`  ${DIM}Change anytime: python3 .archie/config.py set telemetry off${RESET}`);
  console.log("");

  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const ask = (q) => new Promise((resolve) => rl.question(q, resolve));

  let tier = null;
  try {
    const first = (await ask(`  ${CYAN}?${RESET} Help Archie get better? ${DIM}[Y/n]${RESET} `)).trim().toLowerCase();
    if (first === "" || first === "y" || first === "yes") {
      tier = "community";
    } else {
      const second = (await ask(`  ${CYAN}?${RESET} Send anonymous metrics only ${DIM}(strips installation id)${RESET}? ${DIM}[y/N]${RESET} `)).trim().toLowerCase();
      tier = (second === "y" || second === "yes") ? "anonymous" : "off";
    }
  } finally {
    rl.close();
  }

  const apply = spawnSync("python3", [configScript, "apply-prompt-result", tier], { stdio: "ignore" });
  if (apply.status === 0) {
    if (tier === "off") {
      console.log(`  ${GREEN}✓${RESET} telemetry off ${DIM}(re-enable: python3 .archie/config.py set telemetry community)${RESET}`);
    } else {
      console.log(`  ${GREEN}✓${RESET} telemetry: ${tier} ${DIM}(stored at ~/.archie/config.json)${RESET}`);
      // Fire a single anonymous "install" event so we can count adoption.
      const syncScript = join(archieDir, "telemetry_sync.py");
      if (existsSync(syncScript)) {
        spawnSync("python3", [syncScript, "record-install", "--version", readPackageVersion()], { stdio: "ignore" });
      }
    }
  }
}

// Write a machine-level version marker so telemetry_sync can label events
// without re-reading the npm package.json. Also records "JUST_UPGRADED" via
// update_check.py so the next slash-command preamble can show a one-off ack.
function writeArchieVersionMarker() {
  const home = process.env.HOME || process.env.USERPROFILE;
  if (!home) return;
  const archieConfigDir = join(home, ".archie");
  const versionFile = join(archieConfigDir, "version");
  const newVersion = readPackageVersion();

  let oldVersion = "";
  try {
    if (existsSync(versionFile)) oldVersion = readFileSync(versionFile, "utf8").trim();
  } catch { /* noop */ }

  try {
    mkdirSync(archieConfigDir, { recursive: true });
    writeFileSync(versionFile, newVersion);
  } catch { return; }

  if (hasPython && oldVersion && oldVersion !== newVersion) {
    const updateScript = join(archieDir, "update_check.py");
    if (existsSync(updateScript)) {
      spawnSync("python3", [updateScript, "mark-upgraded", newVersion], { stdio: "ignore" });
    }
  }
}

writeArchieVersionMarker();
await maybePromptTelemetry();

// Done
console.log("");
console.log(`${BOLD}  Installed!${RESET}`);
console.log("");
console.log(`  Next steps:`);
console.log(`  1. Open this project in ${BOLD}Claude Code${RESET}`);
console.log(`  2. Run ${BOLD}/archie-scan${RESET} for a fast architecture health check (1-3 min)`);
console.log(`  3. Run ${BOLD}/archie-deep-scan${RESET} for a comprehensive baseline (15-20 min)`);
console.log(`  ${DIM}Usage: npx @bitraptors/archie [path] [--commands-dir dir]${RESET}`);
console.log("");

console.log(`  ${DIM}What gets generated:${RESET}`);
console.log(`  ${DIM}  CLAUDE.md            — architecture context for AI agents${RESET}`);
console.log(`  ${DIM}  AGENTS.md            — multi-agent guidance${RESET}`);
console.log(`  ${DIM}  .claude/hooks/       — real-time architecture enforcement${RESET}`);
console.log(`  ${DIM}  per-folder CLAUDE.md — directory-level context${RESET}`);
console.log("");

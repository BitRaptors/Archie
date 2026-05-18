#!/usr/bin/env node

import { mkdirSync, writeFileSync, readFileSync, existsSync, chmodSync, unlinkSync, readdirSync, rmSync } from "fs";
import { join, resolve, dirname, delimiter } from "path";
import { fileURLToPath } from "url";
import { execSync, spawnSync } from "child_process";

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

const args = process.argv.slice(2);
let projectRootArg = ".";
let commandsDirArg = null;

const USAGE = `Usage: npx @bitraptors/archie [path] [--commands-dir dir]

Installs Archie tooling into the project at <path> (default: current directory).
  path             Project directory to install into. Defaults to the cwd.
  --commands-dir   Legacy Claude-only override. Multi-CLI installs ignore it.
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
  }
}

const projectRoot = resolve(projectRootArg);
const archieDir = join(projectRoot, ".archie");
const claudeCommands = join(projectRoot, ".claude", "commands");
const claudeSkills = join(projectRoot, ".claude", "skills");

console.log("");
console.log(`${BOLD}${CYAN}  Archie${RESET} — architecture enforcement for AI coding agents`);
console.log("");

if (commandsDirArg) {
  console.log(`  ${DIM}note: --commands-dir is ignored for multi-CLI installs${RESET}`);
}

mkdirSync(archieDir, { recursive: true });

let cleanedCount = 0;

if (existsSync(archieDir)) {
  for (const f of readdirSync(archieDir)) {
    if (f.endsWith(".py")) {
      try { unlinkSync(join(archieDir, f)); cleanedCount++; } catch {}
    }
  }
}

if (existsSync(claudeCommands)) {
  for (const f of readdirSync(claudeCommands)) {
    if (f.startsWith("archie-") && f.endsWith(".md")) {
      try { unlinkSync(join(claudeCommands, f)); cleanedCount++; } catch {}
    }
  }
  const legacyDeepScanDir = join(claudeCommands, "archie-deep-scan");
  if (existsSync(legacyDeepScanDir)) {
    try { rmSync(legacyDeepScanDir, { recursive: true, force: true }); cleanedCount++; } catch {}
  }
  const sharedFile = join(claudeCommands, "_shared", "scope_resolution.md");
  if (existsSync(sharedFile)) {
    try { unlinkSync(sharedFile); cleanedCount++; } catch {}
  }
}

if (existsSync(claudeSkills)) {
  const skillDeepScanDir = join(claudeSkills, "archie-deep-scan");
  if (existsSync(skillDeepScanDir)) {
    try { rmSync(skillDeepScanDir, { recursive: true, force: true }); cleanedCount++; } catch {}
  }
}

const hooksDir = join(projectRoot, ".claude", "hooks");
if (existsSync(hooksDir)) {
  try { rmSync(hooksDir, { recursive: true, force: true }); cleanedCount++; } catch {}
}

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

const platformRulesPath = join(archieDir, "platform_rules.json");
if (existsSync(platformRulesPath)) {
  try { unlinkSync(platformRulesPath); cleanedCount++; } catch {}
}

const installPkgDir = join(archieDir, "_install_pkg");
if (existsSync(installPkgDir)) {
  try { rmSync(installPkgDir, { recursive: true, force: true }); cleanedCount++; } catch {}
}

if (cleanedCount > 0) {
  console.log(`  ${DIM}cleaned ${cleanedCount} previous Archie files${RESET}`);
}

for (const script of ["_common.py", "scanner.py", "refresh.py", "intent_layer.py", "renderer.py", "install_hooks.py", "merge.py", "finalize.py", "validate.py", "viewer.py", "drift.py", "extract_output.py", "arch_review.py", "measure_health.py", "check_rules.py", "detect_cycles.py", "upload.py", "share_setup.py", "telemetry.py", "lint_gate.py", "code_shape.py", "rule_index.py", "align_check.py", "verify_findings.py", "apply_verdicts.py", "migrate_blueprint_rules.py", "config.py", "telemetry_sync.py", "update_check.py", "analytics.py"]) {
  const src = join(ASSETS, script);
  const dest = join(archieDir, script);
  if (existsSync(src)) {
    writeFileSync(dest, readFileSync(src, "utf8"));
    chmodSync(dest, 0o755);
    console.log(`  ${GREEN}✓${RESET} .archie/${script}`);
  }
}

for (const dataFile of ["platform_rules.json"]) {
  const src = join(ASSETS, dataFile);
  const dest = join(archieDir, dataFile);
  if (existsSync(src)) {
    writeFileSync(dest, readFileSync(src, "utf8"));
    console.log(`  ${GREEN}✓${RESET} .archie/${dataFile}`);
  }
}

const ASSET_SUBDIR_MAP = [
  ["hook_scripts", "hooks"],
  ["prompts", "prompts"],
  ["pi_extension", "pi_extension"],
  ["_install_pkg", "_install_pkg"],
];
for (const [srcName, destName] of ASSET_SUBDIR_MAP) {
  const src = join(ASSETS, srcName);
  if (existsSync(src)) {
    const dest = join(archieDir, destName);
    if (existsSync(dest)) rmSync(dest, { recursive: true, force: true });
    cpDirSync(src, dest);
    console.log(`  ${GREEN}✓${RESET} .archie/${destName}/ (canonical asset subtree)`);
  }
}

const archieignoreSrc = join(ASSETS, "archieignore.default");
const archieignoreDest = join(projectRoot, ".archieignore");
if (!existsSync(archieignoreDest) && existsSync(archieignoreSrc)) {
  writeFileSync(archieignoreDest, readFileSync(archieignoreSrc, "utf8"));
  console.log(`  ${GREEN}✓${RESET} .archieignore (default patterns)`);
}

const archiebulkSrc = join(ASSETS, "archiebulk.default");
const archiebulkDest = join(projectRoot, ".archiebulk");
if (!existsSync(archiebulkDest) && existsSync(archiebulkSrc)) {
  writeFileSync(archiebulkDest, readFileSync(archiebulkSrc, "utf8"));
  console.log(`  ${GREEN}✓${RESET} .archiebulk (default bulk-content rules)`);
}

const gitignorePath = join(projectRoot, ".gitignore");
const archieGitignoreBlock = `\n# Archie (installed tooling — outputs are NOT ignored)\n.archie/*.py\n.archie/__pycache__/\n.archie/platform_rules.json\n.claude/commands/archie-*.md\n.claude/skills/archie-deep-scan/\n.claude/commands/_shared/scope_resolution.md\n.claude/hooks/\n.claude/settings.local.json\n.agents/skills/archie-*/\n.codex/agents/archie-*.toml\n.codex/hooks.json\n`;

let gitignoreContent = "";
if (existsSync(gitignorePath)) {
  gitignoreContent = readFileSync(gitignorePath, "utf8");
}

if (gitignoreContent.includes("# Archie")) {
  gitignoreContent = gitignoreContent.replace(/\n?# Archie[^\n]*\n(?:[^\n#]*\n)*/m, archieGitignoreBlock);
  writeFileSync(gitignorePath, gitignoreContent);
  console.log(`  ${GREEN}✓${RESET} .gitignore updated (Archie section refreshed)`);
} else {
  writeFileSync(gitignorePath, gitignoreContent + archieGitignoreBlock);
  console.log(`  ${GREEN}✓${RESET} .gitignore updated (Archie tooling ignored)`);
}

let hasPython = false;
try {
  execSync("python3 --version", { stdio: "ignore" });
  hasPython = true;
} catch { /* noop */ }

if (hasPython) {
  const env = {
    ...process.env,
    ARCHIE_ASSETS_ROOT: ASSETS,
    ARCHIE_STANDALONE_ROOT: ASSETS,
    PYTHONPATH: process.env.PYTHONPATH ? `${archieDir}${delimiter}${process.env.PYTHONPATH}` : archieDir,
  };
  const result = spawnSync("python3", ["-m", "_install_pkg.install", projectRoot, "--target=auto"], {
    cwd: archieDir,
    env,
    stdio: "inherit",
  });
  if (result.status !== 0) {
    console.log(`  ${DIM}⚠ Python install loop exited with status ${result.status}${RESET}`);
  }
} else {
  console.log("");
  console.log("  ⚠ python3 not found — Claude/Codex shims not written. Install Python 3.9+ and re-run.");
}

const viewerSrc = join(ASSETS, "viewer");
const viewerDest = join(archieDir, "viewer");
if (existsSync(viewerSrc)) {
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
  }
}

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
      spawnSync("python3", [updateScript, "mark-upgraded", newVersion, oldVersion], { stdio: "ignore" });
    }
  }
}

writeArchieVersionMarker();

console.log("");
console.log(`${BOLD}  Installed!${RESET}`);
console.log("");
console.log("  Next steps:");
console.log(`  1. Open this project in ${BOLD}Claude Code${RESET} or ${BOLD}Codex${RESET}`);
console.log(`  2. Run ${BOLD}/archie-scan${RESET} for a fast architecture health check (1-3 min)`);
console.log(`  3. Run ${BOLD}/archie-deep-scan${RESET} for a comprehensive baseline (15-20 min)`);
console.log(`  ${DIM}Usage: npx @bitraptors/archie [path] [--commands-dir dir]${RESET}`);
console.log("");
console.log(`  ${DIM}This install writes shared Archie assets and delegates CLI shims to the Python connector loop.${RESET}`);
console.log("");
console.log(`  ${DIM}Telemetry: the first Archie command you run asks once when the harness supports prompting.${RESET}`);
console.log(`  ${DIM}whether to share anonymous usage data (opt-in). Nothing is sent until then.${RESET}`);
console.log("");

console.log(`  ${DIM}What gets generated:${RESET}`);
console.log(`  ${DIM}  CLAUDE.md            — architecture context for AI agents${RESET}`);
console.log(`  ${DIM}  AGENTS.md            — multi-agent guidance${RESET}`);
console.log(`  ${DIM}  .claude/hooks/       — real-time architecture enforcement${RESET}`);
console.log(`  ${DIM}  per-folder CLAUDE.md — directory-level context${RESET}`);
console.log("");

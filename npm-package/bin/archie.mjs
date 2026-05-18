#!/usr/bin/env node

import { mkdirSync, writeFileSync, readFileSync, existsSync, chmodSync, unlinkSync, readdirSync, rmSync } from "fs";
import { join, resolve } from "path";
import { fileURLToPath } from "url";
import { dirname } from "path";
import { execSync, spawnSync } from "child_process";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const ASSETS = join(__dirname, "..", "assets");

const COMMANDS = [
  ["archie-scan", "Architecture health check (1-3 min)."],
  ["archie-deep-scan", "Comprehensive architecture baseline (15-20 min)."],
  ["archie-intent-layer", "Generate per-folder CLAUDE.md context via bottom-up DAG."],
  ["archie-viewer", "Open the blueprint inspector in the browser."],
  ["archie-share", "Upload the blueprint and return a share link."],
];

const CODEX_HOOKS = [
  ["PreToolUse", "Edit|Write|MultiEdit", ".archie/hooks/pre-validate.sh"],
  ["PreToolUse", "Bash", ".archie/hooks/pre-commit-review.sh"],
  ["PreToolUse", "Glob|Grep", ".archie/hooks/blueprint-nudge.sh"],
  ["PostToolUse", "ExitPlanMode", ".archie/hooks/post-plan-review.sh"],
  ["PostToolUse", "Edit|Write|MultiEdit", ".archie/hooks/post-lint.sh"],
  ["UserPromptSubmit", null, ".archie/hooks/pre-turn.sh"],
];

const CODEX_MATCHERS = {
  "Edit|Write|MultiEdit": "^apply_patch$",
  "Bash": "^Bash$",
  "Glob|Grep": "^(Glob|Grep)$",
  "ExitPlanMode": "^ExitPlanMode$",
};

const CODEX_AGENTS = [
  ["archie-wave1-structure", "Wave-1 structure pass: components, layers, file placement.", ".archie/prompts/codex/wave1_structure.md", null],
  ["archie-wave1-patterns", "Wave-1 patterns pass: communication, design patterns, integrations.", ".archie/prompts/codex/wave1_patterns.md", null],
  ["archie-wave1-technology", "Wave-1 technology pass: stack, deployment, dev rules.", ".archie/prompts/codex/wave1_technology.md", null],
  ["archie-wave1-ui", "Wave-1 UI pass: components, state, routing (only when frontend_ratio >= 0.20).", ".archie/prompts/codex/wave1_ui.md", null],
  ["archie-wave2-reasoning", "Wave-2 reasoning pass: synthesizes Wave-1 outputs into decision chain, pitfalls, trade-offs.", ".archie/prompts/codex/wave2_reasoning.md", "opus"],
];

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

function tomlString(value) {
  return value.replaceAll("\\", "\\\\").replaceAll("\"", "\\\"");
}

function tomlSerializeValue(value) {
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return Number.isInteger(value) ? `${value}` : `${value}`;
  if (typeof value === "string") return `"${tomlString(value)}"`;
  if (Array.isArray(value)) return `[${value.map(tomlSerializeValue).join(", ")}]`;
  throw new Error(`Unsupported TOML value: ${value}`);
}

function parseInlineStringArray(raw) {
  const normalized = raw.trim();
  if (!normalized.startsWith("[") || !normalized.includes("]")) return [];
  const inner = normalized.slice(1, normalized.lastIndexOf("]"));
  return [...inner.matchAll(/"((?:[^"\\]|\\.)*)"/g)].map((m) =>
    m[1].replaceAll("\\\"", "\"").replaceAll("\\\\", "\\")
  );
}

function insertTopLevelAssignment(content, assignment) {
  const sectionMatch = content.match(/^\[/m);
  const insertAt = sectionMatch ? sectionMatch.index : content.length;
  let head = content.slice(0, insertAt);
  const tail = content.slice(insertAt);
  if (head && !head.endsWith("\n")) head += "\n";
  if (head && tail && !head.endsWith("\n\n")) head += "\n";
  return `${head}${assignment}\n${tail}`;
}

function findTomlAssignments(content, key) {
  const lines = content.match(/[^\n]*\n|[^\n]+/g) || [];
  const entries = [];
  let pos = 0;
  let scope = "top";
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const stripped = line.trim();
    if (stripped.startsWith("[") && stripped.endsWith("]")) {
      scope = "section";
      pos += line.length;
      continue;
    }
    const match = line.match(/^([A-Za-z0-9_\-]+)\s*=\s*(.*)$/);
    if (!match || match[1] !== key) {
      pos += line.length;
      continue;
    }
    const start = pos;
    let rawValue = match[2];
    let end = pos + line.length;
    while (rawValue.trimStart().startsWith("[") && !rawValue.includes("]") && i + 1 < lines.length) {
      i += 1;
      rawValue += lines[i];
      end += lines[i].length;
      if (lines[i].includes("]")) break;
    }
    entries.push({ scope, start, end, rawValue });
    pos = end;
  }
  return entries;
}

function tomlSetTopLevel(content, key, value) {
  const entries = findTomlAssignments(content, key);
  const existing = entries.find((e) => e.scope === "top") || entries.find((e) => e.scope === "section");
  let nextValue = value;
  if (existing && Array.isArray(value)) {
    const merged = [...parseInlineStringArray(existing.rawValue.trim())];
    for (const item of value) {
      if (!merged.includes(item)) merged.push(item);
    }
    nextValue = merged;
  }
  const assignment = `${key} = ${tomlSerializeValue(nextValue)}`;
  if (!existing) return insertTopLevelAssignment(content, assignment);
  const replacement = content.slice(existing.end - 1, existing.end) === "\n" ? `${assignment}\n` : assignment;
  if (existing.scope === "top") {
    return `${content.slice(0, existing.start)}${replacement}${content.slice(existing.end)}`;
  }
  const withoutSection = `${content.slice(0, existing.start)}${content.slice(existing.end)}`;
  return insertTopLevelAssignment(withoutSection, assignment);
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
const codexSkillsDir = join(projectRoot, ".agents", "skills");
const codexAgentsDir = join(projectRoot, ".codex", "agents");
const codexHooksPath = join(projectRoot, ".codex", "hooks.json");
mkdirSync(claudeCommands, { recursive: true });
mkdirSync(claudeSkills, { recursive: true });
mkdirSync(archieDir, { recursive: true });
mkdirSync(codexSkillsDir, { recursive: true });
mkdirSync(codexAgentsDir, { recursive: true });

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

if (existsSync(codexSkillsDir)) {
  for (const entry of readdirSync(codexSkillsDir, { withFileTypes: true })) {
    if (!entry.isDirectory() || !entry.name.startsWith("archie-")) continue;
    try { rmSync(join(codexSkillsDir, entry.name), { recursive: true, force: true }); cleanedCount++; } catch {}
  }
}

if (existsSync(codexAgentsDir)) {
  for (const entry of readdirSync(codexAgentsDir)) {
    if (!entry.startsWith("archie-") || !entry.endsWith(".toml")) continue;
    try { unlinkSync(join(codexAgentsDir, entry)); cleanedCount++; } catch {}
  }
}

if (existsSync(codexHooksPath)) {
  try { unlinkSync(codexHooksPath); cleanedCount++; } catch {}
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

function codexBodyPath(commandName) {
  const basename = `skill_${commandName.replaceAll("-", "_")}.md`;
  const codexPath = join(ASSETS, "prompts", "codex", basename);
  return existsSync(codexPath)
    ? `.archie/prompts/codex/${basename}`
    : `.archie/prompts/${basename}`;
}

function installCodexSkills() {
  for (const [name, description] of COMMANDS) {
    const destDir = join(codexSkillsDir, name);
    mkdirSync(destDir, { recursive: true });
    const bodyPath = codexBodyPath(name);
    writeFileSync(
      join(destDir, "SKILL.md"),
      `---\nname: ${name}\ndescription: ${description}\n---\n\nRead \`${bodyPath}\` in full and execute the instructions as written. The canonical body lives there so Claude Code, Codex, and Pi sessions all follow the same workflow.\n`
    );
    console.log(`  ${GREEN}✓${RESET} .agents/skills/${name}/SKILL.md`);
  }
}

function installCodexHooks() {
  const config = { hooks: {} };
  for (const [eventName, toolMatch, scriptPath] of CODEX_HOOKS) {
    const bucket = config.hooks[eventName] || [];
    const entry = {
      hooks: [{ type: "command", command: resolve(projectRoot, scriptPath), timeout: 30 }],
    };
    const matcher = toolMatch ? (CODEX_MATCHERS[toolMatch] || toolMatch) : null;
    if (matcher) entry.matcher = matcher;
    bucket.push(entry);
    config.hooks[eventName] = bucket;
  }
  mkdirSync(dirname(codexHooksPath), { recursive: true });
  writeFileSync(codexHooksPath, JSON.stringify(config, null, 2) + "\n");
  console.log(`  ${GREEN}✓${RESET} .codex/hooks.json`);
}

function installCodexAgents() {
  for (const [name, description, promptPath, model] of CODEX_AGENTS) {
    const absPrompt = resolve(projectRoot, promptPath);
    const absRoot = resolve(projectRoot);
    const lines = [
      `name = "${tomlString(name)}"`,
      `description = "${tomlString(description)}"`,
      `developer_instructions = """Project root: ${absRoot}. Read ${join(absRoot, "AGENTS.md")} first if it exists, then read and follow ${absPrompt} in full. You are the ${name} sub-agent for Archie deep-scan."""`,
      `sandbox_mode = "read-only"`,
    ];
    if (model) lines.push(`model = "${tomlString(model)}"`);
    writeFileSync(join(codexAgentsDir, `${name}.toml`), lines.join("\n") + "\n");
    console.log(`  ${GREEN}✓${RESET} .codex/agents/${name}.toml`);
  }
}

function patchCodexConfig() {
  const home = process.env.HOME || process.env.USERPROFILE;
  if (!home) return;
  const codexDir = join(home, ".codex");
  const configPath = join(codexDir, "config.toml");
  let content = "";
  try {
    if (existsSync(configPath)) content = readFileSync(configPath, "utf8");
  } catch {
    content = "";
  }
  let updated = tomlSetTopLevel(content, "project_doc_max_bytes", 131072);
  updated = tomlSetTopLevel(updated, "project_doc_fallback_filenames", ["CLAUDE.md"]);
  try {
    mkdirSync(codexDir, { recursive: true });
    writeFileSync(configPath, updated);
    console.log(`  ${GREEN}✓${RESET} ~/.codex/config.toml patched`);
  } catch {
    console.log(`  ${DIM}⚠ could not patch ~/.codex/config.toml in this environment${RESET}`);
  }
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

// 3b². Copy canonical asset subdirs into .archie/ so install_hooks.py
// (sibling) and the Connector-based installers (Codex/Pi) find them.
// Maps source subdirs to deployed subdirs:
//   npm-package/assets/hook_scripts/  → .archie/hooks/        (sibling to install_hooks.py)
//   npm-package/assets/prompts/       → .archie/prompts/      (referenced by SKILL shims)
//   npm-package/assets/pi_extension/  → .archie/pi_extension/ (Pi TS template + manifest)
const ASSET_SUBDIR_MAP = [
  ["hook_scripts", "hooks"],
  ["prompts",      "prompts"],
  ["pi_extension", "pi_extension"],
];
for (const [src_name, dest_name] of ASSET_SUBDIR_MAP) {
  const src = join(ASSETS, src_name);
  if (existsSync(src)) {
    const dest = join(archieDir, dest_name);
    if (existsSync(dest)) rmSync(dest, { recursive: true, force: true });
    cpDirSync(src, dest);
    console.log(`  ${GREEN}✓${RESET} .archie/${dest_name}/ (canonical asset subtree)`);
  }
}

installCodexSkills();
installCodexHooks();
installCodexAgents();

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
const archieGitignoreBlock = `\n# Archie (installed tooling — outputs are NOT ignored)\n.archie/*.py\n.archie/__pycache__/\n.archie/platform_rules.json\n.claude/commands/archie-*.md\n.claude/skills/archie-deep-scan/\n.claude/commands/_shared/scope_resolution.md\n.claude/hooks/\n.claude/settings.local.json\n.agents/skills/archie-*/\n.codex/agents/archie-*.toml\n.codex/hooks.json\n`;

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

patchCodexConfig();

// 5. Telemetry consent is NOT asked here. An `npx` install can be
//    non-interactive (CI, pipe, agent shell), so the prompt belongs where
//    interactivity is guaranteed: the Archie slash commands, which always run
//    inside Claude Code. Every command's preamble loads the shared
//    `_shared/telemetry-consent.md` fragment, which checks
//    `config.py should-prompt` and asks once via AskUserQuestion. The installer
//    just leaves the config defaults (telemetry off, telemetry_prompted=false);
//    the first command the user runs does the asking.

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
      // Pass oldVersion explicitly — the version marker on disk was already
      // overwritten with newVersion above, so update_check.py can't re-derive it.
      spawnSync("python3", [updateScript, "mark-upgraded", newVersion, oldVersion], { stdio: "ignore" });
    }
  }
}

writeArchieVersionMarker();

// Done
console.log("");
console.log(`${BOLD}  Installed!${RESET}`);
console.log("");
console.log(`  Next steps:`);
console.log(`  1. Open this project in ${BOLD}Claude Code${RESET} or ${BOLD}Codex${RESET}`);
console.log(`  2. Run ${BOLD}/archie-scan${RESET} for a fast architecture health check (1-3 min)`);
console.log(`  3. Run ${BOLD}/archie-deep-scan${RESET} for a comprehensive baseline (15-20 min)`);
console.log(`  ${DIM}Usage: npx @bitraptors/archie [path] [--commands-dir dir]${RESET}`);
console.log("");
console.log(`  ${DIM}This install writes Claude shims, Codex shims, shared Archie assets, and Codex config patches.${RESET}`);
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

# Skill: sync-architecture

Provision architecture outputs (CLAUDE.md, rules, per-folder context, MCP config) from a generated Archie blueprint to the target project's local checkout.

## Instructions

You are synchronizing architecture files from Archie blueprint storage to a developer's local project. Follow these steps exactly.

### Step 1: Identify the Archie storage path

Read `~/.archie/config.json`. Extract the `storage_path` value. If the file does not exist, ask the user:

> "I need to know where Archie stores blueprints. What is the absolute path to the `backend/storage` directory of your Archie installation?"

Then create `~/.archie/config.json` with `{ "storage_path": "<their answer>" }`.

### Step 2: Resolve the current project's blueprint

1. Run `git remote get-url origin` in the current working directory to get the remote URL.
2. Extract the `owner/repo` identifier from the URL (handles both `https://github.com/owner/repo.git` and `git@github.com:owner/repo.git` formats).
3. List all directories under `{storage_path}/blueprints/`.
4. For each directory (each is a `repo_id`), read `{storage_path}/blueprints/{repo_id}/blueprint.json` and check if `meta.repository` matches the extracted `owner/repo`.
5. If no match is found, tell the user: "No blueprint found for `owner/repo`. Please analyze this repository first via the Archie web UI."
6. If a match is found, save the `repo_id` to `.archie/repo_id` in the project root for future lookups.

**Shortcut:** If `.archie/repo_id` already exists in the project root, read it and verify the blueprint still exists at that path. Skip the scan if valid.

### Step 3: Read all intent layer files

The generated outputs live at `{storage_path}/blueprints/{repo_id}/intent_layer/`. List all files recursively in this directory. These are the files to provision.

### Step 4: Write files to the project

For each file from the intent layer, write it to the corresponding relative path in the current working directory.

**Merge rules for root-level files only:**

- **`CLAUDE.md` and `AGENTS.md`**: If the file already exists in the project:
  - Look for `<!-- gbr:start repo=... -->` and `<!-- gbr:end -->` markers
  - If markers exist, replace only the content between them with the new content
  - If no markers exist, append the new content wrapped in markers at the end
  - If the file doesn't exist, write it wrapped in markers
  - The marker format is: `<!-- gbr:start repo={repo_name} -->` where `repo_name` is the last segment of the project path

- **`.mcp.json` and `.cursor/mcp.json`**: If the file already exists:
  - Parse the existing JSON
  - Only upsert the `mcpServers.archie` key — preserve all other keys
  - If the file doesn't exist, write the new JSON directly

- **`.claude/settings.json`**: If the file already exists:
  - Parse the existing JSON
  - Only upsert the `hooks` key — preserve `permissions` and all other top-level keys
  - Within `hooks`, replace per event type (PreToolUse, PostToolUse, Stop, SessionStart)
  - If the file doesn't exist, write the new JSON directly

- **`.claude/hooks/*.sh`**: Overwrite entirely. After writing, set executable permissions (`chmod +x`).

- **All other files** (rule files, per-folder CLAUDE.md files): Overwrite entirely. These are fully generated and not meant to be hand-edited.

### Step 5: Report

List all files that were written or updated, grouped by category:
- Root documentation (CLAUDE.md, AGENTS.md, CODEBASE_MAP.md)
- Claude Code rules (.claude/rules/*)
- Cursor rules (.cursor/rules/*)
- Claude Code hooks (.claude/hooks/*.sh, .claude/settings.json)
- MCP config (.mcp.json, .cursor/mcp.json)
- Per-folder context (*/CLAUDE.md)

Include the total count.

# Claude Code Skills & Hooks

Pure skill-based integration that gives Claude Code full architectural awareness without requiring the Archie backend server to be running. All skills work by reading directly from the local blueprint storage on the filesystem.

## Why Skills Instead of MCP

The MCP server (`/mcp/sse`) requires the backend to be running. Skills read the same data directly from `backend/storage/blueprints/` — the same filesystem the MCP server reads from. This means:

- **Zero dependencies** — No server, no database, no network
- **Works offline** — Blueprint data is local JSON files
- **No startup friction** — Developer types a slash command and it just works
- **Same data source** — Skills read the exact same `blueprint.json` and intent layer files that the MCP tools use

## Setup

Skills require one piece of configuration: where the blueprint storage lives.

On first use of any skill, it will ask for the path and create `~/.archie/config.json`:

```json
{
  "storage_path": "/path/to/archie/backend/storage"
}
```

Each project also caches its `repo_id` in `.archie/repo_id` after first resolution (auto-created by the skills).

## Skills Reference

### `/sync-architecture`

**Purpose:** Provision architecture outputs to the local project.

**What it does:**
1. Resolves the current project against analyzed blueprints (via git remote URL → `meta.repository` matching)
2. Reads all files from the blueprint's `intent_layer/` directory
3. Writes them to the project root with smart merging:
   - Root markdown files (`CLAUDE.md`, `AGENTS.md`): Preserves user content outside `<!-- gbr:start -->` markers
   - JSON configs (`.mcp.json`): Upserts only the `architecture-blueprints` MCP server key
   - Everything else (rules, per-folder CLAUDE.md): Overwrites entirely
4. Reports what was written/updated

**When to use:** After analyzing a repo for the first time, or after re-running analysis to pick up changes.

**Files provisioned:**
- `CLAUDE.md` — Root architecture context for Claude Code
- `AGENTS.md` — Multi-agent coordination guide
- `CODEBASE_MAP.md` — Full architecture map with module guide
- `.claude/rules/*.md` — Claude Code rule files (architecture, recipes, pitfalls, patterns, etc.)
- `.cursor/rules/*.md` — Cursor rule files (same content, Cursor format)
- `.mcp.json`, `.cursor/mcp.json` — MCP server configuration
- `*/CLAUDE.md` — Per-folder context files for every significant directory

---

### `/where-to-put`

**Purpose:** Answer "where should this new code go?" using the project's architecture rules.

**What it does:**
1. Reads `blueprint.json` for the current project
2. Looks up `quick_reference.where_to_put_code` and `architecture_rules.file_placement_rules`
3. Matches the user's query to the correct component type
4. Returns the exact path, naming convention, and related files to update

**Example:**
```
> /where-to-put a new payment webhook handler

Location: worker/webhooks/payment_webhook.py
Naming: snake_case, no suffix needed for webhook handlers
Pattern: Follow existing webhook handler structure in worker/webhooks/
Also update: worker/main.py (register handler), tests/webhooks/ (add tests)
```

**Why it's useful:** Prevents architectural drift. New developers don't have to guess where code goes — the blueprint tells them.

---

### `/check-naming`

**Purpose:** Validate a name against the project's established conventions.

**What it does:**
1. Reads `architecture_rules.naming_conventions` from the blueprint
2. Determines the scope (file, class, function, variable, route, etc.)
3. Checks the name against the convention
4. Returns pass/fail with the correct convention if failed

**Example:**
```
> /check-naming PaymentWebhookHandler as a class name

Name: PaymentWebhookHandler
Scope: class
Convention: PascalCase, no suffix for handlers in this project
Verdict: PASS
```

**Why it's useful:** Naming consistency across a team without memorizing conventions. Especially valuable in polyglot repos where conventions differ by language/layer.

---

### `/how-to-implement`

**Purpose:** Look up how existing capabilities were built — libraries, patterns, key files.

**What it does:**
1. Reads `implementation_guidelines` from the blueprint
2. Fuzzy-matches the user's query against capability names
3. Returns the matching guideline with libraries, key files, usage examples, and tips

**Example:**
```
> /how-to-implement email verification

Capability: Email/SMS Verification
Libraries: firebase-functions, Gmail API
Key files: gmail_webhook/main.py, worker/email_handler.py
Usage: Webhook receives Gmail push notification → parses verification code → stores in Supabase
Tips: Use the existing GmailWebhookParser class, don't roll your own parser
```

**Why it's useful:** Prevents developers from re-inventing patterns that already exist in the codebase. Surfaces tribal knowledge that lives in code but isn't documented anywhere.

---

### `/check-architecture`

**Purpose:** Validate uncommitted changes against the architecture blueprint.

**What it does:**
1. Runs `git diff --name-status` to find added/renamed files
2. For each new file, checks:
   - **Placement**: Is it in the correct directory per `file_placement_rules`?
   - **Naming**: Does the filename follow `naming_conventions`?
   - **Layer boundaries**: Do imports violate layer rules (e.g., domain importing from infrastructure)?
3. Reports a checklist of pass/fail per file

**Example:**
```
> /check-architecture

Architecture Review — 3 files checked

worker/services/payment_service.py
  Placement: PASS
  Naming: PASS
  Layers: PASS

worker/models/user.py
  Placement: FAIL (expected: worker/domain/entities/user.py)
  Naming: PASS
  Layers: PASS

agent-results-dashboard/src/components/PaymentForm.tsx
  Placement: PASS
  Naming: PASS
  Layers: PASS

Summary: 2 passed, 1 issue found
```

**Why it's useful:** Catches architectural violations before code review. Acts as an automated architecture reviewer that runs in seconds.

---

## Hooks

### Architecture Staleness Check

**File:** `.claude/hooks/check-architecture-staleness.sh`

**Trigger:** `SessionStart` — fires when a Claude Code conversation begins.

**What it does:**
- Checks if local `CLAUDE.md` is older than the source blueprint
- If stale: prints "Architecture files are outdated. Run `/sync-architecture` to update."
- If missing: prints "No architecture files found. Run `/sync-architecture` to provision them."
- If current: silent (no output)

**Why it's useful:** Developers don't have to remember to re-sync after a re-analysis. The staleness check is passive — it notifies but doesn't auto-modify files.

---

### Post-Edit Architecture Validation

**File:** `.claude/hooks/validate-architecture.sh`

**Trigger:** `PostToolUse` on `Write` — fires after Claude Code creates a new file.

**What it does:**
1. Reads the new file's path from the hook input (stdin JSON)
2. Loads the project's `blueprint.json` from Archie storage
3. Matches the filename against `architecture_rules.file_placement_rules` naming patterns
4. If the file matches a known component type, checks whether it's in the expected directory
5. If it's in the wrong location: **exits with code 2** and sends feedback via stderr
6. Claude Code receives the feedback and self-corrects by moving the file

**What it skips:**
- Edit operations (existing files are assumed to be in the right place)
- Non-source files (markdown, JSON, YAML, CSS, HTML)
- Files in ignored directories (node_modules, .git, __pycache__, etc.)
- Files that don't match any known naming pattern (no rule = no opinion)

**Example flow:**
```
1. Developer: "add a new service for notifications"
2. Claude Code creates worker/notifications/service.py
3. Hook fires, reads blueprint placement rules
4. Finds: *_service.py files belong in worker/auto_browser/services/
5. Hook exits 2 with: "Architecture violation: Service implementation
   files belong in worker/auto_browser/services/"
6. Claude Code receives feedback, moves the file to the correct location
```

**Why it's useful:** Turns the architecture blueprint from a passive document into an active guardrail. Catches placement violations at the moment of creation, before they reach code review. Claude Code self-corrects immediately — no human intervention needed.

**Performance:** The hook reads one JSON file and does string matching. Typical execution is <100ms. Only fires on `Write` (new files), not `Edit`, so it doesn't add latency to every keystroke.

**Configuration** (in `.claude/settings.json` or project settings):
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/validate-architecture.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

---

## Architecture

```
Developer's Project                       Archie Storage (local filesystem)
├── .archie/                              backend/storage/blueprints/{repo_id}/
│   └── repo_id  ─────────────────────►   ├── blueprint.json     ◄── Skills read this
├── CLAUDE.md          ◄── /sync ────────  ├── intent_layer/
├── AGENTS.md          ◄── /sync ────────  │   ├── CLAUDE.md
├── .claude/rules/*.md ◄── /sync ────────  │   ├── .claude/rules/
├── .cursor/rules/*.md ◄── /sync ────────  │   ├── .cursor/rules/
└── .mcp.json          ◄── /sync ────────  │   └── */CLAUDE.md
                                           └── ...

Skills (/where-to-put, /check-naming, /how-to-implement, /check-architecture)
  └── Read blueprint.json directly, no server needed
```

## Relationship to MCP Server

The MCP server (`/mcp/sse`) and these skills serve the same purpose through different channels:

| | MCP Tools | Skills |
|---|---|---|
| Requires server | Yes | No |
| Transport | SSE/HTTP | Filesystem reads |
| Data source | `blueprint.json` via BlueprintTools | `blueprint.json` via Claude Code Read |
| Best for | Web UI, remote access, cross-repo | Local Claude Code workflow, offline use |

Both coexist. The skills are not a replacement for MCP — they're a complementary path for the local development workflow where starting a server adds unnecessary friction.

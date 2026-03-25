# Supabase MCP Server for Claude Code Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Configure Supabase MCP server in Claude Code with environment variable-based token management.

**Architecture:** Project-level MCP configuration in `.claude/settings.local.json` with access token stored in `.claude.env` for security.

**Tech Stack:** Supabase MCP Server (@supabase/mcp-server-supabase), Claude Code MCP integration

---

## Task 1: Generate Supabase Access Token (Manual)

This is a manual step that must be done in the browser.

**Files:**
- None (external action)

**Step 1: Navigate to Supabase Dashboard**

1. Open browser and go to [https://app.supabase.com](https://app.supabase.com)
2. Log in if needed
3. Select the BedtimeApp project (or the relevant Supabase project)

**Step 2: Generate Access Token**

1. Click **Settings** in the left sidebar
2. Click **API** section
3. Scroll down to **Project API keys**
4. Copy the **service_role** key (this is your access token)
   - Alternative: Generate a new **Personal Access Token** from Account Settings → Access Tokens

**Step 3: Save token temporarily**

Copy the token to a secure location (clipboard or password manager) - you'll need it in Task 2.

**Expected token format:** `sbp_` followed by alphanumeric characters

---

## Task 2: Create `.claude.env` file with token

**Files:**
- Create: `/Users/csacsi/DEV/BedtimeApp/.claude.env`

**Step 1: Create the `.claude.env` file**

```bash
cd /Users/csacsi/DEV/BedtimeApp
touch .claude.env
```

**Step 2: Add the access token**

Add this content to `.claude.env` (replace `YOUR_TOKEN_HERE` with the actual token from Task 1):

```bash
# Supabase MCP Server Access Token for Claude Code
SUPABASE_ACCESS_TOKEN=YOUR_TOKEN_HERE
```

**Step 3: Verify file was created**

Run:
```bash
ls -la .claude.env
```

Expected: File exists with permissions `-rw-------` (only you can read/write)

**Step 4: Set restrictive permissions**

Run:
```bash
chmod 600 .claude.env
```

This ensures only you can read the file.

**Step 5: Commit**

**DO NOT commit this file yet** - we'll add it to `.gitignore` first in Task 3.

---

## Task 3: Update `.gitignore`

**Files:**
- Modify: `/Users/csacsi/DEV/BedtimeApp/.gitignore`

**Step 1: Check if `.gitignore` exists**

Run:
```bash
ls -la .gitignore
```

If it doesn't exist, create it:
```bash
touch .gitignore
```

**Step 2: Add `.claude.env` to `.gitignore`**

Add this line to `.gitignore`:

```
# Claude Code environment variables
.claude.env
```

**Step 3: Verify it's ignored**

Run:
```bash
git status
```

Expected: `.claude.env` should NOT appear in untracked files.

**Step 4: Commit**

```bash
git add .gitignore
git commit -m "chore: add .claude.env to gitignore

Prevents committing Claude Code Supabase MCP access token.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Update `.claude/settings.local.json`

**Files:**
- Modify: `/Users/csacsi/DEV/BedtimeApp/.claude/settings.local.json`

**Step 1: Read current content**

Current content:
```json
{
  "permissions": {
    "allow": [
      "Read(//Users/csacsi/.claude/**)",
      "Read(//Users/csacsi/DEV/BedtimeApp/**)"
    ]
  }
}
```

**Step 2: Add `mcpServers` configuration**

Replace the entire file content with:

```json
{
  "permissions": {
    "allow": [
      "Read(//Users/csacsi/.claude/**)",
      "Read(//Users/csacsi/DEV/BedtimeApp/**)"
    ]
  },
  "mcpServers": {
    "supabase": {
      "command": "npx",
      "args": [
        "-y",
        "@supabase/mcp-server-supabase",
        "--access-token",
        "${SUPABASE_ACCESS_TOKEN}"
      ]
    }
  }
}
```

**Step 3: Verify JSON is valid**

Run:
```bash
cat .claude/settings.local.json | python3 -m json.tool
```

Expected: Pretty-printed JSON with no errors.

**Step 4: Commit**

```bash
git add .claude/settings.local.json
git commit -m "feat: add Supabase MCP server configuration for Claude Code

Enables database access via MCP protocol with environment variable-based
token management.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Load environment variables in Claude Code

Claude Code needs to be configured to load `.claude.env` file.

**Files:**
- None (Claude Code configuration)

**Step 1: Check if Claude Code supports `.env` loading**

Claude Code may need explicit configuration to load environment variables from `.claude.env`.

**Option A: If Claude Code auto-loads `.claude.env`:**
- No action needed, proceed to Task 6

**Option B: If manual configuration needed:**
- Add to `.claude/settings.local.json`:
```json
{
  "permissions": { ... },
  "mcpServers": { ... },
  "envFile": ".claude.env"
}
```

**For now, assume Option A (auto-load) and test in Task 6.**

---

## Task 6: Restart Claude Code and verify MCP connection

**Files:**
- None (verification step)

**Step 1: Completely quit Claude Code**

- Press Cmd+Q or use File → Quit
- Verify process is terminated:
```bash
ps aux | grep -i claude
```

Expected: No Claude Code processes running.

**Step 2: Restart Claude Code**

Open Claude Code normally.

**Step 3: Open BedtimeApp project**

Navigate to `/Users/csacsi/DEV/BedtimeApp` in Claude Code.

**Step 4: Verify MCP server connection**

In Claude Code chat, ask:
```
Can you see any MCP servers connected? List them.
```

Expected response should mention "supabase" MCP server.

**Step 5: Test basic Supabase query**

Ask Claude Code:
```
Using the Supabase MCP server, list all tables in the database.
```

Expected: Claude should return a list of tables: `users`, `families`, `characters`, `stories`, `memories`, etc.

**Step 6: Verify schema access**

Ask:
```
Describe the 'characters' table schema using Supabase MCP.
```

Expected: Column names and types for the characters table.

---

## Task 7: Document setup in README (Optional)

**Files:**
- Modify: `/Users/csacsi/DEV/BedtimeApp/README.md` (or create `CLAUDE_SETUP.md`)

**Step 1: Add MCP setup section**

Add this section to README or create a new `CLAUDE_SETUP.md`:

```markdown
## Claude Code Setup

### Supabase MCP Server

Claude Code can access the Supabase database via MCP.

**Setup:**

1. Create `.claude.env` in project root:
   ```
   SUPABASE_ACCESS_TOKEN=your_token_here
   ```

2. Generate token from Supabase Dashboard → Settings → API

3. Restart Claude Code

**Verify:**
- Ask Claude: "List all Supabase tables"
- Should see: users, families, characters, stories, memories
```

**Step 2: Commit**

```bash
git add README.md  # or CLAUDE_SETUP.md
git commit -m "docs: add Claude Code Supabase MCP setup instructions

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Troubleshooting

**If MCP server doesn't connect:**

1. Check `.claude.env` exists and has correct token format
2. Verify `.claude/settings.local.json` syntax is valid JSON
3. Check Claude Code console for errors (if available)
4. Verify `@supabase/mcp-server-supabase` package is accessible:
   ```bash
   npx -y @supabase/mcp-server-supabase --help
   ```

**If environment variable not loaded:**

Add explicit `envFile` to `.claude/settings.local.json`:
```json
{
  "permissions": { ... },
  "envFile": ".claude.env",
  "mcpServers": { ... }
}
```

**If token invalid:**

Re-generate token from Supabase Dashboard and update `.claude.env`.

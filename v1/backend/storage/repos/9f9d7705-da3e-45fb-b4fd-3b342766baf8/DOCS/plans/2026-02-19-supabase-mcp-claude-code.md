# Supabase MCP Server Integration for Claude Code

**Date**: 2026-02-19
**Status**: Approved
**Goal**: Add Supabase MCP server to Claude Code for database access and management via Model Context Protocol.

---

## Overview

Enable Claude Code to interact with the BedtimeApp's Supabase database through the MCP (Model Context Protocol) using the official `@supabase/mcp-server-supabase` package.

## Context

The project already has Supabase MCP configured for Cursor (`.cursor/mcp.json`). We need the same functionality in Claude Code but with:
- A separate access token for security isolation
- Environment variable-based token management for better security
- Project-level configuration in `.claude/settings.local.json`

## Architecture

### Configuration Location

`.claude/settings.local.json` - Claude Code's project-specific configuration file. This file:
- Already exists in the project
- Is local-only (not committed to git)
- Supports `mcpServers` configuration

### MCP Server Configuration

Add an `mcpServers` object to `.claude/settings.local.json`:

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

**Key Design Decisions:**
- Uses `npx -y` to auto-install the package if not present
- Token loaded from environment variable for security
- Server name is `"supabase"` for clarity

### Token Storage

Create a `.claude.env` file in the project root:

```
# Supabase MCP Server Access Token for Claude Code
SUPABASE_ACCESS_TOKEN=sbp_your_new_token_here
```

**Why separate `.claude.env`?**
- Keeps Claude-specific config separate from backend/frontend `.env` files
- Easy to add to `.gitignore`
- Clear separation of concerns

### Token Generation

New Supabase access token will be generated via:
1. Supabase Dashboard → Settings → API
2. Generate new Personal Access Token or use Service Role Key
3. Store in `.claude.env`

**Security Notes:**
- Use a dedicated token for Claude Code (not the same as Cursor)
- Token has full database access - treat as sensitive credential
- Never commit `.claude.env` to git

---

## What Changes

| File | Change |
|------|--------|
| `.claude/settings.local.json` | Add `mcpServers` configuration |
| `.claude.env` | **New** - Store `SUPABASE_ACCESS_TOKEN` |
| `.gitignore` | Add `.claude.env` to ignore list |

---

## Capabilities Enabled

Once configured, Claude Code will be able to:
- Query Supabase database tables (users, families, characters, stories, memories)
- Inspect schema and relationships
- Run SQL queries for debugging
- Manage database migrations (if needed)
- Access Supabase Storage buckets info

**MCP Tools Available:**
- `supabase_query` - Run SQL queries
- `supabase_list_tables` - List database tables
- `supabase_describe_table` - Get table schema
- Additional tools provided by `@supabase/mcp-server-supabase`

---

## Security Considerations

1. **Token Scope**: The access token has full database access. Be cautious with queries.
2. **Token Rotation**: Consider rotating the token periodically
3. **Git Safety**: Ensure `.claude.env` is in `.gitignore`
4. **Separate Tokens**: Cursor and Claude Code use different tokens for isolation

---

## Testing

After configuration:
1. Restart Claude Code
2. Verify MCP server connection in Claude Code
3. Test a simple query: "List all tables in the Supabase database"
4. Verify Claude can access schema information

---
description: Architecture MCP server usage rules
alwaysApply: true
---

## Architecture MCP Server (MANDATORY)

The `architecture-blueprints` MCP server is the single source of truth for this codebase's architecture.
You MUST call its tools for every architecture decision — no exceptions.

| Tool | When to Use | Required |
|------|------------|----------|
| `where_to_put` | Creating or moving any file | **Always** |
| `check_naming` | Naming any new component | **Always** |
| `list_implementations` | Discovering available implementation patterns | **Always** |
| `how_to_implement_by_id` | Getting full details for a specific capability | **Always** |
| `how_to_implement` | Fuzzy search when exact capability name unknown | Fallback |
| `get_file_content` | Reading source files referenced in guidelines | As needed |
| `list_source_files` | Browsing available source files | As needed |
| `get_repository_blueprint` | Understanding overall architecture | As needed |

### Workflow

1. Call `list_implementations` to see all known patterns
2. Match task to capability, call `how_to_implement_by_id` with its ID
3. Fall back to `how_to_implement` with keyword search if no match
4. Call `get_file_content` to study referenced source files
5. Call `where_to_put` before creating any file
6. Call `check_naming` before naming any component

> If a tool rejects a decision, do NOT proceed — fix the violation first.
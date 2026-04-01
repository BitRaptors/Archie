# Architecture Validation Hooks Design

**Date:** 2026-03-09
**Status:** Approved

## Problem

AI agents write code that works but may violate architectural rules — wrong file placement, wrong naming conventions, wrong patterns. Currently only `PostToolUse` on `Write` validates file placement. No validation on Edit, no review at end of session, and no automatic blueprint/CLAUDE.md refresh.

## Solution: 3-Hook Architecture Validation

### Hook 1: PreToolUse (Write) — Pre-creation validation

**Event:** `PreToolUse`, **Matcher:** `Write`

Validates file placement BEFORE the file is created. Reads `blueprint.json` directly (no MCP). If the file would go to the wrong location, exits with code 2 to block creation and provide corrective feedback.

**Difference from existing PostToolUse hook:** Prevents the bad file from ever being written, rather than flagging it after.

**Script:** `.claude/hooks/pre-validate-architecture.sh`

### Hook 2: PostToolUse (Write|Edit) — Immediate post-edit validation

**Event:** `PostToolUse`, **Matcher:** `Write|Edit`

Extends the existing `validate-architecture.sh` to also run on Edit operations. Checks:
- File placement rules (existing logic)
- Naming conventions (new: checks against `naming_conventions` in blueprint)

**Script:** Update existing `.claude/hooks/validate-architecture.sh`

### Hook 3: Stop — Session-end review + intent layer refresh

**Event:** `Stop`, **Matcher:** none (always fires)

When Claude finishes responding:

1. **Collect changes:** `git diff --name-only` (unstaged + staged) to find all affected files
2. **Validate each file** against blueprint:
   - `file_placement_rules` check
   - `naming_conventions` check
3. **Check per-folder CLAUDE.md freshness** for affected directories
4. **Refresh intent layer:** If changes detected, call backend API (`POST /delivery/apply` with `strategy=local`) to regenerate affected CLAUDE.md files
5. **Output summary** to stdout so Claude sees it

**Script:** `.claude/hooks/stop-review-and-refresh.sh`

## Technical Decisions

### Blueprint access: Direct file read (not MCP)
- PreToolUse and PostToolUse read `blueprint.json` directly via python3
- Fast, no network dependency for validation
- MCP is for external tool consumers, not internal hooks

### Intent layer refresh: Backend API call (hybrid)
- Stop hook calls `curl http://localhost:8000/delivery/apply` with `strategy=local`
- Backend handles rendering logic (deterministic + optional AI enrichment)
- Only triggered at session end, not per-edit

### Blueprint location resolution
All hooks resolve blueprint via:
1. `~/.archie/config.json` → `storage_path`
2. `{cwd}/.archie/repo_id` → `repo_id`
3. `{storage_path}/blueprints/{repo_id}/blueprint.json`

### Exit codes
- `0` = pass (or no blueprint found, graceful skip)
- `2` = violation found, Claude should correct

## Configuration

Added to `.claude/settings.local.json`:

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Write",
      "hooks": [{"type": "command", "command": "./.claude/hooks/pre-validate-architecture.sh", "timeout": 5}]
    }],
    "PostToolUse": [{
      "matcher": "Write|Edit",
      "hooks": [{"type": "command", "command": "./.claude/hooks/validate-architecture.sh", "timeout": 5}]
    }],
    "Stop": [{
      "hooks": [{"type": "command", "command": "./.claude/hooks/stop-review-and-refresh.sh", "timeout": 30}]
    }]
  }
}
```

## Files to create/modify

| File | Action | Purpose |
|------|--------|---------|
| `.claude/hooks/pre-validate-architecture.sh` | Create | PreToolUse Write validation |
| `.claude/hooks/validate-architecture.sh` | Modify | Add Edit support + naming validation |
| `.claude/hooks/stop-review-and-refresh.sh` | Create | Stop review + intent layer refresh |
| `.claude/settings.local.json` | Modify | Register all 3 hooks |

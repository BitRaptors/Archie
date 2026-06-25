#!/usr/bin/env bash
# Archie churn tracker — accumulate edit volume since the last sync.
# Non-blocking: ALWAYS exit 0. Fires on PostToolUse Edit/Write (Claude) and
# apply_patch (Codex) via the manifest matcher mapping. The Python side
# normalizes both CLIs' envelope field names.
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
[ ! -f "$PROJECT_ROOT/.archie/blueprint.json" ] && exit 0
ENVELOPE=$(cat || true)
[ -z "$ENVELOPE" ] && exit 0
printf '%s' "$ENVELOPE" \
  | python3 "$PROJECT_ROOT/.archie/sync.py" churn-bump "$PROJECT_ROOT" >/dev/null 2>&1 || true
exit 0

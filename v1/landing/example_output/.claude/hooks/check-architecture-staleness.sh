#!/bin/bash
# Hook: check-architecture-staleness
# Runs on conversation start. Checks if local architecture files
# are older than the blueprint source and notifies the user.
# Does NOT auto-sync — just surfaces the information.

set -euo pipefail

CONFIG=".archie/config.json"

# Skip if no archie config exists
if [ ! -f "$CONFIG" ]; then
    exit 0
fi

# Read storage path
STORAGE_PATH=$(python3 -c "import json; print(json.load(open('$CONFIG'))['storage_path'])" 2>/dev/null)
if [ -z "$STORAGE_PATH" ]; then
    exit 0
fi

# Skip if no repo_id cached
REPO_ID_FILE=".archie/repo_id"
if [ ! -f "$REPO_ID_FILE" ]; then
    exit 0
fi

REPO_ID=$(cat "$REPO_ID_FILE")
SOURCE_CLAUDE="$STORAGE_PATH/blueprints/$REPO_ID/intent_layer/CLAUDE.md"
LOCAL_CLAUDE="CLAUDE.md"

# Skip if source blueprint doesn't exist
if [ ! -f "$SOURCE_CLAUDE" ]; then
    exit 0
fi

# If local CLAUDE.md doesn't exist at all, suggest sync
if [ ! -f "$LOCAL_CLAUDE" ]; then
    echo "No architecture files found. Run /sync-architecture to provision them."
    exit 0
fi

# Compare modification times
if [ "$SOURCE_CLAUDE" -nt "$LOCAL_CLAUDE" ]; then
    echo "Architecture files are outdated. Run /sync-architecture to update."
fi

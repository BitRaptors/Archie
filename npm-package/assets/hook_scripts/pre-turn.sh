#!/usr/bin/env bash
# Archie pre-turn reset — clears the per-turn rule-injection marker so the
# next Write/Edit surfaces applicable rules again. Runs on UserPromptSubmit.
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
TURN_HASH=$(printf '%s' "$PROJECT_ROOT" | cksum | awk '{print $1}')
rm -f "/tmp/.archie_turn_$TURN_HASH"

# Archie intent capture (best-effort; never blocks the turn). Feeds the clean-room
# intent transform. The prompt is on stdin as JSON; capture it verbatim.
if [ -f .archie/intent_capture.py ]; then
  python3 -c "import sys,json;print(json.load(sys.stdin).get('prompt',''))" 2>/dev/null \
    | python3 .archie/intent_capture.py user-turn . 2>/dev/null || true
fi

exit 0

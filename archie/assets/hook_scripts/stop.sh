#!/usr/bin/env bash
# Archie Stop hook (canonical, source of truth).
# Runs when the agent finishes a turn/session (CLI-dependent semantics).
# Light cleanup, then nudges the agent to run /archie-sync when there is
# unrecorded work — blocking signal is exit code 2 on BOTH Claude and Codex.
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
INPUT=$(cat 2>/dev/null || true)   # Stop event envelope (may be empty on some CLIs)
TURN_HASH=$(printf '%s' "$PROJECT_ROOT" | cksum | awk '{print $1}')
# Avoid leaking per-turn rule injection state if a session ends without the
# next UserPromptSubmit event clearing it.
rm -f "/tmp/.archie_turn_$TURN_HASH"

[ ! -f "$PROJECT_ROOT/.archie/blueprint.json" ] && exit 0

# Loop guard: if the agent is ALREADY continuing because of our previous Stop
# nudge (stop_hook_active is true), do not nudge again — let it stop. Without
# this, the exit-2 nudge re-fires on every stop attempt until a sync resets
# churn, which would defeat the "Decline if nothing is worth recording"
# affordance and risk an indefinite stop loop.
STOP_ACTIVE=$(printf '%s' "$INPUT" | python3 -c "
import sys, json
try: print('1' if json.load(sys.stdin).get('stop_hook_active') else '')
except Exception: print('')
" 2>/dev/null || echo "")
[ -n "$STOP_ACTIVE" ] && exit 0

CHURN=$(python3 "$PROJECT_ROOT/.archie/sync.py" churn-status "$PROJECT_ROOT" 2>/dev/null || echo '{}')
PLANS=$(python3 "$PROJECT_ROOT/.archie/sync.py" plan-list "$PROJECT_ROOT" 2>/dev/null || echo '{}')

NUDGE=$(CHURN="$CHURN" PLANS="$PLANS" python3 - <<'PY'
import json, os
churn = json.loads(os.environ.get("CHURN") or "{}")
plans = json.loads(os.environ.get("PLANS") or "{}")
nplans = len(plans.get("plans", []))
if churn.get("crossed") or nplans:
    f, l = churn.get("files", 0), churn.get("lines", 0)
    extra = f", {nplans} captured plan(s)" if nplans else ""
    print(f"Archie: considerable work since last sync ({f} files / {l} lines changed{extra}). "
          f"Run /archie-sync to record any behavior change, impact, or rule, then stop. "
          f"Decline if nothing is worth recording.")
PY
)

if [ -n "$NUDGE" ]; then
    printf '%s\n' "$NUDGE" >&2
    exit 2
fi
exit 0

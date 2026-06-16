# Archie Development Studio — New Issue

Create a new ticket.

1. Ask the user (or infer from their request): title, type
   (feature/bugfix/refactor/chore), labels.
2. Run: `python3 .archie/studio.py new . --title "<title>" --type <type>
   --label <label>` (repeat `--label` per label).
3. Open the created ticket file under `.archie/issues/planned/` and fill in the
   `## Context` section. Leave `## Plan` empty (it is filled during `{{COMMAND_PREFIX}}archie-work`).
4. Commit `docs(issues): add <ISS-NNN> <title>` and push so the ticket is visible.
5. Tell the user the ticket id and that `{{COMMAND_PREFIX}}archie-work` will pick it up.

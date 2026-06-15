# Archie Development Studio — Setup

Set up the development studio in this project.

1. Run: `python3 .archie/studio.py init .`
   This scaffolds `.archie/issues/` (status folders, `_TEMPLATE.md`, `WORKFLOW.md`,
   `INDEX.md`) and inserts a pointer block into `AGENTS.md`.
2. Confirm `.archie/issues/WORKFLOW.md` exists and read it — it is the source of truth
   for the workflow.
3. If `.archie/blueprint.json` is missing, tell the user the loop will run without
   architectural enforcement/guidance and recommend running `{{COMMAND_PREFIX}}archie-deep-scan` first.
4. Report what was created and point the user at `{{COMMAND_PREFIX}}archie-issue` (create a ticket) and
   `{{COMMAND_PREFIX}}archie-work` (run the loop).

Do not commit automatically — let the user review, then commit
`docs(studio): initialize development studio`.

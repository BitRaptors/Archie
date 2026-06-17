# Archie Development Studio — Setup

Set up the development studio in this project.

1. Ask the user two setup questions (these are saved to `.archie/studio.json` and
   apply to every ticket in this project):
   - **Ticket prefix** — the short code tickets are numbered with (e.g. `ISS`, `KAV`,
     `SUB`). Suggest a code derived from the project name; default `ISS`. 2–6
     alphanumeric chars, uppercased automatically.
   - **Documentation language** — the language the agent writes ticket content in
     (Context, Plan, Iteration Log, Review Notes, PR descriptions); default `English`.
     Code, identifiers, and commit prefixes always stay as-is.
   Then run: `python3 .archie/studio.py init . --prefix <PREFIX> --lang <LANGUAGE>`
   This scaffolds `.archie/issues/` (status folders, `_TEMPLATE.md`, `WORKFLOW.md`,
   `INDEX.md`), writes `.archie/studio.json`, and inserts a pointer block into
   `AGENTS.md` recording both settings.
2. Confirm `.archie/issues/WORKFLOW.md` exists and read it — it is the source of truth
   for the workflow.
3. If `.archie/blueprint.json` is missing, tell the user the loop will run without
   architectural enforcement/guidance and recommend running `{{COMMAND_PREFIX}}archie-deep-scan` first.
4. Report what was created and point the user at `{{COMMAND_PREFIX}}archie-issue` (create a ticket) and
   `{{COMMAND_PREFIX}}archie-work` (run the loop).

Do not commit automatically — let the user review, then commit
`docs(studio): initialize development studio`.

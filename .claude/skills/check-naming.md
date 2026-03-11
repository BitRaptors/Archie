# Skill: check-naming

Validate a name (file, class, function, variable) against the project's architecture conventions.

## Instructions

The user wants to check if a name follows the project's established conventions. Use the Archie blueprint to validate.

### Step 1: Resolve the blueprint

1. Read `~/.archie/config.json` to get `storage_path`. If missing, ask the user for the path to their `backend/storage` directory and create the config.
2. Read `.archie/repo_id` from the current project root. If missing, resolve it:
   - Run `git remote get-url origin`, extract `owner/repo`
   - Scan `{storage_path}/blueprints/*/blueprint.json` to find the matching `meta.repository`
   - Save the `repo_id` to `.archie/repo_id`
3. Read `{storage_path}/blueprints/{repo_id}/blueprint.json`.

### Step 2: Extract naming conventions

From the blueprint, read:
- `architecture_rules.naming_conventions` — the full list of naming rules by scope (files, classes, functions, variables, routes, database tables, etc.)

### Step 3: Validate

The user provides a name and optionally a scope (e.g., "is `PaymentService` a good class name?", "check `get-user-data` as an endpoint").

1. Determine the scope from context (file, class, function, variable, route, etc.)
2. Find the matching naming convention for that scope
3. Check the name against the convention rules (case style, prefix/suffix, patterns)

### Step 4: Respond

- If valid: Confirm it follows the convention, state which rule it matches
- If invalid: Explain why, show the correct convention, suggest the corrected name

Keep responses short:

```
Name: {name}
Scope: {scope}
Convention: {rule}
Verdict: PASS or FAIL
Suggestion: {corrected name if failed}
```

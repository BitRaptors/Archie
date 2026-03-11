# Skill: where-to-put

Answer "where should I put this new code?" by consulting the project's Archie blueprint.

## Instructions

The user is asking where a new piece of code (component, service, route, utility, test, etc.) should be placed in their project. Use the Archie blueprint to give a precise answer.

### Step 1: Resolve the blueprint

1. Read `~/.archie/config.json` to get `storage_path`. If missing, ask the user for the path to their `backend/storage` directory and create the config.
2. Read `.archie/repo_id` from the current project root. If missing, resolve it:
   - Run `git remote get-url origin`, extract `owner/repo`
   - Scan `{storage_path}/blueprints/*/blueprint.json` to find the matching `meta.repository`
   - Save the `repo_id` to `.archie/repo_id`
3. Read `{storage_path}/blueprints/{repo_id}/blueprint.json`.

### Step 2: Extract placement rules

From the blueprint, read these sections:
- `quick_reference.where_to_put_code` — a mapping of component types to their locations
- `architecture_rules.file_placement_rules` — detailed rules with patterns, examples, and conventions
- `architecture_rules.naming_conventions` — how to name files and classes

### Step 3: Match and respond

1. Identify what kind of component the user is asking about (service, route, model, test, utility, component, hook, etc.)
2. Find the matching entry in `where_to_put_code` and `file_placement_rules`
3. Respond with:
   - **Path**: The exact directory and suggested filename
   - **Naming**: The naming convention to follow (case, prefix/suffix)
   - **Pattern**: Any architectural pattern to follow (e.g., "register route in app.py", "extend base class", "add to __init__.py exports")
   - **Related files**: Files the user will likely also need to touch (e.g., route registration, dependency injection, tests)

### Response format

Keep it concise and actionable:

```
Location: {path}/{suggested_filename}
Naming: {convention}
Pattern: {what to follow}
Also update: {related files}
```

If the component type doesn't match any rule, say so and suggest the closest match.

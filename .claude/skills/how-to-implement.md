# Skill: how-to-implement

Look up how an existing capability was implemented in the project — libraries, patterns, key files, and usage examples.

## Instructions

The user wants to know how something is already implemented in their project (e.g., "how was auth done?", "how do push notifications work?", "what library handles email?"). Use the Archie blueprint to answer.

### Step 1: Resolve the blueprint

1. Read `~/.archie/config.json` to get `storage_path`. If missing, ask the user for the path to their `backend/storage` directory and create the config.
2. Read `.archie/repo_id` from the current project root. If missing, resolve it:
   - Run `git remote get-url origin`, extract `owner/repo`
   - Scan `{storage_path}/blueprints/*/blueprint.json` to find the matching `meta.repository`
   - Save the `repo_id` to `.archie/repo_id`
3. Read `{storage_path}/blueprints/{repo_id}/blueprint.json`.

### Step 2: Search implementation guidelines

From the blueprint, read `implementation_guidelines`. This is an array of objects, each with:
- `capability` — what it does (e.g., "Push Notifications", "Authentication")
- `libraries` — third-party libraries used
- `key_files` — the source files that implement it
- `usage_example` — code snippets showing how to use it
- `tips` — practical advice

Fuzzy-match the user's query against `capability` names and descriptions. If no exact match, find the closest.

### Step 3: Respond

Present the matching implementation guideline clearly:

```
Capability: {name}
Libraries: {list}
Key files: {paths}

Usage:
{example code}

Tips:
{practical advice}
```

If the user's query matches multiple capabilities, list all matches briefly and ask which one they want details on.

If no match is found, say so. Suggest checking `developer_recipes` in the blueprint for task-oriented guides, or recommend looking at the `components` section for module-level documentation.

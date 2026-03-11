# Skill: check-architecture

Validate recent code changes against the project's Archie blueprint — check file placement, naming, and layer boundary violations.

## Instructions

The user wants to verify their recent changes follow the established architecture. Review the git diff against the Archie blueprint rules.

### Step 1: Resolve the blueprint

1. Read `~/.archie/config.json` to get `storage_path`. If missing, ask the user for the path to their `backend/storage` directory and create the config.
2. Read `.archie/repo_id` from the current project root. If missing, resolve it:
   - Run `git remote get-url origin`, extract `owner/repo`
   - Scan `{storage_path}/blueprints/*/blueprint.json` to find the matching `meta.repository`
   - Save the `repo_id` to `.archie/repo_id`
3. Read `{storage_path}/blueprints/{repo_id}/blueprint.json`.

### Step 2: Get changed files

Run `git diff --name-status HEAD` (or `git diff --name-status` if there are unstaged changes) to get the list of added (A), modified (M), and renamed (R) files. Focus on **added** and **renamed** files for placement checks — modified files are assumed to be in the right place already.

If there are no changes, tell the user: "No uncommitted changes to check."

### Step 3: Load architecture rules

From the blueprint, read:
- `architecture_rules.file_placement_rules` — where each component type belongs
- `architecture_rules.naming_conventions` — how files and symbols should be named
- `components` — the layer structure (which layers can import from which)
- `quick_reference.where_to_put_code` — quick lookup table

### Step 4: Validate each new/renamed file

For each added or renamed file:

1. **Placement check**: Determine what kind of component the file is (from its path and name). Check if it's in the correct directory according to `file_placement_rules` and `where_to_put_code`. Flag if it's in the wrong location.

2. **Naming check**: Check the filename against `naming_conventions` for its scope. Flag if it doesn't follow the convention.

3. **Layer boundary check** (if detectable from imports): For added files, read the file content. Check if imports cross layer boundaries in the wrong direction (e.g., domain importing from infrastructure, API importing directly from persistence). This is a best-effort check based on the `components` section.

### Step 5: Report

Format the results as a checklist:

```
Architecture Review — {n} files checked

{filename}
  Placement: PASS or FAIL (expected: {correct_path})
  Naming: PASS or FAIL (convention: {rule})
  Layers: PASS or FAIL (violation: {detail})

Summary: {pass_count} passed, {fail_count} issues found
```

If everything passes, say so briefly. If there are failures, explain each one with the correct alternative.

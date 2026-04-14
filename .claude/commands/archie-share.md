# Archie Share — Upload Blueprint for Sharing

Share your architecture blueprint via a URL. Useful for showing teammates, stakeholders, or clients an analysis of your codebase without needing them to install anything.

**Prerequisites:** Requires `.archie/blueprint.json`. Run `/archie-scan` (or `/archie-deep-scan`) first if it doesn't exist.

## Resolve target blueprint

Read the persisted scope config to determine which blueprint(s) can be shared:

```bash
python3 .archie/intent_layer.py scan-config "$PWD" read
```

- **Exit 1 (no config) or scope is `single` or `whole`** → there's one blueprint at the repo root. Use `TARGET="$PWD"`.
- **scope is `per-package`** → multiple workspace-level blueprints exist.
  - If exactly one workspace is listed → use that one: `TARGET="$PWD/<workspace>"`.
  - If multiple → ask the user:
    > You have per-package blueprints in: `<workspace-1>`, `<workspace-2>`, ...
    > Which one should I share? (number/name/`all`)
    If they answer `all`, loop and upload each separately.
- **scope is `hybrid`** → root has a monorepo-wide blueprint AND each listed workspace has its own.
  - Ask the user:
    > Share the monorepo-wide blueprint, or a specific workspace?
    > Options: `root`, `<workspace-1>`, `<workspace-2>`, ...
  - `root` → `TARGET="$PWD"`. Workspace name → `TARGET="$PWD/<workspace>"`.

## Run

For each resolved `TARGET`:

```bash
python3 .archie/upload.py "$TARGET"
```

The script prints a shareable URL on success. For `all` mode in per-package, print one URL per workspace with a label (e.g., `apps/webui: <url>`).

If the upload fails (network issues, server down), your local blueprint is unaffected. Try again later.

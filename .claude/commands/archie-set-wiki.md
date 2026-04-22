# Archie — Wiki generation setting

Enable or disable Archie's wiki generation for this project. The setting is persisted in `.archie/archie_config.json` so it survives across scans.

**Usage:**
- `/archie-set-wiki` — show current status
- `/archie-set-wiki on` — enable wiki generation
- `/archie-set-wiki off` — disable wiki generation

**Prerequisites:** `.archie/intent_layer.py` must exist. If it does not, tell the user to run `npx @bitraptors/archie` first.

---

## Behavior

Parse the user's argument (the text after `/archie-set-wiki`). Normalize by lowercasing and trimming.

### No argument (or `status`) → show current state

```bash
python3 .archie/intent_layer.py config "$PWD" get wiki_enabled
```

Parse the JSON. Present a short human-readable summary:

- If `source == "config"` → "Wiki generation is **{enabled|disabled}** (persisted in `.archie/archie_config.json`)."
- If `source == "default"` → "Wiki generation is **{enabled|disabled}** (default — not explicitly set)."
- If `source` starts with `env-override` → "Wiki generation is **{enabled|disabled}** via the `ARCHIE_WIKI_ENABLED` environment variable. This overrides any `.archie/archie_config.json` setting for the current shell."

Also remind the user how to change it: "Run `/archie-set-wiki on` or `/archie-set-wiki off` to change the persisted value."

### Argument `on` / `true` / `enable` / `yes` → enable

```bash
python3 .archie/intent_layer.py config "$PWD" set wiki_enabled on
```

Confirm: "Wiki generation **enabled**. The next `/archie-scan` or `/archie-deep-scan` will build the wiki at `.archie/wiki/`."

If the `ARCHIE_WIKI_ENABLED` env var is set to a falsy value, warn the user: "Note: `ARCHIE_WIKI_ENABLED` is set in your environment and will override this setting until you unset it."

### Argument `off` / `false` / `disable` / `no` → disable

```bash
python3 .archie/intent_layer.py config "$PWD" set wiki_enabled off
```

Confirm: "Wiki generation **disabled**. Scans and deep-scans will skip the wiki build step. Existing files in `.archie/wiki/` are kept untouched — delete them manually if you want them gone."

### Anything else → reject

Print: "Unknown argument. Use `on`, `off`, or no argument to show status."

---

## Notes

- Only boolean flags are supported today. The underlying `intent_layer.py config` command has an allowlist of settable keys; adding more (e.g., `intent_layer_enabled`) is a one-line change in `_CONFIG_FLAGS`.
- The env var precedence is: `ARCHIE_WIKI_ENABLED` > `archie_config.json` > default (true). This matches what `renderer.py` and `wiki_builder.py` already do.

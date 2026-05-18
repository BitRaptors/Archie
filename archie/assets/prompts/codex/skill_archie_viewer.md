---
name: archie-viewer
description: Codex-native launcher for the Archie local viewer.
---

# Archie Viewer For Codex

Run the Archie local viewer without relying on Claude-only primitives.

## Preconditions

- If `.archie/viewer.py` is missing, stop and tell the user to run `npx @bitraptors/archie "$PWD"` first.
- If `.archie/viewer/dist/index.html` is missing, tell the user the local viewer bundle is not built yet and they should rerun `npx @bitraptors/archie "$PWD"` in a networked shell.
- Use the repository root as the working directory.

## Telemetry adaptation

The shared Archie flow references a Claude-only `AskUserQuestion` telemetry prompt. In Codex:

- if the session is interactive and you need to ask, use one short plain-text yes/no question
- if the session is non-interactive, skip the prompt and continue

## Launch

Run:

```bash
python3 .archie/viewer.py "$PWD"
```

If the viewer starts successfully, report the local URL. If it fails, report the command error directly.

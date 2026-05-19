---
name: archie-share
description: Codex-native wrapper for Archie share.
---

# Archie Share For Codex

Run Archie share from Codex while translating Claude-specific interaction primitives into normal chat.

## How to execute

Read `.archie/prompts/skill_archie_share.md` in full and execute it, with these required adaptations:

- When the shared prompt says `AskUserQuestion`, ask the user a concise plain-text question and wait for the answer.
- When the shared prompt expects a single-choice picker, present the options in plain text and ask the user to reply with one choice.
- When the shared prompt expects a multi-select picker, ask the user to reply with a comma-separated list.
- When the shared prompt mentions Claude-specific UI affordances, map them to ordinary Codex chat responses instead of stopping.

Do not invent a new share flow. Reuse the same Archie scripts and artifacts the shared prompt requires.

---
name: archie-intent-layer
description: Codex-native wrapper for Archie intent-layer generation.
---

# Archie Intent Layer For Codex

Run Archie intent-layer generation from Codex while adapting Claude-only orchestration terms.

## How to execute

Read `.archie/prompts/skill_archie_intent_layer.md` in full and execute it, with these required adaptations:

- When the shared prompt says `AskUserQuestion`, ask the user a concise plain-text question and wait for the answer.
- When the shared prompt says to use the Claude `Agent` tool, use Codex subagents if they are clearly available and helpful.
- If Codex subagents are unavailable, continue locally instead of failing just because the prompt mentioned Claude’s tool name.
- Keep all file writes, script invocations, and artifact paths identical to the shared Archie flow.

If a Claude-only instruction is purely about UI wording, translate it to normal Codex chat and continue.

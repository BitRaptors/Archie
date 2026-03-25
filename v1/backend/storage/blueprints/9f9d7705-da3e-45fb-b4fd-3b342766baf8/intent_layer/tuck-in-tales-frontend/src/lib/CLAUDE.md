# lib/
> Centralized configuration library exposing prompt templates and utility functions for story generation AI pipelines.

## Patterns

- PromptVariable interface standardizes all template variables: name, description, sample value
- PROMPT_VARIABLES keyed by AI task type (avatar_description, story_outline, page_text, image_prompt) enables task-specific variable injection
- AVAILABLE_PROVIDERS and AVAILABLE_MODELS use parallel Record structure for provider→models mapping
- Sample values in PromptVariable demonstrate real, domain-specific formatting (multilingual, character birthdates, visual descriptions)
- cn() utility combines clsx + twMerge for safe Tailwind class merging without conflicts

## Navigation

**Parent:** [`src/`](../CLAUDE.md)
**Peers:** [`components/`](../components/CLAUDE.md) | [`hooks/`](../hooks/CLAUDE.md) | [`models/`](../models/CLAUDE.md) | [`pages/`](../pages/CLAUDE.md) | [`utils/`](../utils/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `promptVariables.ts` | Define all AI prompt templates and model availability | Add new task: create Record key + PromptVariable[] with real samples. Update AVAILABLE_MODELS when adding providers. |
| `utils.ts` | Export reusable utility functions | cn() is the only export; extend here for classname utilities only, not business logic. |

## Key Imports

- `import { PromptVariable, PROMPT_VARIABLES } from '@/lib/promptVariables'`
- `import { cn } from '@/lib/utils'`

## Add a new AI generation task with its prompt variables

1. Add Record key (e.g., 'story_epilogue') to PROMPT_VARIABLES
2. Define PromptVariable[] with realistic sample values matching task requirements
3. If new provider needed, add to AVAILABLE_PROVIDERS and AVAILABLE_MODELS

## Don't

- Don't hardcode prompt variables in components — they live in promptVariables.ts for consistency
- Don't create new style utilities outside utils.ts — cn() is the single source for Tailwind merging
- Don't add sample values that aren't realistic — samples guide downstream prompt construction accuracy

## Why It's Built This Way

- PromptVariable.sample is mandatory because it documents expected format and trains downstream code generation — not just reference
- Task-keyed Record structure allows UI to dynamically render variable forms per task without hardcoding logic in components

## Dependencies

**Depends on:** `Backend API`, `Firebase Auth`, `Supabase`
**Exposes to:** `end users (browser)`

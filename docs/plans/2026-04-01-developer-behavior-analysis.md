# Developer Behavior Analysis — Design Notes

## The Idea

Analyze the developer's interaction patterns with Claude Code — not just the code, but what they ask for, what they correct, what they never think about. Cross-reference with the architecture to surface blind spots and implicit rules.

**No other tool does this.** Static analysis looks at code. Archie looks at architecture. This looks at the **developer-AI interaction gap** — the space between what the developer wants and what the AI produces. That gap IS where architectural knowledge is missing.

## Technical Foundation

**`UserPromptSubmit` hook** — Claude Code fires this on every user message. It receives:
```json
{
  "session_id": "abc123",
  "prompt": "the actual user text",
  "cwd": "/path/to/project"
}
```

A hook can log every prompt to `.archie/prompt_log.jsonl`.

## Three Layers

### Layer 1: Accumulate
A `UserPromptSubmit` hook logs every user prompt:
```jsonl
{"timestamp": "ISO-8601", "prompt": "add a caching layer to the API", "session_id": "abc"}
{"timestamp": "ISO-8601", "prompt": "no, don't put that in the ViewModel", "session_id": "abc"}
{"timestamp": "ISO-8601", "prompt": "where should I put the error handling?", "session_id": "abc"}
```

### Layer 2: Correlate
Cross-reference with git history. For each session:
- What files were changed? (git log by timestamp range)
- What was the intent vs the outcome?
- Did the developer correct the AI? How many times?

### Layer 3: Analyze
During `/archie-deep-scan` or a dedicated command, an AI agent reads the accumulated prompt log + blueprint and identifies:

- **Implicit rules**: "Developer corrected file placement 4 times in same area → propose rule"
- **Blind spots**: "Developer never mentions testing, error handling, accessibility, security → flag as areas needing attention"
- **Intent patterns**: "80% of prompts are about UI, 0% about security → security is a blind spot"
- **Correction patterns**: "Developer frequently says 'no not there' or 'that's wrong' → architecture description might be misleading the AI"
- **Missing context**: "Developer keeps explaining the same constraint → it should be a rule"
- **Proactive questions**: The agent can ASK about things the developer never brings up — "I notice you've never discussed error recovery. How should failed API calls be handled in this codebase?"

## What Makes This Unique

The developer's behavior reveals what they **don't think about** — and those are exactly the blind spots where AI agents will make mistakes. By accumulating interaction data over time and cross-referencing with the evolving codebase, Archie can:

1. Propose rules the developer never explicitly stated
2. Ask questions the developer never thought to answer
3. Detect when the developer's mental model diverges from the actual architecture
4. Surface areas of the codebase that get zero attention (maintenance blind spots)

## Open Questions

- Privacy: should prompt logging be opt-in? (probably yes)
- Storage: how much data before it's useful? (probably 50+ sessions)
- Analysis: part of deep scan or separate command?
- Scope: project-level or cross-project patterns?

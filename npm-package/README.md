# Archie

AI-powered architecture enforcement for Claude Code. Zero dependencies.

Archie scans your codebase, builds a structured architecture blueprint, and enforces it in real-time through Claude Code hooks. When your AI agent tries to break an architectural constraint, Archie catches it before the code is written.

Works with any language. Any framework. Any project size.

## Install

```bash
npx @bitraptors/archie /path/to/your/project
```

Then open your project in Claude Code and run:

- `/archie-scan` -- Architecture health check (1-3 min, run often)
- `/archie-deep-scan` -- Comprehensive baseline (15-20 min, run once)
- `/archie-viewer` -- Open the blueprint inspector in your browser

## What it does

- Analyzes your codebase structure, dependencies, and patterns
- Builds an evolving architectural blueprint (knowledge compounds with each scan)
- Generates `CLAUDE.md`, `AGENTS.md`, and per-folder context files
- Installs 4 real-time enforcement hooks (file validation, commit review, plan review, architecture nudge)
- Proposes enforceable rules with confidence scores and deep rationale
- Tracks health metrics over time (erosion, complexity distribution, duplication)
- Detects architectural drift and dependency cycles
- Ships 40+ platform-specific rules (Android, Swift, TypeScript, Python)

## What it generates

- `CLAUDE.md` -- Architecture context for AI agents
- `AGENTS.md` -- Multi-agent coordination guidance
- `.claude/hooks/` -- Real-time architecture enforcement
- `.archie/blueprint.json` -- Evolving architectural knowledge base
- `.archie/rules.json` -- Enforceable architecture rules
- `.archie/health_history.json` -- Health score trends over time

## Requirements

- Python 3.9+
- Node.js 18+
- Claude Code

## License

MIT

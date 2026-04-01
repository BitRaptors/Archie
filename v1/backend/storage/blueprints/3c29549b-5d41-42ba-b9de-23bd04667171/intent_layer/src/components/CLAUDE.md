# components/
> UI component library for web generation UI: modal dialogs, code terminal streaming, generation panels, GitHub integration, preview frames, and settings management.

## Patterns

- Use CSS custom properties (var(--*)) for theming: accent, surface, text, border, radius tokens across all components
- Modal/dialog pattern: fixed inset-0 backdrop with stopPropagation on inner div to prevent accidental closes
- Streaming event handlers parse SSE data format (data: JSON lines) into component state updates via setEntries
- Terminal output uses type discriminator (system|tool-start|tool-result|text|code-preview|cost) to render different line styles
- File operation display: truncate code blocks (8 lines max), format byte sizes, extract filename from full path
- Async initialization: fetch /api/settings on mount to populate provider/token/repo state without blocking render

## Navigation

**Parent:** [`src/`](../CLAUDE.md)
**Peers:** [`app/`](../app/CLAUDE.md) | [`lib/`](../lib/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `ClaudeTerminal.tsx` | SSE streaming executor, displays Claude tool calls and results | Add entry types in handleEvent; update TOOL_ICONS for new tool names |
| `GeneratePanel.tsx` | Prompt input and generation orchestrator (Gemini vs Claude branch) | Conditional render ClaudeTerminal only when provider==='claude'; handle result propagation |
| `AddPinModal.tsx` | Form modal for pinning inspiration links with title/notes | Ref focus in useEffect, stopPropagation on modal content, trim all inputs before submit |
| `GitHubPanel.tsx` | GitHub repo browser: fetch metadata, readme, file tree via API | Save to /api/settings on connect, decode base64 package.json if present |
| `PreviewFrame.tsx` | Iframe sandbox display, unclear from truncated code | Check for sandbox restrictions if cross-origin or file:// preview needed |

## Key Imports

- `from react import useState, useEffect, useRef`
- `ClaudeTerminal imported into GeneratePanel for conditional streaming path`

## Add new code generation tool to terminal display

1. Add tool name to TOOL_ICONS const with unicode emoji
2. Add conditional block in handleToolUse() to extract tool-specific input fields
3. Call addEntry('tool-start', ...) with formatted output, addEntry('tool-result', ...) for results

## Don't

- Don't fetch settings on every render — fetch once on mount, store in state
- Don't open modals without input ref focus + useEffect dependency array — breaks keyboard UX
- Don't render streaming UI unconditionally — branch on provider state or streaming boolean flag

## Testing

- Test modal backdrop click closes but content click doesn't — verify stopPropagation on wrapper
- Mock fetch /api/settings to verify provider state populated before generate button enabled

## Why It's Built This Way

- Use entryId counter (idRef) instead of array.length to ensure stable keys during streaming appends
- Truncate code display to 8 lines max with '... (N more lines)' to prevent terminal overflow on large file writes

## What Goes Here

- **All UI components live flat in src/components** — `PascalCase.tsx`
- new_react_component → `src/components/[Name].tsx`

## Dependencies

**Depends on:** `API Route Handlers via fetch`
**Exposes to:** `Pages/Views Layer`

## Templates

### Feature Component
**Path:** `src/components/[Name]Panel.tsx`
```
'use client';
import { useState, useEffect } from 'react';
export default function MyPanel() {
  const [data, setData] = useState(null); ... }
```

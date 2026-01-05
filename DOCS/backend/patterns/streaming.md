---
id: backend-pattern-streaming
title: Streaming Responses
category: backend
tags: [pattern, streaming, sse, real-time]
related: [backend-patterns-overview]
---

# Pattern 3: Streaming Responses

**When to Use**: Long-running operations, real-time updates, progressive rendering.

```
Client ────request────▶ Server
       ◀───chunk 1─────
       ◀───chunk 2─────
       ◀───chunk 3─────
       ◀───end────────
```

**Implementation Approach**:

```
┌────────────────────────────────────────────────────────────────┐
│  Streaming Response Handler                                     │
│                                                                 │
│  1. start()    → Set headers (Content-Type, Transfer-Encoding) │
│  2. send(data) → Write chunk to response stream                │
│  3. close()    → End the response                              │
│                                                                 │
│  Chunk Format: JSON + delimiter (e.g., "DATA_END\n")           │
└────────────────────────────────────────────────────────────────┘
```

**When to Use**:

- AI text generation (token streaming)
- Large data exports
- Real-time progress updates
- SSE (Server-Sent Events) for UI updates



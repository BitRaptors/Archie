---
id: backend-pattern-sync-request
title: Synchronous Request-Response
category: backend
tags: [pattern, synchronous, request-response]
related: [backend-patterns-overview]
---

# Pattern 1: Synchronous Request-Response

**When to Use**: Simple operations where the caller waits for a result.

```
Controller ──call──▶ Service ──call──▶ Repository ──call──▶ Database
    ◀──response────     ◀──response────     ◀──response────
```

**Characteristics**:

- Caller blocks until response
- Simple error propagation
- Suitable for: CRUD operations, data retrieval, validation



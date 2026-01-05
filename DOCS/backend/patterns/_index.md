---
id: backend-patterns-overview
title: Communication Patterns
category: backend
tags: [patterns, communication, architecture]
related: [backend-layers]
---

# Communication Patterns

This section defines **how components communicate** within and across layers.

## Available Patterns

1. [Synchronous Request-Response](./sync-request.md) - Simple operations where caller waits for result
2. [Service Orchestration](./service-orchestration.md) - Complex operations requiring multiple services
3. [Streaming Responses](./streaming.md) - Long-running operations, real-time updates
4. [Task Graph Execution](./task-graph.md) - Operations with dependencies between sub-tasks
5. [Service Registry](./service-registry.md) - Multiple implementations of same interface
6. [Composite Services](./composite-services.md) - Same operation to multiple destinations

## Choosing a Communication Pattern

| Scenario                  | Pattern          | Rationale               |
| ------------------------- | ---------------- | ----------------------- |
| Simple data fetch         | Synchronous      | No complexity needed    |
| Multi-step workflow       | Orchestrator     | Central coordination    |
| AI generation             | Streaming        | Progressive results     |
| Dynamic task dependencies | Task Graph       | Parallel + dependencies |
| Multiple providers        | Service Registry | Plugin architecture     |
| Multi-destination logging | Composite        | Fan-out                 |

## Synchronous vs Asynchronous Decision

```
┌─────────────────────────────────────────────────────────────────┐
│  DECISION: Sync or Async?                                        │
│                                                                  │
│  Use SYNCHRONOUS when:                                           │
│    ✓ Operation completes quickly (< 1 second)                   │
│    ✓ Result is needed immediately for next step                 │
│    ✓ Failure should fail the entire request                     │
│                                                                  │
│  Use ASYNCHRONOUS when:                                          │
│    ✓ Operation is long-running (> 1 second)                     │
│    ✓ Result can be delivered later                              │
│    ✓ Failure shouldn't fail the main request                    │
│    ✓ Operation is fire-and-forget                               │
│                                                                  │
│  Use STREAMING when:                                             │
│    ✓ Result is progressively available                          │
│    ✓ User benefits from seeing partial results                  │
│    ✓ Total result is large                                      │
└─────────────────────────────────────────────────────────────────┘
```



---
id: backend-pattern-task-graph
title: Task Graph Execution
category: backend
tags: [pattern, task-graph, dependencies, parallel]
related: [backend-patterns-overview]
---

# Pattern 4: Task Graph Execution

**When to Use**: Operations with dependencies between sub-tasks.

```
┌─────────────────────────────────────────────────────────────────┐
│                    TASK GRAPH                                    │
│                                                                  │
│    Task A ─────────────────────┐                                │
│                                ▼                                 │
│    Task B ──────────────────▶ Task D ──────▶ Task E             │
│                                ▲                                 │
│    Task C ─────────────────────┘                                │
│                                                                  │
│  Execution:                                                      │
│    1. Parse dependencies                                         │
│    2. Execute independent tasks in parallel (A, B, C)           │
│    3. Wait for dependencies before dependent tasks (D waits)    │
│    4. Stream results as tasks complete                          │
└─────────────────────────────────────────────────────────────────┘
```

**Key Responsibilities**:

- **Task Graph**: Manages execution order, handles dependencies
- **Task Functions**: Individual task execution logic
- **Listeners**: React to task completion (update UI, trigger next step)

**Decision Criteria**:

| Use Task Graph When             | Use Sequential When           |
| ------------------------------- | ----------------------------- |
| Tasks have complex dependencies | Tasks are strictly ordered    |
| Some tasks can run in parallel  | Each task depends on previous |
| Need streaming updates          | Batch result is acceptable    |
| Task count/structure is dynamic | Fixed number of steps         |



---
id: backend-pattern-service-orchestration
title: Service Orchestration
category: backend
tags: [pattern, orchestration, services]
related: [backend-patterns-overview]
---

# Pattern 2: Service Orchestration

**When to Use**: Complex operations requiring multiple services or steps.

```
┌─────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR                                │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  run(serviceId, params, context)                         │    │
│  │    1. Lookup service by ID                               │    │
│  │    2. Validate params                                    │    │
│  │    3. Route to appropriate handler                       │    │
│  │    4. Execute and return result                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│          ┌───────────────────┼───────────────────┐              │
│          ▼                   ▼                   ▼              │
│   ┌────────────┐     ┌────────────┐     ┌────────────┐         │
│   │ AI Service │     │ DB Service │     │ API Service│         │
│   │  Handler   │     │  Handler   │     │  Handler   │         │
│   └────────────┘     └────────────┘     └────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

**Key Decisions**:

- Orchestrator owns the **routing logic**
- Individual handlers own **execution logic**
- Orchestrator can attach cross-cutting concerns (logging, analytics)



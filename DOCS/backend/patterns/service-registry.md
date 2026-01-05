---
id: backend-pattern-service-registry
title: Service Registry
category: backend
tags: [pattern, service-registry, plugin, factory]
related: [backend-patterns-overview]
---

# Pattern 5: Service Registry

**When to Use**: Multiple implementations of same interface, plugin-style architecture.

```
┌─────────────────────────────────────────────────────────────────┐
│                    SERVICE REGISTRY                              │
│                                                                  │
│  Interface: IService                                             │
│    - generate(input) → result                                   │
│                                                                  │
│  Registry Operations:                                            │
│    - use(id, implementation)  → Register a provider             │
│    - get(id) → implementation → Retrieve by ID                  │
│    - call(id, args) → result  → Execute by ID                   │
│                                                                  │
│  Registered Implementations:                                     │
│    ┌──────────┬─────────────────────┐                           │
│    │ ID       │ Implementation       │                           │
│    ├──────────┼─────────────────────┤                           │
│    │ "openai" │ OpenAIService       │                           │
│    │ "anthropic"│ AnthropicService  │                           │
│    │ "google" │ GoogleAIService     │                           │
│    └──────────┴─────────────────────┘                           │
│                                                                  │
│  Benefits:                                                       │
│    - Add new providers without modifying registry               │
│    - Runtime provider selection                                 │
│    - Easy testing with mock providers                           │
└─────────────────────────────────────────────────────────────────┘
```



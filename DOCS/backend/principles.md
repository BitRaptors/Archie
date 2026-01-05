---
id: backend-principles
title: Core Principles
category: backend
tags: [solid, principles, srp, ocp, lsp, isp, dip]
related: [backend-layers]
---

# Core Principles

## SOLID Principles

These principles guide ALL architectural decisions:

### Single Responsibility Principle (SRP)

Each component has ONE reason to change:

| Component       | Single Responsibility          |
| --------------- | ------------------------------ |
| Controller      | HTTP request/response handling |
| Service         | Business logic orchestration   |
| Repository      | Data persistence               |
| External Client | Third-party API communication  |

**Violation Example**: A controller that validates business rules, calls the database directly, and formats the response.

### Open/Closed Principle (OCP)

Components are open for extension, closed for modification.

**Pattern**: Service Registry

```
┌─────────────────────────────────────────────┐
│           Service Registry                   │
│  ┌─────────────────────────────────────┐    │
│  │  use(id, implementation)             │    │
│  │  get(id) → implementation            │    │
│  │  call(id, args) → result             │    │
│  └─────────────────────────────────────┘    │
│                                              │
│  Registered:                                 │
│    "openai"    → OpenAIService              │
│    "anthropic" → AnthropicService           │
│    "replicate" → ReplicateService           │
│    (add new without modifying registry)     │
└─────────────────────────────────────────────┘
```

New providers are added by registering, not by modifying existing code.

### Liskov Substitution Principle (LSP)

Any implementation can replace its interface without breaking the system.

**Requirement**: All implementations of an interface MUST honor the contract exactly.

### Interface Segregation Principle (ISP)

Clients depend only on methods they use.

**Example**: Separate `IReadRepository` from `IWriteRepository` if some clients only read.

### Dependency Inversion Principle (DIP)

High-level modules depend on abstractions, not concrete implementations.

```
┌─────────────────┐         ┌─────────────────┐
│   UserService   │ ──────▶ │  IUserRepository │  (abstraction)
└─────────────────┘         └─────────────────┘
                                    ▲
                                    │ implements
                            ┌───────┴────────┐
                            │ SupabaseUserRepo │  (concrete)
                            └────────────────┘
```

### Additional Guiding Principles

- **YAGNI**: Implement only what's needed NOW. Don't add "future-proofing" abstractions.
- **KISS**: The simplest solution that works. Complexity is a cost.
- **DRY**: Single source of truth. But don't force abstraction for the sake of it.



---
id: backend-layer-architecture
title: Layer Architecture
category: backend
tags: [layers, domain, infrastructure, presentation, application]
related: [backend-principles, backend-contracts]
---

# Layer Architecture

## Layer Responsibilities

Each layer has a **specific responsibility** and **dependency rules**:

```
┌─────────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                          │
│                                                                  │
│  Responsibility: HTTP/Protocol concerns ONLY                    │
│  Contains: Routes, Controllers, Request/Response DTOs,          │
│            Middleware, Validators                                │
│  Depends On: Application Layer                                   │
│  Knows About: HTTP, request formats, response formats           │
│  Does NOT Know: Business rules, database, external services     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     APPLICATION LAYER                            │
│                                                                  │
│  Responsibility: Use case orchestration, transaction boundaries │
│  Contains: Application Services, Use Case Handlers,             │
│            DTO Mappers, Orchestrators                            │
│  Depends On: Domain Layer interfaces                             │
│  Knows About: Use cases, workflow coordination                   │
│  Does NOT Know: HTTP, specific databases, external API details  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DOMAIN LAYER                                │
│                                                                  │
│  Responsibility: Core business logic, rules, and constraints    │
│  Contains: Entities, Value Objects, Domain Services,            │
│            Interfaces (Protocols), Domain Exceptions             │
│  Depends On: NOTHING (pure, no external dependencies)           │
│  Knows About: Business rules, domain concepts                   │
│  Does NOT Know: Persistence, HTTP, external services            │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ implements
┌─────────────────────────────────────────────────────────────────┐
│                   INFRASTRUCTURE LAYER                           │
│                                                                  │
│  Responsibility: External world integration                      │
│  Contains: Repository implementations, External API clients,    │
│            Cache implementations, Message publishers             │
│  Depends On: Domain Layer interfaces                             │
│  Knows About: Specific technologies (Supabase, Redis, OpenAI)   │
│  Does NOT Know: HTTP concerns, use case flow                    │
└─────────────────────────────────────────────────────────────────┘
```

## Dependency Rules (CRITICAL)

```
✅ Presentation → Application → Domain ← Infrastructure
❌ Domain → anything
❌ Application → Infrastructure (directly)
❌ Any layer → Presentation
```

The Domain Layer is the **core**. All other layers point toward it.

## Layer Communication Summary

| From Layer     | To Layer       | Mechanism             |
| -------------- | -------------- | --------------------- |
| Presentation   | Application    | Direct method call    |
| Application    | Domain         | Direct method call    |
| Application    | Infrastructure | Via Domain interfaces |
| Infrastructure | Domain         | Implements interfaces |



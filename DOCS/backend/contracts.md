---
id: backend-contracts
title: Component Contracts
category: backend
tags: [contracts, interfaces, repository, service, cache]
related: [backend-layers]
---

# Component Contracts

## Repository Interface

Repositories abstract data persistence. ALL repositories implement this base contract:

```
┌─────────────────────────────────────────────────────────────────┐
│  IRepository<Entity, ID>                                         │
│                                                                  │
│  READ OPERATIONS:                                                │
│    get_by_id(id) → Entity | None                                │
│    get_all(limit, offset) → List[Entity]                        │
│    exists(id) → bool                                             │
│                                                                  │
│  WRITE OPERATIONS:                                               │
│    add(entity) → Entity                                          │
│    update(entity) → Entity                                       │
│    delete(id) → bool                                             │
│                                                                  │
│  Entity-specific methods extend this base.                       │
└─────────────────────────────────────────────────────────────────┘
```

## Service Interface

External services (AI, payments, etc.) implement provider-specific interfaces:

```
┌─────────────────────────────────────────────────────────────────┐
│  IAIService                                                      │
│                                                                  │
│  generate(input) → Result | AsyncIterator[Chunk]                │
│                                                                  │
│  Input contains:                                                 │
│    - model_id: str                                              │
│    - parameters: dict                                           │
│    - output_format: enum                                        │
│                                                                  │
│  All AI providers implement this interface.                     │
└─────────────────────────────────────────────────────────────────┘
```

## Cache Interface

```
┌─────────────────────────────────────────────────────────────────┐
│  ICache                                                          │
│                                                                  │
│  get(key, fetcher, ttl) → T                                     │
│    - Returns cached value if exists                             │
│    - Calls fetcher and caches if not                            │
│                                                                  │
│  set(key, value, ttl) → void                                    │
│  delete(key) → void                                              │
│  clear() → void                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Event Publisher Interface

```
┌─────────────────────────────────────────────────────────────────┐
│  IEventPublisher                                                 │
│                                                                  │
│  publish(event) → void                                          │
│  publish_many(events) → void                                    │
│                                                                  │
│  Event contains:                                                 │
│    - name: str                                                  │
│    - params: dict                                               │
│    - timestamp: datetime                                        │
└─────────────────────────────────────────────────────────────────┘
```



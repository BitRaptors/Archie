---
id: backend-errors
title: Error Handling Strategy
category: backend
tags: [errors, exceptions, domain-errors, infrastructure-errors]
related: [backend-layers]
---

# Error Handling Strategy

## Error Categories

```
┌─────────────────────────────────────────────────────────────────┐
│                    ERROR CATEGORIES                              │
│                                                                  │
│  DOMAIN ERRORS (Business rule violations)                        │
│    - EntityNotFound: Resource doesn't exist                     │
│    - ValidationError: Input violates business rules             │
│    - AuthorizationError: User lacks permission                  │
│    - BusinessRuleViolation: Domain constraint violated          │
│    → These are EXPECTED. Return appropriate HTTP status.        │
│                                                                  │
│  INFRASTRUCTURE ERRORS (External failures)                       │
│    - DatabaseError: DB connection/query failure                 │
│    - ExternalServiceError: Third-party API failure              │
│    - TimeoutError: Operation took too long                      │
│    → These may be RETRIABLE. Consider retry logic.              │
│                                                                  │
│  SYSTEM ERRORS (Unexpected failures)                              │
│    - Unhandled exceptions                                       │
│    - Programming errors                                         │
│    → Log, alert, return generic error to client.                │
└─────────────────────────────────────────────────────────────────┘
```

## Error Flow

```
Controller ← Service ← Repository
     │          │          │
     │          │          └── Throws InfrastructureError
     │          │
     │          └── Catches, may rethrow as DomainError
     │                or let propagate
     │
     └── Global error handler maps to HTTP status
```

## Error Mapping

| Domain Error          | HTTP Status |
| --------------------- | ----------- |
| NotFoundError         | 404         |
| ValidationError       | 400         |
| AuthenticationError   | 401         |
| AuthorizationError    | 403         |
| ConflictError         | 409         |
| BusinessRuleViolation | 422         |
| InternalError         | 500         |



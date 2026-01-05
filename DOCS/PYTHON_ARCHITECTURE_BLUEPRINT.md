# Backend Architecture Blueprint

## Purpose

This document defines the **architectural principles, patterns, and decisions** for building maintainable backend applications. It is technology-agnostic in its principles but uses Python as the reference implementation language.

The document is structured in two parts:

1. **Architecture** (Sections 1-7): Defines **what** components exist, **why** they exist, and **how they communicate**. These principles are technology-agnostic.

2. **Implementation Guide** (Section 8): Provides a complete, opinionated guide to implementing this architecture from scratch with specific technology recommendations.

---

## Table of Contents

### Part 1: Architecture

1. [Architectural Decision Rationale](#architectural-decision-rationale)
2. [Core Principles](#core-principles)
3. [Layer Architecture](#layer-architecture)
4. [Communication Patterns](#communication-patterns)
5. [Component Contracts](#component-contracts)
6. [Error Handling Strategy](#error-handling-strategy)
7. [Cross-Cutting Concerns](#cross-cutting-concerns)

### Part 2: Implementation

8. [Implementation Guide](#implementation-guide) — Complete project setup with technology recommendations

---

## Architectural Decision Rationale

### Why This Architecture for ALL Projects?

We adopt a **layered architecture with dependency inversion** for every project because:

1. **Consistency**: Same patterns across all projects, easier onboarding and context switching
2. **Evolution**: Even simple projects grow into complex systems; starting right prevents rewrites
3. **Testability**: Each layer can be tested in isolation with mocked dependencies
4. **Flexibility**: Infrastructure can be swapped without changing business logic
5. **Team Scalability**: Clear boundaries allow parallel development
6. **Maintainability**: Changes are localized to specific layers

### Trade-offs Accepted

| We Accept                  | In Exchange For              |
| -------------------------- | ---------------------------- |
| More files and indirection | Clear separation of concerns |
| Initial setup overhead     | Long-term maintainability    |
| Interface definitions      | Swappable implementations    |
| Mapping between layers     | Independent evolution        |

### What This Architecture Does NOT Solve

- **Performance optimization** – This is orthogonal to architecture
- **Deployment strategy** – Monolith vs microservices is a separate decision
- **Data modeling** – Domain design requires domain expertise
- **UI/Frontend concerns** – This covers backend only

---

## Core Principles

### SOLID Principles

These principles guide ALL architectural decisions:

#### Single Responsibility Principle (SRP)

Each component has ONE reason to change:

| Component       | Single Responsibility          |
| --------------- | ------------------------------ |
| Controller      | HTTP request/response handling |
| Service         | Business logic orchestration   |
| Repository      | Data persistence               |
| External Client | Third-party API communication  |

**Violation Example**: A controller that validates business rules, calls the database directly, and formats the response.

#### Open/Closed Principle (OCP)

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

#### Liskov Substitution Principle (LSP)

Any implementation can replace its interface without breaking the system.

**Requirement**: All implementations of an interface MUST honor the contract exactly.

#### Interface Segregation Principle (ISP)

Clients depend only on methods they use.

**Example**: Separate `IReadRepository` from `IWriteRepository` if some clients only read.

#### Dependency Inversion Principle (DIP)

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

---

## Layer Architecture

### Layer Responsibilities

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

### Dependency Rules (CRITICAL)

```
✅ Presentation → Application → Domain ← Infrastructure
❌ Domain → anything
❌ Application → Infrastructure (directly)
❌ Any layer → Presentation
```

The Domain Layer is the **core**. All other layers point toward it.

### Layer Communication Summary

| From Layer     | To Layer       | Mechanism             |
| -------------- | -------------- | --------------------- |
| Presentation   | Application    | Direct method call    |
| Application    | Domain         | Direct method call    |
| Application    | Infrastructure | Via Domain interfaces |
| Infrastructure | Domain         | Implements interfaces |

---

## Communication Patterns

This section defines **how components communicate** within and across layers.

### Pattern 1: Synchronous Request-Response

**When to Use**: Simple operations where the caller waits for a result.

```
Controller ──call──▶ Service ──call──▶ Repository ──call──▶ Database
    ◀──response────     ◀──response────     ◀──response────
```

**Characteristics**:

- Caller blocks until response
- Simple error propagation
- Suitable for: CRUD operations, data retrieval, validation

### Pattern 2: Service Orchestration

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

### Pattern 3: Streaming Responses

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

### Pattern 4: Task Graph Execution

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

### Pattern 5: Service Registry

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

### Pattern 6: Composite Services

**When to Use**: Same operation needs to go to multiple destinations.

```
┌─────────────────────────────────────────────────────────────────┐
│                   COMPOSITE SERVICE                              │
│                                                                  │
│  log(event) {                                                    │
│    for (service in registeredServices) {                        │
│      service.log(event)  // Fan out to all                      │
│    }                                                             │
│  }                                                               │
│                                                                  │
│  Registered:                                                     │
│    ┌─────────────────┐                                          │
│    │ MixpanelService │                                          │
│    ├─────────────────┤                                          │
│    │ OpenMeterService│                                          │
│    └─────────────────┘                                          │
│                                                                  │
│  Use Cases:                                                      │
│    - Analytics to multiple providers                            │
│    - Notifications to multiple channels                         │
│    - Audit logging to multiple destinations                     │
└─────────────────────────────────────────────────────────────────┘
```

### Choosing a Communication Pattern

| Scenario                  | Pattern          | Rationale               |
| ------------------------- | ---------------- | ----------------------- |
| Simple data fetch         | Synchronous      | No complexity needed    |
| Multi-step workflow       | Orchestrator     | Central coordination    |
| AI generation             | Streaming        | Progressive results     |
| Dynamic task dependencies | Task Graph       | Parallel + dependencies |
| Multiple providers        | Service Registry | Plugin architecture     |
| Multi-destination logging | Composite        | Fan-out                 |

### Synchronous vs Asynchronous Decision

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

---

## Component Contracts

### Repository Interface

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

### Service Interface

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

### Cache Interface

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

### Event Publisher Interface

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

---

## Error Handling Strategy

### Error Categories

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
│  SYSTEM ERRORS (Unexpected failures)                             │
│    - Unhandled exceptions                                       │
│    - Programming errors                                         │
│    → Log, alert, return generic error to client.                │
└─────────────────────────────────────────────────────────────────┘
```

### Error Flow

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

### Error Mapping

| Domain Error          | HTTP Status |
| --------------------- | ----------- |
| NotFoundError         | 404         |
| ValidationError       | 400         |
| AuthenticationError   | 401         |
| AuthorizationError    | 403         |
| ConflictError         | 409         |
| BusinessRuleViolation | 422         |
| InternalError         | 500         |

---

## Cross-Cutting Concerns

### Where Concerns Live

| Concern        | Lives In                    | Applied Via           |
| -------------- | --------------------------- | --------------------- |
| Authentication | Presentation (Middleware)   | Middleware chain      |
| Authorization  | Application (Service)       | Service method checks |
| Validation     | Presentation (Request DTOs) | DTO validation        |
| Logging        | All layers                  | Injected logger       |
| Caching        | Application/Infrastructure  | Cache service         |
| Analytics      | Application                 | Analytics manager     |

### Middleware Chain

```
Request → Auth → RateLimit → Validate → Controller → Response
```

### Injecting Cross-Cutting Concerns

```
service = AppServices.createInstance()
service.attachDebugger(debugger)    # Optional attachment
service.attachAnalytics(analytics)  # Optional attachment
result = service.run(...)
service.detachLoggers()             # Cleanup
```

---

## Implementation Guide

This section provides a complete, opinionated guide to implementing this architecture from scratch using Python.

### Technology Stack

#### Core Framework

| Component         | Technology         | Purpose                                               |
| ----------------- | ------------------ | ----------------------------------------------------- |
| **Web Framework** | FastAPI            | Async-first API framework with automatic OpenAPI docs |
| **ASGI Server**   | Gunicorn + Uvicorn | Production server (4 workers)                         |
| **Validation**    | Pydantic v2        | Data validation and settings (`model_dump()` syntax)  |

#### Database & Storage

| Component          | Technology            | Purpose                                  |
| ------------------ | --------------------- | ---------------------------------------- |
| **Database**       | Supabase (PostgreSQL) | Managed PostgreSQL with auth and storage |
| **File Storage**   | Supabase Storage      | Document and file storage                |
| **Vector Search**  | pgvector (Supabase)   | Semantic search for ideas and documents  |
| **Cache/Sessions** | Redis                 | Session storage and caching              |

#### AI/LLM Providers

| Component          | Technology             | Purpose                            |
| ------------------ | ---------------------- | ---------------------------------- |
| **Primary AI**     | OpenAI (Responses API) | Primary AI provider                |
| **Alternative AI** | Google Gemini          | Alternative AI provider            |
| **Abstraction**    | Provider Factory       | Unified interface for AI providers |

#### Authentication

| Component       | Technology    | Purpose                                     |
| --------------- | ------------- | ------------------------------------------- |
| **Auth**        | Supabase Auth | JWT-based authentication                    |
| **JWT Library** | PyJWT         | Token validation using Supabase JWT secrets |

#### Real-time Communication

| Component     | Technology               | Purpose                            |
| ------------- | ------------------------ | ---------------------------------- |
| **Streaming** | Server-Sent Events (SSE) | Streaming AI responses to frontend |

#### Dependency Injection

| Component        | Technology          | Purpose                                    |
| ---------------- | ------------------- | ------------------------------------------ |
| **DI Container** | dependency-injector | Explicit DI with scopes and lifecycle mgmt |
| **Wiring**       | Auto-wiring         | Automatic injection into FastAPI endpoints |

#### Background Tasks

| Component      | Technology | Purpose                              |
| -------------- | ---------- | ------------------------------------ |
| **Task Queue** | ARQ        | Async-native, Redis-based task queue |
| **Broker**     | Redis      | Shared with cache/sessions           |
| **Scheduling** | ARQ cron   | Periodic task execution              |

#### Deployment

| Component            | Technology         | Purpose                                              |
| -------------------- | ------------------ | ---------------------------------------------------- |
| **Containerization** | Docker             | Container builds (Dockerfile, Dockerfile.production) |
| **Cloud Platform**   | Google Cloud Run   | Serverless container deployment                      |
| **Server**           | Gunicorn + Uvicorn | 4 workers configured                                 |

#### Key Python Libraries

| Library         | Purpose                                        |
| --------------- | ---------------------------------------------- |
| `asyncio`       | Async operations                               |
| `uuid`          | ID generation                                  |
| `threading`     | Thread-local storage for connection pooling    |
| `psutil`        | System monitoring (health endpoints)           |
| `requests`      | HTTP client for external APIs                  |
| `python-dotenv` | Environment variable management (`.env.local`) |

#### Development Tools

| Tool             | Purpose                            |
| ---------------- | ---------------------------------- |
| `pytest`         | Testing framework                  |
| `pytest-asyncio` | Async test support                 |
| `ruff`           | Linting and formatting             |
| `mypy`           | Static type checking (strict mode) |

### Project Setup from Scratch

#### Step 1: Initialize Project

```bash
# Create project directory
mkdir my-project && cd my-project

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install fastapi uvicorn[standard] gunicorn
pip install pydantic pydantic-settings python-dotenv
pip install supabase redis
pip install openai google-generativeai
pip install PyJWT requests psutil
pip install sse-starlette
pip install dependency-injector  # DI container
pip install arq                  # Task queue

# Dev dependencies
pip install pytest pytest-asyncio ruff mypy
```

#### Step 2: Create Directory Structure

```bash
mkdir -p src/{api/{routes,controllers,middleware,dto},application/{services,mappers},domain/{entities,interfaces,exceptions},infrastructure/{persistence,external,cache,ai},config}
mkdir -p tests/{unit,integration}
touch src/__init__.py src/main.py
```

Complete structure:

```
my-project/
├── src/
│   ├── __init__.py
│   ├── main.py                          # Application entry point
│   │
│   ├── api/                             # PRESENTATION LAYER
│   │   ├── __init__.py
│   │   ├── app.py                       # FastAPI app factory
│   │   ├── dependencies.py              # DI container setup
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── v1.py                    # Version 1 router
│   │   │   ├── health.py
│   │   │   ├── users.py
│   │   │   └── sse.py                   # SSE streaming endpoints
│   │   ├── controllers/
│   │   │   ├── __init__.py
│   │   │   └── user_controller.py
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                  # JWT validation with Supabase
│   │   │   ├── error_handler.py
│   │   │   └── request_context.py
│   │   └── dto/
│   │       ├── __init__.py
│   │       ├── requests.py
│   │       └── responses.py
│   │
│   ├── application/                     # APPLICATION LAYER
│   │   ├── __init__.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── user_service.py
│   │   │   └── ai_service.py            # AI orchestration
│   │   └── mappers/
│   │       ├── __init__.py
│   │       └── user_mapper.py
│   │
│   ├── domain/                          # DOMAIN LAYER
│   │   ├── __init__.py
│   │   ├── entities/
│   │   │   ├── __init__.py
│   │   │   └── user.py
│   │   ├── interfaces/
│   │   │   ├── __init__.py
│   │   │   ├── repositories.py
│   │   │   └── ai_provider.py           # AI provider interface
│   │   └── exceptions/
│   │       ├── __init__.py
│   │       └── domain_exceptions.py
│   │
│   ├── infrastructure/                  # INFRASTRUCTURE LAYER
│   │   ├── __init__.py
│   │   ├── persistence/
│   │   │   ├── __init__.py
│   │   │   ├── supabase_client.py       # Supabase connection
│   │   │   └── supabase_user_repository.py
│   │   ├── ai/                          # AI provider implementations
│   │   │   ├── __init__.py
│   │   │   ├── provider_factory.py      # Factory for AI providers
│   │   │   ├── openai_provider.py
│   │   │   └── gemini_provider.py
│   │   ├── cache/
│   │   │   ├── __init__.py
│   │   │   └── redis_cache.py
│   │   └── search/
│   │       ├── __init__.py
│   │       └── vector_search.py         # pgvector semantic search
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── constants.py
│   │   └── container.py                 # DI container definition
│   │
│   └── workers/                         # Background task workers
│       ├── __init__.py
│       ├── worker.py                    # ARQ worker entry point
│       └── tasks.py                     # Task definitions
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   └── ...
│   └── integration/
│       └── ...
│
├── Dockerfile
├── Dockerfile.production
├── cloudbuild.yaml
├── pyproject.toml
├── requirements.txt
├── .env.local
├── .env.example
├── .gitignore
└── README.md
```

### Core File Templates

#### `src/config/settings.py`

```python
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from dotenv import load_dotenv

# Load from .env.local
load_dotenv(".env.local")


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Application
    app_name: str = Field(default="API")
    app_version: str = Field(default="1.0.0")
    environment: str = Field(default="development")
    debug: bool = Field(default=False)

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # Supabase (Database, Auth, Storage)
    supabase_url: str = Field(...)
    supabase_key: str = Field(...)
    supabase_jwt_secret: str = Field(...)  # For JWT validation

    # Redis (Sessions/Cache)
    redis_url: str = Field(default="redis://localhost:6379")

    # AI Providers
    openai_api_key: str = Field(...)
    google_ai_api_key: str | None = Field(default=None)
    default_ai_provider: str = Field(default="openai")  # "openai" or "gemini"

    model_config = {
        "env_file": ".env.local",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

#### `src/domain/entities/user.py`

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Self
import uuid


@dataclass
class User:
    """User domain entity."""

    id: str
    email: str
    name: str
    created_at: datetime
    updated_at: datetime | None = None

    @classmethod
    def create(cls, email: str, name: str) -> Self:
        """Factory method for creating new users."""
        now = datetime.utcnow()
        return cls(
            id=str(uuid.uuid4()),
            email=email,
            name=name,
            created_at=now,
        )

    def update_name(self, name: str) -> None:
        """Update user name with timestamp."""
        self.name = name
        self.updated_at = datetime.utcnow()
```

#### `src/domain/interfaces/repositories.py`

```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")
ID = TypeVar("ID")


class IRepository(ABC, Generic[T, ID]):
    """Base repository interface."""

    @abstractmethod
    async def get_by_id(self, id: ID) -> T | None:
        ...

    @abstractmethod
    async def get_all(self, limit: int = 100, offset: int = 0) -> list[T]:
        ...

    @abstractmethod
    async def add(self, entity: T) -> T:
        ...

    @abstractmethod
    async def update(self, entity: T) -> T:
        ...

    @abstractmethod
    async def delete(self, id: ID) -> bool:
        ...


class IUserRepository(IRepository["User", str]):
    """User-specific repository interface."""

    @abstractmethod
    async def get_by_email(self, email: str) -> "User | None":
        ...
```

#### `src/domain/interfaces/ai_provider.py`

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator
from dataclasses import dataclass


@dataclass
class AIMessage:
    role: str  # "user", "assistant", "system"
    content: str


@dataclass
class AIResponse:
    content: str
    model: str
    usage: dict[str, int] | None = None


class IAIProvider(ABC):
    """Interface for AI providers (OpenAI, Gemini, etc.)."""

    @abstractmethod
    async def generate(
        self,
        messages: list[AIMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AIResponse:
        """Generate a completion."""
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[AIMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream completion tokens."""
        ...
```

#### `src/infrastructure/ai/provider_factory.py`

```python
from domain.interfaces.ai_provider import IAIProvider
from infrastructure.ai.openai_provider import OpenAIProvider
from infrastructure.ai.gemini_provider import GeminiProvider
from config.settings import Settings


class AIProviderFactory:
    """Factory for creating AI providers."""

    _providers: dict[str, type[IAIProvider]] = {
        "openai": OpenAIProvider,
        "gemini": GeminiProvider,
    }

    @classmethod
    def create(cls, provider_id: str, settings: Settings) -> IAIProvider:
        """Create an AI provider by ID."""
        if provider_id not in cls._providers:
            raise ValueError(f"Unknown AI provider: {provider_id}")

        provider_class = cls._providers[provider_id]

        if provider_id == "openai":
            return provider_class(api_key=settings.openai_api_key)
        elif provider_id == "gemini":
            return provider_class(api_key=settings.google_ai_api_key)

        raise ValueError(f"No configuration for provider: {provider_id}")

    @classmethod
    def get_default(cls, settings: Settings) -> IAIProvider:
        """Get the default AI provider."""
        return cls.create(settings.default_ai_provider, settings)
```

#### `src/infrastructure/ai/openai_provider.py`

```python
from typing import AsyncIterator
from openai import OpenAI
from domain.interfaces.ai_provider import IAIProvider, AIMessage, AIResponse


class OpenAIProvider(IAIProvider):
    """OpenAI implementation using Responses API."""

    DEFAULT_MODEL = "gpt-4o"

    def __init__(self, api_key: str):
        self._client = OpenAI(api_key=api_key)

    async def generate(
        self,
        messages: list[AIMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AIResponse:
        response = self._client.chat.completions.create(
            model=model or self.DEFAULT_MODEL,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
        )

        return AIResponse(
            content=response.choices[0].message.content or "",
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            } if response.usage else None,
        )

    async def stream(
        self,
        messages: list[AIMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        stream = self._client.chat.completions.create(
            model=model or self.DEFAULT_MODEL,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
```

#### `src/infrastructure/ai/gemini_provider.py`

```python
from typing import AsyncIterator
import google.generativeai as genai
from domain.interfaces.ai_provider import IAIProvider, AIMessage, AIResponse


class GeminiProvider(IAIProvider):
    """Google Gemini implementation."""

    DEFAULT_MODEL = "gemini-pro"

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(self.DEFAULT_MODEL)

    async def generate(
        self,
        messages: list[AIMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AIResponse:
        # Convert messages to Gemini format
        history = []
        for msg in messages[:-1]:
            role = "user" if msg.role == "user" else "model"
            history.append({"role": role, "parts": [msg.content]})

        chat = self._model.start_chat(history=history)
        response = chat.send_message(
            messages[-1].content,
            generation_config={"temperature": temperature},
        )

        return AIResponse(
            content=response.text,
            model=model or self.DEFAULT_MODEL,
        )

    async def stream(
        self,
        messages: list[AIMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        history = []
        for msg in messages[:-1]:
            role = "user" if msg.role == "user" else "model"
            history.append({"role": role, "parts": [msg.content]})

        chat = self._model.start_chat(history=history)
        response = chat.send_message(
            messages[-1].content,
            generation_config={"temperature": temperature},
            stream=True,
        )

        for chunk in response:
            if chunk.text:
                yield chunk.text
```

#### `src/domain/exceptions/domain_exceptions.py`

```python
from typing import Any


class DomainException(Exception):
    """Base domain exception."""

    def __init__(
        self,
        message: str,
        code: str = "DOMAIN_ERROR",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class NotFoundError(DomainException):
    """Entity not found."""

    def __init__(self, entity_type: str, entity_id: str):
        super().__init__(
            message=f"{entity_type} with id '{entity_id}' not found",
            code="NOT_FOUND",
            details={"entity_type": entity_type, "entity_id": entity_id},
        )


class ValidationError(DomainException):
    """Validation failed."""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details={"field": field} if field else {},
        )


class ConflictError(DomainException):
    """Entity already exists."""

    def __init__(self, entity_type: str, field: str, value: str):
        super().__init__(
            message=f"{entity_type} with {field}='{value}' already exists",
            code="CONFLICT",
            details={"entity_type": entity_type, "field": field, "value": value},
        )


class AuthorizationError(DomainException):
    """User not authorized."""

    def __init__(self, message: str = "Not authorized"):
        super().__init__(message=message, code="FORBIDDEN")
```

#### `src/infrastructure/persistence/supabase_user_repository.py`

```python
from supabase import Client
from domain.entities.user import User
from domain.interfaces.repositories import IUserRepository


class SupabaseUserRepository(IUserRepository):
    """Supabase implementation of user repository."""

    TABLE = "users"

    def __init__(self, client: Client):
        self._client = client

    async def get_by_id(self, id: str) -> User | None:
        result = (
            self._client.table(self.TABLE)
            .select("*")
            .eq("id", id)
            .maybe_single()
            .execute()
        )
        return self._to_entity(result.data) if result.data else None

    async def get_by_email(self, email: str) -> User | None:
        result = (
            self._client.table(self.TABLE)
            .select("*")
            .eq("email", email)
            .maybe_single()
            .execute()
        )
        return self._to_entity(result.data) if result.data else None

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[User]:
        result = (
            self._client.table(self.TABLE)
            .select("*")
            .range(offset, offset + limit - 1)
            .execute()
        )
        return [self._to_entity(row) for row in result.data]

    async def add(self, entity: User) -> User:
        data = self._to_dict(entity)
        result = self._client.table(self.TABLE).insert(data).execute()
        return self._to_entity(result.data[0])

    async def update(self, entity: User) -> User:
        data = self._to_dict(entity)
        result = (
            self._client.table(self.TABLE)
            .update(data)
            .eq("id", entity.id)
            .execute()
        )
        return self._to_entity(result.data[0])

    async def delete(self, id: str) -> bool:
        result = self._client.table(self.TABLE).delete().eq("id", id).execute()
        return len(result.data) > 0

    def _to_entity(self, data: dict) -> User:
        return User(
            id=data["id"],
            email=data["email"],
            name=data["name"],
            created_at=data["created_at"],
            updated_at=data.get("updated_at"),
        )

    def _to_dict(self, entity: User) -> dict:
        return {
            "id": entity.id,
            "email": entity.email,
            "name": entity.name,
            "created_at": entity.created_at.isoformat(),
            "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
        }
```

#### `src/application/services/user_service.py`

```python
from domain.entities.user import User
from domain.interfaces.repositories import IUserRepository
from domain.exceptions.domain_exceptions import NotFoundError, ConflictError


class UserService:
    """User application service."""

    def __init__(self, user_repository: IUserRepository):
        self._repo = user_repository

    async def get_user(self, user_id: str) -> User:
        user = await self._repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        return user

    async def create_user(self, email: str, name: str) -> User:
        existing = await self._repo.get_by_email(email)
        if existing:
            raise ConflictError("User", "email", email)

        user = User.create(email=email, name=name)
        return await self._repo.add(user)

    async def update_user(self, user_id: str, name: str | None = None) -> User:
        user = await self.get_user(user_id)

        if name is not None:
            user.update_name(name)

        return await self._repo.update(user)

    async def delete_user(self, user_id: str) -> bool:
        await self.get_user(user_id)  # Ensure exists
        return await self._repo.delete(user_id)
```

#### `src/api/dto/requests.py`

```python
from pydantic import BaseModel, Field, EmailStr


class CreateUserRequest(BaseModel):
    """Request to create a user."""

    email: EmailStr = Field(..., description="User email")
    name: str = Field(..., min_length=1, max_length=100)

    model_config = {"extra": "forbid"}


class UpdateUserRequest(BaseModel):
    """Request to update a user."""

    name: str | None = Field(None, min_length=1, max_length=100)

    model_config = {"extra": "forbid"}
```

#### `src/api/dto/responses.py`

```python
from pydantic import BaseModel
from datetime import datetime


class UserResponse(BaseModel):
    """User response DTO."""

    id: str
    email: str
    name: str
    created_at: datetime
    updated_at: datetime | None = None

    @classmethod
    def from_entity(cls, user: "User") -> "UserResponse":
        return cls(
            id=user.id,
            email=user.email,
            name=user.name,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )


class ErrorResponse(BaseModel):
    """Standard error response."""

    code: str
    message: str
    details: dict = {}
```

#### `src/api/middleware/auth.py`

```python
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from typing import Optional
from dataclasses import dataclass

from config.settings import get_settings


@dataclass
class CurrentUser:
    """Authenticated user from JWT."""
    id: str
    email: str
    role: str | None = None


security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> CurrentUser | None:
    """Extract and validate JWT token, return user or None."""
    if not credentials:
        return None

    settings = get_settings()

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )

        return CurrentUser(
            id=payload.get("sub", ""),
            email=payload.get("email", ""),
            role=payload.get("role"),
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


async def require_auth(
    user: CurrentUser | None = Depends(get_current_user),
) -> CurrentUser:
    """Require authenticated user."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user
```

#### `src/api/middleware/error_handler.py`

```python
from fastapi import Request, status
from fastapi.responses import JSONResponse
from domain.exceptions.domain_exceptions import (
    DomainException,
    NotFoundError,
    ValidationError,
    ConflictError,
    AuthorizationError,
)


EXCEPTION_STATUS_MAP = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ValidationError: status.HTTP_400_BAD_REQUEST,
    ConflictError: status.HTTP_409_CONFLICT,
    AuthorizationError: status.HTTP_403_FORBIDDEN,
}


async def domain_exception_handler(request: Request, exc: DomainException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    for exc_type, code in EXCEPTION_STATUS_MAP.items():
        if isinstance(exc, exc_type):
            status_code = code
            break

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {},
            }
        },
    )
```

#### `src/api/routes/health.py`

```python
from fastapi import APIRouter
import psutil
from datetime import datetime

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Health check endpoint with system metrics."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "system": {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent,
        },
    }


@router.get("/health/live")
async def liveness():
    """Kubernetes liveness probe."""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness():
    """Kubernetes readiness probe."""
    # Add dependency checks here (DB, Redis, etc.)
    return {"status": "ready"}
```

#### `src/api/routes/sse.py`

```python
from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse
from typing import AsyncIterator
import asyncio
import json

from api.middleware.auth import require_auth, CurrentUser
from api.dependencies import get_ai_provider
from domain.interfaces.ai_provider import IAIProvider, AIMessage

router = APIRouter(prefix="/sse", tags=["sse"])


@router.post("/chat/stream")
async def stream_chat(
    request: Request,
    prompt: str,
    user: CurrentUser = Depends(require_auth),
    ai_provider: IAIProvider = Depends(get_ai_provider),
):
    """Stream AI response via SSE."""

    async def event_generator() -> AsyncIterator[dict]:
        messages = [AIMessage(role="user", content=prompt)]

        try:
            async for token in ai_provider.stream(messages):
                if await request.is_disconnected():
                    break
                yield {
                    "event": "token",
                    "data": json.dumps({"content": token}),
                }

            yield {
                "event": "done",
                "data": json.dumps({"status": "complete"}),
            }
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }

    return EventSourceResponse(event_generator())
```

#### `src/config/container.py`

```python
from dependency_injector import containers, providers
from supabase import create_client
import redis

from config.settings import Settings
from infrastructure.persistence.supabase_user_repository import SupabaseUserRepository
from infrastructure.ai.openai_provider import OpenAIProvider
from infrastructure.ai.gemini_provider import GeminiProvider
from infrastructure.cache.redis_cache import RedisCache
from application.services.user_service import UserService


class Container(containers.DeclarativeContainer):
    """Dependency injection container using dependency-injector."""

    wiring_config = containers.WiringConfiguration(
        modules=[
            "api.routes.users",
            "api.routes.sse",
            "api.routes.health",
            "workers.tasks",
        ]
    )

    # Configuration
    config = providers.Configuration()

    # Infrastructure - Clients (Singletons)
    supabase_client = providers.Singleton(
        create_client,
        supabase_url=config.supabase_url,
        supabase_key=config.supabase_key,
    )

    redis_client = providers.Singleton(
        redis.from_url,
        url=config.redis_url,
    )

    # Infrastructure - Repositories (Factory - new instance per request)
    user_repository = providers.Factory(
        SupabaseUserRepository,
        client=supabase_client,
    )

    # Infrastructure - Cache
    cache = providers.Singleton(
        RedisCache,
        client=redis_client,
    )

    # Infrastructure - AI Providers
    openai_provider = providers.Singleton(
        OpenAIProvider,
        api_key=config.openai_api_key,
    )

    gemini_provider = providers.Singleton(
        GeminiProvider,
        api_key=config.google_ai_api_key,
    )

    # AI Provider selector (based on config)
    ai_provider = providers.Selector(
        config.default_ai_provider,
        openai=openai_provider,
        gemini=gemini_provider,
    )

    # Application Services
    user_service = providers.Factory(
        UserService,
        user_repository=user_repository,
    )


def create_container(settings: Settings) -> Container:
    """Create and configure the DI container."""
    container = Container()
    container.config.from_dict({
        "supabase_url": settings.supabase_url,
        "supabase_key": settings.supabase_key,
        "redis_url": settings.redis_url,
        "openai_api_key": settings.openai_api_key,
        "google_ai_api_key": settings.google_ai_api_key,
        "default_ai_provider": settings.default_ai_provider,
    })
    return container
```

#### `src/api/dependencies.py`

```python
from dependency_injector.wiring import Provide, inject
from fastapi import Depends

from config.container import Container
from domain.interfaces.repositories import IUserRepository
from domain.interfaces.ai_provider import IAIProvider
from application.services.user_service import UserService
from infrastructure.cache.redis_cache import RedisCache


# Dependency injection helpers for FastAPI routes
# These use dependency-injector's Provide marker

def get_user_service(
    service: UserService = Depends(Provide[Container.user_service])
) -> UserService:
    return service


def get_ai_provider(
    provider: IAIProvider = Depends(Provide[Container.ai_provider])
) -> IAIProvider:
    return provider


def get_cache(
    cache: RedisCache = Depends(Provide[Container.cache])
) -> RedisCache:
    return cache


def get_user_repository(
    repo: IUserRepository = Depends(Provide[Container.user_repository])
) -> IUserRepository:
    return repo
```

#### `src/infrastructure/cache/redis_cache.py`

```python
import redis
import json
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class RedisCache:
    """Redis cache implementation."""

    def __init__(self, client: redis.Redis):
        self._client = client

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        value = self._client.get(key)
        if value:
            return json.loads(value)
        return None

    async def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        """Set value in cache with TTL."""
        self._client.setex(key, ttl_seconds, json.dumps(value))

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        return bool(self._client.delete(key))

    async def get_or_set(
        self,
        key: str,
        fetcher: Callable[[], T],
        ttl_seconds: int = 3600,
    ) -> T:
        """Get from cache or fetch and cache."""
        cached = await self.get(key)
        if cached is not None:
            return cached

        value = await fetcher() if callable(fetcher) else fetcher
        await self.set(key, value, ttl_seconds)
        return value
```

#### `src/workers/tasks.py`

```python
from arq import cron
from dependency_injector.wiring import Provide, inject
from typing import Any

from config.container import Container
from application.services.user_service import UserService
from domain.interfaces.ai_provider import IAIProvider


# Background task definitions for ARQ


@inject
async def send_welcome_email(
    ctx: dict,
    user_id: str,
    user_service: UserService = Provide[Container.user_service],
) -> dict[str, Any]:
    """Send welcome email to new user (background task)."""
    user = await user_service.get_user(user_id)
    # Send email logic here...
    return {"status": "sent", "user_id": user_id, "email": user.email}


@inject
async def process_ai_batch(
    ctx: dict,
    prompts: list[str],
    ai_provider: IAIProvider = Provide[Container.ai_provider],
) -> dict[str, Any]:
    """Process multiple AI prompts in background."""
    results = []
    for prompt in prompts:
        from domain.interfaces.ai_provider import AIMessage
        response = await ai_provider.generate([AIMessage(role="user", content=prompt)])
        results.append(response.content)
    return {"status": "complete", "results": results}


async def cleanup_expired_sessions(ctx: dict) -> dict[str, Any]:
    """Periodic task to clean up expired sessions."""
    redis_client = ctx["redis"]
    # Cleanup logic here...
    return {"status": "cleaned"}


# Cron jobs (periodic tasks)
cron_jobs = [
    cron(cleanup_expired_sessions, hour={0, 12}),  # Run at midnight and noon
]
```

#### `src/workers/worker.py`

```python
from arq import create_pool
from arq.connections import RedisSettings
import asyncio

from config.settings import get_settings
from config.container import create_container
from workers.tasks import send_welcome_email, process_ai_batch, cron_jobs


async def startup(ctx: dict) -> None:
    """Worker startup - initialize DI container."""
    settings = get_settings()
    container = create_container(settings)
    container.wire(modules=["workers.tasks"])
    ctx["container"] = container
    ctx["redis"] = container.redis_client()


async def shutdown(ctx: dict) -> None:
    """Worker shutdown - cleanup."""
    pass


class WorkerSettings:
    """ARQ worker configuration."""

    functions = [
        send_welcome_email,
        process_ai_batch,
    ]

    cron_jobs = cron_jobs

    on_startup = startup
    on_shutdown = shutdown

    @staticmethod
    def redis_settings() -> RedisSettings:
        settings = get_settings()
        return RedisSettings.from_dsn(settings.redis_url)


# To run the worker:
# arq src.workers.worker.WorkerSettings
```

#### `src/application/services/task_service.py`

```python
from arq import ArqRedis
from typing import Any


class TaskService:
    """Service for enqueueing background tasks."""

    def __init__(self, redis_pool: ArqRedis):
        self._pool = redis_pool

    async def enqueue_welcome_email(self, user_id: str) -> str:
        """Enqueue welcome email task."""
        job = await self._pool.enqueue_job("send_welcome_email", user_id)
        return job.job_id

    async def enqueue_ai_batch(self, prompts: list[str]) -> str:
        """Enqueue AI batch processing task."""
        job = await self._pool.enqueue_job("process_ai_batch", prompts)
        return job.job_id

    async def get_job_result(self, job_id: str) -> Any:
        """Get result of a completed job."""
        job = await self._pool.job(job_id)
        if job:
            return await job.result()
        return None
```

#### `src/api/routes/users.py`

```python
from fastapi import APIRouter, Depends, status
from api.dependencies import get_user_service
from api.dto.requests import CreateUserRequest, UpdateUserRequest
from api.dto.responses import UserResponse
from application.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    service: UserService = Depends(get_user_service),
):
    user = await service.get_user(user_id)
    return UserResponse.from_entity(user)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: CreateUserRequest,
    service: UserService = Depends(get_user_service),
):
    user = await service.create_user(email=request.email, name=request.name)
    return UserResponse.from_entity(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    service: UserService = Depends(get_user_service),
):
    user = await service.update_user(user_id=user_id, name=request.name)
    return UserResponse.from_entity(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    service: UserService = Depends(get_user_service),
):
    await service.delete_user(user_id)
```

#### `src/api/app.py`

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager

from api.routes import users, health, sse
from api.middleware.error_handler import (
    domain_exception_handler,
    unhandled_exception_handler,
)
from domain.exceptions.domain_exceptions import DomainException
from config.settings import get_settings
from config.container import create_container


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - setup and teardown."""
    # Startup: Initialize DI container
    settings = get_settings()
    container = create_container(settings)
    container.wire(modules=[
        "api.routes.users",
        "api.routes.sse",
        "api.routes.health",
    ])
    app.state.container = container

    yield

    # Shutdown: Cleanup resources
    container.unwire()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    # Exception handlers
    app.add_exception_handler(DomainException, domain_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Routes
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(users.router, prefix="/api/v1")
    app.include_router(sse.router, prefix="/api/v1")

    return app
```

#### `src/main.py`

```python
import uvicorn
from api.app import create_app
from config.settings import get_settings

app = create_app()

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
```

#### `requirements.txt`

```txt
# Core
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
gunicorn>=21.0.0

# Data validation
pydantic>=2.5.0
pydantic-settings>=2.1.0

# Database & Storage
supabase>=2.3.0

# Cache & Sessions
redis>=5.0.0

# Dependency Injection
dependency-injector>=4.41.0

# Task Queue
arq>=0.25.0

# AI Providers
openai>=1.10.0
google-generativeai>=0.3.0

# Auth
PyJWT>=2.8.0

# HTTP
requests>=2.31.0
httpx>=0.26.0

# SSE
sse-starlette>=1.8.0

# Utilities
python-dotenv>=1.0.0
psutil>=5.9.0
```

#### `pyproject.toml`

```toml
[project]
name = "my-project"
version = "0.1.0"
requires-python = ">=3.11"

[tool.ruff]
target-version = "py311"
line-length = 100
select = ["E", "F", "I", "N", "UP", "B", "C4", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

#### `.env.example`

```bash
# Application
APP_NAME=MyAPI
APP_VERSION=1.0.0
ENVIRONMENT=development
DEBUG=true

# Server
HOST=0.0.0.0
PORT=8000

# Supabase (Database, Auth, Storage)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_JWT_SECRET=your-jwt-secret

# Redis (Sessions/Cache)
REDIS_URL=redis://localhost:6379

# AI Providers
OPENAI_API_KEY=sk-...
GOOGLE_AI_API_KEY=...
DEFAULT_AI_PROVIDER=openai
```

#### `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ ./src/

# Set Python path
ENV PYTHONPATH=/app/src

# Expose port
EXPOSE 8000

# Run with uvicorn for development
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### `Dockerfile.production`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ ./src/

# Set Python path
ENV PYTHONPATH=/app/src

# Expose port
EXPOSE 8000

# Run with Gunicorn + Uvicorn workers (4 workers)
CMD ["gunicorn", "src.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120"]
```

#### `cloudbuild.yaml`

```yaml
steps:
  # Build the container image
  - name: "gcr.io/cloud-builders/docker"
    args:
      [
        "build",
        "-t",
        "gcr.io/$PROJECT_ID/${_SERVICE_NAME}:$COMMIT_SHA",
        "-f",
        "Dockerfile.production",
        ".",
      ]

  # Push the container image to Container Registry
  - name: "gcr.io/cloud-builders/docker"
    args: ["push", "gcr.io/$PROJECT_ID/${_SERVICE_NAME}:$COMMIT_SHA"]

  # Deploy container image to Cloud Run
  - name: "gcr.io/google.com/cloudsdktool/cloud-sdk"
    entrypoint: gcloud
    args:
      - "run"
      - "deploy"
      - "${_SERVICE_NAME}"
      - "--image"
      - "gcr.io/$PROJECT_ID/${_SERVICE_NAME}:$COMMIT_SHA"
      - "--region"
      - "${_REGION}"
      - "--platform"
      - "managed"
      - "--allow-unauthenticated"

substitutions:
  _SERVICE_NAME: my-api
  _REGION: us-central1

images:
  - "gcr.io/$PROJECT_ID/${_SERVICE_NAME}:$COMMIT_SHA"
```

### Running the Application

#### Development

```bash
# Setup environment
cp .env.example .env.local
# Edit .env.local with your values

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run development server
python src/main.py

# Or with uvicorn directly (with hot reload)
uvicorn src.main:app --reload
```

#### Background Worker (ARQ)

```bash
# Run the ARQ worker (separate terminal)
arq src.workers.worker.WorkerSettings

# Or run with watch mode for development
arq src.workers.worker.WorkerSettings --watch src/
```

#### Production (Docker)

```bash
# Build production image
docker build -f Dockerfile.production -t my-api:latest .

# Run API container
docker run -p 8000:8000 --env-file .env.local my-api:latest

# Run worker container
docker run --env-file .env.local my-api:latest \
    arq src.workers.worker.WorkerSettings
```

#### Docker Compose (Full Stack)

```yaml
# docker-compose.yml
version: "3.8"

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.production
    ports:
      - "8000:8000"
    env_file:
      - .env.local
    depends_on:
      - redis

  worker:
    build:
      context: .
      dockerfile: Dockerfile.production
    command: arq src.workers.worker.WorkerSettings
    env_file:
      - .env.local
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

```bash
# Run full stack
docker-compose up -d
```

#### Testing & Quality

```bash
# Install dev dependencies
pip install pytest pytest-asyncio ruff mypy

# Run tests
pytest

# Lint and format
ruff check src/
ruff format src/

# Type check
mypy src/
```

---

## Summary

This architecture provides:

| Benefit             | How                                                  |
| ------------------- | ---------------------------------------------------- |
| **Maintainability** | Clear layer separation and responsibilities          |
| **Testability**     | Dependencies via interfaces enable mocking           |
| **Flexibility**     | Swap implementations without changing business logic |
| **Scalability**     | Clear boundaries enable team parallelization         |

**Remember**: Architecture is about **trade-offs**. Even small projects benefit from this structure because they inevitably evolve into complex systems.

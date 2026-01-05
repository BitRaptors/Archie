---
id: frontend-overview
title: Frontend Architecture Blueprint
category: frontend
tags: [overview, architecture, react]
---

# Frontend Architecture Blueprint

## Purpose

This document defines the **architectural patterns and conventions** for building maintainable React applications. It reflects real-world React idioms rather than backend-derived concepts.

The document is structured in two parts:

1. **Architecture** (Sections 1-5): Core patterns and conventions
2. **Implementation Guide** (Section 6): Complete project setup with code templates

---

## Table of Contents

### Part 1: Architecture

1. [Guiding Principles](./principles.md)
2. [Project Structure](./structure.md)
3. [Core Patterns](./patterns/_index.md)
4. [Service Abstraction](./services.md)
5. [Cross-Cutting Concerns](#cross-cutting-concerns)

### Part 2: Implementation

6. [Implementation Guide](./implementation.md) — Complete setup with templates

---

## Cross-Cutting Concerns

### Provider Composition

All providers are composed in `pages/_app.tsx`:

```typescript
<PersistQueryClientProvider>
  <ServiceProvider>
    <TranslationsProvider>
      <AuthContextProvider>
        <ConfigContextProvider>
          <TooltipProvider>
            {children}
          </TooltipProvider>
        </ConfigContextProvider>
      </AuthContextProvider>
    </TranslationsProvider>
  </ServiceProvider>
</PersistQueryClientProvider>
```

### Error Boundaries

Error boundaries catch React errors and display fallback UI. See implementation guide for details.



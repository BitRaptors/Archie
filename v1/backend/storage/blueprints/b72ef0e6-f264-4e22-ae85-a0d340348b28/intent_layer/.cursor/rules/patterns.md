---
description: Communication and design patterns, key architectural decisions
alwaysApply: true
---

## Communication Patterns

### StateFlow/SharedFlow ViewModel→Fragment
- **When:** All UI state updates and one-time navigation/dialog events
- **How:** ViewModel exposes StateFlow<UiState>; Fragment collects inside repeatOnLifecycle(STARTED)

### Koin Dependency Injection
- **When:** Providing repositories, controllers, ViewModels to all layers
- **How:** Module-per-feature DSL; root context started in BabyWeatherApplication with all modules

### Navigation Component SafeArgs
- **When:** Fragment-to-fragment navigation with typed arguments
- **How:** NavigationRequest sealed events emitted by Controllers; MainActivity executes via NavController

### RecyclerView Adapter Delegates
- **When:** Heterogeneous list screens (dashboard, settings, tips, locations)
- **How:** adapterDelegateViewBinding DSL creates typed delegates composed into one adapter

### REST API via Retrofit+Moshi
- **When:** All server data fetching (weather, settings, children, tips)
- **How:** APIService interface; OkHttp with auth interceptor; Moshi codegen DTOs; NetworkResponse sealed wrapper

## Pattern Selection Guide

| Scenario | Pattern | Rationale |
|----------|---------|-----------|
| UI needs continuous state updates | StateFlow<UiState> in ViewModel | Survives recomposition, lifecycle-safe with repeatOnLifecycle |
| One-time events (navigate, show dialog) | MutableSharedFlow<UiEvent>.tryEmit() | Avoids re-delivery on configuration change unlike StateFlow |
| Cross-feature data sharing | Shared repository singleton via Koin | Single source of truth; no direct feature-to-feature dependencies |

## Quick Pattern Lookup

- **state_management** -> StateFlow for UI state, SharedFlow for events
- **dependency_injection** -> Koin module DSL; single{} for services, viewModel{} for ViewModels
- **navigation** -> NavController via NavigationRequest sealed events from Controllers
- **lists** -> adapterDelegateViewBinding with GenericListItem cells

## Key Decisions

### Koin over Hilt for DI
**Chosen:** Koin service locator with module-per-feature composition
**Rationale:** Simpler setup, no annotation processing overhead, fits Kotlin-first approach

### Controller pattern alongside ViewModel
**Chosen:** Controllers (MainController, LoginController) orchestrate cross-cutting concerns
**Rationale:** Separates analytics/navigation side-effects from pure UI state in ViewModel

### RevenueCat for subscriptions
**Chosen:** RevenueCat SDK abstracts Google Play Billing
**Rationale:** Cross-platform abstraction, receipt validation, entitlement management

### Sealed state machines for auth/nav
**Chosen:** LoginSheetState, LoginState sealed interfaces drive state transitions
**Rationale:** Type-safe exhaustive state handling prevents illegal state combinations

### buildSrc Kotlin DSL for dependency management
**Chosen:** Centralized version objects in buildSrc/src/main/kotlin/Dependencies.kt
**Rationale:** Single source of truth for versions; IDE autocomplete; no hardcoded strings
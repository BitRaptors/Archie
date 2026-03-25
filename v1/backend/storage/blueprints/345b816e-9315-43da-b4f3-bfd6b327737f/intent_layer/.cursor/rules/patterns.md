---
description: Communication and design patterns, key architectural decisions
alwaysApply: true
---

## Communication Patterns

### PublishRelay Input / Driver Output
- **When:** All ViewModel and Provider data flow on iOS
- **How:** PublishRelay accepts user intent; flatMapLatest calls Firebase; result emitted as Driver to ViewController

### RxSwift scan() state accumulation
- **When:** When multiple input actions must accumulate into a state dictionary
- **How:** scan() operator reduces InputType enum actions (.add/.merge/.reset) into immutable state copies

### Firebase Firestore real-time listeners
- **When:** Live album/recording sync between Firestore and iOS client
- **How:** FirebaseProvider attaches snapshot listeners returning Observable; errors propagate to errorSubject

### Firebase Cloud Functions HTTPS calls
- **When:** Complex server-side operations requiring auth or cascading Firestore writes
- **How:** iOS calls callable HTTPS functions via Firebase SDK; TypeScript handlers validate and execute

### Observable.merge error aggregation
- **When:** Surfacing errors from multiple async sources to single UI error handler
- **How:** errorOutput merges PublishSubjects from all providers/managers into single Observable<ASError>

## Pattern Selection Guide

| Scenario | Pattern | Rationale |
|----------|---------|-----------|
| User triggers action in ViewController | PublishRelay.accept() → ViewModel input | Relay never completes; safe for UI lifecycle |
| Live Firestore data needed in UI | FirebaseProvider snapshot listener → Driver | Driver guarantees main thread; no nil emissions |
| Server-side cascading write needed | Firebase Cloud Function HTTPS call | Bypasses client security constraints; atomic server operations |

## Quick Pattern Lookup

- **reactive_input** -> PublishRelay<T> for user actions; never use Subject for inputs
- **reactive_output** -> Driver<T> for UI-bound outputs; Observable<T> for non-UI chains
- **error_handling** -> ASErrorFactory.create*() → errorSubject.onNext() → errorOutput observable merge
- **local_persistence** -> Disk library for file-based caching; SettingsManager for user preferences
- **di_registration** -> Register in DepedencyContainer.swift; resolve via Resolver.swift

## Key Decisions

### Firebase as sole backend
**Chosen:** Firestore + Cloud Functions + Storage + FCM + Auth
**Rationale:** Single vendor covers all backend needs: real-time sync, serverless compute, file storage, push notifications, auth

### RxSwift for state management
**Chosen:** RxSwift PublishRelay/BehaviorRelay with Driver for UI binding
**Rationale:** Unidirectional data flow; Driver guarantees main-thread delivery; no accidental stream termination with Relay

### Swinject for dependency injection
**Chosen:** Centralized Swinject container initialized in AppDelegate
**Rationale:** Explicit protocol-based registration enables mock substitution for testing; all dependencies resolved at init time

### Protocol-based abstractions for all services
**Chosen:** Every major service has a Protocol variant (FirebaseProviderProtocol, GeneralPlayerProtocol, etc.)
**Rationale:** Enables unit testing via mock conformance without framework coupling

### Serverless Firebase Cloud Functions for backend logic
**Chosen:** TypeScript Cloud Functions triggered by HTTP and Firestore events
**Rationale:** No server management; scales automatically; integrates natively with Firestore triggers for cascading operations
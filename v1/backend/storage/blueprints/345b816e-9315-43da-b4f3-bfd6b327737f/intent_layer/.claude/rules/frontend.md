---
paths:
  - **/*.swift
---

## Frontend Architecture

**Framework:** UIKit (iOS) + Android native

**Rendering:** Imperative UIKit with programmatic and XIB-based layout; RxDataSources for reactive table updates

**Styling:** UIKit Auto Layout with SnapKit DSL; ColorUtil for centralized color constants; no SwiftUI

**State management:** RxSwift unidirectional data flow: PublishRelay inputs → flatMapLatest → Driver outputs
  - Server state: Firebase Firestore real-time listeners via FirebaseProvider snapshot subscriptions
  - Local state: ViewModel-owned BehaviorSubject/PublishSubject; Disk library for persistent cache; SettingsManager for preferences

**Conventions:**
- Use Driver (not Observable) for all ViewController bindings to guarantee main thread
- Use PublishRelay (not Subject) for input ports to prevent accidental stream termination
- Dispose all subscriptions via DisposeBag scoped to ViewController lifecycle
- Always use ASErrorFactory to create errors; never instantiate error types directly
- Converters must be pure functions; no side effects in DTO-to-domain transformation
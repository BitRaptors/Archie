---
description: Common pitfalls and error mapping
alwaysApply: true
---

## Pitfalls

- **RxSwift stream termination:** Using PublishSubject as input relay will terminate the entire stream on onError(); downstream Providers stop emitting permanently
  - *Always use PublishRelay for input ports; reserve PublishSubject only for error subjects that feed errorOutput*
- **Firebase Firestore snapshot listeners:** Firestore real-time listeners are long-lived and not automatically removed when a ViewController is dismissed; causes memory leaks and phantom updates
  - *Store the Firestore unsubscribe function and call it in deinit or on navigation away; ensure DisposeBag is deallocated with ViewController*
- **Swinject DI resolution order:** DepedencyContainer.swift registers services in a specific order; circular dependencies or resolving before registration causes silent nil crashes
  - *Always register leaf dependencies (ErrorFactory, Analytics) before composite services (Providers, ViewModels) in DepedencyContainer.swift*
- **Driver vs Observable threading:** Binding an Observable (not Driver) to UIKit elements can crash if the observable emits on a background thread from Firestore callbacks
  - *Convert all ViewController-bound outputs to Driver via .asDriver(onErrorJustReturn:) before exposing from ViewModels*
- **Python 2.7 admin tools:** platform/tools/bin/ scripts use Python 2.7 syntax (urlparse, print statements, unicode literals); will fail silently on Python 3
  - *Always run admin tools with Python 2.7 interpreter; do not port to Python 3 without full regression on Firestore query outputs*

## Error Mapping

| Error | Status Code |
|-------|------------|
| `FirebaseError` | 0 |
| `RecordingError` | 0 |
| `ShareError` | 0 |
## Components

### FirebaseProvider
- **Location:** `iOS/AroundSound/App/Networking/FirebaseProvider.swift`
- **Responsibility:** Abstracts all Firestore/Storage/Functions SDK calls into RxSwift Observables
- **Depends on:** Firebase SDK, CodableFirebase, Models/Dtos

### Domain Providers
- **Location:** `iOS/AroundSound/App/Domain/Provider/`
- **Responsibility:** Filtered/computed data views on top of FirebaseProvider; expose Input relays and Output observables
- **Depends on:** FirebaseProvider, ASErrorFactory

### ViewModels
- **Location:** `iOS/AroundSound/App/ViewModel/`
- **Responsibility:** Presentation logic; transforms domain models to UI-ready formats via RxSwift; receives injected dependencies
- **Depends on:** Domain Providers, FirebaseProvider, ASErrorFactory, GeneralPlayer, GeneralRecorder

### AudioEngine
- **Location:** `iOS/AroundSound/App/AudioEngine/`
- **Responsibility:** Wraps AVFoundation recording and playback in protocol-based RxSwift interfaces
- **Depends on:** AVFoundation, RxSwift, MediaPlayer

### Firebase Cloud Functions
- **Location:** `platform/firebase/functions/src/`
- **Responsibility:** Serverless HTTP and Firestore-triggered handlers for all backend business logic
- **Depends on:** firebase-admin, google-cloud/firestore, google-cloud/bigquery

### DI Container
- **Location:** `iOS/AroundSound/App/DI/`
- **Responsibility:** Swinject container registering and resolving all iOS service dependencies
- **Depends on:** Swinject

### Error Handling
- **Location:** `iOS/AroundSound/App/ErrorHandling/`
- **Responsibility:** Typed error hierarchy with factory, severity, and routing to UI
- **Depends on:** ASAnalyticsManager

## File Placement

| Component Type | Location | Naming | Example |
|---------------|----------|--------|---------|
| ViewModel | `iOS/AroundSound/App/ViewModel/` | `*ViewModel.swift` | `iOS/AroundSound/App/ViewModel/AlbumsViewModel.swift` |
| ViewController | `iOS/AroundSound/App/ViewControllers/` | `*ViewController.swift` | `iOS/AroundSound/App/ViewControllers/AlbumsViewController.swift` |
| DomainProvider | `iOS/AroundSound/App/Domain/Provider/` | `*Provider.swift` | `iOS/AroundSound/App/Domain/Provider/AlbumProvider.swift` |
| FirestoreConverter | `iOS/AroundSound/App/Networking/Converters/` | `*Converter.swift` | `iOS/AroundSound/App/Networking/Converters/AlbumConverter.swift` |
| DomainModel | `iOS/AroundSound/App/Models/` | `*.swift (no suffix)` | `iOS/AroundSound/App/Models/Recording.swift` |
| CloudFunction | `platform/firebase/functions/src/` | `<domain>.ts` | `platform/firebase/functions/src/albums.ts` |

## Where to Put Code

- **new_screen** -> `iOS/AroundSound/App/ViewControllers/`
- **new_viewmodel** -> `iOS/AroundSound/App/ViewModel/`
- **new_domain_provider** -> `iOS/AroundSound/App/Domain/Provider/`
- **new_firebase_operation** -> `iOS/AroundSound/App/Networking/FirebaseProvider.swift`
- **new_cloud_function** -> `platform/firebase/functions/src/<domain>.ts + export in index.ts`
- **new_error_type** -> `iOS/AroundSound/App/ErrorHandling/<Domain>Error/`
- **new_dto** -> `iOS/AroundSound/App/Models/Dtos/`
- **new_converter** -> `iOS/AroundSound/App/Networking/Converters/`

## Naming Conventions

- **iOS errors**: AS<Domain>Error (e.g. `ASError`, `FirebaseError`, `RecordingError`, `ShareError`)
- **iOS DTOs**: <Entity>Dto.swift (e.g. `AlbumDto.swift`, `RecordingDto.swift`, `SharedLinkDto.swift`)
- **iOS Analytics**: AS<Service> (e.g. `ASAnalyticsManager`, `ASAnalyticsService`, `ASAnalyticsEvent`)
- **Firebase functions**: snake_case files, camelCase exports (e.g. `cloud_function_utils.ts`, `promise_utils.ts`, `shared_links.ts`)
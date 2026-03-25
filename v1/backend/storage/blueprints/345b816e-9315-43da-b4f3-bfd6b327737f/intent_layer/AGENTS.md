# AGENTS.md

> Agent guidance for **local/AroundSound**
> Generated: 2026-03-13T12:58:08.659237+00:00

AroundSound is a geotagged audio recording and sharing app for iOS and Android backed by Firebase. The iOS app uses MVVM with RxSwift reactive bindings, Swinject DI, and UIKit. The Android app uses MVVM with native Android patterns. The backend is Firebase Cloud Functions (TypeScript/Node.js) with Firestore, Cloud Storage, FCM, and BigQuery. Architecture separates Presentation, ViewModel, Repository, Provider, and Networking layers on iOS with protocol-based abstractions throughout.

---

## Tech Stack

- **analytics:** Firebase Analytics + AppCenter 2.x
- **backend:** Firebase Cloud Functions 1.x / Node.js 8
- **database:** Cloud Firestore google-cloud-firestore 0.29.0+
- **di:** Swinject 2.x
- **image:** Nuke latest
- **layout:** SnapKit latest
- **reactive:** RxSwift + RxCocoa 4.x
- **reactive_datasources:** RxDataSources latest
- **serialization:** CodableFirebase latest
- **ui:** UIKit iOS 11+

## Deployment

**Runs on:** On-device iOS/Android + Google Cloud Platform (Firebase)
**Compute:** Firebase Cloud Functions (Node.js 8 serverless), Cloud Firestore (managed NoSQL), Firebase Cloud Storage (audio binaries), BigQuery (analytics aggregation)
**Container:** None (serverless + native mobile) + None
**CI/CD:**
- GitLab CI: platform/.gitlab-ci.yml — manual trigger for dev/prod Firebase deploy; master-only for prod
- GitLab CI: android/.gitlab-ci.yml — ./gradlew test then ./gradlew assembleDebug on push
**Distribution:**
- Apple App Store (iOS)
- Google Play Store (Android)

## Commands

```bash
# ios_setup
cd iOS/AroundSound && pod install && open AroundSound.xcworkspace
# firebase_dev_setup
cd platform/firebase && bash prepare-local-development-environment.sh
# firebase_functions_build
cd platform/firebase/functions && npm run build
# firebase_functions_lint
cd platform/firebase/functions && npm run lint
# firebase_deploy
cd platform/firebase && bash deploy-to-environment.sh
# firebase_functions_test
cd platform/firebase/functions && npm test
# android_build
cd android && ./gradlew assembleDebug
# android_test
cd android && ./gradlew test
```

## Project Structure

```
aroundsound/
├── iOS/
│   └── AroundSound/
│       ├── App/
│       │   ├── Analytics/
│       │   ├── Appdelegate/
│       │   ├── AudioEngine/
│       │   ├── DI/
│       │   ├── Deeplinking/
│       │   ├── Domain/Provider/
│       │   ├── ErrorHandling/
│       │   ├── Location/
│       │   ├── Models/Dtos/
│       │   ├── Networking/Converters/
│       │   ├── SettingsManager/
│       │   ├── Utils/
│       │   ├── ViewModel/AlbumCellTypes/
│       │   ├── ViewModel/Trimming/
│       │   ├── ViewControllers/Animators/
│       │   └── Views/Cells/Player/Recorder/Trim/
│       ├── AppUnitTests/
│       └── AppUITests/
├── android/
│   └── app/src/main/
├── platform/
│   ├── firebase/
│   │   ├── functions/src/
│   │   ├── functions/views/
│   │   └── bin/adhoc/
│   └── tools/bin/adhoc/
└── designs/
```

## Code Style

- **iOS errors:** AS<Domain>Error (e.g. `ASError`, `FirebaseError`, `RecordingError`, `ShareError`)
- **iOS DTOs:** <Entity>Dto.swift (e.g. `AlbumDto.swift`, `RecordingDto.swift`, `SharedLinkDto.swift`)
- **iOS Analytics:** AS<Service> (e.g. `ASAnalyticsManager`, `ASAnalyticsService`, `ASAnalyticsEvent`)
- **Firebase functions:** snake_case files, camelCase exports (e.g. `cloud_function_utils.ts`, `promise_utils.ts`, `shared_links.ts`)

### ViewModel: iOS ViewModel with RxSwift Input/Output pattern

File: `iOS/AroundSound/App/ViewModel/{Name}ViewModel.swift`

```
struct {Name}ViewModel {
  let output: Driver<[Model]>
  init(provider: ProviderProtocol, errorFactory: ASErrorFactoryProtocol) { ... }
}
```

### DomainProvider: Domain provider with PublishRelay input and Driver output

File: `iOS/AroundSound/App/Domain/Provider/{Name}Provider.swift`

```
struct {Name}Provider {
  let actionInput = PublishRelay<ActionType>()
  let dataOutput: Driver<[Model]>
  let errorOutput: Observable<ASError>
}
```

### CloudFunction: Firebase Cloud Function HTTPS handler

File: `platform/firebase/functions/src/{domain}.ts`

```
export const myFunction = functions.https.onCall(async (data, context) => {
  validateAuth(context); validateParams(data);
  return await db.collection('entity').add(data);
});
```

## Development Rules

### Ci Cd

- Always run npm run lint then npm run build before deploying Firebase Functions — predeploy hooks enforce this; lib/index.js is the compiled artifact loaded at runtime *(source: `platform/firebase/functions/package.json scripts: lint → tslint, build → tsc, main: lib/index.js`)*
- Never deploy to production (aroundsound-prod) from any branch other than master — GitLab CI enforces only: [master] on the prod deploy stage *(source: `platform/.gitlab-ci.yml deploy aroundsound-prod stage only: [master] constraint`)*

### Code Style

- Always use PublishRelay (never PublishSubject) for ViewModel and Provider input ports — Relay prevents accidental stream termination via onError/onCompleted propagation *(source: `iOS/AroundSound/App/Domain/Provider/AlbumProvider.swift and SharedAlbumPreviewProvider.swift relay-based input pattern`)*
- Always expose ViewController-bound outputs as Driver<T> (never Observable<T>) — Driver guarantees main-thread delivery and no-error contract required by UIKit bindings *(source: `iOS/AroundSound/App/ViewModel/MainViewModel.swift stateOfRecorderOutput, locationOutput, isLoadingOutput all Driver`)*

### Dependency Management

- Always use CocoaPods for iOS dependencies; never add Swift packages manually — Podfile is the sole source of truth for Firebase, RxSwift, Swinject, Nuke, SnapKit *(source: `iOS/AroundSound/App/Appdelegate/AppDelegate.swift imports confirm CocoaPods-managed frameworks`)*
- Always use npm for Firebase Functions dependencies in platform/firebase/functions/package.json — never edit package-lock.json manually; lock file is committed and must match CI environment *(source: `platform/firebase/functions/package.json specifies firebase-admin, @google-cloud/bigquery with pinned versions`)*

### Environment

- Always use environment-specific google-services.json for Android builds — debug builds use aroundsound-dev project; release builds use aroundsound-prod project *(source: `android/app/src/main/AndroidManifest.xml with debug/release google-services.json variants`)*

### Testing

- Always run ./gradlew test before ./gradlew assembleDebug in Android CI — unit tests must pass before debug artifact is generated *(source: `android/.gitlab-ci.yml debug_assemble stage runs gradlew test then gradlew assembleDebug sequentially`)*

## Boundaries

### Always

- Run tests before committing
- Use `where_to_put` MCP tool before creating files
- Use `check_naming` MCP tool before naming components
- Follow file placement rules (see `.claude/rules/architecture.md`)

### Ask First

- Database schema changes
- Adding new dependencies
- Modifying CI/CD configuration
- Changes to deployment configuration

### Never

- Commit secrets or API keys
- Edit vendor/node_modules directories
- Remove failing tests without authorization

## Testing

```bash
# firebase_functions_lint
cd platform/firebase/functions && npm run lint
# firebase_functions_test
cd platform/firebase/functions && npm test
# android_test
cd android && ./gradlew test
```

## Common Workflows

### Add a new Firebase-backed feature (e.g. new entity CRUD)
Files: `iOS/AroundSound/App/Models/Dtos/RecordingDto.swift`, `iOS/AroundSound/App/Models/Recording.swift`, `iOS/AroundSound/App/Networking/Converters/RecordingConverter.swift`, `iOS/AroundSound/App/Networking/FirebaseProvider.swift`, `iOS/AroundSound/App/Domain/Provider/AlbumProvider.swift`, `iOS/AroundSound/App/ViewModel/AlbumsViewModel.swift`, `iOS/AroundSound/App/DI/DepedencyContainer.swift`, `platform/firebase/functions/src/index.ts`
1. Create Dto in Models/Dtos/ and domain model in Models/; write Converter in Networking/Converters/
2. Add Firestore methods to FirebaseProvider.swift (return Observable); update FirebaseProviderProtocol
3. Create Provider in Domain/Provider/ with PublishRelay inputs and Driver outputs; register in DepedencyContainer.swift
4. Inject Provider into ViewModel; expose Output Driver for ViewController binding
5. Add Cloud Function handler in platform/firebase/functions/src/<domain>.ts; export in index.ts; run npm run build

### Add a new iOS screen
Files: `iOS/AroundSound/App/ViewControllers/AlbumsViewController.swift`, `iOS/AroundSound/App/ViewModel/AlbumsViewModel.swift`, `iOS/AroundSound/App/DI/DepedencyContainer.swift`, `iOS/AroundSound/App/DI/Resolver.swift`
1. Create <Name>ViewController.swift in ViewControllers/; create <Name>ViewModel.swift in ViewModel/
2. Define ViewModel struct with injected dependencies and expose Driver outputs + PublishRelay inputs
3. Register ViewModel in DepedencyContainer.swift; add resolve helper in Resolver.swift
4. In ViewController.viewDidLoad() bind ViewModel outputs to UI via .drive(); bind UI events to ViewModel inputs via .bind(to:); add all to disposeBag

### Deploy Firebase Cloud Functions to dev
Files: `platform/firebase/functions/src/index.ts`, `platform/firebase/deploy-to-environment.sh`
1. cd platform/firebase/functions && npm run lint && npm run build (compiles TS to lib/)
2. Trigger GitLab CI manual job 'deploy aroundsound-dev' OR run bash deploy-to-environment.sh locally
3. Verify with: firebase functions:log --project aroundsound-dev

### Run a bulk data operation using admin tools
Files: `platform/tools/bin/bulk-download.py`, `platform/tools/bin/requirements.txt`
1. pip install -r platform/tools/bin/requirements.txt (Python 2.7 required)
2. Set GOOGLE_APPLICATION_CREDENTIALS to service account JSON for target project
3. python platform/tools/bin/bulk-download.py --project-id=aroundsound-dev <user-id>

## Pitfalls & Gotchas

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

## Architecture MCP Server

The `architecture-blueprints` MCP server is the single source of truth.
Call its tools for every architecture decision.

| Tool | When to Use |
|------|------------|
| `where_to_put` | Before creating or moving any file |
| `check_naming` | Before naming any new component |
| `list_implementations` | Discovering available implementation patterns |
| `how_to_implement_by_id` | Getting full details for a specific capability |
| `how_to_implement` | Fuzzy search when exact capability name unknown |
| `get_file_content` | Reading source files referenced in guidelines |

## File Placement

- **new_screen** → `iOS/AroundSound/App/ViewControllers/`
- **new_viewmodel** → `iOS/AroundSound/App/ViewModel/`
- **new_domain_provider** → `iOS/AroundSound/App/Domain/Provider/`
- **new_firebase_operation** → `iOS/AroundSound/App/Networking/FirebaseProvider.swift`
- **new_cloud_function** → `platform/firebase/functions/src/<domain>.ts + export in index.ts`
- **new_error_type** → `iOS/AroundSound/App/ErrorHandling/<Domain>Error/`
- **new_dto** → `iOS/AroundSound/App/Models/Dtos/`
- **new_converter** → `iOS/AroundSound/App/Networking/Converters/`

---
*Auto-generated from structured architecture analysis.*
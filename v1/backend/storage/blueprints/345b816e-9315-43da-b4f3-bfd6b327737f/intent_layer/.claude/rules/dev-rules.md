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
## Developer Recipes

### Add a new Firebase-backed feature (e.g. new entity CRUD)
Files: `iOS/AroundSound/App/Models/Dtos/RecordingDto.swift`, `iOS/AroundSound/App/Models/Recording.swift`, `iOS/AroundSound/App/Networking/Converters/RecordingConverter.swift`, `iOS/AroundSound/App/Networking/FirebaseProvider.swift`, `iOS/AroundSound/App/Domain/Provider/AlbumProvider.swift`, `iOS/AroundSound/App/ViewModel/AlbumsViewModel.swift`, `iOS/AroundSound/App/DI/DepedencyContainer.swift`, `platform/firebase/functions/src/index.ts`
1. 1. Create Dto in Models/Dtos/ and domain model in Models/; write Converter in Networking/Converters/
2. 2. Add Firestore methods to FirebaseProvider.swift (return Observable); update FirebaseProviderProtocol
3. 3. Create Provider in Domain/Provider/ with PublishRelay inputs and Driver outputs; register in DepedencyContainer.swift
4. 4. Inject Provider into ViewModel; expose Output Driver for ViewController binding
5. 5. Add Cloud Function handler in platform/firebase/functions/src/<domain>.ts; export in index.ts; run npm run build

### Add a new iOS screen
Files: `iOS/AroundSound/App/ViewControllers/AlbumsViewController.swift`, `iOS/AroundSound/App/ViewModel/AlbumsViewModel.swift`, `iOS/AroundSound/App/DI/DepedencyContainer.swift`, `iOS/AroundSound/App/DI/Resolver.swift`
1. 1. Create <Name>ViewController.swift in ViewControllers/; create <Name>ViewModel.swift in ViewModel/
2. 2. Define ViewModel struct with injected dependencies and expose Driver outputs + PublishRelay inputs
3. 3. Register ViewModel in DepedencyContainer.swift; add resolve helper in Resolver.swift
4. 4. In ViewController.viewDidLoad() bind ViewModel outputs to UI via .drive(); bind UI events to ViewModel inputs via .bind(to:); add all to disposeBag

### Deploy Firebase Cloud Functions to dev
Files: `platform/firebase/functions/src/index.ts`, `platform/firebase/deploy-to-environment.sh`
1. 1. cd platform/firebase/functions && npm run lint && npm run build (compiles TS to lib/)
2. 2. Trigger GitLab CI manual job 'deploy aroundsound-dev' OR run bash deploy-to-environment.sh locally
3. 3. Verify with: firebase functions:log --project aroundsound-dev

### Run a bulk data operation using admin tools
Files: `platform/tools/bin/bulk-download.py`, `platform/tools/bin/requirements.txt`
1. 1. pip install -r platform/tools/bin/requirements.txt (Python 2.7 required)
2. 2. Set GOOGLE_APPLICATION_CREDENTIALS to service account JSON for target project
3. 3. python platform/tools/bin/bulk-download.py --project-id=aroundsound-dev <user-id>

## Implementation Guidelines

### Reactive Audio Recording with State Management [media]
Libraries: `RxSwift 4.x`, `AVFoundation`
Pattern: GeneralRecorder wraps AVAudioRecorder in a protocol-based class emitting recordingStatus as Driver<RecordingStatus> and newlyCreatedRecording as Observable<RawLocalRecording>; state transitions via delegate callbacks update internal BehaviorSubject
Key files: `iOS/AroundSound/App/AudioEngine/Recording/GeneralRecorder.swift`, `iOS/AroundSound/App/AudioEngine/Recording/RecordingStatus.swift`, `iOS/AroundSound/App/AudioEngine/Recording/RecordingPermission.swift`, `iOS/AroundSound/App/Views/Recorder/RecorderView.swift`
Example: `recorder.recordingStatus.drive(onNext: { status in updateUI(status) }).disposed(by: disposeBag)`
- recordingStatus is Driver (main thread, no error); newlyCreatedRecording is Observable (handle threading explicitly)
- Request permission via recordingPermission() before calling start(); check iOS 14.5+ privacy requirements
- Recorder disables MPRemoteCommandCenter during recording to avoid control center interference

### Reactive Audio Playback with Remote Transport Controls [media]
Libraries: `RxSwift 4.x`, `AVFoundation`, `MediaPlayer`
Pattern: GeneralPlayer merges two underlying players (local AVAudioPlayer + remote AVPlayer) via Observable.merge(); exposes percentage Driver and playbackStatus Driver; integrates MPRemoteCommandCenter for Control Center controls
Key files: `iOS/AroundSound/App/AudioEngine/Playback/GeneralPlayer.swift`, `iOS/AroundSound/App/AudioEngine/Playback/PlaybackStatus.swift`, `iOS/AroundSound/App/Utils/AVPlayer+Rx.swift`, `iOS/AroundSound/App/Utils/AVPlayerItem+Rx.swift`, `iOS/AroundSound/App/Views/Player/FullscreenPlayer.swift`
Example: `player.percentage.drive(seekSlider.rx.value).disposed(by: disposeBag)`
- currentRecordingInput is ReplaySubject(bufferSize:1); late subscribers receive last value immediately
- Call stopCurrentRecording() before releasing player to avoid AVAudioPlayer memory leaks
- seek(valueFromSlider:) takes normalized 0.0-1.0; seekTo(value:) takes absolute seconds

### Firestore Real-time Sync with Reactive Repositories [networking]
Libraries: `Firebase Admin SDK`, `RxSwift 4.x`, `CodableFirebase`
Pattern: FirebaseProvider wraps Firestore CRUD in Observable.create{}; Repositories merge disk cache + Firebase live updates + runtime changes via Observable.merge(); errors propagate via .catchError(to: errorSubject)
Key files: `iOS/AroundSound/App/Networking/FirebaseProvider.swift`, `iOS/AroundSound/App/Domain/Provider/AlbumProvider.swift`, `iOS/AroundSound/App/Networking/Sync/FirebaseSyncManager.swift`, `platform/firebase/functions/src/albums.ts`, `platform/firebase/functions/src/recordings.ts`
Example: `albumProvider.albumsOutput.drive(tableView.rx.items(...)).disposed(by: disposeBag)`
- Use PublishRelay for inputs; never Subject (prevents accidental completion of album stream)
- Converters (AlbumConverter, RecordingConverter) must be pure functions; no Firebase calls inside converters
- Backend Cloud Functions must validate request.auth manually; firestore.rules enforces field-level access

### Swinject Dependency Injection Container [state_management]
Libraries: `Swinject 2.x`
Pattern: AppDelegate initializes DepedencyContainer at launch; all services registered as singletons or transients; ViewControllers resolve dependencies via Resolver; all injectable types have Protocol variants enabling mock substitution in tests
Key files: `iOS/AroundSound/App/DI/DepedencyContainer.swift`, `iOS/AroundSound/App/DI/Dependencies.swift`, `iOS/AroundSound/App/DI/Resolver.swift`, `iOS/AroundSound/App/Appdelegate/AppDelegate.swift`
Example: `let vm = resolver.resolve(AlbumsViewModel.self)!`
- Register leaf services first (ErrorFactory, Analytics) before composites (Providers, ViewModels)
- All ViewModels are structs with constructor injection of ~10-15 dependencies
- Never use property injection; all dependencies must be resolved at initialization time

### Typed Error Hierarchy with Analytics Integration [error_handling]
Libraries: `RxSwift 4.x`, `Firebase Analytics`, `AppCenter`
Pattern: ASErrorFactory creates domain-typed errors (FirebaseError, RecordingError, ShareError, PersistenceError, GeneralError) with analytics logging; errors propagate via PublishSubject.onNext() to errorOutput observables merged in ViewModels; ASErrorRouter routes to UI
Key files: `iOS/AroundSound/App/ErrorHandling/ASErrorFactory.swift`, `iOS/AroundSound/App/ErrorHandling/ASError.swift`, `iOS/AroundSound/App/ErrorHandling/ASErrorRouter.swift`, `iOS/AroundSound/App/ErrorHandling/ASErrorSeverity.swift`
Example: `let error = errorFactory.createFirebaseError(kind: .readFailed, externalError: err); errorSubject.onNext(error)`
- ASErrorFactory.createFirebaseError() detects NSError code -1009 for no-internet and provides specialized handling
- Never instantiate FirebaseError/RecordingError directly; always use ASErrorFactory methods
- errorOutput in ViewModels must merge all provider/manager error observables to avoid silent failures
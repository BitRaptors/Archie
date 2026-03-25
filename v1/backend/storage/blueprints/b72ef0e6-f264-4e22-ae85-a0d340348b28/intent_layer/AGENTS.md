# AGENTS.md

> Agent guidance for **local/BabyWeather.Android**
> Generated: 2026-03-13T10:52:40.430502+00:00

BabyWeather.Android is a native Android app providing weather-based clothing recommendations for babies. Built with Kotlin, Jetpack (Navigation, ViewModel, Flow), and Koin DI. Architecture uses feature-sliced modules (page_*) each owning Fragment, ViewModel, Controller, and Koin module. Domain layer centralizes repository interfaces and REST API communication via Retrofit+Moshi. Firebase suite handles analytics, crash reporting, and remote config; RevenueCat manages subscriptions.

---

## Tech Stack

- **analytics:** Mixpanel varies
- **animation:** Lottie varies
- **async:** Kotlin Coroutines + Flow 1.6.0
- **dependency_injection:** Koin 3.x
- **firebase:** Firebase Suite (Analytics, Crashlytics, Perf, RemoteConfig) varies
- **image_loading:** Glide varies
- **internal_sdk:** BitRaptors SDK Android private
- **language:** Kotlin 1.8.20
- **layout:** ConstraintLayout / MotionLayout varies
- **list_adapter:** hannesdorfmann/adapterdelegates4 4.x
- **monetization:** RevenueCat varies
- **navigation:** AndroidX Navigation + SafeArgs 2.4.2
- **networking:** Retrofit 2 + OkHttp 2.9.0 / 4.9.2
- **serialization:** Moshi 1.12.0
- **ui_framework:** AndroidX Fragment + Jetpack varies

## Deployment

**Runs on:** Android devices (minSdk 23 / targetSdk 34); backend REST API on Heroku
**Compute:** Google Play Store (production distribution), AppCenter (BitRaptors/BabyWeather-Android — staging/beta distribution), Heroku (REST API backend: babyweather-dev.herokuapp.com / babyweather.herokuapp.com)
**Container:** None — APK/AAB native Android package + None
**CI/CD:**
- Azure Pipelines — triggered on PR to develop branch
- Tasks: assemble[BuildType] + cleanTestDebugUnitTest + testDebugUnitTest
- Artifacts uploaded to AppCenter via release stage
**Distribution:**
- Google Play Store (release buildType)
- AppCenter (staging buildType — QA distribution)
- Direct APK install (debug buildType — local dev)

## Commands

```bash
# debug_build
./gradlew assembleDebug
# staging_build
./gradlew assembleStaging
# release_build
./gradlew assembleRelease
# unit_tests
./gradlew cleanTestDebugUnitTest testDebugUnitTest
# install_debug
./gradlew installDebug
```

## Project Structure

```
BabyWeather.Android/
├── app/
│   ├── build.gradle.kts
│   ├── proguard-rules.pro
│   ├── src/
│   │   ├── main/
│   │   │   ├── AndroidManifest.xml
│   │   │   ├── kotlin/com/bitraptors/babyweather/
│   │   │   │   ├── BabyWeatherApplication.kt
│   │   │   │   ├── activity_main/
│   │   │   │   ├── page_dashboard/
│   │   │   │   ├── page_locations/
│   │   │   │   ├── page_settings/
│   │   │   │   ├── page_settings_detail/
│   │   │   │   ├── page_baby_settings/
│   │   │   │   ├── page_tips/
│   │   │   │   ├── page_subscription_detail/
│   │   │   │   ├── page_feedback/
│   │   │   │   ├── page_login_bottomsheet/
│   │   │   │   ├── common/domain/
│   │   │   │   ├── baseclasses/
│   │   │   │   ├── sdk/
│   │   │   │   └── util/services/
│   │   │   └── res/
│   │   │       ├── layout/, drawable/, navigation/, values*/
│   │   ├── debug/
│   │   ├── staging/  (google-services.json, launcher icons)
│   │   └── release/  (google-services.json, launcher icons)
│   └── staging|release/output-metadata.json
├── buildSrc/
│   ├── build.gradle.kts
│   └── src/main/kotlin/
│       ├── Dependencies.kt
│       ├── DependencyConfig.kt
│       ├── Extensions.kt
│       └── Release.kt
├── build.gradle.kts
├── settings.gradle.kts
├── android-debug.jks
└── babyweather_release
```

## Code Style

- **kotlin_classes:** PascalCase with role suffix (e.g. `DashboardViewModel`, `LoginController`, `LocationRepository`)
- **layout_files:** <type>_<feature>_<element>.xml (e.g. `fragment_dashboard.xml`, `cell_settings_baby_item.xml`, `dialog_login.xml`)
- **build_types:** lowercase: debug | staging | release (e.g. `buildTypes.debug`, `buildTypes.staging`, `buildTypes.release`)
- **flow_fields:** _<name> private MutableXFlow, <name> public immutable (e.g. `_currentPage / currentPage`, `_loginSheetState / loginSheetState`)

### feature_viewmodel: ViewModel with StateFlow and SharedFlow for a page_* feature

File: `app/src/main/java/com/bitraptors/babyweather/page_<feature>/fragment/<Feature>ViewModel.kt`

```
class <Feature>ViewModel(private val repo: <Domain>Repository) : ViewModel() {
  val uiState = MutableStateFlow<UiModel<<Feature>UiState>>(UiModel.Loading)
  val events = MutableSharedFlow<UiEvent>() }
```

### koin_module: Koin module registering ViewModel and dependencies for a feature

File: `app/src/main/java/com/bitraptors/babyweather/page_<feature>/Modules<Feature>.kt`

```
val <feature>Modules = module {
  viewModel { <Feature>ViewModel(get()) }
  single { <Feature>Controller(get(), get()) } }
```

### adapter_cell: RecyclerView cell using adapterDelegateViewBinding DSL

File: `app/src/main/java/com/bitraptors/babyweather/page_<feature>/cells/<Name>Cell.kt`

```
fun <name>Cell() = adapterDelegateViewBinding<ItemModel, GenericListItem, Cell<Name>Binding>(
  { inflater, parent -> Cell<Name>Binding.inflate(inflater, parent, false) }
) { binding.title.text = item.title }
```

## Development Rules

### Ci Cd

- Always run cleanTestDebugUnitTest testDebugUnitTest Gradle tasks before assembling APK in CI; never skip unit tests *(source: `azure-pipelines.yml gradleTasks variable: 'assemble[BuildType] cleanTestDebugUnitTest testDebugUnitTest'`)*

### Code Style

- Always organize new features as page_<feature>/ directories containing Fragment, ViewModel, Modules<Feature>.kt, cells/, dialog/, controller/ subdirectories *(source: `Feature-slice pattern observed across page_dashboard, page_locations, page_settings, page_tips, page_baby_settings`)*
- Always use Kotlin source sets (src/main/kotlin, src/debug/kotlin, src/release/kotlin); never add Java files to this project *(source: `app/build.gradle.kts sourceSets block explicitly sets java.srcDirs to kotlin directories only`)*

### Dependency Management

- Always declare dependency versions in buildSrc/src/main/kotlin/Dependencies.kt objects; never hardcode version strings in app/build.gradle.kts *(source: `buildSrc/src/main/kotlin/Dependencies.kt — AndroidSdk.compileApi, Network.retrofit, Firebase.* objects consumed by app/build.gradle.kts`)*
- Always authenticate to GitHub Packages Maven repo using getGprUser()/getGprKey() functions from gradle.properties for BitRaptors SDK; never hardcode credentials *(source: `build.gradle.kts allprojects.repositories maven{url=https://maven.pkg.github.com/BitRaptors/BitRaptors.SDK.Android}`)*

### Deployment

- Never commit real keystore passwords to source; use Azure Pipelines variable group 'babyweather-android-build-variables' to override signingConfig values in CI *(source: `app/build.gradle.kts signingConfigs currently contains plaintext passwords (WeatherBaby, BabyWeather) — security risk requiring CI variable override`)*

### Environment

- Always place google-services.json in variant-specific source sets (src/debug/, src/staging/, src/release/); never in src/main/ *(source: `app/src/staging/google-services.json, app/src/release/google-services.json — separate Firebase configs per variant`)*

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
- Rotate passwords to Azure Pipelines variable group 'babyweather-android-build-variables'; never commit real credentials

## Testing

```bash
# unit_tests
./gradlew cleanTestDebugUnitTest testDebugUnitTest
```

## Common Workflows

### Add a new feature screen
Files: `app/src/main/res/layout/fragment_<feature>.xml`, `app/src/main/res/navigation/navigation_main.xml`
1. Create page_<feature>/ dir with Fragment.kt, ViewModel.kt, Modules<Feature>.kt
2. Add fragment_<feature>.xml layout in res/layout/
3. Register destination in navigation_main.xml with SafeArgs arguments if needed
4. Add Modules<Feature> to startKoin{} modules list in BabyWeatherApplication

### Add a new REST API endpoint
Files: `buildSrc/src/main/kotlin/Dependencies.kt`
1. Add @JsonClass(generateAdapter=true) DTO data class in common/domain/api/dto/
2. Add suspend fun to APIService interface with @GET/@POST/@PUT/@DELETE annotation
3. Add mapping function in Repository implementation; expose via repository interface
4. Inject repository into feature ViewModel via Koin; call in viewModelScope.launch{}

### Add a new build dependency
Files: `buildSrc/src/main/kotlin/Dependencies.kt`, `buildSrc/src/main/kotlin/DependencyConfig.kt`, `app/build.gradle.kts`
1. Add version constant to appropriate object in buildSrc/src/main/kotlin/Dependencies.kt
2. Add dependency string constant referencing the version constant
3. Reference via object accessor in app/build.gradle.kts dependencies block (e.g. Libraries.newLib)

### Change app version
Files: `buildSrc/src/main/kotlin/Release.kt`
1. Update versionCode (format: YYYYMMDDnn) in Release.kt
2. Update versionName (semantic: X.Y.Z) in Release.kt
3. Commit; Azure Pipelines will pick up new values on next triggered build

## Pitfalls & Gotchas

- **Koin module registration:** Feature Koin modules not added to BabyWeatherApplication startKoin{} block cause runtime NoBeanDefFoundException—no compile-time safety.
  - *Always add new Modules<Feature>.kt to the modules list in BabyWeatherApplication immediately when creating a feature*
- **Moshi codegen:** DTOs missing @JsonClass(generateAdapter=true) compile without error but fail at runtime with JsonDataException.
  - *Annotate every DTO used with Moshi; enable kapt strict mode to catch missing adapters at build time*
- **Signing credentials in source:** app/build.gradle.kts contains plaintext keystore passwords (WeatherBaby, BabyWeather) and OAuth tokens in buildConfigField.
  - *Rotate passwords to Azure Pipelines variable group 'babyweather-android-build-variables'; never commit real credentials*
- **Flow collection in Fragments:** Collecting StateFlow/SharedFlow outside repeatOnLifecycle(STARTED) causes events to be processed when Fragment is stopped.
  - *Always wrap flow collection in lifecycleScope.launch { repeatOnLifecycle(Lifecycle.State.STARTED) { ... } }*
- **Staging vs Release Firebase config:** Staging uses production Firebase project (babyweather-ad243), not a separate staging Firebase project—analytics and crash data mingles.
  - *Treat staging Firebase data as potentially polluted; filter by app_version or variant in Firebase console*

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

- **new_screen** → `Create page_<feature>/ with Fragment, ViewModel, Modules<Feature>.kt; register module in BabyWeatherApplication`
- **new_api_endpoint** → `Add to APIService interface in common/domain/api/; add DTO with @JsonClass(generateAdapter=true)`
- **new_dependency_version** → `Add version constant to buildSrc/src/main/kotlin/Dependencies.kt; reference in app/build.gradle.kts`
- **new_list_item** → `Add cell_<name>.xml to res/layout/; create Cell.kt with adapterDelegateViewBinding in feature cells/ dir`
- **new_analytics_event** → `Create event class extending BasicEvent in util/services/analytics/events/; emit via raptorAnalytics.logEvent()`

---
*Auto-generated from structured architecture analysis.*
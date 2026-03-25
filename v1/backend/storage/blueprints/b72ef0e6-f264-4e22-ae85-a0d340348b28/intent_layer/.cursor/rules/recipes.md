---
description: Developer recipes and implementation guidelines
alwaysApply: true
---

## Developer Recipes

### Add a new feature screen
Files: `app/src/main/res/layout/fragment_<feature>.xml`, `app/src/main/res/navigation/navigation_main.xml`
1. 1. Create page_<feature>/ dir with Fragment.kt, ViewModel.kt, Modules<Feature>.kt
2. 2. Add fragment_<feature>.xml layout in res/layout/
3. 3. Register destination in navigation_main.xml with SafeArgs arguments if needed
4. 4. Add Modules<Feature> to startKoin{} modules list in BabyWeatherApplication

### Add a new REST API endpoint
Files: `buildSrc/src/main/kotlin/Dependencies.kt`
1. 1. Add @JsonClass(generateAdapter=true) DTO data class in common/domain/api/dto/
2. 2. Add suspend fun to APIService interface with @GET/@POST/@PUT/@DELETE annotation
3. 3. Add mapping function in Repository implementation; expose via repository interface
4. 4. Inject repository into feature ViewModel via Koin; call in viewModelScope.launch{}

### Add a new build dependency
Files: `buildSrc/src/main/kotlin/Dependencies.kt`, `buildSrc/src/main/kotlin/DependencyConfig.kt`, `app/build.gradle.kts`
1. 1. Add version constant to appropriate object in buildSrc/src/main/kotlin/Dependencies.kt
2. 2. Add dependency string constant referencing the version constant
3. 3. Reference via object accessor in app/build.gradle.kts dependencies block (e.g. Libraries.newLib)

### Change app version
Files: `buildSrc/src/main/kotlin/Release.kt`
1. 1. Update versionCode (format: YYYYMMDDnn) in Release.kt
2. 2. Update versionName (semantic: X.Y.Z) in Release.kt
3. 3. Commit; Azure Pipelines will pick up new values on next triggered build

## Implementation Guidelines

### Koin Dependency Injection [state_management]
Libraries: `Koin 3.x`
Pattern: Each feature declares a module DSL file (Modules<Feature>.kt); all modules composed in BabyWeatherApplication.startKoin{}. Singletons for services, viewModel{} for screen-scoped state, factory{} for parameterized instances (BabySettingsViewModel with babyId).
Key files: `buildSrc/src/main/kotlin/DependencyConfig.kt`, `app/build.gradle.kts`
Example: `single { MainController(get(), get()) } — get() resolves RaptorAnalytics and InAppReviewManager from container`
- Use factory { (babyId: String) -> BabySettingsViewModel(babyId, get()) } for parameterized ViewModels
- Avoid circular dependencies between feature modules—route through domain layer instead
- Test modules with koin-test checkModules() to catch missing bindings before runtime

### REST API with Retrofit + Moshi + NetworkResponse [networking]
Libraries: `Retrofit 2.9.0`, `OkHttp 4.9.2`, `Moshi 1.12.0`
Pattern: APIService interface with suspend functions; Moshi converter with @JsonClass codegen DTOs; NetworkResponseAdapterFactory wraps all responses in sealed NetworkResponse<T, String>; HttpRequestInterceptor injects Bearer token; logging interceptor active in debug only.
Key files: `app/src/main/res/xml/network_security_config.xml`
Example: `@GET("pages/home") suspend fun getHomePage(@Query("locationKey") key: String): NetworkResponse<HomePageDto, String>`
- Handle all four NetworkErrorResponse variants (ApiError, NetworkError, AuthenticationError, UnknownError) exhaustively in repositories
- Base URL differs per buildType: debug→babyweather-dev.herokuapp.com, release/staging→babyweather.herokuapp.com
- Disable logging interceptor in release builds to prevent PII in crash logs

### Firebase Remote Config + Feature Flags [analytics]
Libraries: `Firebase Remote Config`, `BitRaptors Feature Flag SDK`
Pattern: Default values declared in res/xml/remote_config_defaults.xml; fetched at startup via BitRaptors Feature Flag SDK. Feature modules conditionally render UI based on flag values without redeployment.
Key files: `app/src/main/res/xml/remote_config_defaults.xml`, `app/src/staging/google-services.json`
Example: `featureFlagService.isEnabled("premium_features") gates subscription UI in SettingsFragment`
- Staging and release both use the same Firebase project (babyweather-ad243)—use Remote Config conditions to target staging package
- featureFlagDataSourceOverrideModule allows local override of flags in debug builds for testing

### Sealed State Machine Authentication [auth]
Libraries: `BitRaptors Login SDK`, `Google Sign-In`
Pattern: LoginController wraps RaptorLoginManager; transforms external UserState to app's LoginState (AnonymousUser/LoggedInUser). LoginSheetState sealed interface (Init→Visible→Expanded→Hidden) drives bottom sheet visibility. SharedPreferences persist terms acceptance.
Key files: `app/src/main/res/layout/dialog_login.xml`
Example: `loginController.handleGoogleLogin(activityResultLauncher) — triggers Google Sign-In and emits LoginState.LoggedInUser on success`
- OAuth client IDs differ by buildType; debug uses project 151823554728, release/staging uses 898696094253
- appStartService.refreshAfterLogin() must be called after successful token receipt to reload all app data
- Use EncryptedSharedPreferences in production for token storage

### Multi-variant Build Configuration [environment]
Libraries: `Android Gradle Plugin`, `buildSrc Kotlin DSL`
Pattern: Three buildTypes (debug, staging, release) each with distinct buildConfigField values for API URLs, OAuth tokens, Mixpanel keys, and RevenueCat keys. Version constants centralized in buildSrc/src/main/kotlin/. Source sets allow variant-specific Kotlin code and resources.
Key files: `app/build.gradle.kts`, `buildSrc/src/main/kotlin/Dependencies.kt`, `buildSrc/src/main/kotlin/Release.kt`
Example: `BuildConfig.BASE_API_URL resolves to env-specific URL at compile time; no runtime URL switching needed`
- Never reference BuildConfig fields at module init time before Application.onCreate(); use lazy or inject
- Staging APK suffix is '-staging'; use versionName to identify variant in crash reports
- buildSrc changes invalidate the entire Gradle cache; minimize changes during active development
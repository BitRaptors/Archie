---
description: Development rules: imperative do/don't rules from codebase signals
alwaysApply: true
---

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
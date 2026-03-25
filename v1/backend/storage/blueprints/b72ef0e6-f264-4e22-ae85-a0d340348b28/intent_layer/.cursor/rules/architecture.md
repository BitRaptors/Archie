---
description: Architecture rules: components, file placement, naming conventions
alwaysApply: true
---

## Components

### Application/Process Layer
- **Location:** `app/src/main/java/com/bitraptors/babyweather/`
- **Responsibility:** Koin DI init, process lifecycle, analytics/crash setup, dark mode init
- **Depends on:** Domain Layer, Infrastructure/SDK Layer

### Activity/Navigation Layer
- **Location:** `app/src/main/java/com/bitraptors/babyweather/activity_main/`
- **Responsibility:** NavController host, bottom nav, global dialogs, theme observation
- **Depends on:** Feature Layer, Domain Layer

### Feature Layer (page_*)
- **Location:** `app/src/main/java/com/bitraptors/babyweather/page_*/`
- **Responsibility:** User-facing screens: dashboard, locations, settings, tips, baby profiles, subscriptions
- **Depends on:** Domain Layer, Common/Shared Layer

### Domain Layer
- **Location:** `app/src/main/java/com/bitraptors/babyweather/common/domain/`
- **Responsibility:** Repository interfaces, domain entities, DataSource abstraction, API DTOs
- **Depends on:** Infrastructure/SDK Layer

### Build Configuration
- **Location:** `buildSrc/src/main/kotlin/`
- **Responsibility:** Centralized version management, dependency declarations, build plugins

## File Placement

| Component Type | Location | Naming | Example |
|---------------|----------|--------|---------|
| feature_module | `app/src/main/java/com/bitraptors/babyweather/page_<feature>/` | `page_<feature>/` | `page_dashboard/fragment/DashboardFragment.kt` |
| koin_module | `app/src/main/java/com/bitraptors/babyweather/page_<feature>/` | `Modules<Feature>.kt` | `page_dashboard/ModulesDashboard.kt` |
| repository | `app/src/main/java/com/bitraptors/babyweather/common/domain/repository/` | `<Name>Repository.kt / <Name>RepositoryImpl.kt` | `common/domain/repository/home/LocationRepository.kt` |
| recycler_cell | `app/src/main/res/layout/ + page_<feature>/cells/` | `cell_<name>.xml + <Name>Cell.kt` | `cell_dashboard_piece_of_clothing.xml` |
| build_version | `buildSrc/src/main/kotlin/Dependencies.kt` | `object <Category> in Dependencies.kt` | `AndroidSdk.compileApi, Network.retrofit` |
| environment_config | `app/src/debug/ | app/src/release/ | app/src/staging/` | `google-services.json per source set` | `app/src/staging/google-services.json` |

## Where to Put Code

- **new_screen** -> `Create page_<feature>/ with Fragment, ViewModel, Modules<Feature>.kt; register module in BabyWeatherApplication`
- **new_api_endpoint** -> `Add to APIService interface in common/domain/api/; add DTO with @JsonClass(generateAdapter=true)`
- **new_dependency_version** -> `Add version constant to buildSrc/src/main/kotlin/Dependencies.kt; reference in app/build.gradle.kts`
- **new_list_item** -> `Add cell_<name>.xml to res/layout/; create Cell.kt with adapterDelegateViewBinding in feature cells/ dir`
- **new_analytics_event** -> `Create event class extending BasicEvent in util/services/analytics/events/; emit via raptorAnalytics.logEvent()`

## Naming Conventions

- **kotlin_classes**: PascalCase with role suffix (e.g. `DashboardViewModel`, `LoginController`, `LocationRepository`)
- **layout_files**: <type>_<feature>_<element>.xml (e.g. `fragment_dashboard.xml`, `cell_settings_baby_item.xml`, `dialog_login.xml`)
- **build_types**: lowercase: debug | staging | release (e.g. `buildTypes.debug`, `buildTypes.staging`, `buildTypes.release`)
- **flow_fields**: _<name> private MutableXFlow, <name> public immutable (e.g. `_currentPage / currentPage`, `_loginSheetState / loginSheetState`)
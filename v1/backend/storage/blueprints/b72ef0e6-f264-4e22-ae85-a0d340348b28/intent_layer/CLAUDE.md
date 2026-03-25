# CLAUDE.md

> Architecture guidance for **local/BabyWeather.Android**
> Style: Feature-sliced MVVM with centralized domain layer and Koin DI
> Generated: 2026-03-13T10:52:40.430485+00:00

## Overview

BabyWeather.Android is a native Android app providing weather-based clothing recommendations for babies. Built with Kotlin, Jetpack (Navigation, ViewModel, Flow), and Koin DI. Architecture uses feature-sliced modules (page_*) each owning Fragment, ViewModel, Controller, and Koin module. Domain layer centralizes repository interfaces and REST API communication via Retrofit+Moshi. Firebase suite handles analytics, crash reporting, and remote config; RevenueCat manages subscriptions.

## Architecture

**Style:** page_* feature modules each own UI+state+DI; shared domain layer owns repositories
**Structure:** Feature-sliced modular monorepo (single Android app module)

Enables team parallelization on features while sharing API/business logic

**Runs on:** Android devices (minSdk 23 / targetSdk 34); backend REST API on Heroku
**Compute:** Google Play Store (production distribution), AppCenter (BitRaptors/BabyWeather-Android — staging/beta distribution), Heroku (REST API backend: babyweather-dev.herokuapp.com / babyweather.herokuapp.com)
**CI/CD:** Azure Pipelines — triggered on PR to develop branch, Tasks: assemble[BuildType] + cleanTestDebugUnitTest + testDebugUnitTest, Artifacts uploaded to AppCenter via release stage

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

## Key Rules

Detailed architecture rules are split into topic files under `.claude/rules/`:

- `architecture.md` — Components, file placement, naming conventions
- `patterns.md` — Communication patterns, key decisions
- `recipes.md` — Developer recipes, implementation guidelines
- `pitfalls.md` — Common pitfalls, error mapping
- `dev-rules.md` — Development rules (always/never imperatives)
- `mcp-tools.md` — MCP server tool reference
- `frontend.md` — Frontend rules (when applicable)

## Architecture MCP Server (MANDATORY)

The `architecture-blueprints` MCP server is the single source of truth.
You MUST call `where_to_put` before creating files and `check_naming` before naming components.
See `.claude/rules/mcp-tools.md` for the full tool reference and workflow.

---
*Auto-generated from structured architecture analysis. Place in project root.*
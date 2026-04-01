# CLAUDE.md

> Architecture guidance for **local/AroundSound**
> Style: Multi-platform monorepo: iOS MVVM+RxSwift, Android MVVM, Firebase serverless backend
> Generated: 2026-03-13T12:58:08.659220+00:00

## Overview

AroundSound is a geotagged audio recording and sharing app for iOS and Android backed by Firebase. The iOS app uses MVVM with RxSwift reactive bindings, Swinject DI, and UIKit. The Android app uses MVVM with native Android patterns. The backend is Firebase Cloud Functions (TypeScript/Node.js) with Firestore, Cloud Storage, FCM, and BigQuery. Architecture separates Presentation, ViewModel, Repository, Provider, and Networking layers on iOS with protocol-based abstractions throughout.

## Architecture

**Style:** MVVM with RxSwift Observables/Drivers, PublishRelay inputs, protocol-based DI via Swinject
**Structure:** layered

Enables testable ViewModels via protocol mocks; reactive streams unify Firebase real-time updates, local changes, and UI events into single data pipelines

**Runs on:** On-device iOS/Android + Google Cloud Platform (Firebase)
**Compute:** Firebase Cloud Functions (Node.js 8 serverless), Cloud Firestore (managed NoSQL), Firebase Cloud Storage (audio binaries), BigQuery (analytics aggregation)
**CI/CD:** GitLab CI: platform/.gitlab-ci.yml — manual trigger for dev/prod Firebase deploy; master-only for prod, GitLab CI: android/.gitlab-ci.yml — ./gradlew test then ./gradlew assembleDebug on push

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
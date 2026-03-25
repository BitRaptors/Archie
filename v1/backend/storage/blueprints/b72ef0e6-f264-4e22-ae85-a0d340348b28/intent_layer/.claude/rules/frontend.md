---
paths:
  - **/*.kt
---

## Frontend Architecture

**Framework:** Android Native Kotlin (Jetpack Fragment + XML layouts)

**Rendering:** Imperative XML layouts with ConstraintLayout/MotionLayout; ViewBinding for type-safe view access

**Styling:** Material Design 3 with XML themes; day/night variants in values/themes.xml + values-night/themes.xml; API-level overrides in values-v31/v32/v33; adaptive color resources in res/color/

**State management:** MVVM with StateFlow/SharedFlow; Controllers for cross-cutting orchestration
  - Server state: Fetched in repositories via Retrofit; cached in-memory in ViewModel StateFlow
  - Local state: SharedPreferences for auth tokens, dark mode, terms acceptance

**Conventions:**
- ViewBinding enabled; always use binding.* not findViewById()
- Fragments use BaseBindingFragment from BitRaptors SDK
- All new code in Kotlin; Java deprecated
- Shared element transitions defined in res/transition/shared_element_transiton.xml
- Feature modules must not import other feature modules directly
## Pitfalls

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

## Error Mapping

| Error | Status Code |
|-------|------------|
| `NetworkErrorResponse.AuthenticationError` | 401 |
| `NetworkErrorResponse.ApiError` | 400 |
| `NetworkErrorResponse.NetworkError` | 0 |
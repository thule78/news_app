# Technology Stack

**Analysis Date:** 2026-04-14

## Framework & Language

**Flutter SDK:** `flutter` (latest via flutter SDK)
- Channel: default (stable)
- Purpose: Cross-platform mobile app framework

**Dart Version:** `>=3.3.0 <4.0.0`
- Constraint from `pubspec.yaml` environment

## Key Dependencies

### Core Flutter
- `flutter` SDK - Core framework
- `cupertino_icons: ^1.0.8` - iOS-style icons

### State Management
- `provider: ^6.1.2` - ChangeNotifier-based state management
  - Used for `ResetSessionController` and `AppLifecycleService`
  - Pattern: `ChangeNotifierProvider<ResetSessionController>.value`
  - Pattern: `Provider<AppLifecycleService>.value`

### Persistence
- `shared_preferences: ^2.5.5` - Local key-value storage
  - Wrapped by `LocalStorageService` in `lib/services/storage/local_storage_service.dart`
  - Stores: device_id, trial_start_at, recovery_snapshot, local_event_log
  - JSON serialization for complex objects

### Testing
- `flutter_test` - Widget and unit testing
- `integration_test` - End-to-end testing
- `flutter_lints: ^3.0.2` - Code quality linting

## Architecture Pattern

**Pattern:** Feature-first Clean Architecture

**Layers:**
```
lib/
├── app/                    # App bootstrap and entry
├── core/                   # Shared utilities, constants, theme
├── features/               # Feature modules (currently: acute_reset)
│   └── acute_reset/
│       ├── config/         # Flow configuration
│       ├── data/           # Repository implementations
│       ├── domain/         # Controllers, models, repository interfaces
│       └── presentation/   # Screens, widgets
├── router/                 # Navigation
└── services/               # Cross-cutting services (storage, lifecycle)
```

## State Management Approach

**Framework:** Provider (ChangeNotifier pattern)

**Primary State Holder:** `ResetSessionController` (`lib/features/acute_reset/domain/controllers/reset_session_controller.dart`)
- Extends `ChangeNotifier`
- Owns reset flow state machine
- Lifecycle-aware via `AppLifecycleService` binding
- Notifies listeners on state changes

**Service Providers:**
- `LocalStorageService` - Injected via constructor
- `AppLifecycleService` - Provided via `MultiProvider`

**Widget Rebuild Strategy:** Uses `context.read()` for actions, avoiding high-level `watch()`

## Build Configuration

**Entry Point:** `lib/main.dart`
- Initializes `WidgetsFlutterBinding`
- Runs `AppBootstrap().initialize()` for dependency setup
- Passes `AppDependencies` to `RoxApp`

**Build Target:** Mobile (iOS, Android) via Flutter

---

*Stack analysis: 2026-04-14*

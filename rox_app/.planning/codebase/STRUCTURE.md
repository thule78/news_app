# Codebase Structure

**Analysis Date:** 2026-04-14

## Directory Layout

```
rox_app/
├── lib/
│   ├── app/               # Application bootstrap and root
│   ├── core/              # Shared utilities and constants
│   ├── features/          # Feature modules (business capabilities)
│   ├── router/            # Navigation configuration
│   ├── services/          # Application-wide services
│   └── main.dart          # Entry point
├── test/
│   ├── unit/              # Unit tests
│   └── widget/            # Widget tests
├── integration_test/      # Integration tests
└── pubspec.yaml          # Dependencies
```

## Directory Purposes

### `lib/app/`

**Purpose:** Application initialization and root widget composition

**Contains:**
- `bootstrap.dart` - Dependency injection and initialization
- `app.dart` - Root `RoxApp` widget

**Key Files:**
- `lib/app/bootstrap.dart` - Creates all dependencies
- `lib/app/app.dart` - Sets up `MultiProvider` and MaterialApp

### `lib/core/`

**Purpose:** Cross-cutting utilities shared by all features

**Subdirectories:**
- `accessibility/` - Accessibility helpers
- `constants/` - App-wide constants
- `errors/` - Exception types
- `theme/` - Visual design tokens
- `utils/` - General-purpose utilities

**Key Files:**
- `lib/core/constants/storage_keys.dart` - SharedPreferences key constants
- `lib/core/constants/reset_constants.dart` - Reset-specific event names
- `lib/core/theme/app_colors.dart` - Color palette
- `lib/core/theme/app_theme.dart` - ThemeData builder
- `lib/core/accessibility/reduced_motion_helper.dart` - Motion preference check
- `lib/core/utils/clock.dart` - Time abstraction for testability
- `lib/core/utils/id_generator.dart` - Unique ID generation

### `lib/features/`

**Purpose:** Feature modules organized by business capability

**Contains:**
- `acute_reset/` - The single MVP feature

### `lib/router/`

**Purpose:** Navigation configuration and route definitions

**Key Files:**
- `lib/router/route_names.dart` - Route name constants (strings)
- `lib/router/app_router.dart` - `onGenerateRoute` implementation

### `lib/services/`

**Purpose:** Application-wide infrastructure services

**Subdirectories:**
- `lifecycle/` - App lifecycle management
- `storage/` - Persistence abstraction

**Key Files:**
- `lib/services/lifecycle/app_lifecycle_service.dart` - Lifecycle observer with Stream
- `lib/services/storage/local_storage_service.dart` - SharedPreferences wrapper

### `lib/main.dart`

**Purpose:** Application entry point

**Responsibilities:**
- Initialize Flutter bindings
- Bootstrap dependencies
- Launch `RoxApp`

## Key File Locations

### Entry Points

- `lib/main.dart` - Application entry point
- `lib/app/app.dart` - Root widget with Provider setup
- `lib/app/bootstrap.dart` - Dependency bootstrap

### Configuration

- `lib/core/constants/storage_keys.dart` - Storage key definitions
- `lib/features/acute_reset/config/reset_flow_config.dart` - Flow constants
- `lib/core/theme/app_theme.dart` - Theme configuration

### Core Logic

- `lib/features/acute_reset/domain/controllers/reset_session_controller.dart` - State machine
- `lib/features/acute_reset/domain/models/reset_session.dart` - Session state model
- `lib/features/acute_reset/domain/models/reset_stage.dart` - Stage enum with extensions
- `lib/features/acute_reset/domain/policies/recovery_policy.dart` - Recovery rules
- `lib/features/acute_reset/domain/policies/trial_policy.dart` - Trial day calculation

### Repository Interfaces (Domain)

- `lib/features/acute_reset/domain/repositories/reset_repository.dart`
- `lib/features/acute_reset/domain/repositories/local_event_repository.dart`

### Repository Implementations (Data)

- `lib/features/acute_reset/data/repositories/reset_repository_impl.dart`
- `lib/features/acute_reset/data/repositories/local_event_repository_impl.dart`

### Screens (Presentation)

- `lib/features/acute_reset/presentation/screens/reset_entry_screen.dart`
- `lib/features/acute_reset/presentation/screens/active_reset_screen.dart`
- `lib/features/acute_reset/presentation/screens/recovery_screen.dart`
- `lib/features/acute_reset/presentation/screens/completion_screen.dart`

### Widgets (Presentation)

- `lib/features/acute_reset/presentation/widgets/reset_visual_core.dart`
- `lib/features/acute_reset/presentation/widgets/compress_gesture_zone.dart`
- `lib/features/acute_reset/presentation/widgets/disrupt_gesture_layer.dart`
- `lib/features/acute_reset/presentation/widgets/clear_gesture_layer.dart`
- `lib/features/acute_reset/presentation/widgets/reset_progress_indicator.dart`
- `lib/features/acute_reset/presentation/widgets/stage_copy_label.dart`
- `lib/features/acute_reset/presentation/widgets/completion_card.dart`
- `lib/features/acute_reset/presentation/widgets/feedback_actions.dart`

### Testing

- `test/unit/reset_session_controller_test.dart`
- `test/unit/reset_repository_impl_test.dart`
- `test/widget/reset_entry_screen_test.dart`

## Naming Conventions

### Files

- Dart source files: `snake_case.dart`
- Test files: `*_test.dart` or `*_spec.dart`
- Configuration: `*_config.dart`
- Policy: `*_policy.dart`

### Directories

- Feature modules: `snake_case/` (e.g., `acute_reset/`)
- Layer directories: `domain/`, `data/`, `presentation/`, `config/`
- Subdirectories within layers: `controllers/`, `models/`, `repositories/`, `screens/`, `widgets/`, `policies/`

### Classes

- Controllers: `*{Controller,Service}` (e.g., `ResetSessionController`)
- Repositories: `*{Repository}` (interface), `*{RepositoryImpl}` (implementation)
- Models: PascalCase (e.g., `ResetSession`, `ResetStage`)
- Policies: `*{Policy}` (e.g., `RecoveryPolicy`)
- Screens: `*{Screen}` (e.g., `ResetEntryScreen`)
- Widgets: PascalCase, descriptive (e.g., `ResetVisualCore`)
- Services: `*{Service}` (e.g., `LocalStorageService`)

### Variables

- Private members: `_camelCase` (e.g., `_session`)
- Public members: `camelCase` (e.g., `session`)
- Constants: `CONSTANT_CASE` (e.g., `disruptSwipeCount` in config)

## Where to Add New Code

### New Feature

**Primary code:** `lib/features/{new_feature}/`
- Follow the existing `domain/`, `data/`, `presentation/` structure
- Add feature-specific config in `config/`

**Tests:** `test/unit/` and `test/widget/`

### New Screen

**Implementation:** `lib/features/{feature}/presentation/screens/{name}_screen.dart`
- Stateless unless requires local state
- Use `Selector` for targeted rebuilds
- Access controllers via `context.read<Controller>()`

### New Widget

**Implementation:** `lib/features/{feature}/presentation/widgets/{name}.dart`
- Keep stateless and pure (no business logic)
- Accept data through constructor parameters

### New Controller

**Implementation:** `lib/features/{feature}/domain/controllers/{name}_controller.dart`
- Extend `ChangeNotifier`
- Inject dependencies through constructor
- Expose state through getters
- Perform persistence in repository after state updates

### New Repository

**Interface:** `lib/features/{feature}/domain/repositories/{name}_repository.dart`
- Define abstract methods
- Use `Future<>` return types for async operations

**Implementation:** `lib/features/{feature}/data/repositories/{name}_repository_impl.dart`
- Implement interface
- Use services from `lib/services/`

### New Policy

**Implementation:** `lib/features/{feature}/domain/policies/{name}_policy.dart`
- Simple class with configurable constants
- Methods for business rule calculations

### New Model

**Implementation:** `lib/features/{feature}/domain/models/{name}.dart`
- Immutable class (const constructor preferred)
- Include `toJson()` and `tryParse()` for serialization
- Use extension methods for computed properties

### New Service

**Location:** `lib/services/{category}/`
- Create new subdirectory if needed
- Follow existing patterns (e.g., lifecycle, storage)

### New Utility

**Location:** `lib/core/utils/`
- Place general-purpose utilities here
- Keep focused and single-purpose

## Special Directories

### `lib/core/accessibility/`

**Purpose:** Accessibility helpers
**Generated:** No
**Committed:** Yes

### `lib/core/errors/`

**Purpose:** Domain exception types
**Generated:** No
**Committed:** Yes

### `test/unit/`

**Purpose:** Unit tests for controllers, repositories, policies
**Pattern:** `*_test.dart`

### `test/widget/`

**Purpose:** Widget tests for screens and components
**Pattern:** `*_test.dart`

### `integration_test/`

**Purpose:** End-to-end integration tests
**Pattern:** `*_test.dart`

---

*Structure analysis: 2026-04-14*
